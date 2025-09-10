--Numeración de facturas
CREATE SEQUENCE IF NOT EXISTS pms.invoice_seq;

CREATE OR REPLACE FUNCTION pms.next_invoice_number(p_property UUID)
RETURNS TEXT LANGUAGE sql AS $$
  SELECT 'F-' || to_char(now(),'YYYYMMDD') || '-' || nextval('pms.invoice_seq')::text
$$;


-- Pendiente/confirmada más próxima para check-in
CREATE OR REPLACE FUNCTION pms.fn_find_pending_reservation_by_dni(p_property UUID, p_dni TEXT)
RETURNS text LANGUAGE sql AS $$
SELECT res.id::text
FROM pms.reservations res
JOIN pms.guests g ON g.id = res.guest_id
WHERE res.property_id = p_property
  AND g.dni = p_dni
  AND res.status IN ('pending','confirmed')
ORDER BY res.start_date ASC
LIMIT 1;
$$;

-- Estancia activa (checked_in) para check-out
CREATE OR REPLACE FUNCTION pms.fn_find_checkedin_reservation_by_dni(p_property UUID, p_dni TEXT)
RETURNS UUID LANGUAGE sql AS $$
SELECT res.id
FROM pms.reservations res
JOIN pms.guests g ON g.id = res.guest_id
WHERE res.property_id = p_property
  AND g.dni = p_dni
  AND res.status = 'checked_in'
ORDER BY res.start_date DESC
LIMIT 1;
$$;


--Desglose por habitación (recalcula precios y reparte promo)
"""
Recalcula el precio base por habitación y por día según: rates.base_rate x season_multiplier x weekend_multiplier.
Si la reserva tiene promo (porcentaje/monto), distribuye el descuento proporcionalmente entre habitaciones.
"""
CREATE OR REPLACE FUNCTION pms.fn_reservation_room_breakdown(p_reservation UUID)
RETURNS TABLE (
  room_id UUID,
  room_code TEXT,
  room_type TEXT,
  subtotal_room NUMERIC,     -- total por habitación ya con promo prorrateada
  currency TEXT
) LANGUAGE sql AS $$
WITH res AS (
  SELECT r.*, r.currency as res_currency
  FROM pms.reservations r
  JOIN pms.properties p ON p.id = r.property_id
  WHERE r.id = p_reservation
),
days AS (
  SELECT generate_series(res.start_date, res.end_date - 1, '1 day')::date AS d, res.res_currency as currency
  FROM res
),
rooms AS (
  SELECT rr.room_id, rm.code AS room_code, rt.name AS room_type, res.res_currency as currency
  FROM pms.reservation_rooms rr
  JOIN pms.rooms rm ON rm.id = rr.room_id
  JOIN pms.room_types rt ON rt.id = rm.room_type_id
  JOIN res ON TRUE
),
base_calc AS (
  SELECT
    r.room_id,
    r.room_code,
    r.room_type,
    d.d AS day,
    r.currency,
    rt2.id AS room_type_id,
    COALESCE(s.multiplier, 1.0) AS season_mult,
    CASE WHEN EXTRACT(ISODOW FROM d.d) IN (6,7) THEN ra.weekend_multiplier ELSE 1.0 END AS wk_mult,
    ra.base_rate
  FROM rooms r
  JOIN pms.rooms rm2 ON rm2.id = r.room_id
  JOIN pms.room_types rt2 ON rt2.id = rm2.room_type_id
  JOIN res ON TRUE
  JOIN pms.rates ra
    ON ra.property_id = (SELECT property_id FROM res)
   AND ra.room_type_id = rt2.id
   AND ra.active = TRUE
  JOIN days d ON TRUE
  LEFT JOIN pms.rate_seasons s
    ON s.property_id = (SELECT property_id FROM res)
   AND d.d BETWEEN s.start_date AND s.end_date
),
room_sum AS (
  SELECT
    room_id, room_code, room_type, currency,
    SUM(base_rate * season_mult * wk_mult) AS base_sum_room
  FROM base_calc
  GROUP BY room_id, room_code, room_type, currency
),
total_base AS (
  SELECT SUM(base_sum_room) AS base_all
  FROM room_sum
),
promo AS (
  SELECT
    COALESCE(pr.percent_off,0) AS percent_off,
    COALESCE(pr.amount_off,0)  AS amount_off
  FROM res
  LEFT JOIN pms.promos pr
    ON pr.property_id = res.property_id
   AND pr.code = res.promo_code
   AND pr.active = TRUE
   AND (pr.start_date IS NULL OR pr.start_date <= res.start_date)
   AND (pr.end_date   IS NULL OR pr.end_date   >= res.start_date)
),
discounted_total AS (
  SELECT
    GREATEST( (tb.base_all * (1 - promo.percent_off/100.0)) - promo.amount_off, 0 ) AS grand_total
  FROM total_base tb, promo
)
SELECT
  rs.room_id,
  rs.room_code,
  rs.room_type,
  CASE
    WHEN tb.base_all IS NULL OR tb.base_all = 0 THEN 0
    ELSE ROUND( rs.base_sum_room * (dt.grand_total / tb.base_all), 2)
  END AS subtotal_room,
  rs.currency
