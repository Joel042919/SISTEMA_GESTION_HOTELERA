import streamlit as st
from app.repositories.pg_repo import PgRepo
from app.services.billing import BillingService
from app.auth.session import current_user


u = current_user()
if not u: st.stop()
repo = PgRepo()
bill = BillingService(repo)


st.header("Check-in / Check-out")
res_id = st.text_input("Reservation ID")
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("Registrar pago (efectivo) 100.00") and res_id:
        bill.register_payment(res_id, "cash", 100.00, "PEN", u['id'])
        st.toast("Pago registrado")
with col2:
    if st.button("Postear cargo Minibar 30.00") and res_id:
        bill.post_charge(res_id, "Minibar", 30.00, "IGV", u['id'])
        st.toast("Cargo posteado")
with col3:
    if st.button("Checkout y emitir factura") and res_id:
        inv = bill.checkout(res_id, {"notes":"checkout"}, u['id'])
        st.success(f"Factura emitida: {inv}")