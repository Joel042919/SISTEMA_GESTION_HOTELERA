import streamlit as st
from datetime import date, timedelta
from typing import Dict
from app.services.reservations import ReservationsService
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user
from app.services.rooms import RoomsService

u = current_user()
if not u:
    st.stop()
    
repo = PgRepo()
svc = ReservationsService(repo)
svc_rooms = RoomsService(repo)

st.header("Reservas")

@st.cache_data(show_spinner=False, ttl=300)
def _get_room_type_options(property_id:str)->Dict[str,str]:
    """
    Devuelve {label:id} para el selectBox
    """
    rows = svc_rooms.list_room_types(property_id)
    return {name:rid for(rid, name) in rows}

rt_options = _get_room_type_options(u['property_id'])

if not rt_options:
    st.info("No hay tipos de habitación para esta propiedad.")
    st.stop()

with st.form("quote_form"):
    label = st.selectbox("Room Types",list(rt_options.keys()))
    room_type_id = rt_options[label]
    start = st.date_input("Inicio", value=date.today())
    end = st.date_input("Fin", value=date.today()+timedelta(days=1))
    promo = st.text_input("Código promo", placeholder="Opcional")
    guests = st.number_input("Huéspedes", 1, 6, 1)
    do_quote = st.form_submit_button("Cotizar")


if do_quote:
    try:
        days = (end-start).days
        if days<=0:
            st.error("Rango de fechas inválidas")
        else:
            q = svc.quote(u['property_id'], room_type_id, start.isoformat(), end.isoformat(), int(guests), promo or None)
            if q:
                st.info(f"Noches: {q['nights']} · Total: {q['grand_total']}")
                st.json(q['nightly'])
            else:
                st.warning("No se obtuvo cotizacion")
    except Exception as e:
        st.error("No hay tarifa activa para ese tipo de habitación")
        st.exception(e)


st.subheader("Crear reserva")
with st.form("create_form"):
    label2 = st.selectbox("Tipo de habitación", list(rt_options.keys()), key="rt2")
    room_type_id2 = rt_options[label2]
    guest_id = st.text_input("Guest ID", placeholder="UUID de huésped (crea en Admin/Clientes)")
    start2 = st.date_input("Inicio R", value=date.today(), key="s2")
    end2 = st.date_input("Fin R", value=date.today()+timedelta(days=1), key="e2")
    promo2 = st.text_input("Código promo R", placeholder="Opcional")
    submit = st.form_submit_button("Crear y Confirmar")


if submit and guest_id and room_type_id2:
    try:
        days = (end2-start2).days
        if days<=0:
            st.error("Rango de fechas inválido")
        else:
            dates = [ (start2 + timedelta(days=i)).isoformat() for i in range((end2-start2).days) ]
            rid = svc.create(u['property_id'], guest_id, room_type_id2, dates, promo2 or None, u['id'])
            st.success(f"Reserva creada: {rid}")
    except Exception as e:
        st.error("No se pudo crear la reserva. Revisa Room Type, Guest y rango de fechas.")
        st.exception(e)  # 👈 opcional
    