FROM room_sum rs, total_base tb, discounted_total dt
ORDER BY rs.room_code;
$$;



--Ver todos los cargos y costos -Total a pagar- de una reservacion
CREATE OR REPLACE FUNCTION pms.fn_reservation_financials(p_reservation UUID)
RETURNS TABLE(
  base_total NUMERIC,
  charges_total NUMERIC,
  payments_total NUMERIC,
  balance_due NUMERIC,
  currency TEXT
) LANGUAGE sql AS $$
WITH res AS (
  SELECT
    r.*,
    p.currency AS prop_currency,
    r.currency AS res_currency
  FROM pms.reservations r
  JOIN pms.properties   p ON p.id = r.property_id
  WHERE r.id = p_reservation
),
room_total AS (
  SELECT
    SUM(subtotal_room) AS base_total,
    MAX(currency)      AS currency
  FROM pms.fn_reservation_room_breakdown(p_reservation)
),
charges AS (
  SELECT COALESCE(SUM(c.amount),0) AS charges_total
  FROM pms.charges c
  WHERE c.reservation_id = p_reservation
),
payments AS (
  SELECT COALESCE(SUM(p.amount),0) AS payments_total
  FROM pms.payments p
  WHERE p.reservation_id = p_reservation
)
SELECT
  rt.base_total,
  ch.charges_total,
  pm.payments_total,
  ROUND( (rt.base_total + ch.charges_total - pm.payments_total), 2) AS balance_due,
  -- Si quieres forzar la moneda de la reserva, usa res.res_currency
  COALESCE(rt.currency, res.res_currency) AS currency
FROM room_total rt, charges ch, payments pm, res;
$$;

--Funcion para el checkin
CREATE OR REPLACE FUNCTION pms.sp_check_in(
  p_reservation UUID,
  p_method TEXT,          -- ej. 'cash','card','yape','plin'
  p_received_by UUID
) RETURNS TABLE(invoice_number TEXT, paid_amount NUMERIC, new_status TEXT)
LANGUAGE plpgsql AS $$
DECLARE
  v_fin RECORD;
  v_inv TEXT;
  v_currency TEXT;
BEGIN
  SELECT * INTO v_fin FROM pms.fn_reservation_financials(p_reservation);
  IF v_fin IS NULL THEN RAISE EXCEPTION 'RES_NOT_FOUND'; END IF;

  -- si ya está checked_in no repetir
  IF (SELECT status FROM pms.reservations WHERE id = p_reservation) = 'checked_in' THEN
    RETURN QUERY SELECT NULL::TEXT, 0::NUMERIC, 'checked_in';
    RETURN; 
  END IF;

  v_currency := v_fin.currency;

  -- cobrar lo pendiente si hay
  IF v_fin.balance_due > 0 THEN
    INSERT INTO pms.payments(reservation_id, method, amount, currency, received_by)
    VALUES (p_reservation, p_method, v_fin.balance_due, v_currency, p_received_by);
  END IF;

  -- facturar el total de la reserva base (sin extras) o la parte cobrada ahora; 
  -- en hoteles se suele facturar lo cobrado en check-in (puede ser total base)
  v_inv := pms.next_invoice_number( (SELECT property_id FROM pms.reservations WHERE id=p_reservation) );
  INSERT INTO pms.invoices(reservation_id, number, amount, tax_amount, currency)
  VALUES (p_reservation, v_inv, v_fin.balance_due, 0, v_currency);

  -- ocupar habitaciones
  UPDATE pms.rooms r
  SET status = 'occupied'
  WHERE r.id IN (SELECT room_id FROM pms.reservation_rooms WHERE reservation_id = p_reservation);

  -- status
  UPDATE pms.reservations SET status='checked_in' WHERE id=p_reservation;

  RETURN QUERY SELECT v_inv, v_fin.balance_due, 'checked_in';
END;
$$;
