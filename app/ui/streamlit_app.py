import os, sys
import streamlit as st
from app.core.config import settings
from app.core.security import verify_password
from app.core.db import POOL
from app.auth.session import SESSION_USER_KEY



st.set_page_config(page_title="PMS · Casa Andina", page_icon="🏨", layout="wide")

st.markdown("""
<style>
/* Oculta el navegador multipágina nativo de Streamlit */
section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] { display: none !important; }
/* (fallback para versiones) */
div[data-testid="stSidebarNav"] { display: none !important; }
</style>
""", unsafe_allow_html=True)


# ---------- Warmup DB ----------
@st.cache_resource
def _warm_db():
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
_warm_db()

# ---------- Estilos Globales ----------
CSS = """
<style>
/* Fuente y reset suave */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap');
html, body, [class*="css"]  { font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif; }

:root{
  --brand:#0f766e;      /* teal-700 */
  --brand-2:#14b8a6;    /* teal-500 */
  --brand-3:#99f6e4;    /* teal-200 */
  --ink:#0f172a;        /* slate-900 */
  --muted:#475569;      /* slate-600 */
  --card:#14b8a6;
}

.block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; }

/* ---------- HERO ---------- */
.ca-hero {
  position: relative;
  border-radius: 24px;
  padding: 64px 48px;
  background: radial-gradient(1200px 600px at 10% -20%, rgba(20,184,166,0.25), transparent 50%),
              radial-gradient(1000px 600px at 110% 10%, rgba(16,185,129,0.20), transparent 50%),
              linear-gradient(135deg, #0f766e, #0ea5e9);
  color: white;
  overflow: hidden;
  box-shadow: 0 30px 60px rgba(15, 118, 110, 0.25);
  animation: ca-fade 900ms ease 1;
}

@keyframes ca-fade { from { opacity: 0; transform: translateY(6px);} to { opacity: 1; transform: translateY(0);} }

.ca-hero h1 {
  font-size: clamp(28px, 4vw, 46px);
  line-height: 1.05;
  margin: 0 0 10px 0;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.ca-hero p {
  font-size: clamp(14px, 1.4vw, 18px);
  opacity: 0.92;
  max-width: 820px;
  margin: 8px 0 0 0;
}

/* montañas decorativas */
.ca-mountains {
  position:absolute; inset:auto -10% -35% -10%;
  height: 60%;
  background: linear-gradient( to top, rgba(255,255,255,0.20), rgba(255,255,255,0.0) ),
              url('https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?q=80&w=1400&auto=format&fit=crop') center/cover no-repeat;
  filter: blur(6px) opacity(0.35);
  transform: translateY(0);
  animation: floaty 9s ease-in-out infinite alternate;
}
@keyframes floaty { from { transform: translateY(0px);} to { transform: translateY(10px);} }

/* ---------- CTA buttons ---------- */
.ca-cta { margin-top: 22px; display: flex; gap: 12px; flex-wrap: wrap; }
.ca-btn {
  display:inline-flex; align-items:center; gap:10px;
  padding: 12px 16px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.25);
  color:white; text-decoration:none; font-weight:600; backdrop-filter: blur(4px);
  transition: all .2s ease;
}
.ca-btn:hover { transform: translateY(-2px); box-shadow: 0 10px 24px rgba(0,0,0,.15); border-color: rgba(255,255,255,0.5); }

/* ---------- Feature Cards ---------- */
.ca-grid { display:grid; grid-template-columns: repeat(12, 1fr); gap: 16px; margin-top: 22px; }
.ca-card {
  grid-column: span 4;
  background: var(--card);
  border-radius: 18px;
  padding: 18px 18px 16px;
  box-shadow: 0 12px 30px rgba(2, 6, 23, .06);
  border: 1px solid rgba(2, 6, 23, .06);
  transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
}
.ca-card:hover { transform: translateY(-4px); box-shadow: 0 18px 38px rgba(2, 6, 23, .10); border-color: rgba(2,6,23,.12); }

.ca-card h3 { margin: 6px 0 2px; font-size: 18px; color: var(--ink); }
.ca-card p { margin: 0; color: var(--muted); font-size: 14px; }

.ca-badge {
  display:inline-flex; align-items:center; gap:8px;
  font-size: 12px; padding: 6px 10px; border-radius: 999px;
  background: linear-gradient( to right, rgba(153,246,228,.9), rgba(20,184,166,.8));
  color:#064e3b; border: 1px solid rgba(255,255,255,.5);
  box-shadow: 0 6px 16px rgba(20,184,166,.25);
}

/* ---------- KPIs pills ---------- */
.ca-kpis { display:flex; gap: 12px; flex-wrap: wrap; margin-top: 14px; }
.ca-kpi {
  background: #14b8a6; border-radius: 12px; padding: 10px 14px;
  border: 1px solid rgba(2,6,23,.06); box-shadow: 0 8px 22px rgba(2,6,23,.05);
  display: inline-flex; align-items:center; gap: 10px; font-weight: 600; color: var(--ink);
}

/* ---------- Sidebar: separadores y navegación ---------- */
.sidebar-title { font-weight: 800; font-size: 14px; color: var(--ink); margin: 6px 0 4px; }
.sidebar-pill {
  font-size: 12px; padding: 6px 10px; border-radius: 999px; background: #ecfeff; color: #0e7490; display:inline-block;
  border: 1px solid #cffafe; margin-bottom: 8px;
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ---------- SIDEBAR ----------
if SESSION_USER_KEY not in st.session_state:
    st.sidebar.header("Iniciar sesión")
    email = st.sidebar.text_input("Correo", value="admin@demo.local")
    password = st.sidebar.text_input("Contraseña", type="password", value="admin123")
    if st.sidebar.button("Entrar", use_container_width=True):
        import psycopg
        with psycopg.connect(POOL.conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, full_name, password_hash FROM pms.users WHERE email=%s", (email,))
                row = cur.fetchone()
                if row and verify_password(password, row[2]):
                    # roles del usuario para la propiedad por defecto
                    cur.execute("""
                        SELECT r.name FROM pms.user_roles ur
                        JOIN pms.roles r ON r.id=ur.role_id
                        WHERE ur.user_id=%s AND ur.property_id=%s
                    """, (row[0], settings.default_property_id))
                    roles = [r[0] for r in cur.fetchall()]

                    st.session_state[SESSION_USER_KEY] = {
                        'id': row[0], 'name': row[1], 'email': email,
                        'roles': roles, 'property_id': settings.default_property_id
                    }
                    st.toast("¡Bienvenido!")
                    st.rerun()
                else:
                    st.error("Credenciales inválidas")
else:
    u = st.session_state[SESSION_USER_KEY]
    with st.sidebar:
        st.markdown("### 🧭 Navegación")
        st.write(f"👤 **{u['name']}**")
        st.write("🔑 Roles: " + (", ".join(u['roles']) if u['roles'] else "—"))
        st.markdown('<span class="sidebar-pill">Propiedad activa</span>', unsafe_allow_html=True)

        # Links con emojis (solo en sidebar)
        st.page_link("pages/dashboard.py",        label="📊  Dashboard")
        st.page_link("pages/reservas.py",         label="🗓️  Reservas")
        st.page_link("pages/checkIn_checkOut.py", label="🧾  Check-in / Check-out")
        st.page_link("pages/habitaciones.py",     label="🛏️  Habitaciones")
        st.page_link("pages/housekeeping.py",     label="🧹  Housekeeping")
        st.page_link("pages/facturacion_Caja.py", label="💵  Facturación y Caja")
        st.page_link("pages/Reportes.py",         label="📑  Reportes")
        st.page_link("pages/usuarios.py",         label="👥  Usuarios")
        st.divider()
        if st.button("Salir", use_container_width=True):
            del st.session_state[SESSION_USER_KEY]
            st.rerun()

# ---------- CONTENIDO PRINCIPAL: Landing ----------
# (No más page_link aquí: los movimos al sidebar)
st.markdown("""
<div class="ca-hero">
  <div class="ca-mountains"></div>
  <span class="ca-badge">🏔️ Casa Andina · PMS</span>
  <h1>Hospitalidad andina, gestión moderna.</h1>
  <p>
    Bienvenido a <b>Casa Andina</b>, donde la calidez del servicio se encuentra con un
    <i>Property Management System</i> ágil, seguro y diseñado para operaciones reales de hotel.
    Controla reservas, ocupación, housekeeping y caja desde un solo lugar.
  </p>
  <div class="ca-cta">
    <a class="ca-btn" href="#features">✨ Ver funcionalidades</a>
    <a class="ca-btn" href="#kpis">📈 KPIs clave</a>
  </div>
