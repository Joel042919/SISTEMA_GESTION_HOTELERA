import streamlit as st
from datetime import date, timedelta
import pandas as pd
#from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user
from app.core.db import POOL

st.set_page_config(page_title="Housekeeping", layout="wide")
u = current_user()
if not u: st.stop()

prop_id = u['property_id']
user_id = u['id']

# ---------- HELPERS DB (vía POOL) ----------
def _rows_to_dicts(cur_rows, cur_desc):
    if not cur_rows:
        return []
    cols = [d[0] for d in cur_desc]
    return [dict(zip(cols, r)) for r in cur_rows]

def fetch_all(sql: str, params=()):
    """Devuelve lista de dicts."""
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
            return _rows_to_dicts(rows, cur.description)

def fetch_one(sql: str, params=()):
    """Devuelve un dict o None."""
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in cur.description]
            return dict(zip(cols, row))

def fetch_df(sql: str, params=()):
    """DataFrame (útil si quieres mostrar tablas directo)."""
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)

def fetch_scalar(sql: str, params=()):
    """Un solo valor (columna 0) o None."""
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            row = cur.fetchone()
            return row[0] if row else None

def exec_sql(sql: str, params=()):
    """Ejecución con commit explícito."""
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
        conn.commit()

# -------- título/filtros --------
st.title("🧹 Housekeeping")
colf1, colf2, colf3 = st.columns([1,1,1])
with colf1:
    d = st.date_input("Fecha", value=date.today())
with colf2:
    priority_filter = st.multiselect("Prioridad", ["low","normal","high","urgent"], default=["normal","high","urgent"])
with colf3:
    status_filter = st.multiselect("Estado", ["pending","in_progress","done"], default=["pending","in_progress"])

# -------- KPIs --------
kpis = fetch_one("SELECT * FROM pms.fn_hk_kpis(%s,%s)", (prop_id, d))
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Tareas", int(kpis["tasks_total"]))
c2.metric("Pendientes", int(kpis["tasks_pending"]))
c3.metric("En progreso", int(kpis["tasks_in_progress"]))
c4.metric("Completadas", int(kpis["tasks_done"]))
c5.metric("Incidentes abiertos", int(kpis["incidents_open"]))
c6.metric("Críticos", int(kpis["incidents_critical"]))

st.divider()
tab_tasks, tab_incidents, tab_plan = st.tabs(["📝 Tareas", "🛠️ Incidentes", "📅 Planificador"])

# =================== TAREAS ===================
with tab_tasks:
    st.subheader("Tareas programadas")
    # lista filtrada
    rows = fetch_all("""
      SELECT id, room_code, scheduled_date, status, priority, assigned_to, started_at, completed_at, checklist, notes
      FROM pms.v_hk_tasks
      WHERE property_id=%s AND scheduled_date=%s
        AND priority = ANY(%s) AND status = ANY(%s)
      ORDER BY priority DESC, room_code
    """, (prop_id, d, priority_filter or ["low","normal","high","urgent"], status_filter or ["pending","in_progress","done"]))
    df = pd.DataFrame(rows)

    # Bulk-create desde rooms sucias
    with st.expander("➕ Crear tareas (bulk)"):
        dirty = fetch_all("""
          SELECT id::text as room_id, code as room_code
          FROM pms.rooms
          WHERE property_id=%s AND status IN ('dirty','cleaning')
          ORDER BY code
        """, (prop_id,))
        options = {r['room_code']: r['room_id'] for r in dirty}
        picks = st.multiselect("Habitaciones", list(options.keys()))
        colb1, colb2, colb3 = st.columns([1,1,2])
        with colb1:
            pr = st.selectbox("Prioridad", ["low","normal","high","urgent"], index=2)
        with colb2:
            assign_to = st.text_input("Asignar a (UUID opcional)", value="")
        with colb3:
            notes = st.text_input("Notas", value="")

        if st.button("Crear tareas para seleccionadas"):
            if picks:
                room_ids = [options[x] for x in picks]
                exec_sql("SELECT pms.sp_hk_create_tasks(%s,%s::uuid[],%s,%s,%s,%s,%s)",
                         (prop_id, room_ids, d, pr, assign_to or None, '[]', notes or None))
                st.success(f"Creado para {len(room_ids)} habitación(es).")
                st.rerun()
            else:
                st.info("Selecciona al menos una habitación.")

    # tabla editable simple
    if not df.empty:
        st.dataframe(df[['room_code','priority','status','assigned_to','started_at','completed_at','notes']],
                     use_container_width=True, hide_index=True)
    else:
        st.info("No hay tareas con esos filtros.")

    st.subheader("Acciones")
    colA, colB, colC = st.columns(3)
    task_id = colA.text_input("Task ID")
    assn    = colB.text_input("Asignar a (UUID)")
    if colB.button("Asignar"):
        if task_id and assn:
            exec_sql("SELECT pms.sp_hk_assign(%s,%s)", (task_id, assn))
            st.success("Asignado.")
            st.rerun()

    if colA.button("Iniciar tarea"):
        if task_id:
            exec_sql("SELECT pms.sp_hk_start(%s,%s)", (task_id, user_id))
            st.success("Tarea en progreso y habitación en 'cleaning'.")
            st.rerun()

    if colC.button("Completar tarea"):
        if task_id:
            new_state = fetch_one("SELECT pms.sp_hk_complete(%s,%s) AS new_state", (task_id, user_id))
            st.success(f"Tarea completada. Habitación ⇒ {new_state['new_state']}.")
            st.rerun()

