import streamlit as st
import pandas as pd
from app.repositories.pg_repo import PgRepo
from app.services.reservations import ReservationsService
from app.services.billing import BillingService
from app.auth.session import current_user

# ---- SIEMPRE ARRIBA ----
st.set_page_config(page_title="Check-in / Check-out", layout="wide")

u = current_user()
if not u: st.stop()

repo = PgRepo()
repo_reservation = ReservationsService(repo)
repo_bill = BillingService(repo)

st.header("Check-in / Check-out")

prop_id = u['property_id']
user_id = u['id']

# ======= SESSION STATE (persistencia) =======
st.session_state.setdefault("checkin_res_id", None)
st.session_state.setdefault("checkout_res_id", None)

tab_in, tab_out = st.tabs(["🟢 Check-in", "🔵 Check-out"])

# ---------- helpers ----------
def _fetch_one(sql, params=()):
    with PgRepo() as db:
        rows = db.query(sql, params)
        return dict(rows[0]) if rows else None

def _fetch_all(sql, params=()):
    with PgRepo() as db:
        rows = db.query(sql, params)
        return [dict(r) for r in rows] if rows else []

def render_checkin_detail(res_id: str):
    """Dibuja toda la sección de detalle del check-in para un res_id dado."""
    # 2) Cabecera
    cab = repo_reservation.search_guest_reservation(res_id)
    st.text_input(label='Huésped', value=cab['full_name'], disabled=True)
    st.text_input(label='DNI', value=cab['dni'], disabled=True)
    st.text_input(label='Estadía', value=f"{cab['start_date']} → {cab['end_date']}", disabled=True)
    st.text_input(label='Estado', value=cab['status'], disabled=True)

    # 3) Desglose por habitación
    items = repo_reservation.get_rooms_reservations(res_id)
    st.subheader("Habitaciones reservadas")
    df = pd.DataFrame(items)
    if not df.empty:
        df['price_fmt'] = df.apply(lambda r: f"{r['currency']} {r['price']:.2f}", axis=1)
        st.dataframe(df[['room_code','room_type','price_fmt']], hide_index=True, use_container_width=True)
    else:
        st.info("No hay habitaciones vinculadas a esta reserva.")

    # 4) Saldos
    fin = repo_reservation.get_reservation_financials(res_id)
    if fin:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total reserva", f"{fin['currency']} {fin['base_total']:.2f}")
        c2.metric("Cargos", f"{fin['currency']} {fin['charges_total']:.2f}")
        c3.metric("Pagos", f"{fin['currency']} {fin['payments_total']:.2f}")
        c4.metric("Pendiente", f"{fin['currency']} {fin['balance_due']:.2f}")

        # Usa un FORM para que sólo el submit ejecute la acción (aunque el select cause rerun, el estado persiste)
        with st.form("checkin_payment_form", clear_on_submit=False):
            method = st.selectbox("Método de pago", ["cash","card","yape","plin","transfer"], key="checkin_method")
            do_checkin = st.form_submit_button("Registrar pago y Check-in", type="primary")
        if do_checkin:
            out = repo_reservation.check_in(res_id, method, user_id)
            if out:
                st.success(f"Check-in OK. Factura {out['invoice_number'] or '—'}. "
                           f"Cobrado: {fin['currency']} {out['paid_amount']:.2f}")
            else:
                st.info("No se efectuó cobro (ya estaba check-in o sin saldo).")

# ---------- CHECK-IN ----------
with tab_in:
    c1, c2 = st.columns([2,1])
    with c1:
        dni = st.text_input("DNI del huésped", key="dni_in")
    with c2:
        if st.button("Buscar reserva pendiente/confirmada"):
            res_id = repo_reservation.search_reservation(prop_id, dni)
            if not res_id:
                st.session_state["checkin_res_id"] = None
                st.warning("No se encontró reserva pendiente/confirmada para este DNI.")
            else:
                st.session_state["checkin_res_id"] = res_id
                st.success(f"Reserva encontrada: {res_id}")

    # Si ya hay una reserva en sesión, vuelve a pintarla aunque haya rerun por widgets
    if st.session_state["checkin_res_id"]:
        render_checkin_detail(st.session_state["checkin_res_id"])

# ---------- CHECK-OUT ----------
def render_checkout_detail(res_id: str):
    cab = _fetch_one("""
        SELECT r.id::text AS reservation_id, g.full_name, g.dni,
               r.start_date, r.end_date, r.status
        FROM pms.reservations r
        JOIN pms.guests g ON g.id = r.guest_id
        WHERE r.id=%s
    """, (res_id,))
    st.write(f"**Huésped:** {cab['full_name']}  |  **DNI:** {cab['dni']}")
    st.write(f"**Estadía:** {cab['start_date']} → {cab['end_date']}  |  **Estado:** {cab['status']}")

    items2 = _fetch_all("""
        SELECT room_code, room_type, subtotal_room AS price, currency
        FROM pms.fn_reservation_room_breakdown(%s)
        ORDER BY room_code
    """, (res_id,))
    if items2:
        df2 = pd.DataFrame(items2)
        df2['price_fmt'] = df2.apply(lambda r: f"{r['currency']} {r['price']:.2f}", axis=1)
        st.dataframe(df2[['room_code','room_type','price_fmt']], hide_index=True, use_container_width=True)

    fin2 = _fetch_one("SELECT * FROM pms.fn_reservation_financials(%s)", (res_id,))
    if fin2:
        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Total reserva", f"{fin2['currency']} {fin2['base_total']:.2f}")
        c2.metric("Cargos", f"{fin2['currency']} {fin2['charges_total']:.2f}")
        c3.metric("Pagos", f"{fin2['currency']} {fin2['payments_total']:.2f}")
        c4.metric("Pendiente", f"{fin2['currency']} {fin2['balance_due']:.2f}")

        if fin2['balance_due'] > 0:
            st.warning("Aún hay saldo pendiente (cargos o diferencias). Se cobrará ahora en el check-out.")

        with st.form("checkout_payment_form", clear_on_submit=False):
            method2 = st.selectbox("Método de pago", ["cash","card","yape","plin","transfer"], key="checkout_method")
            do_checkout = st.form_submit_button("Cobrar saldo y Check-out", type="primary")
        if do_checkout:
            out2 = _fetch_one("SELECT * FROM pms.sp_check_out(%s,%s,%s)", (res_id, method2, user_id))
            if out2:
                st.success(f"Check-out OK. Factura final: {out2['invoice_number'] or '—'}. "
                           f"Cobrado: {fin2['currency']} {out2['paid_amount']:.2f}")
            else:
                st.success("Check-out OK sin cobro adicional.")

with tab_out:
    c1, c2 = st.columns([2,1])
    with c1:
        dni2 = st.text_input("DNI del huésped", key="dni_out")
    with c2:
        if st.button("Buscar reserva con check-in"):
            res = _fetch_one("SELECT pms.fn_find_checkedin_reservation_by_dni(%s,%s) AS res_id", (prop_id, dni2))
            if not res or not res.get('res_id'):
                st.session_state["checkout_res_id"] = None
                st.warning("No se encontró reserva en estado CHECKED_IN para este DNI.")
            else:
                st.session_state["checkout_res_id"] = res['res_id']
                st.success(f"Reserva encontrada: {res['res_id']}")

    if st.session_state["checkout_res_id"]:
        render_checkout_detail(st.session_state["checkout_res_id"])
