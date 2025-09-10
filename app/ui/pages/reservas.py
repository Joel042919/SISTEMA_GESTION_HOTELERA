import streamlit as st
from datetime import date, timedelta
from typing import Dict
from app.services.reservations import ReservationsService
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user
from app.services.rooms import RoomsService
from app.services.guestsHotel import GuestsHotelService
import pandas as pd
import time
from app.ui.layout import hide_native_multipage_nav, inject_sidebar_style, guard_login, render_sidebar_nav

hide_native_multipage_nav()   # oculta menú multipágina nativo (evita links antes del login)
inject_sidebar_style()        # estilos bonitos del sidebar/nav
u = guard_login()             # exige sesión (si no hay, detiene la página)
render_sidebar_nav()          # pinta los links con emojis en el sidebar
u = current_user()
if not u:
    st.stop()
    
repo = PgRepo()
svc = ReservationsService(repo)
svc_rooms = RoomsService(repo)
svc_guest = GuestsHotelService(repo)

#------------------------
# UTILS
#-----------------------
def verificar_rango_fecha(startDate:str,endDate:str):
    return (endDate-startDate).days <=0

def set_guest(guest_id:str,full_name:str,dni:str):
    st.session_state["guest_id"] = guest_id
    st.session_state["guest_name"] = full_name
    st.session_state["guest_dni"] = dni


if "guest_id" not in st.session_state:
    st.session_state["guest_id"] = ""
if "guest_name" not in st.session_state:
    st.session_state["guest_name"] = ""

st.session_state.setdefault("open_dni_dialog", False)
st.session_state.setdefault("open_new_guest_dialog", False)

def open_dni_dialog():
    st.session_state["open_dni_dialog"] = True

def close_dni_dialog():
    st.session_state["open_dni_dialog"] = False

def open_new_guest_dialog():
    st.session_state["open_new_guest_dialog"] = True

def close_new_guest_dialog():
    st.session_state["open_new_guest_dialog"] = False

#--------------------------
#EXTRAER TIPOS DE HABITACIONES
#----------------------------
st.header("Reservas")

@st.cache_data(show_spinner=False, ttl=300)
def _get_room_type_options(property_id:str)->Dict[str,str]:
    """
    Devuelve {label:id} para el selectBox
    """
    rows = svc_rooms.list_room_types(property_id)
    
    return {name: str(rid) for(rid, name) in rows}

rt_options = _get_room_type_options(u['property_id'])

if not rt_options:
    st.info("No hay tipos de habitación para esta propiedad.")
    st.stop()

#--------------------------
#FORMULARIO: COTIZAR
#----------------------------

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


# =========================
# Crear reserva: Fechas y disponibilidad
# =========================

st.subheader("Crear reserva")

start2 = st.date_input("Inicio R", value=date.today(), key="s2")
end2 = st.date_input("Fin R", value=date.today()+timedelta(days=1), key="e2")


@st.cache_data(ttl=60,show_spinner=False)
def _get_rooms_available(property_id:str,start:date,end:date):
    #usa start.isoformat(), end.isoformat()
    return svc_rooms.list_rooms_available(
        property_id,
        start,
        end
    )

df_rooms = pd.DataFrame()
if verificar_rango_fecha(start2,end2):
    st.warning("Rango de fechas inválido")
else:
    df_rooms = _get_rooms_available(u['property_id'],start2,end2)

selected_room_ids = []
if not df_rooms.empty and 'id' in df_rooms.columns:
    df_view = df_rooms.copy().set_index("id")
    df_view.insert(0, "☝️", False)

    wanted = ["☝️","code","type","capacity_adults","capacity_children","amenities"]
    available = [c for c in wanted if c in df_view.columns]

    edited = st.data_editor(
        df_view[available],
        hide_index=True,
        use_container_width=True,
        height=280,
        column_config={
            "☝️": st.column_config.CheckboxColumn("☝️", default=False)
        }
    )
    selected_room_ids = [idx for idx, row in edited.iterrows() if row.get("☝️", False)]
else:
    st.info("No hay habitaciones disponibles para ese rango")


# =========================
# MODALES (o popover/sidebar como fallback) PARA HUESPED
# =========================

