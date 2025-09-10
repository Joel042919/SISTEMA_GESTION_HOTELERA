

-- =========================
-- Helpers de calendario
-- =========================
CREATE OR REPLACE FUNCTION pms.fn_series_dates(p_start DATE, p_end DATE)
RETURNS TABLE(d DATE) LANGUAGE sql AS $$
SELECT generate_series(p_start, p_end, '1 day')::date;
$$;

-- Habitaciones totales por propiedad
CREATE OR REPLACE VIEW pms.v_rooms_total AS
SELECT property_id, COUNT(*) AS rooms_total
FROM pms.rooms
WHERE status <> 'out_of_order' -- si quieres excluir fuera de servicio de la capacidad "disponible"
GROUP BY property_id;

-- Ocupación por día (cuántas habitaciones están ocupadas ese día)
CREATE OR REPLACE FUNCTION pms.fn_rooms_occupied_on(p_property UUID, p_date DATE)
RETURNS INTEGER LANGUAGE sql AS $$
SELECT COUNT(DISTINCT rr.room_id)
FROM pms.reservations res
JOIN pms.reservation_rooms rr ON rr.reservation_id = res.id
WHERE res.property_id = p_property
  AND res.status IN ('confirmed','checked_in')
  AND res.start_date <= p_date
  AND res.end_date   >  p_date;
$$;

-- Ingresos de habitaciones del día:
-- Reparte el total de cada reserva en sus noches y suma las noches que caen en p_date.
-- (Usamos el mismo criterio de tu breakdown pero distribuido por día para performance.)
CREATE OR REPLACE FUNCTION pms.fn_room_revenue_on(p_reservation UUID, p_date DATE)
RETURNS NUMERIC LANGUAGE sql AS $$
WITH res AS (
  SELECT r.*, (r.end_date - r.start_date) AS nights
  FROM pms.reservations r WHERE r.id = p_reservation
),
the_day AS (
  SELECT CASE WHEN (SELECT nights FROM res) > 0
              AND p_date >= (SELECT start_date FROM res)
              AND p_date <  (SELECT end_date   FROM res)
         THEN 1 ELSE 0 END AS is_night
),
rev AS (
  -- Base total prorrateada por noche (simple). Si quieres exactitud por tarifa/temporada,
  -- puedes usar tu fn_reservation_room_breakdown y dividir por noches.
  SELECT CASE WHEN (SELECT nights FROM res) > 0
              THEN (SELECT total_amount FROM res) / (SELECT nights FROM res)
              ELSE 0 END AS per_night
)
SELECT CASE WHEN (SELECT is_night FROM the_day)=1 THEN (SELECT per_night FROM rev) ELSE 0 END;
$$;

CREATE OR REPLACE FUNCTION pms.fn_room_revenue_day(p_property UUID, p_date DATE)
RETURNS NUMERIC LANGUAGE sql AS $$
SELECT COALESCE(SUM(pms.fn_room_revenue_on(res.id, p_date)),0)
FROM pms.reservations res
WHERE res.property_id = p_property
  AND res.status IN ('confirmed','checked_in')
  AND res.start_date <= p_date
  AND res.end_date   >  p_date;
$$;

-- Ingresos extras (charges) del día
CREATE OR REPLACE FUNCTION pms.fn_extra_revenue_day(p_property UUID, p_date DATE)
RETURNS NUMERIC LANGUAGE sql AS $$
SELECT COALESCE(SUM(c.amount),0)
FROM pms.charges c
JOIN pms.reservations r ON r.id = c.reservation_id
WHERE r.property_id = p_property
  AND c.posted_at::date = p_date;
$$;

-- Pagos del día
CREATE OR REPLACE FUNCTION pms.fn_payments_day(p_property UUID, p_date DATE)
RETURNS NUMERIC LANGUAGE sql AS $$
SELECT COALESCE(SUM(p.amount),0)
FROM pms.payments p
JOIN pms.reservations r ON r.id = p.reservation_id
WHERE r.property_id = p_property
  AND p.paid_at::date = p_date;
$$;

-- Facturas del día
CREATE OR REPLACE FUNCTION pms.fn_invoices_day(p_property UUID, p_date DATE)
RETURNS NUMERIC LANGUAGE sql AS $$
SELECT COALESCE(SUM(i.amount),0)
FROM pms.invoices i
JOIN pms.reservations r ON r.id = i.reservation_id
WHERE r.property_id = p_property
  AND i.issued_at::date = p_date;
$$;

-- Check-ins / Check-outs del día
CREATE OR REPLACE FUNCTION pms.fn_checkins_day(p_property UUID, p_date DATE)
RETURNS INTEGER LANGUAGE sql AS $$
SELECT COUNT(*) FROM pms.reservations
WHERE property_id = p_property AND start_date = p_date;
$$;

CREATE OR REPLACE FUNCTION pms.fn_checkouts_day(p_property UUID, p_date DATE)
RETURNS INTEGER LANGUAGE sql AS $$
SELECT COUNT(*) FROM pms.reservations
WHERE property_id = p_property AND end_date = p_date;
$$;