# =================== INCIDENTES ===================
with tab_incidents:
    st.subheader("Incidentes abiertos")
    inc = fetch_all("""
      SELECT id, room_code, title, severity, status, reported_at, updated_at
      FROM pms.v_incidents_open
      WHERE property_id=%s
      ORDER BY severity DESC, reported_at
    """, (prop_id,))
    if inc:
        st.dataframe(pd.DataFrame(inc), use_container_width=True, hide_index=True)
    else:
        st.info("Sin incidentes abiertos.")

    st.subheader("Reportar incidente")
    c1,c2 = st.columns(2)
    # Rooms candidates
    rooms_all = fetch_all("SELECT id::text AS id, code FROM pms.rooms WHERE property_id=%s ORDER BY code", (prop_id,))
    rmap = {r['code']: r['id'] for r in rooms_all}
    room_code = c1.selectbox("Habitación", list(rmap.keys()) if rmap else [])
    severity  = c2.selectbox("Severidad", ["minor","major","critical"], index=0)
    title     = st.text_input("Título")
    desc      = st.text_area("Descripción", height=80)
    mark_ooo  = st.checkbox("Marcar fuera de servicio (OOO)")

    if st.button("Crear incidente"):
        if room_code and title:
            room_id = rmap[room_code]
            inc_id = fetch_one("SELECT pms.sp_incident_report(%s,%s,%s,%s,%s,%s,%s) AS id",
                               (prop_id, room_id, title, desc or None, severity, user_id, mark_ooo))
            st.success(f"Incidente creado: {inc_id['id']}")
            st.rerun()
        else:
            st.warning("Selecciona habitación y título.")

    st.subheader("Actualizar estado de incidente")
    c3,c4 = st.columns(2)
    inc_id = c3.text_input("Incident ID")
    new_status = c4.selectbox("Nuevo estado", ["open","in_progress","paused","resolved","canceled"], index=3)
    if st.button("Actualizar incidente"):
        if inc_id:
            exec_sql("SELECT pms.sp_incident_update_status(%s,%s::pms.incident_status)", (inc_id, new_status))
            st.success("Estado actualizado.")
            st.rerun()

# =================== PLANIFICADOR ===================
with tab_plan:
    st.subheader("Planificador por fecha")
    d2 = st.date_input("Fecha a planificar", value=date.today()+timedelta(days=1))
    # Sugerir rooms sucias o checkouts de ese día para programar:
    suggest = fetch_all("""
      SELECT DISTINCT r.id::text AS room_id, r.code AS room_code
      FROM pms.rooms r
      WHERE r.property_id=%s
        AND r.status IN ('dirty','cleaning','maintenance','out_of_order')
      ORDER BY r.code
    """, (prop_id,))
    opts = {x['room_code']: x['room_id'] for x in suggest}
    picked = st.multiselect("Selecciona habitaciones a programar", list(opts.keys()))
    pr2 = st.selectbox("Prioridad", ["low","normal","high","urgent"], index=1)
    notes2 = st.text_input("Notas (opcional)")
    if st.button("Programar tareas"):
        if picked:
            exec_sql("SELECT pms.sp_hk_create_tasks(%s,%s::uuid[],%s,%s,%s,%s,%s)",
                     (prop_id, [opts[c] for c in picked], d2, pr2, None, '[]', notes2 or None))
            st.success("Tareas programadas.")
            st.rerun()
        else:
            st.info("Selecciona al menos una habitación.")
