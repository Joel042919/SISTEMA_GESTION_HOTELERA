import os,sys

import streamlit as st
from app.core.config import settings
from app.core.security import verify_password
from app.core.db import POOL
from app.auth.session import SESSION_USER_KEY


st.set_page_config(page_title="PMS Demo", layout='wide')


@st.cache_resource
def _warm_db():
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")


_warm_db()

# Login simple en sidebar
if SESSION_USER_KEY not in st.session_state:
    st.sidebar.header("Iniciar sesión")
    email = st.sidebar.text_input("Correo", value="admin@demo.local")
    password = st.sidebar.text_input("Contraseña", type="password",value="admin123")
    if st.sidebar.button("Entrar", use_container_width=True):
        import psycopg
        with psycopg.connect(POOL.conninfo) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, full_name, password_hash FROM pms.users WHERE email=%s", (email,))
                row = cur.fetchone()
                if row and verify_password(password, row[2]):
                    # roles
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
        st.write(f"👤 {u['name']} · Roles: {', '.join(u['roles'])}")
        if st.button("Salir", use_container_width=True):
            del st.session_state[SESSION_USER_KEY]
            st.rerun()


st.title("🏨 PMS — Demo MVP")
st.caption("Dashboard de KPIs y navegación por páginas (ver carpeta pages)")


st.page_link("pages/dashboard.py", label="Dashboard", icon="📊")
st.page_link("pages/reservas.py", label="Reservas", icon="🗓️")
st.page_link("pages/checkIn_checkOut.py", label="Check-in/Check-out", icon="🧾")
st.page_link("pages/habitaciones.py", label="Habitaciones", icon="🛏️")
st.page_link("pages/housekeeping.py", label="Housekeeping", icon="🧹")
st.page_link("pages/facturacion_Caja.py", label="Facturación y Caja", icon="💵")
st.page_link("pages/Reportes.py", label="Reportes", icon="📑")
st.page_link("pages/usuarios.py", label="Usuarios", icon="👥")
#st.page_link("app/ui/pages/10_Administracion.py", label="Administración", icon="⚙️")