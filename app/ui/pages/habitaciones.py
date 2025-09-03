import streamlit as st
import psycopg
from app.core.db import POOL
from app.services.rooms import RoomsService
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user


u = current_user()
if not u: st.stop()
svc = RoomsService(PgRepo())


st.header("Habitaciones — Estado en tiempo real")


with psycopg.connect(POOL.conninfo) as conn:
    df = None
    try:
        df = conn.execute("SELECT id, code, status FROM pms.rooms WHERE property_id=%s ORDER BY code", (u['property_id'],)).fetchall()
    except Exception as e:
        st.error(str(e))


if df:
    for r in df:
        c1, c2, c3, c4 = st.columns([1,1,1,2])
        c1.write(r[1])
        c2.write(r[2])
        new_status = c3.selectbox("Nuevo estado", ['available','occupied','dirty','cleaning','maintenance','out_of_order'], key=r[0])
        if c4.button("Actualizar", key=f"btn_{r[0]}"):
            svc.set_status(r[0], new_status, u['id'])
            st.rerun()