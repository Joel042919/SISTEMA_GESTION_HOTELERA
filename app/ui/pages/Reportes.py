import streamlit as st
from datetime import date, timedelta
import pandas as pd
import psycopg
from app.core.db import POOL
from app.auth.session import current_user

st.set_page_config(page_title="Reportes y Exportación", layout="wide")
u = current_user(); 
if not u: st.stop()

prop_id = u['property_id']

st.header("Reportes y Exportación")


import streamlit as st

col1, col2 = st.columns([2,2])  # centro con proporción 3
with col1:
    st.markdown("### 🎯 Objetivos de negocio")
    st.markdown("""
    - **Maximizar ocupación** manteniendo ADR saludable.  
    - **Incrementar RevPAR** (ingreso por habitación disponible).  
    - Controlar **cancela/no-show** y mejorar **anticipación de compra**.  
    - Reducir **tiempos y pendientes** en housekeeping; minimizar **out_of_order**.  
    - Asegurar **flujo de caja** (pagos) y **facturación diaria**.  
    """)
with col2:
    st.markdown("### 📈 Métricas e indicadores clave")
    st.markdown("""
    - **Rooms total** (capacidad), **rooms ocupadas** por día.  
    - **Ocupación %** = ocupadas / total.  
    - **ADR (Average Daily Rate):** ingreso de habitaciones / habitaciones ocupadas.  
    - **RevPAR:** ingreso de habitaciones / habitaciones disponibles.  
    - **Ingresos habitaciones**, **Ingresos extras (charges)**, **Pagos**, **Facturado**.  
    - **Check-ins / Check-outs** por día.  
    - **Lead Time:** días entre `created_at` y `start_date`.  
    - **Cancelaciones, No-Show** por rango.  
    - **HK pendientes, Out of order** (capacidad fuera de servicio).  
    - **Por tipo de habitación:** ocupación y ADR.  
    """)



# --------- Filtros ---------
colf1, colf2, colf3 = st.columns([1,1,1])
with colf1:
    start = st.date_input("Inicio", value=date.today().replace(day=1))
with colf2:
    end = st.date_input("Fin", value=date.today(), min_value=start)
with colf3:
    gran = st.selectbox("Granularidad", ["Diaria","Mensual"], index=0)

# --------- Helpers DB ---------
def fetch_df(sql: str, params=()):
    with POOL.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = cur.fetchall()
    return pd.DataFrame(rows, columns=cols)

# --------- KPIs diarios (tabla fuente) ---------
df = fetch_df("""
    SELECT * FROM pms.fn_daily_kpis_between(%s,%s,%s)
    ORDER BY d
""", (prop_id, start, end))

if df.empty:
    st.info("No hay datos en el rango seleccionado.")
    st.stop()

# --------- KPIs Resumen ---------
last = df.iloc[-1]
c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Ocupación hoy (%)", f"{last['occupancy']:.2f}")
c2.metric("ADR", f"{last['adr']:.2f}")
c3.metric("RevPAR", f"{last['revpar']:.2f}")
c4.metric("Ingresos hab. hoy", f"{last['room_revenue']:.2f}")
c5.metric("Ingresos extras hoy", f"{last['extra_revenue']:.2f}")
c6.metric("Check-ins / Check-outs", f"{int(last['checkins'])} / {int(last['checkouts'])}")

# --------- Gráficos (serie temporal) ---------
st.subheader("Tendencias")
g1, g2 = st.columns(2)
with g1:
    st.line_chart(df.set_index('d')[['occupancy']], height=260)
    st.caption("Ocupación (%)")

with g2:
    st.line_chart(df.set_index('d')[['adr','revpar']], height=260)
    st.caption("ADR y RevPAR")

g3, g4 = st.columns(2)
with g3:
    st.area_chart(df.set_index('d')[['room_revenue','extra_revenue']], height=260)
    st.caption("Ingresos por día (habitaciones vs extras)")

with g4:
    st.bar_chart(df.set_index('d')[['payments','invoices']], height=260)
    st.caption("Pagos y Facturación diarios")

# --------- Operaciones ---------
st.subheader("Operaciones y calidad")
ops1, ops2, ops3 = st.columns(3)
# HK pendientes hoy
hk = fetch_df("SELECT pms.fn_housekeeping_pending(%s,%s) AS hk_pending", (prop_id, end)).iloc[0]['hk_pending']
# OOO ahora
ooo = fetch_df("SELECT pms.fn_out_of_order_now(%s) AS out_of_order", (prop_id,)).iloc[0]['out_of_order']
# Lead time y cancel rate en rango
lead = fetch_df("SELECT pms.fn_lead_time_avg(%s,%s,%s) AS lead_avg", (prop_id, start, end)).iloc[0]['lead_avg']
cr = fetch_df("SELECT * FROM pms.fn_cancel_rate(%s,%s,%s)", (prop_id, start, end)).iloc[0]

ops1.metric("HK pendientes (hoy)", int(hk))
ops2.metric("Rooms Out-of-Order (ahora)", int(ooo))
ops3.metric("Lead time prom. (días)", float(lead or 0))

st.caption(f"Cancelaciones: {int(cr['cancel_count'])}  |  No-show: {int(cr['no_show_count'])}  |  "
           f"Total reservas: {int(cr['total'])}  |  Cancel rate: {float(cr['cancel_rate'] or 0):.2f}%  |  "
           f"No-show rate: {float(cr['no_show_rate'] or 0):.2f}%")

# --------- Agregación mensual ---------
if gran == "Mensual":
    dfm = df.copy()
    dfm['month'] = pd.to_datetime(dfm['d']).dt.to_period('M').astype(str)
    agg = dfm.groupby('month', as_index=False).agg(
        rooms_total=('rooms_total','max'),
        occ_rooms=('rooms_occupied','sum'),
        occ_pct=('occupancy','mean'),
        adr=('adr','mean'),
        revpar=('revpar','mean'),
        room_revenue=('room_revenue','sum'),
        extra_revenue=('extra_revenue','sum'),
        payments=('payments','sum'),
        invoices=('invoices','sum'),
        checkins=('checkins','sum'),
        checkouts=('checkouts','sum')
    )
    st.subheader("Resumen mensual")
    st.dataframe(agg, use_container_width=True, hide_index=True)
    st.bar_chart(agg.set_index('month')[['room_revenue','extra_revenue']], height=280)

# --------- Exportación ---------
st.subheader("Exportación")
csv = df.to_csv(index=False).encode('utf-8')
st.download_button("Descargar CSV (diario)", data=csv, file_name="kpis_diarios.csv", mime="text/csv")
