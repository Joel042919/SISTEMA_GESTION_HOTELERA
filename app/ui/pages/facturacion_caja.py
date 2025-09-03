import streamlit as st
from datetime import date
from app.core.db import POOL
from app.repositories.pg_repo import PgRepo
from app.services.billing import BillingService
from app.auth.session import current_user


u = current_user();
if not u: st.stop()
svc = BillingService(PgRepo())


st.header("Facturación y Caja")
res = st.text_input("Reservation ID para cobrar")
col1, col2 = st.columns(2)
with col1:
    concept = st.text_input("Concepto", value="Room Night")
    amount = st.number_input("Monto", min_value=0.0, value=150.0)
    if st.button("Postear cargo") and res:
        svc.post_charge(res, concept, amount, "IGV", u['id'])
        st.success("Cargo posteado")
with col2:
    method = st.selectbox("Método", ["cash","card","transfer"])
    pay = st.number_input("Pago", min_value=0.0, value=150.0)
    if st.button("Registrar pago") and res:
        svc.register_payment(res, method, pay, "PEN", u['id'])
        st.success("Pago registrado")


st.divider()
if st.button("Cerrar caja hoy"):
    from app.repositories.pg_repo import PgRepo
    repo = PgRepo()
    # Llamar directo con SQL: SELECT sp_close_cash(...)
    import psycopg
    with psycopg.connect(POOL.conninfo) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM pms.sp_close_cash(%s,%s,%s)", (u['property_id'], date.today(), u['id']))
        cid = cur.fetchone()[0]
        conn.commit()
        st.success(f"Cierre realizado: {cid}")