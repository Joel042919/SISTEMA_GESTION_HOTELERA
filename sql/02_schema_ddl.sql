-- 02_schema_ddl.sql (versión corregida y consistente)
-- Crea todo el esquema pms con tablas y tipos en orden correcto

CREATE SCHEMA IF NOT EXISTS pms;
SET search_path TO pms, public;

-- =========================
-- Catálogos / Básicos
-- =========================

CREATE TABLE properties (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  country_code TEXT NOT NULL DEFAULT 'PE',
  currency TEXT NOT NULL DEFAULT 'PEN',
  timezone TEXT NOT NULL DEFAULT 'America/Lima',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE room_types (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  capacity_adults INT NOT NULL CHECK (capacity_adults >= 1),
  capacity_children INT NOT NULL DEFAULT 0 CHECK (capacity_children >= 0),
  amenities JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TYPE room_status AS ENUM ('available','occupied','dirty','cleaning','maintenance','out_of_order');

CREATE TABLE rooms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  room_type_id UUID NOT NULL REFERENCES room_types(id) ON DELETE RESTRICT,
  code TEXT NOT NULL,
  status room_status NOT NULL DEFAULT 'available',
  UNIQUE(property_id, code)
);

CREATE TABLE room_status_history (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  old_status room_status,
  new_status room_status NOT NULL,
  changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  changed_by UUID,
  notes TEXT
);

-- =========================
-- Tarifas / Impuestos / Promos
-- =========================

CREATE TABLE tax_codes (
  code TEXT PRIMARY KEY,
  description TEXT,
  rate NUMERIC(5,2) NOT NULL CHECK (rate >= 0)
);

CREATE TABLE rates (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  room_type_id UUID NOT NULL REFERENCES room_types(id) ON DELETE RESTRICT,
  base_rate NUMERIC(12,2) NOT NULL CHECK (base_rate >= 0),
  currency TEXT NOT NULL,
  weekend_multiplier NUMERIC(6,3) NOT NULL DEFAULT 1.00,
  tax_code TEXT NOT NULL REFERENCES tax_codes(code),
  active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE rate_seasons (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  multiplier NUMERIC(6,3) NOT NULL DEFAULT 1.00,
  CHECK (end_date >= start_date)
);

CREATE TABLE promos (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  code TEXT NOT NULL,
  description TEXT,
  percent_off NUMERIC(5,2),
  amount_off NUMERIC(12,2),
  start_date DATE,
  end_date DATE,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  UNIQUE(property_id, code)
);

-- =========================
-- Huéspedes / Reservas
-- =========================

CREATE TYPE reservation_status AS ENUM ('pending','confirmed','checked_in','checked_out','canceled','no_show');

CREATE TABLE guests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name TEXT NOT NULL,
  email TEXT,
  phone TEXT,
  preferences JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE reservations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  guest_id UUID NOT NULL REFERENCES guests(id) ON DELETE RESTRICT,
  room_type_id UUID NOT NULL REFERENCES room_types(id) ON DELETE RESTRICT,
  start_date DATE NOT NULL,
  end_date DATE NOT NULL,
  status reservation_status NOT NULL DEFAULT 'pending',
  promo_code TEXT,
  currency TEXT NOT NULL,
  total_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  deposit_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
  created_by UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (end_date > start_date)
);

-- IMPORTANTE: NO usar EXCLUDE con referencia a otra tabla
-- (postgres no permite referenciar columns de otra tabla en constraints)
CREATE TABLE reservation_rooms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reservation_id UUID NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
  room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
  UNIQUE (reservation_id)
);

CREATE INDEX IF NOT EXISTS idx_rr_room ON reservation_rooms (room_id);

-- =========================
-- Billing: Cargos / Pagos / Invoices
-- =========================

CREATE TABLE charges (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reservation_id UUID NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
  concept TEXT NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  tax_code TEXT REFERENCES tax_codes(code),
  posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  posted_by UUID
);

CREATE TABLE payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reservation_id UUID NOT NULL REFERENCES reservations(id) ON DELETE CASCADE,
  method TEXT NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  currency TEXT NOT NULL,
  paid_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  received_by UUID
);

CREATE TABLE invoices (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reservation_id UUID NOT NULL REFERENCES reservations(id) ON DELETE RESTRICT,
  number TEXT NOT NULL,
  amount NUMERIC(12,2) NOT NULL,
  tax_amount NUMERIC(12,2) NOT NULL,
  currency TEXT NOT NULL,
  issued_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  pdf_url TEXT
);

-- =========================
-- Housekeeping
-- =========================

CREATE TYPE hk_status AS ENUM ('pending','in_progress','done');

CREATE TABLE housekeeping_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
  scheduled_date DATE NOT NULL,
  status hk_status NOT NULL DEFAULT 'pending',
  checklist JSONB NOT NULL DEFAULT '[]',
  assigned_to UUID,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- =========================
-- Usuarios / RBAC
-- =========================

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  password_hash TEXT NOT NULL,
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE roles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE permissions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT UNIQUE NOT NULL
);

CREATE TABLE role_permissions (
  role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
  permission_id UUID REFERENCES permissions(id) ON DELETE CASCADE,
  PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
  property_id UUID REFERENCES properties(id) ON DELETE CASCADE,
  PRIMARY KEY (user_id, role_id, property_id)
);

-- =========================
-- Auditoría / Caja
-- =========================

CREATE TABLE audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  user_id UUID,
  entity TEXT NOT NULL,
  entity_id UUID,
  action TEXT NOT NULL,
  diff_json JSONB
);

CREATE TABLE cash_closures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
  date DATE NOT NULL,
  closed_by UUID,
  total_payments NUMERIC(12,2) NOT NULL DEFAULT 0,
  total_invoices NUMERIC(12,2) NOT NULL DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(property_id, date)
);

ALTER TABLE pms.reservations
  ALTER COLUMN room_type_id DROP NOT NULL;

-- Quita la unicidad por reservation_id
ALTER TABLE pms.reservation_rooms DROP CONSTRAINT IF EXISTS reservation_rooms_reservation_id_key;

-- Asegura que no se repita la misma habitación dentro de la misma reserva
ALTER TABLE pms.reservation_rooms
  ADD CONSTRAINT uq_reservation_room UNIQUE (reservation_id, room_id);
