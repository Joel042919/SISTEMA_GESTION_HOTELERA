import streamlit as st
from datetime import date, timedelta
from app.services.reservations import ReservationsService
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user


u = current_user()
if not u:
    st.stop()
svc = ReservationsService(PgRepo())


st.header("Reservas")
with st.form("quote_form"):
    # UUID del room_type Standard obtenido de la base de datos
    room_type_id = st.selectbox(
        "Tipo de Habitación", 
        options=["a47f584d-8ddb-494d-adbb-d17ef1212632"],
        format_func=lambda x: "Standard" if x == "a47f584d-8ddb-494d-adbb-d17ef1212632" else x
    )
    start = st.date_input("Inicio", value=date.today())
    end = st.date_input("Fin", value=date.today()+timedelta(days=1))
    promo = st.text_input("Código promo", placeholder="Opcional (ej: BIENVENIDA)")
    guests = st.number_input("Huéspedes", 1, 6, 1)
    do_quote = st.form_submit_button("Cotizar")


if do_quote and room_type_id:
    q = svc.quote(u['property_id'], room_type_id, start.isoformat(), end.isoformat(), guests, promo or None)
    if q:
        st.info(f"Noches: {q['nights']} · Total: {q['grand_total']}")
        st.json(q['nightly'])


st.subheader("Crear reserva")
with st.form("create_form"):
    guest_id = st.text_input("Guest ID", placeholder="UUID de huésped (crea en Admin/Clientes)")
    room_type_id2 = st.selectbox(
        "Tipo de Habitación", 
        options=["a47f584d-8ddb-494d-adbb-d17ef1212632"],
        format_func=lambda x: "Standard" if x == "a47f584d-8ddb-494d-adbb-d17ef1212632" else x,
        key="room_type_2"
    )
    start2 = st.date_input("Inicio", value=date.today(), key="s2")
    end2 = st.date_input("Fin", value=date.today()+timedelta(days=1), key="e2")
    promo2 = st.text_input("Código promo", placeholder="Opcional (ej: BIENVENIDA)", key="promo2")
    submit = st.form_submit_button("Crear y Confirmar")


if submit and guest_id and room_type_id2:
    dates = [ (start2 + timedelta(days=i)).isoformat() for i in range((end2-start2).days) ]
    rid = svc.create(u['property_id'], guest_id, room_type_id2, dates, promo2 or None, u['id'])
    st.success(f"Reserva creada: {rid}")