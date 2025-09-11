# app/ui/pages/facturacion_caja.py
import streamlit as st
from decimal import Decimal
from datetime import date
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user
<<<<<<< HEAD
from app.core.db import POOL
=======
from app.ui.layout import hide_native_multipage_nav, inject_sidebar_style, guard_login, render_sidebar_nav

hide_native_multipage_nav()   # oculta menú multipágina nativo (evita links antes del login)
inject_sidebar_style()        # estilos bonitos del sidebar/nav
u = guard_login()             # exige sesión (si no hay, detiene la página)
render_sidebar_nav()          # pinta los links con emojis en el sidebar
>>>>>>> d1211c539bdfdfa1792f6acac0f7a72d1438d3ff

u = current_user()
if not u:
    st.stop()


st.header("Facturación y Caja")

st.subheader("Cargos extra")
with st.form("charges_form"):
    res_id = st.text_input("Reserva a cobrar (UUID)")
    concept = st.text_input("Concepto", placeholder="Minibar / Cargo extra / ...")
    tax_code = st.text_input("Código de impuesto", value="IGV")
    amount = st.number_input("Monto", min_value=0.0, step=1.0)
    do_charge = st.form_submit_button("Registrar cargo")
if do_charge:
    try:
        with POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pms.sp_post_charge(%s, %s, %s::numeric, %s, %s);",
                            (res_id, concept, Decimal(str(amount)), tax_code, u['id']))
        st.success("Cargo registrado.")
    except Exception as e:
        st.error("No se pudo registrar el cargo.")
        st.exception(e)

st.subheader("Pagos")
with st.form("payments_form"):
    res_id_p = st.text_input("Reserva a pagar (UUID)")
    method = st.selectbox("Método", ["cash","card","transfer","other"])
    pay_amount = st.number_input("Monto pagado", min_value=0.0, step=1.0, key="pay")
    currency = st.text_input("Moneda", value="PEN")
    do_payment = st.form_submit_button("Registrar pago")
if do_payment:
    try:
        with POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pms.sp_register_payment(%s, %s, %s::numeric, %s, %s);",
                            (res_id_p, method, Decimal(str(pay_amount)), currency, u['id']))
        st.success("Pago registrado.")
    except Exception as e:
        st.error("No se pudo registrar el pago.")
        st.exception(e)

st.subheader("Checkout")
with st.form("checkout_form"):
    res_id_c = st.text_input("Reserva (UUID)")
    do_checkout = st.form_submit_button("Emitir factura (checkout)")
if do_checkout:
    try:
        with POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pms.sp_checkout(%s, %s::jsonb, %s);",
                            (res_id_c, "{}", u['id']))
                invoice_id = cur.fetchone()[0]
        st.success(f"Checkout OK. Invoice: {invoice_id}")
    except Exception as e:
        st.error("No se pudo realizar el checkout.")
        st.exception(e)

st.subheader("Cierre de caja (día actual)")
if st.button("Cerrar caja de hoy"):
    try:
        today = date.today().isoformat()
        with POOL.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pms.sp_close_cash(%s, %s::date, %s);",
                            (u['property_id'], today, u['id']))
                closure_id = cur.fetchone()[0]
        st.success(f"Cierre OK. ID: {closure_id}")
    except Exception as e:
        st.error("No se pudo cerrar caja.")
        st.exception(e)
