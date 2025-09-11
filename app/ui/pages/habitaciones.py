# app/ui/pages/habitaciones.py
import streamlit as st
import pandas as pd
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user
<<<<<<< HEAD
from app.core.db import POOL
=======
from app.ui.layout import hide_native_multipage_nav, inject_sidebar_style, guard_login, render_sidebar_nav

>>>>>>> d1211c539bdfdfa1792f6acac0f7a72d1438d3ff

hide_native_multipage_nav()   # oculta menú multipágina nativo (evita links antes del login)
inject_sidebar_style()        # estilos bonitos del sidebar/nav
u = guard_login()             # exige sesión (si no hay, detiene la página)
render_sidebar_nav()          # pinta los links con emojis en el sidebar

u = current_user()
if not u:
    st.stop()

st.header("Habitaciones")

@st.cache_data(ttl=60)
def _load_rooms(property_id:str):
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    r.id::text              AS room_id,
                    r.code                  AS code,
                    rt.name                 AS room_type,
                    rt.capacity_adults      AS capacity_adults,
                    rt.capacity_children    AS capacity_children,
                    r.status::text          AS status
                    FROM pms.rooms r
                    JOIN pms.room_types rt ON rt.id = r.room_type_id
                    WHERE r.property_id = %s
                    ORDER BY r.code;

            """, (property_id,))
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=["id","code","type","adults","children","status"])
df = _load_rooms(u['property_id'])
st.dataframe(df, use_container_width=True, hide_index=True)

st.subheader("Cambiar estado")
room_id = st.selectbox("Habitación", df["id"].tolist(), format_func=lambda rid: df.loc[df["id"]==rid, "code"].iloc[0] if not df.empty else rid)
new_status = st.selectbox("Nuevo estado", ["available","occupied","maintenance"])
if st.button("Aplicar"):
    try:
        with POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pms.sp_set_room_status(%s, %s::pms.room_status, %s);",
                            (room_id, new_status, u['id']))
        st.success("Estado actualizado.")
        st.cache_data.clear()
        st.rerun()
    except Exception as e:
        st.error("No se pudo actualizar el estado.")
        st.exception(e)
