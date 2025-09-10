import streamlit as st
import pandas as pd
from app.repositories.pg_repo import PgRepo
from app.services.reservations import ReservationsService
from app.services.billing import BillingService
from app.auth.session import current_user


u = current_user()
if not u: st.stop()
repo = PgRepo()
repo_reservation = ReservationsService(repo)
repo_bill = BillingService(repo)

st.set_page_config(page_title="Check-in / Check-out", layout="wide")
st.header("Check-in / Check-out")

prop_id = u['property_id']
user_id = u['id']

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

# ---------- CHECK-IN ----------
with tab_in:
    dni = st.text_input("DNI del huésped", key="dni_in")
    if st.button("Buscar reserva pendiente/confirmada", use_container_width=False):
        # 1) Buscar reserva
        res_id = repo_reservation.search_reservation(
            prop_id,dni
        )
        if not res_id:
            st.warning("No se encontró reserva pendiente/confirmada para este DNI.")
        else:
            st.success(f"Reserva encontrada: {res_id}")

            # 2) Datos del huésped y cabecera
            cab = repo_reservation.search_guest_reservation(res_id)
            
            st.text_input(label='Huésped',value=cab['full_name'])
            st.text_input(label='DNI',value=cab['dni'])
            st.text_input(label='Estadia Fechas',value=f"{cab['start_date']} → {cab['end_date']}")
            st.text_input(label='Estado',value=cab['status'])

            # 3) Desglose por habitación
            items = repo_reservation.get_rooms_reservations(res_id)
            
            df = pd.DataFrame(items)
            st.subheader("Habitaciones reservadas")
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

                with st.form("checkin_payment_form",clear_on_submit=False):
                    method = st.selectbox("Método de pago", ["cash","card","yape","plin","transfer"])
                    do_checkin = st.form_submit_button("Registrar pago y Check-in", type="primary")
                if do_checkin:
                    out = repo_reservation.check_in(res_id,method,user_id)
                    if out:
                        st.success(f"Check-in OK. Factura {out['invoice_number'] or '—'}. Cobrado: {fin['currency']} {out['paid_amount']:.2f}")
                    else:
                        st.info("No se efectuó cobro (ya estaba check-in o sin saldo).")
                    
            
# ---------- CHECK-OUT ----------
with tab_out:
    dni2 = st.text_input("DNI del huésped", key="dni_out")
    if st.button("Buscar reserva con check-in", use_container_width=False):
        res = _fetch_one(
            "SELECT pms.fn_find_checkedin_reservation_by_dni(%s,%s) AS res_id",
            (prop_id, dni2)
        )
        if not res or not res.get('res_id'):
            st.warning("No se encontró reserva en estado CHECKED_IN para este DNI.")
        else:
            res_id = res['res_id']
            st.success(f"Reserva encontrada: {res_id}")

            cab = _fetch_one("""
                SELECT r.id::text AS reservation_id, g.full_name, g.dni,
                       r.start_date, r.end_date, r.status
                FROM pms.reservations r
                JOIN pms.guests g ON g.id = r.guest_id
                WHERE r.id=%s
            """, (res_id,))
            st.write(f"**Huésped:** {cab['full_name']}  |  **DNI:** {cab['dni']}")
            st.write(f"**Estadía:** {cab['start_date']} → {cab['end_date']}  |  **Estado:** {cab['status']}")

            # Desglose y saldos
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
                method2 = st.selectbox("Método de pago", ["cash","card","yape","plin","transfer"], key="m2")

                if st.button("Cobrar saldo y Check-out", type="primary"):
                    out2 = _fetch_one("SELECT * FROM pms.sp_check_out(%s,%s,%s)", (res_id, method2, user_id))
                    if out2:
                        st.success(f"Check-out OK. Factura final: {out2['invoice_number'] or '—'}. Cobrado: {fin2['currency']} {out2['paid_amount']:.2f}")
                    else:
                        st.success("Check-out OK sin cobro adicional.")



#res_id = st.text_input("Reservation ID")
#col1, col2, col3 = st.columns(3)
#with col1:
#    if st.button("Registrar pago (efectivo) 100.00") and res_id:
#        bill.register_payment(res_id, "cash", 100.00, "PEN", u['id'])
#        st.toast("Pago registrado")
#with col2:
#    if st.button("Postear cargo Minibar 30.00") and res_id:
#        bill.post_charge(res_id, "Minibar", 30.00, "IGV", u['id'])
#        st.toast("Cargo posteado")
#with col3:
#    if st.button("Checkout y emitir factura") and res_id:
#        inv = bill.checkout(res_id, {"notes":"checkout"}, u['id'])
#        st.success(f"Factura emitida: {inv}")