</div>
""", unsafe_allow_html=True)

# Bloque de features
st.markdown('<div id="features" class="ca-grid">', unsafe_allow_html=True)
st.markdown("""
  <div class="ca-card">
    <div>🗓️</div>
    <h3>Reservas inteligentes</h3>
    <p>Precios por temporada, solape seguro y asignación de habitaciones por rango de fechas.</p>
  </div>
""", unsafe_allow_html=True)
st.markdown("""
  <div class="ca-card">
    <div>🧹</div>
    <h3>Housekeeping conectado</h3>
    <p>Tasks automáticas en checkout, prioridades, y estados sincronizados con la disponibilidad.</p>
  </div>
""", unsafe_allow_html=True)
st.markdown("""
  <div class="ca-card">
    <div>💵</div>
    <h3>Facturación & Caja</h3>
    <p>Cargos, pagos e invoices integrados. Cierres diarios y control financiero.</p>
  </div>
""", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# KPIs pills (placeholders agradables)
st.markdown('<div id="kpis" class="ca-kpis">', unsafe_allow_html=True)
st.markdown('<div class="ca-kpi">🏨 Habitaciones totales: <span style="opacity:.8;margin-left:6px;">en tu Dashboard</span></div>', unsafe_allow_html=True)
st.markdown('<div class="ca-kpi">📈 Ocupación hoy: <span style="opacity:.8;margin-left:6px;">ver Reportes</span></div>', unsafe_allow_html=True)
st.markdown('<div class="ca-kpi">🧾 Ventas del día: <span style="opacity:.8;margin-left:6px;">Facturación y Caja</span></div>', unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Mini sección “cómo empezar”
st.markdown("---")
st.markdown("### 🚀 Cómo empezar")
cols = st.columns(3)
with cols[0]:
    st.markdown("**1. Crea/gestiona usuarios**  \nAsigna roles por propiedad en **👥 Usuarios**.")
with cols[1]:
    st.markdown("**2. Configura tipos y rooms**  \nAdministra **🛏️ Habitaciones** y sus tarifas.")
with cols[2]:
    st.markdown("**3. Opera el día a día**  \nUsa **🗓️ Reservas**, **🧹 Housekeeping** y **💵 Caja**.")