-- KPI diario consolidado por fecha
CREATE OR REPLACE FUNCTION pms.fn_daily_kpis(p_property UUID, p_date DATE)
RETURNS TABLE(
  d DATE,
  rooms_total INT,
  rooms_occupied INT,
  occupancy NUMERIC,
  adr NUMERIC,
  revpar NUMERIC,
  room_revenue NUMERIC,
  extra_revenue NUMERIC,
  payments NUMERIC,
  invoices NUMERIC,
  checkins INT,
  checkouts INT
)
LANGUAGE plpgsql AS $$
DECLARE
  v_rt INT:=0;
  v_ro INT:=0;
  v_rr NUMERIC:=0;
  v_er NUMERIC:=0;
BEGIN
  SELECT v.rooms_total INTO v_rt FROM pms.v_rooms_total as v WHERE v.property_id = p_property;
  IF v_rt IS NULL THEN v_rt := 0; END IF;

  SELECT pms.fn_rooms_occupied_on(p_property, p_date) INTO v_ro;

  SELECT pms.fn_room_revenue_day(p_property, p_date) INTO v_rr;
  SELECT pms.fn_extra_revenue_day(p_property, p_date) INTO v_er;

  RETURN QUERY
  SELECT
    p_date AS d,
    v_rt   AS rooms_total,
    v_ro   AS rooms_occupied,
    CASE WHEN v_rt=0 THEN 0 ELSE ROUND((v_ro::numeric / v_rt)*100,2) END AS occupancy,
    -- ADR = room revenue / rooms_occupied
    CASE WHEN v_ro=0 THEN 0 ELSE ROUND((v_rr / v_ro),2) END AS adr,
    -- RevPAR = room revenue / rooms_total
    CASE WHEN v_rt=0 THEN 0 ELSE ROUND((v_rr / v_rt),2) END AS revpar,
    ROUND(v_rr,2) AS room_revenue,
    ROUND(v_er,2) AS extra_revenue,
    ROUND(pms.fn_payments_day(p_property, p_date),2) AS payments,
    ROUND(pms.fn_invoices_day(p_property, p_date),2) AS invoices,
    pms.fn_checkins_day(p_property, p_date) AS checkins,
    pms.fn_checkouts_day(p_property, p_date) AS checkouts;
END;
$$;
--#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$
--#$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$$

-- KPI por rango (devuelve una fila por día)
CREATE OR REPLACE FUNCTION pms.fn_daily_kpis_between(p_property UUID, p_start DATE, p_end DATE)
RETURNS TABLE(
  d DATE,
  rooms_total INT,
  rooms_occupied INT,
  occupancy NUMERIC,
  adr NUMERIC,
  revpar NUMERIC,
  room_revenue NUMERIC,
  extra_revenue NUMERIC,
  payments NUMERIC,
  invoices NUMERIC,
  checkins INT,
  checkouts INT
)
LANGUAGE sql AS $$
SELECT dk.*
FROM pms.fn_series_dates(p_start, p_end) sd
CROSS JOIN LATERAL pms.fn_daily_kpis(p_property, sd.d) as dk
ORDER BY sd.d;
$$;

-- Indicadores de operaciones
-- HK pendientes por día (programadas ese día)
CREATE OR REPLACE FUNCTION pms.fn_housekeeping_pending(p_property UUID, p_date DATE)
RETURNS INTEGER LANGUAGE sql AS $$
SELECT COUNT(*) FROM pms.housekeeping_tasks
WHERE property_id = p_property AND scheduled_date = p_date AND status = 'pending';
$$;

-- Rooms fuera de servicio (OOO) al día (snapshot current)
CREATE OR REPLACE FUNCTION pms.fn_out_of_order_now(p_property UUID)
RETURNS INTEGER LANGUAGE sql AS $$
SELECT COUNT(*) FROM pms.rooms WHERE property_id = p_property AND status='out_of_order';
$$;

-- Lead time (días promedio entre creación y check-in) en un rango
CREATE OR REPLACE FUNCTION pms.fn_lead_time_avg(p_property UUID, p_start DATE, p_end DATE)
RETURNS NUMERIC LANGUAGE sql AS $$
SELECT ROUND(AVG((r.start_date - r.created_at::date)),2)
FROM pms.reservations r
WHERE r.property_id = p_property
  AND r.created_at::date BETWEEN p_start AND p_end
  AND r.status NOT IN ('canceled','no_show');
$$;

-- Cancelaciones y no-show en un rango
CREATE OR REPLACE FUNCTION pms.fn_cancel_rate(p_property UUID, p_start DATE, p_end DATE)
RETURNS TABLE(cancel_count INT, no_show_count INT, total INT, cancel_rate NUMERIC, no_show_rate NUMERIC)
LANGUAGE sql AS $$
WITH base AS (
  SELECT COUNT(*) AS total
  FROM pms.reservations r
  WHERE r.property_id = p_property
    AND r.created_at::date BETWEEN p_start AND p_end
),
agg AS (
  SELECT
    SUM((r.status='canceled')::int) AS cancel_count,
    SUM((r.status='no_show')::int)  AS no_show_count
  FROM pms.reservations r
  WHERE r.property_id = p_property
    AND r.created_at::date BETWEEN p_start AND p_end
)
SELECT
  a.cancel_count,
  a.no_show_count,
  b.total,
  CASE WHEN b.total=0 THEN 0 ELSE ROUND((a.cancel_count::numeric/b.total)*100,2) END AS cancel_rate,
  CASE WHEN b.total=0 THEN 0 ELSE ROUND((a.no_show_count::numeric/b.total)*100,2) END AS no_show_rate
FROM agg a, base b;
$$;

