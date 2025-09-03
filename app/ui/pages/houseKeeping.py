import streamlit as st
from datetime import date
import psycopg
from app.core.db import POOL
from app.auth.session import current_user


u = current_user();
if not u: st.stop()


st.header("Housekeeping")
with psycopg.connect(POOL.conninfo) as conn:
    tasks = conn.execute(
        "SELECT id, room_id, scheduled_date, status FROM pms.housekeeping_tasks WHERE property_id=%s AND scheduled_date=%s",
        (u['property_id'], date.today())
    ).fetchall()


st.write(tasks if tasks else "No hay tareas hoy.")