SET search_path TO pms, public;

-- =========================================
-- Auditoría (helper)
-- =========================================
CREATE OR REPLACE FUNCTION sp_audit_write(
  p_entity TEXT,
  p_entity_id UUID,
  p_action TEXT,
  p_diff JSONB,
  p_user UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO audit_log(entity, entity_id, action, diff_json, user_id)
  VALUES (p_entity, p_entity_id, p_action, p_diff, p_user);
END;
$$;

-- =========================================
-- Cotización
-- =========================================
CREATE OR REPLACE FUNCTION sp_quote_price(
  p_property UUID,
  p_room_type UUID,
  p_start DATE,
  p_end DATE,
  p_guests INT,
  p_promo TEXT
) RETURNS TABLE(
  nights INT,
  base_total NUMERIC,
  promo_discount NUMERIC,
  tax_total NUMERIC,
  grand_total NUMERIC,
  nightly JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_nights INT := (p_end - p_start);
  v_rate RECORD;
  v_tax_rate NUMERIC := 0;
  v_curr TEXT;
  v_date DATE;
  v_base NUMERIC := 0;
  v_nightly JSONB := '[]'::jsonb;
  v_multiplier NUMERIC;
  v_weekend_mult NUMERIC := 1.0;
  v_promo_pct NUMERIC := 0;
  v_promo_amt NUMERIC := 0;
  v_base_total NUMERIC := 0;
  v_discount NUMERIC := 0;
  v_tax NUMERIC := 0;
BEGIN
  IF v_nights <= 0 THEN
    RAISE EXCEPTION 'INVALID_DATES' USING ERRCODE='P0001';
  END IF;

  SELECT r.base_rate, r.currency, r.weekend_multiplier, t.rate
  INTO v_rate
  FROM pms.rates r
  JOIN pms.tax_codes t ON t.code = r.tax_code
  WHERE r.property_id = p_property
    AND r.room_type_id = p_room_type
    AND r.active
  LIMIT 1;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'NO_RATE' USING ERRCODE='P0001';
  END IF;

  v_tax_rate := v_rate.rate;
  v_curr := v_rate.currency;
  v_weekend_mult := v_rate.weekend_multiplier;

  -- Promo
  IF p_promo IS NOT NULL THEN
    SELECT COALESCE(percent_off,0), COALESCE(amount_off,0)
    INTO v_promo_pct, v_promo_amt
    FROM pms.promos
    WHERE property_id = p_property
      AND code = p_promo
      AND active
      AND (start_date IS NULL OR start_date <= p_start)
      AND (end_date IS NULL OR end_date >= p_end)
    LIMIT 1;
  END IF;

  v_date := p_start;
  WHILE v_date < p_end LOOP
    v_multiplier := 1.0;

    -- Temporada
    SELECT COALESCE(MAX(multiplier), 1.0)
    INTO v_multiplier
    FROM pms.rate_seasons
    WHERE property_id = p_property
      AND v_date BETWEEN start_date AND end_date;

    -- Fin de semana (viernes=5, sábado=6)
    IF EXTRACT(ISODOW FROM v_date) IN (5,6) THEN
      v_multiplier := v_multiplier * v_weekend_mult;
    END IF;

    v_base := ROUND(v_rate.base_rate * v_multiplier, 2);
    v_nightly := v_nightly || jsonb_build_array(
      jsonb_build_object('date', v_date, 'base', v_base)
    );
    v_base_total := v_base_total + v_base;
    v_date := v_date + INTERVAL '1 day';
  END LOOP;

  -- Descuentos
  v_discount := ROUND(v_base_total * (v_promo_pct/100.0), 2) + v_promo_amt;
  IF v_discount > v_base_total THEN
    v_discount := v_base_total;
  END IF;

  -- Impuesto
  v_tax := ROUND((v_base_total - v_discount) * (v_tax_rate/100.0), 2);

  nights := v_nights;
  base_total := v_base_total;
  promo_discount := COALESCE(v_discount,0);
  tax_total := v_tax;
  grand_total := v_base_total - promo_discount + v_tax;
  nightly := v_nightly;
  RETURN NEXT;
END;
$$;

-- =========================================
-- Crear reserva
-- =========================================
CREATE OR REPLACE FUNCTION sp_create_reservation(
  p_property UUID,
  p_guest UUID,
  p_room_type UUID,
  p_dates DATE[],
  p_promo TEXT,
  p_user UUID
) RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  v_start DATE := p_dates[1];
  v_end   DATE := p_dates[array_length(p_dates,1)] + 1;
  v_res UUID;
  v_currency TEXT;
  v_tot NUMERIC;
BEGIN
  IF v_start IS NULL OR v_end IS NULL OR v_end <= v_start THEN
    RAISE EXCEPTION 'INVALID_DATES' USING ERRCODE='P0001';
  END IF;

  SELECT currency INTO v_currency
  FROM pms.properties
  WHERE id = p_property;

  INSERT INTO pms.reservations(
    property_id, guest_id, room_type_id, start_date, end_date,
    status, promo_code, currency, created_by
  )
  VALUES (
    p_property, p_guest, p_room_type, v_start, v_end,
    'confirmed', p_promo, v_currency, p_user
  )
  RETURNING id INTO v_res;

  PERFORM pms.sp_audit_write(
    'reservations', v_res, 'create',
    jsonb_build_object('start',v_start,'end',v_end,'promo',p_promo),
    p_user
  );

  -- Total
  SELECT grand_total
  INTO v_tot
  FROM pms.sp_quote_price(p_property, p_room_type, v_start, v_end, 1, p_promo);

  UPDATE pms.reservations SET total_amount = v_tot WHERE id = v_res;

  RETURN v_res;
END;
$$;

-- =========================================
-- Asignar habitación
-- =========================================
CREATE OR REPLACE FUNCTION pms.sp_assign_room(
  p_res  uuid,
  p_room uuid,
  p_user uuid
)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_res        pms.reservations%ROWTYPE;
  v_room       pms.rooms%ROWTYPE;
  v_overlap    int;
  v_old_status pms.rooms.status%TYPE;
BEGIN
  SELECT * INTO v_res
  FROM pms.reservations
  WHERE id = p_res
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'RES_NOT_FOUND' USING ERRCODE='P0001';
  END IF;

  -- solape real con OTRAS reservas (excluye la misma) y rango semi-abierto
  SELECT COUNT(*) INTO v_overlap
  FROM pms.reservation_rooms rr
  JOIN pms.reservations r ON r.id = rr.reservation_id
  WHERE rr.room_id = p_room
    AND r.status IN ('pending','confirmed','checked_in')
    AND r.id <> p_res
    AND daterange(r.start_date, r.end_date, '[)')
        && daterange(v_res.start_date, v_res.end_date, '[)');

  IF v_overlap > 0 THEN
    RAISE EXCEPTION 'ROOM_OVERLAP' USING ERRCODE='P0001';
  END IF;

  INSERT INTO pms.reservation_rooms(reservation_id, room_id)
  VALUES (p_res, p_room)
  ON CONFLICT (reservation_id) DO UPDATE SET room_id = EXCLUDED.room_id;

  UPDATE pms.rooms SET status = 'occupied' WHERE id = p_room;

  INSERT INTO pms.room_status_history(room_id, old_status, new_status, changed_by)
  SELECT id, NULL, 'occupied', p_user FROM rooms WHERE id = p_room;

  PERFORM pms.sp_audit_write(
    'reservation_rooms', p_room, 'assign',
    jsonb_build_object('reservation', p_res),
    p_user
  );
END;
$$;

ALTER FUNCTION pms.sp_assign_room(uuid, uuid, uuid)
  SET search_path TO pms, public;


-- =========================================
-- Cancelar reserva
-- =========================================
CREATE OR REPLACE FUNCTION sp_cancel_reservation(
  p_res UUID,
  p_reason TEXT,
  p_user UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_room UUID;
BEGIN
  UPDATE pms.reservations SET status='canceled' WHERE id = p_res;

  SELECT room_id INTO v_room
  FROM pms.reservation_rooms
  WHERE reservation_id = p_res;

  IF v_room IS NOT NULL THEN
    UPDATE pms.rooms SET status='available' WHERE id = v_room;
  END IF;

  PERFORM pms.sp_audit_write(
    'reservations', p_res, 'cancel',
    jsonb_build_object('reason', p_reason),
    p_user
  );
END;
$$;

-- =========================================
-- Check-in
-- =========================================
CREATE OR REPLACE FUNCTION sp_checkin(
  p_res UUID,
  p_doc JSONB,
  p_user UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  UPDATE pms.reservations SET status='checked_in' WHERE id = p_res;

  PERFORM pms.sp_audit_write(
    'reservations', p_res, 'checkin',
    p_doc,
    p_user
  );
END;
$$;

-- =========================================
-- Cargos
-- =========================================
CREATE OR REPLACE FUNCTION sp_post_charge(
  p_res UUID,
  p_concept TEXT,
  p_amount NUMERIC,
  p_tax_code TEXT,
  p_user UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO pms.charges(reservation_id, concept, amount, tax_code, posted_by)
  VALUES (p_res, p_concept, p_amount, p_tax_code, p_user);

  PERFORM pms.sp_audit_write(
    'charges', p_res, 'post_charge',
    jsonb_build_object('concept', p_concept, 'amount', p_amount),
    p_user
  );
END;
$$;

-- =========================================
-- Pagos
-- =========================================
CREATE OR REPLACE FUNCTION pms.sp_register_payment( 
  p_res      uuid,
  p_method   text,
  p_amount   numeric,
  p_currency text,
  p_user     uuid
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO pms.payments(reservation_id, method, amount, currency, received_by)
  VALUES (p_res, p_method, p_amount, p_currency, p_user);

  PERFORM pms.sp_audit_write(
    'payments', p_res, 'register',
    jsonb_build_object('method', upper(p_method), 'amount', p_amount, 'currency', upper(p_currency)),
    p_user
  );
END;
$$;

-- Asegura el search_path de la función (opcional pero recomendable)
ALTER FUNCTION pms.sp_register_payment(uuid, text, numeric, text, uuid)
  SET search_path TO pms, public;


-- =========================================
-- Checkout (emite invoice)
-- =========================================
CREATE OR REPLACE FUNCTION sp_checkout(
  p_res UUID,
  p_extra JSONB,
  p_user UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  v_total NUMERIC;
  v_tax NUMERIC;
  v_invoice UUID;
  v_curr TEXT;
BEGIN
  SELECT total_amount, currency
  INTO v_total, v_curr
  FROM pms.reservations
  WHERE id = p_res;

  -- Recalcula con cargos del periodo (demo simple: suma de charges)
  SELECT COALESCE(SUM(amount),0)
  INTO v_total
  FROM pms.charges
  WHERE reservation_id = p_res;

  -- IGV asociado a la tarifa del room_type activo
  SELECT ROUND(v_total * (t.rate/100.0), 2)
  INTO v_tax
  FROM pms.reservations r
  JOIN pms.rates ra ON ra.property_id = r.property_id
               AND ra.room_type_id = r.room_type_id
               AND ra.active
  JOIN pms.tax_codes t ON t.code = ra.tax_code
  WHERE r.id = p_res
  LIMIT 1;

  INSERT INTO pms.invoices(reservation_id, number, amount, tax_amount, currency)
  VALUES (
    p_res,
    CONCAT('F-', substr(replace(cast(gen_random_uuid() as text),'-',''),1,8)),
    v_total,
    COALESCE(v_tax,0),
    COALESCE(v_curr,'PEN')
  )
  RETURNING id INTO v_invoice;

  UPDATE pms.reservations SET status='checked_out' WHERE id = p_res;

  PERFORM pms.sp_audit_write(
    'invoices', v_invoice, 'issue',
    jsonb_build_object('extra', p_extra),
    p_user
  );

  RETURN v_invoice;
END;
$$;

-- =========================================
-- Estado de habitación
-- =========================================
CREATE OR REPLACE FUNCTION sp_set_room_status(
  p_room UUID,
  p_status room_status,
  p_user UUID
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
  v_old room_status;
BEGIN
  SELECT status INTO v_old
  FROM pms.rooms
  WHERE id = p_room
  FOR UPDATE;

  UPDATE pms.rooms SET status = p_status WHERE id = p_room;

  INSERT INTO pms.room_status_history(room_id, old_status, new_status, changed_by)
  VALUES (p_room, v_old, p_status, p_user);

  PERFORM pms.sp_audit_write(
    'rooms', p_room, 'set_status',
    jsonb_build_object('from', v_old, 'to', p_status),
    p_user
  );
END;
$$;

-- =========================================
-- Cierre de caja
-- =========================================
CREATE OR REPLACE FUNCTION sp_close_cash(
  p_property UUID,
  p_date DATE,
  p_user UUID
)
RETURNS UUID
LANGUAGE plpgsql
AS $$
DECLARE
  v_id UUID;
  v_pay NUMERIC;
  v_inv NUMERIC;
BEGIN
  SELECT COALESCE(SUM(amount),0)
  INTO v_pay
  FROM pms.payments pa
  JOIN pms.reservations r ON r.id = pa.reservation_id
  WHERE r.property_id = p_property
    AND DATE(pa.paid_at) = p_date;

  SELECT COALESCE(SUM(amount),0)
  INTO v_inv
  FROM pms.invoices i
  JOIN pms.reservations r ON r.id = i.reservation_id
  WHERE r.property_id = p_property
    AND DATE(i.issued_at) = p_date;

  INSERT INTO pms.cash_closures(property_id, date, closed_by, total_payments, total_invoices)
  VALUES (p_property, p_date, p_user, v_pay, v_inv)
  RETURNING id INTO v_id;

  PERFORM pms.sp_audit_write(
    'cash_closures', v_id, 'close',
    jsonb_build_object('date', p_date),
    p_user
  );

  RETURN v_id;
END;
$$;

-- =========================================
-- Reporte diario
-- =========================================
CREATE OR REPLACE FUNCTION sp_report_daily(
  p_property UUID,
  p_date DATE
)
RETURNS TABLE(
  date DATE,
  rooms_total INT,
  rooms_occupied INT,
  occupancy_pct NUMERIC,
  revenue NUMERIC,
  adr NUMERIC,
  revpar NUMERIC
)
LANGUAGE plpgsql
AS $$
DECLARE
  v_rt INT;
  v_ro INT;
  v_rev NUMERIC;
  v_adr NUMERIC;
BEGIN
  SELECT COUNT(*) INTO v_rt
  FROM pms.rooms
  WHERE property_id = p_property;

  SELECT COUNT(*) INTO v_ro
  FROM pms.reservations r
  JOIN pms.reservation_rooms rr ON rr.reservation_id = r.id
  WHERE r.property_id = p_property
    AND p_date >= r.start_date
    AND p_date < r.end_date
    AND r.status IN ('confirmed','checked_in');

  SELECT COALESCE(SUM(amount),0)
  INTO v_rev
  FROM pms.charges c
  JOIN pms.reservations r ON r.id = c.reservation_id
  WHERE r.property_id = p_property
    AND DATE(c.posted_at) = p_date;

  IF v_ro > 0 THEN
    v_adr := v_rev / v_ro;
  ELSE
    v_adr := 0;
  END IF;

  RETURN QUERY
  SELECT
    p_date,
    v_rt,
    v_ro,
    CASE WHEN v_rt > 0 THEN ROUND(100.0 * v_ro / v_rt, 2) ELSE 0 END,
    v_rev,
    v_adr,
    CASE WHEN v_rt > 0 THEN v_rev / v_rt ELSE 0 END;
END;
$$;
