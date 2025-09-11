# app/ui/pages/dashboard.py
import os
import pandas as pd
import altair as alt
import streamlit as st
from datetime import date, timedelta

# Infra de tu proyecto
from app.core.db import POOL
try:
    # Si tienes helper current_user en tu proyecto
    from app.auth.session import current_user, SESSION_USER_KEY
    _get_user = lambda: current_user()
except Exception:
    # Fallback por si no existe
    SESSION_USER_KEY = "user"
    _get_user = lambda: st.session_state.get(SESSION_USER_KEY)

# ----------------------------
# Configuración visual general
# ----------------------------
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

# Paleta rápida (chips/etiquetas)
PILL_STYLES = {
    "success": ("#ECFDF5", "#065F46"),
    "info":    ("#EFF6FF", "#1D4ED8"),
    "warn":    ("#FFFBEB", "#B45309"),
    "danger":  ("#FEF2F2", "#991B1B"),
    "neutral": ("#F3F4F6", "#374151"),
}

def pill(text: str, kind: str = "neutral"):
    bg, fg = PILL_STYLES.get(kind, PILL_STYLES["neutral"])
    st.markdown(
        f"<span style='padding:.25rem .5rem;border-radius:9999px;background:{bg};"
        f"color:{fg};font-weight:600;font-size:.75rem'>{text}</span>",
        unsafe_allow_html=True
    )

# --------------
# Usuario actual
# --------------
u = _get_user()
if not u:
    st.error("Debes iniciar sesión para ver el dashboard.")
    st.stop()

PROPERTY_ID = u.get("property_id", "00000000-0000-0000-0000-000000000000")

# ------------------
# Carga de datos BD
# ------------------
@st.cache_data(ttl=60)
def load_kpis(property_id: str, d: date):
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM pms.fn_daily_kpis(%s::uuid, %s::date);", (property_id, d))
            row = cur.fetchone()
            cols = [c.name for c in cur.description]
    return dict(zip(cols, row)) if row else {}

@st.cache_data(ttl=60)
def load_series(property_id: str, start_d: date, end_d: date):
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT d, rooms_total, rooms_occupied, occupancy, adr, revpar,
                       room_revenue, extra_revenue, payments, invoices, checkins, checkouts
                FROM pms.fn_daily_kpis_between(%s::uuid, %s::date, %s::date);
            """, (property_id, start_d, end_d))
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        df["d"] = pd.to_datetime(df["d"]).dt.date
    return df

@st.cache_data(ttl=60)
def load_hk(property_id: str, d: date):
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            # Resumen Housekeeping
            cur.execute("SELECT * FROM pms.fn_hk_kpis(%s::uuid, %s::date);", (property_id, d))
            hk_row = cur.fetchone()
            hk_cols = [c.name for c in cur.description]
            hk = dict(zip(hk_cols, hk_row)) if hk_row else {}

            # Tareas del día
            cur.execute("""
                SELECT id::text, room_code, status::text, priority::text, scheduled_date,
                       started_at, completed_at, COALESCE(notes,'') AS notes
                FROM pms.v_hk_tasks
                WHERE property_id = %s::uuid AND scheduled_date = %s::date
                ORDER BY priority DESC, status;
            """, (property_id, d))
            t_rows = cur.fetchall()
            t_cols = [c.name for c in cur.description]
            tasks = pd.DataFrame(t_rows, columns=t_cols)

            # Incidentes abiertos
            cur.execute("""
                SELECT id::text, room_code, title, severity::text, status::text,
                       reported_at, updated_at
                FROM pms.v_incidents_open
                WHERE property_id = %s::uuid
                ORDER BY severity DESC, updated_at DESC;
            """, (property_id,))
            i_rows = cur.fetchall()
            i_cols = [c.name for c in cur.description]
            incidents = pd.DataFrame(i_rows, columns=i_cols)

    return hk, tasks, incidents

@st.cache_data(ttl=60)
def load_checkins(property_id: str, d: date):
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT r.id::text AS reservation_id,
                       g.full_name   AS guest,
                       rm.code       AS room_code
                FROM pms.reservations r
                JOIN pms.guests g ON g.id = r.guest_id
                LEFT JOIN pms.reservation_rooms rr ON rr.reservation_id = r.id
                LEFT JOIN pms.rooms rm ON rm.id = rr.room_id
                WHERE r.property_id=%s::uuid AND r.start_date=%s::date
                ORDER BY guest;
            """, (property_id, d))
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
    return pd.DataFrame(rows, columns=cols)

# -------------------
# Obtener los datos
# -------------------
today = date.today()
week_start = today - timedelta(days=6)

kpis = load_kpis(PROPERTY_ID, today)
series = load_series(PROPERTY_ID, week_start, today)
hk, hk_tasks, incidents = load_hk(PROPERTY_ID, today)
df_ci = load_checkins(PROPERTY_ID, today)

