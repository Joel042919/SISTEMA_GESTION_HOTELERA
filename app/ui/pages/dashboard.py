import streamlit as st
from datetime import date
from app.services.reports import ReportsService
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user


st.set_page_config(page_title="Dashboard", layout='wide')


u = current_user()
if not u:
    st.warning("Inicia sesión desde la pantalla principal.")
    st.stop()


svc = ReportsService(PgRepo())
report = svc.daily(u['property_id'], date.today().isoformat())


k1, k2, k3, k4 = st.columns(4)
k1.metric("Ocupación", f"{report['occupancy_pct']}%", help="% habitaciones ocupadas hoy")
k2.metric("Ingresos del día", f"{report['revenue']} PEN")
k3.metric("ADR", f"{report['adr']}")
k4.metric("RevPAR", f"{report['revpar']}")


st.success("KPIs básicos listos. Navega con los enlaces de la izquierda.")