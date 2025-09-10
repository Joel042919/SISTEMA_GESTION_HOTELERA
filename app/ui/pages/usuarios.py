import streamlit as st
from typing import List, Dict
from app.auth.session import current_user
from app.repositories.pg_repo import PgRepo
from app.services.users import UsersService
import pandas as pd
from app.services.base import policy_check
from app.ui.layout import hide_native_multipage_nav, inject_sidebar_style, guard_login, render_sidebar_nav
st.set_page_config(page_title="Usuarios & Roles", layout="wide")
hide_native_multipage_nav()   # oculta menú multipágina nativo (evita links antes del login)
inject_sidebar_style()        # estilos bonitos del sidebar/nav
u = guard_login()             # exige sesión (si no hay, detiene la página)
render_sidebar_nav()          # pinta los links con emojis en el sidebar
u = current_user()
if not u:
    st.stop()

repo = PgRepo()
svc_users = UsersService(repo)

st.header("👤 Gestión de Usuarios")

# ========== Helpers de estado ==========
st.session_state.setdefault("selected_user_id", "")
st.session_state.setdefault("mode", "create")  # "create" | "edit"

# ========== Carga de catálogo de roles ==========
@st.cache_data(ttl=300)
def _get_roles_catalog() -> Dict[str, str]:
    """
    Devuelve {role_name: role_id} para el multiselect
    """
    rows = svc_users.list_roles()
    return {name: rid for (rid, name) in [(r[0], r[1]) for r in rows]}  # si rows viene como [(id,name)]

# la línea anterior puede confundirte si rows ya viene como (id,name)
# Prefiere esto si tu list_roles retorna [(id,name)]:
def _roles_map(rows):
    return {name: rid for (rid, name) in rows}

roles_rows = svc_users.list_roles()
roles_map = _roles_map(roles_rows)  # {name: id}
role_names = list(roles_map.keys())

# ========== Tabla de usuarios ==========
@st.cache_data(ttl=60)
def _load_users(property_id: str) -> pd.DataFrame:
    data = svc_users.list_users(property_id)
    df = pd.DataFrame(data)
    if not df.empty and "roles" in df.columns:
        df["roles"] = df["roles"].apply(lambda xs: ", ".join(xs) if isinstance(xs, list) else "")
    return df

colL, colR = st.columns([3, 2], gap="large")

with colL:
    st.subheader("Listado")
    df_users = _load_users(u["property_id"])
    if df_users.empty:
        st.info("No hay usuarios aún.")
    else:
        st.dataframe(
            df_users[["full_name", "email", "is_active", "roles"]],
            use_container_width=True,
            height=380
        )

    # Selector para editar
    if not df_users.empty:
        user_picker = st.selectbox(
            "Seleccionar usuario para editar",
            options=["—"] + df_users["email"].tolist(),
            index=0
        )
        if user_picker != "—":
            # encuentra el id
            row = df_users.loc[df_users["email"] == user_picker].iloc[0]
            st.session_state["selected_user_id"] = row["id"]
            st.session_state["mode"] = "edit"
        else:
            st.session_state["selected_user_id"] = ""
            st.session_state["mode"] = "create"

with colR:
    st.subheader("Formulario")

    mode = st.session_state["mode"]
    editing = (mode == "edit" and st.session_state["selected_user_id"])

    # Cargar valores si estamos editando
    init_email = ""
    init_full_name = ""
    init_is_active = True
    init_role_ids: List[str] = []

    if editing:
        detail = svc_users.get_user(st.session_state["selected_user_id"], u["property_id"])
        if detail:
            init_email = detail["email"]
            init_full_name = detail["full_name"]
            init_is_active = detail["is_active"]
            init_role_ids = detail.get("role_ids", [])
        else:
            st.warning("No se pudo cargar el usuario. Pasando a modo crear.")
            st.session_state["mode"] = "create"

    with st.form("user_form", clear_on_submit=False):
        email = st.text_input("Email", value=init_email, placeholder="usuario@dominio.com")
        full_name = st.text_input("Nombre completo", value=init_full_name)

        if editing:
            st.caption("Si no deseas cambiar la contraseña, deja el campo vacío.")
            password = st.text_input("Nueva contraseña", type="password", value="")
        else:
            password = st.text_input("Contraseña", type="password", value="")

        is_active = st.checkbox("Usuario activo", value=init_is_active)

        # multiselect por nombre pero guardamos ids
        selected_role_names = st.multiselect(
            "Roles",
            options=role_names,
            default=[name for name, rid in roles_map.items() if rid in init_role_ids]
        )
        selected_role_ids = [roles_map[n] for n in selected_role_names]

        # Botones
        c1, c2, c3 = st.columns([1,1,1])
        submit_btn = c1.form_submit_button("Guardar", use_container_width=True)
        new_btn    = c2.form_submit_button("Nuevo", use_container_width=True)
        delete_btn = c3.form_submit_button("Desactivar", use_container_width=True, disabled=not editing)

    # Handlers
    if new_btn:
        st.session_state["selected_user_id"] = ""
        st.session_state["mode"] = "create"
        st.cache_data.clear()  # limpias caches de listados
        st.rerun()

    if submit_btn:
        try:
            if not email or not full_name:
                st.error("Email y nombre son obligatorios.")
            elif not editing and not password:
                st.error("La contraseña es obligatoria para crear el usuario.")
            else:
                if editing:
                    svc_users.update_user(
                        user_id=st.session_state["selected_user_id"],
                        email=email,
                        full_name=full_name,
                        maybe_plain_password=password,
                        is_active=is_active,
                        role_ids=selected_role_ids,
                        property_id=u["property_id"]
                    )
                    st.success("Usuario actualizado.")
                else:
                    uid = svc_users.create_user(
                        email=email,
                        full_name=full_name,
                        plain_password=password,
                        is_active=is_active,
                        role_ids=selected_role_ids,
                        property_id=u["property_id"]
                    )
                    st.session_state["selected_user_id"] = uid
                    st.session_state["mode"] = "edit"
                    st.success(f"Usuario creado: {uid[:8]}…")

                st.cache_data.clear()  # recarga listados
                st.rerun()
        except Exception as e:
            st.error("No se pudo guardar el usuario (¿email duplicado?).")
            st.exception(e)

    if delete_btn and editing:
        try:
            svc_users.set_active(st.session_state["selected_user_id"], False)
            st.success("Usuario desactivado (is_active = false).")
            st.cache_data.clear()
            st.rerun()
        except Exception as e:
            st.error("No se pudo desactivar el usuario.")
            st.exception(e)