# -------------
# Encabezado UI
# -------------
st.markdown(
    f"""
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:.25rem">
      <div>
        <h1 style="margin:0">Dashboard</h1>
        <div style="color:#6B7280;font-size:.9rem">Propiedad activa · {today:%d %b %Y}</div>
      </div>
      <div>
    """,
    unsafe_allow_html=True,
)
pill("Online", "success")

st.write("")

# -------------------
# KPIs principales
# -------------------
def g(key, default=0.0):
    v = kpis.get(key, default)
    try:
        return float(v if v is not None else default)
    except Exception:
        return default

rooms_total     = int(g("rooms_total", 0))
rooms_occupied  = int(g("rooms_occupied", 0))
occupancy       = g("occupancy", 0.0)
adr             = g("adr", 0.0)
revpar          = g("revpar", 0.0)
room_revenue    = g("room_revenue", 0.0)
extra_revenue   = g("extra_revenue", 0.0)
payments        = g("payments", 0.0)
invoices        = g("invoices", 0.0)
checkins        = int(g("checkins", 0))
checkouts       = int(g("checkouts", 0))

ingresos_hoy = room_revenue + extra_revenue

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.metric("Ocupación", f"{occupancy:.1f}%")
with k2:
    st.metric("ADR", f"S/ {adr:,.2f}")
with k3:
    st.metric("RevPAR", f"S/ {revpar:,.2f}")
with k4:
    st.metric("Ingresos Hoy", f"S/ {ingresos_hoy:,.2f}")

k5, k6, k7, k8 = st.columns(4)
with k5:
    st.metric("Hab. ocupadas", f"{rooms_occupied}/{rooms_total}")
with k6:
    st.metric("Pagos del día", f"S/ {payments:,.2f}")
with k7:
    st.metric("Facturas del día", f"S/ {invoices:,.2f}")
with k8:
    st.metric("Check-ins / Check-outs", f"{checkins} / {checkouts}")

st.divider()

# -----------------------------------
# Gráfico: Ocupación (últimos 7 días)
# -----------------------------------
left, right = st.columns([2, 1])

with left:
    st.subheader("Ocupación • Últimos 7 días")
    if not series.empty:
        chart = (
            alt.Chart(series)
            .mark_bar()
            .encode(
                x=alt.X("d:T", title="Fecha"),
                y=alt.Y("occupancy:Q", title="Ocupación (%)"),
                tooltip=["d:T", alt.Tooltip("occupancy:Q", format=".1f")]
            )
            .properties(height=260)
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("Sin datos suficientes para el rango.")

with right:
    st.subheader("Housekeeping • Hoy")
    cols = st.columns(2)
    t_total = int(hk.get("tasks_total", 0) or 0)
    t_pend  = int(hk.get("tasks_pending", 0) or 0)
    t_prog  = int(hk.get("tasks_in_progress", 0) or 0)
    t_done  = int(hk.get("tasks_done", 0) or 0)
    inc_open = int(hk.get("incidents_open", 0) or 0)
    inc_crit = int(hk.get("incidents_critical", 0) or 0)

    with cols[0]: st.metric("Tareas", t_total)
    with cols[1]: st.metric("Pendientes", t_pend)
    with cols[0]: st.metric("En progreso", t_prog)
    with cols[1]: st.metric("Completadas", t_done)
    st.write("")
    pill(f"Incidentes abiertos: {inc_open}", "warn" if inc_open else "success")
    st.write("")
    pill(f"Críticos: {inc_crit}", "danger" if inc_crit else "success")

st.divider()

# -----------------------------------------
# Listas: Check-ins / Tareas HK / Incidentes
# -----------------------------------------
cA, cB, cC = st.columns(3)

with cA:
    st.subheader("Check-ins de hoy")
    if df_ci.empty:
        st.caption("No hay check-ins programados para hoy.")
    else:
        show_ci = df_ci.rename(columns={
            "reservation_id": "Reserva",
            "guest": "Huésped",
            "room_code": "Hab."
        })
        st.dataframe(show_ci, use_container_width=True, hide_index=True)

with cB:
    st.subheader("Tareas HK (hoy)")
    if hk_tasks.empty:
        st.caption("No hay tareas programadas.")
    else:
        show_t = hk_tasks.rename(columns={
            "room_code":"Hab.",
            "status":"Estado",
            "priority":"Prioridad",
            "notes":"Notas",
            "started_at":"Inicio",
            "completed_at":"Fin"
        })[["Hab.","Estado","Prioridad","Notas","Inicio","Fin"]]
        st.dataframe(show_t, use_container_width=True, hide_index=True)

with cC:
    st.subheader("Incidentes abiertos")
    if incidents.empty:
        st.caption("No hay incidentes abiertos.")
    else:
        show_i = incidents.rename(columns={
            "room_code":"Hab.",
            "title":"Título",
            "severity":"Severidad",
            "status":"Estado",
            "updated_at":"Actualizado"
        })[["Hab.","Título","Severidad","Estado","Actualizado"]]
        st.dataframe(show_i, use_container_width=True, hide_index=True)

st.write("")
st.caption("Datos en tiempo real desde PostgreSQL · Esquema PMS")
