import streamlit as st
from datetime import date, timedelta
from app.services.reservations import ReservationsService
from app.services.guests import GuestsService
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user


u = current_user()
if not u:
    st.stop()
svc = ReservationsService(PgRepo())
guests_svc = GuestsService(PgRepo())


st.header("Reservas")
with st.form("quote_form"):
    # UUID del room_type Standard obtenido de la base de datos
    room_type_options_quote = ["a47f584d-8ddb-494d-adbb-d17ef1212632"]
    room_type_id = st.selectbox(
        "Tipo de Habitación", 
        options=room_type_options_quote,
        format_func=lambda x: "Standard" if x == "a47f584d-8ddb-494d-adbb-d17ef1212632" else x,
        index=0
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

# Cargar lista de huéspedes para el selector
try:
    guests_list = guests_svc.list_guests(limit=200)  # Cargar más huéspedes para el selector
except Exception as e:
    st.error(f"Error al cargar huéspedes: {str(e)}")
    guests_list = []

# Selector de huésped fuera del formulario para permitir interactividad
if guests_list:
    # Crear lista de opciones con valor vacío al inicio
    guest_options_list = [''] + [guest['id'] for guest in guests_list]
    guest_display_names = {
        '': "-- Seleccionar huésped --",
        **{guest['id']: f"{guest['full_name']} ({guest.get('email', 'Sin email')})" for guest in guests_list}
    }
    
    selected_guest = st.selectbox(
        "Huésped",
        options=guest_options_list,
        format_func=lambda x: guest_display_names[x],
        index=0,
        help="Selecciona un huésped existente o crea uno nuevo en la página de Huéspedes"
    )
    guest_id = selected_guest if selected_guest != '' else None
    
    # Opción para buscar huésped
    with st.expander("🔍 Buscar huésped específico"):
        search_query = st.text_input("Buscar por nombre o email", key="guest_search")
        if search_query:
            try:
                search_results = guests_svc.search_guests(search_query)
                if search_results:
                    for guest in search_results[:5]:  # Mostrar máximo 5 resultados
                        if st.button(f"Seleccionar: {guest['full_name']} ({guest.get('email', 'Sin email')})", key=f"select_{guest['id']}"):
                            st.session_state.selected_guest_id = guest['id']
                            st.success(f"Huésped seleccionado: {guest['full_name']}")
                            st.rerun()
                else:
                    st.info("No se encontraron huéspedes con ese criterio")
            except Exception as e:
                st.error(f"Error en la búsqueda: {str(e)}")
else:
    st.warning("⚠️ No hay huéspedes registrados. Crea un huésped primero en la página de Huéspedes.")
    guest_id = None

# Usar session state si se seleccionó desde búsqueda
if 'selected_guest_id' in st.session_state:
    guest_id = st.session_state.selected_guest_id

# Enlace rápido para crear huésped
st.markdown("**¿Huésped nuevo?** 👉 [Ir a Gestión de Huéspedes](huespedes) para registrarlo")

with st.form("create_form"):
    room_type_options = ["a47f584d-8ddb-494d-adbb-d17ef1212632"]
    room_type_id2 = st.selectbox(
        "Tipo de Habitación", 
        options=room_type_options,
        format_func=lambda x: "Standard" if x == "a47f584d-8ddb-494d-adbb-d17ef1212632" else x,
        key="room_type_2",
        index=0
    )
    start2 = st.date_input("Inicio", value=date.today(), key="s2")
    end2 = st.date_input("Fin", value=date.today()+timedelta(days=1), key="e2")
    promo2 = st.text_input("Código promo", placeholder="Opcional (ej: BIENVENIDA)", key="promo2")
    
    # Mostrar información del huésped seleccionado
    if guest_id:
        selected_guest_info = next((g for g in guests_list if g['id'] == guest_id), None)
        if selected_guest_info:
            st.info(f"✅ Huésped seleccionado: {selected_guest_info['full_name']}")
    
    # El botón ahora siempre está habilitado, pero validamos en el submit
    submit = st.form_submit_button("Crear y Confirmar")


if submit:
    if not guest_id:
        st.error("⚠️ Por favor selecciona un huésped antes de crear la reserva.")
    elif not room_type_id2:
        st.error("⚠️ Por favor selecciona un tipo de habitación.")
    elif start2 >= end2:
        st.error("⚠️ La fecha de fin debe ser posterior a la fecha de inicio.")
    else:
        try:
            dates = [ (start2 + timedelta(days=i)).isoformat() for i in range((end2-start2).days) ]
            rid = svc.create(u['property_id'], guest_id, room_type_id2, dates, promo2 or None, u['id'])
            st.success(f"✅ Reserva creada exitosamente: {rid}")
            # Limpiar session state después de crear la reserva
            if 'selected_guest_id' in st.session_state:
                del st.session_state.selected_guest_id
        except Exception as e:
            st.error(f"❌ Error al crear la reserva: {str(e)}")

# =========================================
# LISTADO DE RESERVAS
# =========================================

st.header("📋 Listado de Reservas")

# Filtros para el listado
with st.expander("🔍 Filtros de búsqueda", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        filter_start_date = st.date_input(
            "Fecha inicio desde", 
            value=None, 
            key="filter_start",
            help="Filtrar reservas que inicien desde esta fecha"
        )
        
    with col2:
        filter_end_date = st.date_input(
            "Fecha inicio hasta", 
            value=None, 
            key="filter_end",
            help="Filtrar reservas que inicien hasta esta fecha"
        )
        
    with col3:
        filter_status = st.selectbox(
            "Estado",
            options=['', 'pending', 'confirmed', 'checked_in', 'checked_out', 'canceled', 'no_show'],
            format_func=lambda x: {
                '': 'Todos los estados',
                'pending': '⏳ Pendiente',
                'confirmed': '✅ Confirmada',
                'checked_in': '🏨 Check-in',
                'checked_out': '🚪 Check-out',
                'canceled': '❌ Cancelada',
                'no_show': '👻 No Show'
            }.get(x, x),
            key="filter_status"
        )
    
    # Búsqueda por huésped
    filter_guest_search = st.text_input(
        "Buscar huésped",
        placeholder="Nombre, email o teléfono del huésped",
        key="filter_guest_search"
    )
    
    # Botones de acción
    col_refresh, col_clear = st.columns([1, 1])
    with col_refresh:
        refresh_list = st.button("🔄 Actualizar lista", key="refresh_reservations")
    with col_clear:
        if st.button("🗑️ Limpiar filtros", key="clear_filters"):
            st.session_state.filter_start = None
            st.session_state.filter_end = None
            st.session_state.filter_status = ''
            st.session_state.filter_guest_search = ''
            st.rerun()

# Cargar y mostrar reservas
try:
    # Preparar parámetros de filtro
    start_date_str = filter_start_date.isoformat() if filter_start_date else None
    end_date_str = filter_end_date.isoformat() if filter_end_date else None
    status_str = filter_status if filter_status else None
    guest_search_str = filter_guest_search.strip() if filter_guest_search.strip() else None
    
    # Obtener reservas
    reservations = svc.list_reservations(
        property_id=u['property_id'],
        start_date=start_date_str,
        end_date=end_date_str,
        status=status_str,
        guest_search=guest_search_str,
        limit=100
    )
    
    if reservations:
        st.info(f"📊 Se encontraron {len(reservations)} reserva(s)")
        
        # Mostrar reservas en una tabla interactiva
        for i, reservation in enumerate(reservations):
            with st.container():
                # Crear columnas para la información de la reserva
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                
                with col1:
                    # Información del huésped y reserva
                    status_emoji = {
                        'pending': '⏳',
                        'confirmed': '✅',
                        'checked_in': '🏨',
                        'checked_out': '🚪',
                        'canceled': '❌',
                        'no_show': '👻'
                    }.get(reservation['status'], '❓')
                    
                    st.markdown(f"**{status_emoji} {reservation['guest_name']}**")
                    if reservation['guest_email']:
                        st.caption(f"📧 {reservation['guest_email']}")
                    if reservation['guest_phone']:
                        st.caption(f"📱 {reservation['guest_phone']}")
                
                with col2:
                    # Fechas y habitación
                    st.markdown(f"**📅 {reservation['start_date']} → {reservation['end_date']}**")
                    st.caption(f"🏠 {reservation['room_type_name']}")
                    if reservation['room_number']:
                        st.caption(f"🚪 Habitación: {reservation['room_number']}")
                    else:
                        st.caption("🚪 Sin habitación asignada")
                
                with col3:
                    # Información financiera
                    st.markdown(f"**💰 ${reservation['total_amount']:.2f}**")
                    if reservation['deposit_amount'] > 0:
                        st.caption(f"💳 Depósito: ${reservation['deposit_amount']:.2f}")
                    if reservation['promo_code']:
                        st.caption(f"🎟️ Promo: {reservation['promo_code']}")
                
                with col4:
                    # Botones de acción
                    if st.button("👁️ Ver", key=f"view_{reservation['id']}"):
                        st.session_state.selected_reservation_id = reservation['id']
                        st.session_state.show_reservation_details = True
                        st.rerun()
                    
                    if st.button("✏️ Editar", key=f"edit_{reservation['id']}"):
                        st.session_state[f"editing_{reservation['id']}"] = True
                        st.rerun()
                    
                    if reservation['status'] in ['pending', 'confirmed'] and st.button("❌ Cancelar", key=f"cancel_{reservation['id']}"):
                        st.session_state.cancel_reservation_id = reservation['id']
                        st.session_state.show_cancel_dialog = True
                        st.rerun()
                
                # Selector de estado y formulario de edición
                col_status, col_edit = st.columns(2)
                
                with col_status:
                    # Selector de estado
                    current_status = reservation['status']
                    status_options = ['pending', 'confirmed', 'checked_in', 'checked_out', 'canceled', 'no_show']
                    status_labels = {
                        'pending': '⏳ Pendiente',
                        'confirmed': '✅ Confirmada', 
                        'checked_in': '🏨 Check-in',
                        'checked_out': '🚪 Check-out',
                        'canceled': '❌ Cancelada',
                        'no_show': '👻 No Show'
                    }
                    
                    new_status = st.selectbox(
                        "Cambiar Estado",
                        options=status_options,
                        index=status_options.index(current_status),
                        format_func=lambda x: status_labels[x],
                        key=f"status_{reservation['id']}"
                    )
                    
                    if new_status != current_status:
                        if st.button(f"💾 Actualizar Estado", key=f"update_status_{reservation['id']}", type="primary"):
                            try:
                                svc.update_reservation_status(reservation['id'], new_status, u['id'])
                                st.success(f"Estado cambiado a {status_labels[new_status]}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al cambiar estado: {str(e)}")
                
                # Formulario de edición (si está activado)
                if st.session_state.get(f"editing_{reservation['id']}", False):
                    with col_edit:
                        st.markdown("**✏️ Editar Reserva**")
                        
                        with st.form(f"edit_form_{reservation['id']}"):
                            from datetime import datetime
                            
                            new_start_date = st.date_input(
                                "Nueva fecha de entrada",
                                value=datetime.strptime(reservation['start_date'], '%Y-%m-%d').date(),
                                key=f"edit_start_{reservation['id']}"
                            )
                            new_end_date = st.date_input(
                                "Nueva fecha de salida", 
                                value=datetime.strptime(reservation['end_date'], '%Y-%m-%d').date(),
                                key=f"edit_end_{reservation['id']}"
                            )
                            
                            new_promo_code = st.text_input(
                                "Código promocional",
                                value=reservation.get('promo_code', '') or '',
                                key=f"edit_promo_{reservation['id']}"
                            )
                            
                            col_save, col_cancel_edit = st.columns(2)
                            
                            with col_save:
                                if st.form_submit_button("💾 Guardar", type="primary"):
                                    try:
                                        # Solo enviar campos que cambiaron
                                        updates = {}
                                        if new_start_date.strftime('%Y-%m-%d') != reservation['start_date']:
                                            updates['start_date'] = new_start_date.strftime('%Y-%m-%d')
                                        if new_end_date.strftime('%Y-%m-%d') != reservation['end_date']:
                                            updates['end_date'] = new_end_date.strftime('%Y-%m-%d')
                                        if new_promo_code != (reservation.get('promo_code') or ''):
                                            updates['promo_code'] = new_promo_code
                                        
                                        if updates:
                                            svc.update_reservation(
                                                reservation['id'], 
                                                u['id'],
                                                **updates
                                            )
                                            st.success("Reserva actualizada exitosamente")
                                            st.session_state[f"editing_{reservation['id']}"] = False
                                            st.rerun()
                                        else:
                                            st.info("No hay cambios para guardar")
                                    except Exception as e:
                                        st.error(f"Error al actualizar reserva: {str(e)}")
                            
                            with col_cancel_edit:
                                if st.form_submit_button("❌ Cancelar"):
                                    st.session_state[f"editing_{reservation['id']}"] = False
                                    st.rerun()
                
                st.divider()
    else:
        st.info("📭 No se encontraron reservas con los filtros aplicados")
        
except Exception as e:
    st.error(f"❌ Error al cargar las reservas: {str(e)}")

# =========================================
# MODAL PARA VER DETALLES DE RESERVA
# =========================================

if st.session_state.get('show_reservation_details', False):
    reservation_id = st.session_state.get('selected_reservation_id')
    if reservation_id:
        try:
            reservation_details = svc.get_reservation(reservation_id)
            if reservation_details:
                st.subheader(f"📋 Detalles de Reserva: {reservation_details['guest_name']}")
                
                # Información en columnas
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**👤 Información del Huésped**")
                    st.write(f"**Nombre:** {reservation_details['guest_name']}")
                    st.write(f"**Email:** {reservation_details['guest_email'] or 'No especificado'}")
                    st.write(f"**Teléfono:** {reservation_details['guest_phone'] or 'No especificado'}")
                    
                    st.markdown("**🏨 Información de la Reserva**")
                    st.write(f"**Estado:** {reservation_details['status']}")
                    st.write(f"**Fechas:** {reservation_details['start_date']} → {reservation_details['end_date']}")
                    st.write(f"**Tipo de habitación:** {reservation_details['room_type_name']}")
                    if reservation_details['room_number']:
                        st.write(f"**Habitación asignada:** {reservation_details['room_number']}")
                    else:
                        st.write("**Habitación:** Sin asignar")
                
                with col2:
                    st.markdown("**💰 Información Financiera**")
                    st.write(f"**Total:** ${reservation_details['total_amount']:.2f} {reservation_details['currency']}")
                    st.write(f"**Depósito:** ${reservation_details['deposit_amount']:.2f}")
                    if reservation_details['promo_code']:
                        st.write(f"**Código promocional:** {reservation_details['promo_code']}")
                    
                    st.markdown("**📊 Información del Sistema**")
                    st.write(f"**ID de reserva:** {reservation_details['id']}")
                    st.write(f"**Creada:** {reservation_details['created_at']}")
                
                # Mostrar preferencias del huésped si existen
                if reservation_details['guest_preferences']:
                    st.markdown("**🎯 Preferencias del Huésped**")
                    st.json(reservation_details['guest_preferences'])
                
                # Botón para cerrar
                if st.button("✖️ Cerrar detalles"):
                    st.session_state.show_reservation_details = False
                    if 'selected_reservation_id' in st.session_state:
                        del st.session_state.selected_reservation_id
                    st.rerun()
            else:
                st.error("No se pudo cargar la información de la reserva")
        except Exception as e:
            st.error(f"Error al cargar los detalles: {str(e)}")

# =========================================
# MODAL PARA CANCELAR RESERVA
# =========================================

if st.session_state.get('show_cancel_dialog', False):
    cancel_reservation_id = st.session_state.get('cancel_reservation_id')
    if cancel_reservation_id:
        st.subheader("❌ Cancelar Reserva")
        st.warning("⚠️ Esta acción no se puede deshacer")
        
        cancel_reason = st.text_area(
            "Motivo de cancelación",
            placeholder="Ingresa el motivo de la cancelación...",
            key="cancel_reason"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ Confirmar cancelación", type="primary"):
                if cancel_reason.strip():
                    try:
                        svc.cancel_reservation(cancel_reservation_id, cancel_reason, u['id'])
                        st.success("✅ Reserva cancelada exitosamente")
                        # Limpiar estado y recargar
                        st.session_state.show_cancel_dialog = False
                        if 'cancel_reservation_id' in st.session_state:
                            del st.session_state.cancel_reservation_id
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al cancelar la reserva: {str(e)}")
                else:
                    st.error("Por favor ingresa un motivo para la cancelación")
        
        with col2:
            if st.button("🚫 Cancelar acción"):
                st.session_state.show_cancel_dialog = False
                if 'cancel_reservation_id' in st.session_state:
                    del st.session_state.cancel_reservation_id
                st.rerun()