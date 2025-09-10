CREATE OR REPLACE FUNCTION pms.sp_create_reservation_with_rooms(
  p_property   UUID,
  p_guest      UUID,
  p_dates      DATE[],
  p_room_ids   UUID[],
  p_promo_code TEXT,
  p_created_by UUID
)
RETURNS TABLE(reservation_id text, total_amount NUMERIC)  -- devuelve ambos
LANGUAGE plpgsql
AS $$
DECLARE
  v_currency TEXT;
  v_dates    DATE[];       -- fechas únicas y ordenadas
  v_start    DATE;
  v_end_ex   DATE;         -- end exclusive: max(date)+1
  v_total    NUMERIC := 0;
  v_res_id   UUID := gen_random_uuid();
  v_percent_off NUMERIC := 0;
  v_amount_off  NUMERIC := 0;
  v_room UUID;
  v_date DATE;
  v_room_type UUID;
  v_rate RECORD;
  v_season_mult NUMERIC;
  v_wk_mult NUMERIC;
  v_clash INT;
BEGIN
  -- Validaciones básicas
  IF p_dates IS NULL OR array_length(p_dates,1) IS NULL THEN
    RAISE EXCEPTION 'DATES_EMPTY';
  END IF;
  IF p_room_ids IS NULL OR array_length(p_room_ids,1) IS NULL THEN
    RAISE EXCEPTION 'ROOMS_EMPTY';
  END IF;

  -- Normaliza fechas (únicas, ordenadas)
  SELECT ARRAY(SELECT DISTINCT d::date FROM unnest(p_dates) d ORDER BY 1) INTO v_dates;
  v_start := v_dates[1];
  v_end_ex := (v_dates[array_length(v_dates,1)] + 1);

  -- Moneda de la propiedad
  SELECT currency INTO v_currency FROM pms.properties WHERE id = p_property;
  IF v_currency IS NULL THEN RAISE EXCEPTION 'PROPERTY_NOT_FOUND'; END IF;

  -- Aplica promo si corresponde (se evalúa al inicio de la estancia)
  IF p_promo_code IS NOT NULL THEN
    SELECT COALESCE(percent_off,0), COALESCE(amount_off,0)
    INTO v_percent_off, v_amount_off
    FROM pms.promos
    WHERE property_id = p_property AND code = p_promo_code
      AND active = TRUE
      AND (start_date IS NULL OR start_date <= v_start)
      AND (end_date   IS NULL OR end_date   >= v_start)
    LIMIT 1;
  END IF;

  -- Valida que cada room pertenezca a la propiedad y no tenga solape
  FOR v_room IN SELECT DISTINCT x FROM unnest(p_room_ids) x LOOP
    -- Propiedad + obtiene room_type
    SELECT room_type_id INTO v_room_type
    FROM pms.rooms
    WHERE id = v_room AND property_id = p_property;
    IF v_room_type IS NULL THEN
      RAISE EXCEPTION 'ROOM_NOT_IN_PROPERTY_OR_NOT_FOUND: %', v_room;
    END IF;

    -- Chequeo de solape: si existe alguna reserva activa que toque [v_start, v_end_ex)
    SELECT COUNT(*) INTO v_clash
    FROM pms.reservation_rooms rr
    JOIN pms.reservations res ON res.id = rr.reservation_id
    WHERE rr.room_id = v_room
      AND res.status IN ('pending','confirmed','checked_in')
      AND res.start_date < v_end_ex
      AND res.end_date   > v_start;

    IF v_clash > 0 THEN
      RAISE EXCEPTION 'ROOM_OVERLAP: %', v_room;
    END IF;
  END LOOP;

  -- Suma del total por (habitación × día)
  FOR v_room IN SELECT DISTINCT x FROM unnest(p_room_ids) x LOOP
    -- room_type para esta habitación
    SELECT room_type_id INTO v_room_type
    FROM pms.rooms
    WHERE id = v_room;

    -- Recorre cada fecha
    FOREACH v_date IN ARRAY v_dates LOOP
      -- Tarifa activa para ese room_type
      SELECT r.base_rate, r.weekend_multiplier
      INTO v_rate
      FROM pms.rates r
      WHERE r.property_id = p_property
        AND r.room_type_id = v_room_type
        AND r.active = TRUE
      LIMIT 1;

      IF NOT FOUND THEN
        RAISE EXCEPTION 'RATE_NOT_FOUND for room_type %', v_room_type;
      END IF;

      -- Mult. temporada si aplica ese día
      SELECT COALESCE(MAX(s.multiplier),1.0) INTO v_season_mult
      FROM pms.rate_seasons s
      WHERE s.property_id = p_property
        AND v_date BETWEEN s.start_date AND s.end_date;

      -- Mult. fin de semana (isodow: 6=sábado, 7=domingo)
      v_wk_mult := CASE WHEN EXTRACT(ISODOW FROM v_date) IN (6,7)
                        THEN v_rate.weekend_multiplier ELSE 1.0 END;

      v_total := v_total + (v_rate.base_rate * v_season_mult * v_wk_mult);
    END LOOP;
  END LOOP;

  -- Aplica promo al total (si existe)
  IF v_percent_off IS NOT NULL AND v_percent_off > 0 THEN
    v_total := v_total * (1 - v_percent_off/100.0);
  END IF;
  IF v_amount_off IS NOT NULL AND v_amount_off > 0 THEN
    v_total := v_total - v_amount_off;
  END IF;
  IF v_total < 0 THEN v_total := 0; END IF;

  -- Inserta la reserva (room_type_id NULL porque es mixta)
  INSERT INTO pms.reservations(
    id, property_id, guest_id, room_type_id,
    start_date, end_date, status, promo_code, currency,
    total_amount, deposit_amount, created_by
  ) VALUES (
    v_res_id, p_property, p_guest, NULL,
    v_start, v_end_ex, 'pending', p_promo_code, v_currency,
    v_total, 0, p_created_by
  );

  -- Inserta el vínculo reserva-habitación (varias)
  INSERT INTO pms.reservation_rooms (reservation_id, room_id)
  SELECT v_res_id, x
  FROM (SELECT DISTINCT x FROM unnest(p_room_ids) x) t;

  reservation_id := v_res_id::text;
  total_amount   := v_total;
  RETURN NEXT;
END;
$$;
