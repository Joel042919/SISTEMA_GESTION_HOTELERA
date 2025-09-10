-- Prioridades
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='hk_priority') THEN
    CREATE TYPE pms.hk_priority AS ENUM ('low','normal','high','urgent');
  END IF;
END $$;

-- Ampliar housekeeping_tasks
ALTER TABLE pms.housekeeping_tasks
  ADD COLUMN IF NOT EXISTS priority pms.hk_priority NOT NULL DEFAULT 'normal',
  ADD COLUMN IF NOT EXISTS notes TEXT,
  ADD COLUMN IF NOT EXISTS started_at TIMESTAMPTZ,
  ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ;

-- Índices útiles
CREATE INDEX IF NOT EXISTS idx_hk_prop_date ON pms.housekeeping_tasks(property_id, scheduled_date);
CREATE INDEX IF NOT EXISTS idx_hk_room ON pms.housekeeping_tasks(room_id);


--#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

-- Enums para incidentes
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='incident_status') THEN
    CREATE TYPE pms.incident_status AS ENUM ('open','in_progress','paused','resolved','canceled');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='incident_severity') THEN
    CREATE TYPE pms.incident_severity AS ENUM ('minor','major','critical');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS pms.maintenance_incidents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES pms.properties(id) ON DELETE CASCADE,
  room_id UUID NOT NULL REFERENCES pms.rooms(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  severity pms.incident_severity NOT NULL DEFAULT 'minor',
  status pms.incident_status NOT NULL DEFAULT 'open',
  reported_by UUID,
  reported_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_incidents_prop_status ON pms.maintenance_incidents(property_id, status);
CREATE INDEX IF NOT EXISTS idx_incidents_room ON pms.maintenance_incidents(room_id);

-- Touch updated_at
CREATE OR REPLACE FUNCTION pms.tg_touch_updated_at()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END $$;

DROP TRIGGER IF EXISTS tg_incidents_touch ON pms.maintenance_incidents;
CREATE TRIGGER tg_incidents_touch
BEFORE UPDATE ON pms.maintenance_incidents
FOR EACH ROW EXECUTE FUNCTION pms.tg_touch_updated_at();



--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
-- Crea tareas HK para todas las rooms de una reserva (p. ej. tras checkout)
CREATE OR REPLACE FUNCTION pms.sp_hk_schedule_after_checkout(p_reservation UUID, p_priority pms.hk_priority DEFAULT 'normal')
RETURNS INTEGER  -- cantidad de tareas creadas
LANGUAGE plpgsql AS $$
DECLARE
  v_property UUID;
  v_cnt INT := 0;
BEGIN
  SELECT property_id INTO v_property FROM pms.reservations WHERE id = p_reservation;
  IF v_property IS NULL THEN RAISE EXCEPTION 'RES_NOT_FOUND'; END IF;

  INSERT INTO pms.housekeeping_tasks(property_id, room_id, scheduled_date, status, checklist, priority, notes)
  SELECT v_property, rr.room_id, CURRENT_DATE, 'pending', '[]'::jsonb, p_priority,
         'Auto-programada por checkout'
  FROM pms.reservation_rooms rr
  WHERE rr.reservation_id = p_reservation
  ON CONFLICT DO NOTHING;

  GET DIAGNOSTICS v_cnt = ROW_COUNT;
  -- Marcar rooms como 'dirty' (ya lo haces en sp_check_out, pero reforzamos)
  UPDATE pms.rooms r
    SET status='dirty'
  WHERE r.id IN (SELECT rr.room_id FROM pms.reservation_rooms rr WHERE rr.reservation_id = p_reservation);

  RETURN v_cnt;
END;
$$;


--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
-- Crear varias tareas para rooms en una fecha
CREATE OR REPLACE FUNCTION pms.sp_hk_create_tasks(
  p_property UUID,
  p_room_ids UUID[],
  p_date DATE,
  p_priority pms.hk_priority DEFAULT 'normal',
  p_assigned_to UUID DEFAULT NULL,
  p_checklist JSONB DEFAULT '[]',
  p_notes TEXT DEFAULT NULL
) RETURNS INTEGER LANGUAGE plpgsql AS $$
DECLARE v_cnt INT := 0;
BEGIN
  INSERT INTO pms.housekeeping_tasks(property_id, room_id, scheduled_date, status, checklist, assigned_to, priority, notes)
  SELECT p_property, rid, p_date, 'pending', COALESCE(p_checklist,'[]'::jsonb), p_assigned_to, p_priority, p_notes
  FROM unnest(p_room_ids) AS rid
  ON CONFLICT DO NOTHING;
  GET DIAGNOSTICS v_cnt = ROW_COUNT;
  RETURN v_cnt;
END;
$$;

-- Asignar responsable
CREATE OR REPLACE FUNCTION pms.sp_hk_assign(p_task UUID, p_user UUID)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  UPDATE pms.housekeeping_tasks SET assigned_to = p_user WHERE id = p_task;
END;
$$;

-- Iniciar tarea: pone room en 'cleaning'
CREATE OR REPLACE FUNCTION pms.sp_hk_start(p_task UUID, p_user UUID)
RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE v_room UUID;
BEGIN
  UPDATE pms.housekeeping_tasks
     SET status='in_progress', started_at=now(), assigned_to = COALESCE(assigned_to, p_user)
   WHERE id = p_task;

  SELECT room_id INTO v_room FROM pms.housekeeping_tasks WHERE id = p_task;
  IF v_room IS NOT NULL THEN
    UPDATE pms.rooms SET status='cleaning' WHERE id = v_room;
  END IF;
END;
$$;

-- Completar tarea: si no hay incidentes abiertos, deja room 'available', si hay -> 'maintenance'
CREATE OR REPLACE FUNCTION pms.sp_hk_complete(p_task UUID, p_user UUID)
RETURNS TEXT
LANGUAGE plpgsql AS $$
DECLARE
  v_room UUID;
  v_new pms.room_status := 'available'::pms.room_status;
  v_open_inc INT := 0;
  v_curr pms.room_status;
BEGIN
  -- Marca done y obtiene la habitación en una sola operación
  UPDATE pms.housekeeping_tasks
     SET status='done', completed_at=now(), assigned_to = COALESCE(assigned_to, p_user)
   WHERE id = p_task
   RETURNING room_id INTO v_room;

  IF v_room IS NULL THEN
    RAISE EXCEPTION 'HK_TASK_NOT_FOUND: %', p_task;
  END IF;

  -- ¿Quedan incidentes abiertos?
  SELECT COUNT(*) INTO v_open_inc
  FROM pms.maintenance_incidents
  WHERE room_id = v_room AND status IN ('open','in_progress','paused');

  IF v_open_inc > 0 THEN
    v_new := 'maintenance'::pms.room_status;
  ELSE
    v_new := 'available'::pms.room_status;
  END IF;

  -- No sobrescribir si está OOO
  SELECT status INTO v_curr FROM pms.rooms WHERE id = v_room;
  IF v_curr <> 'out_of_order'::pms.room_status THEN
    UPDATE pms.rooms SET status = v_new WHERE id = v_room;
    RETURN v_new::text;
  ELSE
    RETURN v_curr::text; -- queda out_of_order
  END IF;
END;
$$;


--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

-- Reportar incidente
CREATE OR REPLACE FUNCTION pms.sp_incident_report(
  p_property UUID, p_room UUID, p_title TEXT, p_description TEXT,
  p_severity pms.incident_severity DEFAULT 'minor', p_reported_by UUID DEFAULT NULL,
  p_mark_ooo BOOLEAN DEFAULT FALSE
) RETURNS UUID LANGUAGE plpgsql AS $$
DECLARE v_id UUID := gen_random_uuid();
BEGIN
  INSERT INTO pms.maintenance_incidents(id, property_id, room_id, title, description, severity, status, reported_by)
  VALUES (v_id, p_property, p_room, p_title, p_description, p_severity, 'open', p_reported_by);

  IF p_mark_ooo THEN
    UPDATE pms.rooms SET status='out_of_order' WHERE id=p_room;
  ELSE
    UPDATE pms.rooms SET status='maintenance' WHERE id=p_room AND status <> 'out_of_order';
  END IF;

  RETURN v_id;
END;
$$;

-- Cambiar estado de incidente (y ajustar room si corresponde)
CREATE OR REPLACE FUNCTION pms.sp_incident_update_status(
  p_incident UUID, p_status pms.incident_status
) RETURNS VOID LANGUAGE plpgsql AS $$
DECLARE v_room UUID; v_open INT;
BEGIN
  UPDATE pms.maintenance_incidents
     SET status = p_status,
         resolved_at = CASE WHEN p_status='resolved' THEN now() ELSE NULL END
   WHERE id = p_incident;

  SELECT room_id INTO v_room FROM pms.maintenance_incidents WHERE id = p_incident;

  -- Si todos los incidentes de la room están resueltos/cancelados, libera room a 'available' (si no hay HK en curso)
  IF v_room IS NOT NULL THEN
    SELECT COUNT(*) INTO v_open
    FROM pms.maintenance_incidents
    WHERE room_id = v_room AND status IN ('open','in_progress','paused');

    IF v_open = 0 THEN
      -- si había tarea HK en progreso no forzamos 'available'
      UPDATE pms.rooms SET status = CASE
        WHEN EXISTS (SELECT 1 FROM pms.housekeeping_tasks WHERE room_id=v_room AND status='in_progress') THEN 'cleaning'
        ELSE 'available'
      END
      WHERE id = v_room AND status <> 'out_of_order';
    END IF;
  END IF;
END;
$$;


--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

-- Conteos para la fecha dada
CREATE OR REPLACE FUNCTION pms.fn_hk_kpis(p_property UUID, p_date DATE)
RETURNS TABLE(
  tasks_total INT,
  tasks_pending INT,
  tasks_in_progress INT,
  tasks_done INT,
  incidents_open INT,
  incidents_critical INT
) LANGUAGE sql AS $$
WITH t AS (
  SELECT
    COUNT(*) FILTER (WHERE scheduled_date = p_date) AS tasks_total,
    COUNT(*) FILTER (WHERE scheduled_date = p_date AND status='pending') AS tasks_pending,
    COUNT(*) FILTER (WHERE scheduled_date = p_date AND status='in_progress') AS tasks_in_progress,
    COUNT(*) FILTER (WHERE scheduled_date = p_date AND status='done') AS tasks_done
  FROM pms.housekeeping_tasks
  WHERE property_id = p_property
),
i AS (
  SELECT
    COUNT(*) FILTER (WHERE status IN ('open','in_progress','paused')) AS incidents_open,
    COUNT(*) FILTER (WHERE status IN ('open','in_progress','paused') AND severity='critical') AS incidents_critical
  FROM pms.maintenance_incidents
  WHERE property_id = p_property
)
SELECT * FROM t, i;
$$;

-- Listado de tareas por fecha
CREATE OR REPLACE VIEW pms.v_hk_tasks AS
SELECT
  hk.id, hk.property_id, hk.room_id, r.code AS room_code,
  hk.scheduled_date, hk.status, hk.priority, hk.assigned_to, hk.started_at, hk.completed_at,
  hk.checklist, hk.notes
FROM pms.housekeeping_tasks hk
JOIN pms.rooms r ON r.id = hk.room_id;

-- Incidentes abiertos
CREATE OR REPLACE VIEW pms.v_incidents_open AS
SELECT
  mi.id, mi.property_id, mi.room_id, r.code AS room_code,
  mi.title, mi.severity, mi.status, mi.reported_at, mi.updated_at
FROM pms.maintenance_incidents mi
JOIN pms.rooms r ON r.id = mi.room_id
WHERE mi.status IN ('open','in_progress','paused');


--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
--$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$