try:
    @st.dialog("Buscar huespes por DNI")
    def dialog_buscar_dni():
        dni = st.text_input("DNI", placeholder="Ingrese DNI")
        if st.button("Buscar"):
            try:
                results = svc_guest.search_guest_by_dni(dni)
                #idGuestSearch,fullNameSearch,dniSearch = results
                #st.session_state["guest_id"]=idGuestSearch
                #st.write("Nada" if not results else "TOdO")
                if not results:
                    st.write("Sin resultados.")
                else:
                    idGuestSearch,fullNameSearch,dniSearch = results
                    st.text_input("ID",value=idGuestSearch)
                    st.text_input('NAME',value=fullNameSearch)
                    set_guest(idGuestSearch, fullNameSearch,dniSearch)
                    time.sleep(2)
                    st.rerun()
                    if st.button("Seleccionar", key="sel_btn_pop"):
                        #idGuestSearch,fullNameSearch,dniSearch = results
                        #st.session_state["guest_id"]=idGuestSearch
                        close_dni_dialog()
                        
                        
            except Exception as e:
                st.error("Error en la busqueda")
                st.exception(e)
                
    #--- Crear nuevo huesped ----
    @st.dialog("Nuevo huesped")
    def dialog_nuevo_huesped():
        with st.form("new_guest_form"):
            full_name = st.text_input("Nombre completo")
            dni       = st.text_input("DNI")
            email     = st.text_input("Email", placeholder="opcional")
            phone     = st.text_input("Teléfono", placeholder="opcional")
            crear     = st.form_submit_button("Crear")
        if crear:
            try:
                guest_id_now,guest_name_now = svc_guest.create_guests(full_name=full_name, dni=dni, email=email, phone=phone,preferences=None)
                set_guest(guest_id_now, guest_name_now)
                st.rerun()
            except Exception as e:
                st.error("No se pudo crear el huésped")
                st.exception(e)
                
    c1, c2, c3 = st.columns([1,1,3])
    if c1.button("🔎 Buscar por DNI"):
        dialog_buscar_dni()
    if c2.button("➕ Nuevo huésped"):
        dialog_nuevo_huesped()
except Exception:
    # Fallback si tu versión no soporta st.dialog: usa popovers
    c1, c2, c3 = st.columns([1, 1, 3])

    with c1.popover("🔎 Buscar por DNI"):
        dni = st.text_input("DNI", key="dni_pop")
        if st.button("Buscar", key="btn_buscar_pop"):
            results = svc_guest.search_guest_by_dni(dni)
            st.write(results)
            if not results:
                st.write("Sin resultados.")
            else:
                idGuestSearch,fullNameSearch,dniSearch = results
                if st.button("Seleccionar", key="sel_btn_pop"):
                    set_guest(idGuestSearch, fullNameSearch)
                    st.rerun()

    with c2.popover("➕ Nuevo huésped"):
        with st.form("new_guest_form_pop"):
            full_name = st.text_input("Nombre completo", key="nm_pop")
            dni       = st.text_input("DNI", key="dni_new_pop")
            email     = st.text_input("Email", key="em_pop")
            phone     = st.text_input("Teléfono", key="ph_pop")
            crear     = st.form_submit_button("Crear")
        if crear:
            guest_id_now,guest_name_now = svc_guest.create_guests(full_name=full_name, dni=dni, email=email, phone=phone,preferences=None)
            set_guest(guest_id_now, guest_name_now)
            st.rerun()
            
#Mostrar huesped seleccionado (si hay)
if st.session_state["guest_id"]:
    st.text_input(label='Full Name',value=st.session_state["guest_name"])
    st.text_input(label="DNI",value=st.session_state["guest_dni"])
    short = st.session_state["guest_id"][:8]
    st.success(f"Huésped seleccionado: {st.session_state['guest_name']}  ·  UUID: {short}…")
else:
    st.info("Seleccione o cree un huésped para continuar.")
                

# =========================
# Form de creación (usa el guest del estado)
# =========================

with st.form("create_form"):
    #label2 = st.selectbox("Tipo de habitación", list(rt_options.keys()), key="rt2")
    #room_type_id2 = rt_options[label2]
    
    promo2 = st.text_input("Código promo R", placeholder="Opcional")
    #submit = st.form_submit_button("Crear y Confirmar",disabled=(not st.session_state["guest_id"]))
    submit = st.form_submit_button("Crear y Confirmar")
    
        

if submit and st.session_state["guest_id"]:
    try:
        if verificar_rango_fecha(start2,end2):
            st.error("Rango de fechas inválido")
        else:
            dates = [ (start2 + timedelta(days=i)).isoformat() for i in range((end2-start2).days) ]
            #rid = svc.create(
            #    u['property_id'], 
            #    st.session_state["guest_id"], 
            #    "", 
            #    dates, 
            #    promo2 or None, 
            #    u['id']
            #)
            #st.success(f"Reserva creada: {rid}")
            res_id, total = svc.create(
                u['property_id'],
                st.session_state["guest_id"],
                dates,     # p_dates
                selected_room_ids,                         # p_room_ids
                promo2 or None,                            # p_promo_code
                u['id']
            )
            
            st.success(f"Reserva creada: {res_id}, monto total {total}")
            if selected_room_ids:
                st.caption(f"Habitaciones seleccionadas: {', '.join(map(str, selected_room_ids))}")
    except Exception as e:
        st.error("No se pudo crear la reserva. Revisa Room Type, Guest y rango de fechas.")
        st.exception(e) 
    