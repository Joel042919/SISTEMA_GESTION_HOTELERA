import streamlit as st
from app.auth.session import SESSION_USER_KEY

# ---- 1) Ocultar el navegador multipágina nativo ----
def hide_native_multipage_nav():
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] div[data-testid="stSidebarNav"] { display: none !important; }
    div[data-testid="stSidebarNav"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# ---- 2) Estilos del sidebar/nav (colores, badges, etc.) ----
def inject_sidebar_style():
    st.markdown("""
    <style>
    :root{
      --ink:#0f172a; --muted:#475569;
    }
    .sidebar-title { font-weight: 800; font-size: 14px; color: var(--ink); margin: 6px 0 4px; display:flex; align-items:center; gap:.4rem }
    .sidebar-pill {
      font-size: 12px; padding: 6px 10px; border-radius: 999px; background: #ecfeff; color: #0e7490; display:inline-block;
      border: 1px solid #cffafe; margin-bottom: 8px;
    }
    </style>
    """, unsafe_allow_html=True)

# ---- 3) Guardia de autenticación para páginas ----
def guard_login():
    if SESSION_USER_KEY not in st.session_state:
        # Puedes poner un mensaje suave o redirigir a la home
        st.sidebar.warning("Inicia sesión desde la página principal.")
        st.stop()
    return st.session_state[SESSION_USER_KEY]


def logout_and_redirect():
    """Elimina la sesión, limpia caches y redirige a la home."""
    if SESSION_USER_KEY in st.session_state:
        del st.session_state[SESSION_USER_KEY]
    # Opcional: limpia cachés si las usas mucho
    try:
        st.cache_data.clear()
        st.cache_resource.clear()
    except Exception:
        pass
    _go_home()

def _go_home():
    """
    Redirige a la página principal inmediatamente.
    Probamos varias rutas/etiquetas para distintos layouts de proyecto.
    """
    for target in ("app/ui/streamlit_app.py", "streamlit_app.py", "streamlit app", "Home"):
        try:
            st.switch_page(target)
            return
        except Exception:
            continue
    st.experimental_rerun()  # último recurso



# ---- 4) Navbar estilizado en el sidebar (links con emojis) ----
def render_sidebar_nav():
    """Renderiza los links de navegación estilizados en el sidebar (para usar tras login)."""
    u = st.session_state.get(SESSION_USER_KEY)
    with st.sidebar:
        st.markdown('<div class="sidebar-title">🧭 Navegación</div>', unsafe_allow_html=True)
        if u:
            st.write(f"👤 **{u['name']}**")
            roles_txt = ", ".join(u.get("roles", [])) or "—"
            st.write(f"🔑 Roles: {roles_txt}")
            st.markdown('<span class="sidebar-pill">Propiedad activa</span>', unsafe_allow_html=True)

        # Enlaza tus páginas aquí (mismo set que la home)
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
            logout_and_redirect()
