SET search_path TO pms, public;

-- Propiedad demo
INSERT INTO properties (id, name, country_code, currency)
VALUES ('00000000-0000-0000-0000-000000000000','Hotel Demo','PE','PEN')
ON CONFLICT DO NOTHING;

-- Impuestos
INSERT INTO tax_codes (code, description, rate) VALUES
  ('IGV', 'Impuesto General a las Ventas (PE)', 18.00)
ON CONFLICT DO NOTHING;

-- Roles
INSERT INTO roles (name) VALUES
  ('Administrador'),('Recepcion'),('Housekeeping'),('Finanzas'),('Gerencia')
ON CONFLICT DO NOTHING;

-- Permisos (ejemplos)
INSERT INTO permissions (name) VALUES
  ('reservations.create'),('reservations.view'),('reservations.cancel'),('reservations.assign_room'),
  ('billing.view'),('billing.charge'),('billing.pay'),('billing.close_cash'),
  ('rooms.view'),('rooms.update_status'),('reports.view'),('users.manage')
ON CONFLICT DO NOTHING;

-- Rol Administrador con todos los permisos
INSERT INTO role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM roles r, permissions p
WHERE r.name='Administrador'
ON CONFLICT DO NOTHING;

-- Usuario admin demo (bcrypt("admin123"))
INSERT INTO users (email, full_name, password_hash)
VALUES ('admin@demo.local','Admin Demo', '$2b$12$JXw8rQ0JwZxD1hJ9hG0s2e9q2uVq8sJw9tA6xJ1cQ2jS9c0vN6b7e')
ON CONFLICT DO NOTHING;

-- Asignar rol admin a la propiedad demo
INSERT INTO user_roles (user_id, role_id, property_id)
SELECT u.id, r.id, '00000000-0000-0000-0000-000000000000'
FROM users u, roles r
WHERE u.email='admin@demo.local' AND r.name='Administrador'
ON CONFLICT DO NOTHING;

-- =========================
-- Room type y rooms con CTEs
-- =========================

-- Inserta room_type Standard si no existe y obtén su id
WITH ins_rt AS (
  INSERT INTO room_types (property_id, name, capacity_adults, capacity_children)
  VALUES ('00000000-0000-0000-0000-000000000000','Standard',2,1)
  ON CONFLICT DO NOTHING
  RETURNING id
),
rt AS (
  SELECT id FROM ins_rt
  UNION ALL
  SELECT id FROM room_types
  WHERE property_id='00000000-0000-0000-0000-000000000000' AND name='Standard'
  LIMIT 1
)
INSERT INTO rooms (property_id, room_type_id, code)
SELECT '00000000-0000-0000-0000-000000000000', id, '101' FROM rt
ON CONFLICT DO NOTHING;

WITH rt AS (
  SELECT id FROM room_types
  WHERE property_id='00000000-0000-0000-0000-000000000000' AND name='Standard'
  LIMIT 1
)
INSERT INTO rooms (property_id, room_type_id, code)
SELECT '00000000-0000-0000-0000-000000000000', id, '102' FROM rt
ON CONFLICT DO NOTHING;

-- Tarifa base para el room_type Standard
WITH rt AS (
  SELECT id FROM room_types
  WHERE property_id='00000000-0000-0000-0000-000000000000' AND name='Standard'
  LIMIT 1
)
INSERT INTO rates (property_id, room_type_id, base_rate, currency, weekend_multiplier, tax_code, active)
SELECT '00000000-0000-0000-0000-000000000000', id, 150.00, 'PEN', 1.15, 'IGV', TRUE
FROM rt
ON CONFLICT DO NOTHING;

-- Temporada alta demo
INSERT INTO rate_seasons (property_id, name, start_date, end_date, multiplier)
VALUES ('00000000-0000-0000-0000-000000000000','Alta (Dic-Feb)','2025-12-01','2026-02-28',1.25)
ON CONFLICT DO NOTHING;

-- Promo demo
INSERT INTO promos (property_id, code, description, percent_off, start_date, end_date, active)
VALUES ('00000000-0000-0000-0000-000000000000','BIENVENIDA','Promo bienvenida',10,'2025-01-01','2025-12-31', TRUE)
ON CONFLICT DO NOTHING;
