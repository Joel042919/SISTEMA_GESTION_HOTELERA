import streamlit as st
import json
from datetime import datetime
from app.services.guests import GuestsService
from app.repositories.pg_repo import PgRepo
from app.auth.session import current_user


# Verificar autenticación
u = current_user()
if not u:
    st.stop()

svc = GuestsService(PgRepo())

st.header("🧑‍🤝‍🧑 Gestión de Huéspedes")

# Tabs para organizar funcionalidades
tab1, tab2, tab3 = st.tabs(["📋 Lista de Huéspedes", "➕ Nuevo Huésped", "🔍 Buscar Huésped"])

# Tab 1: Lista de huéspedes
with tab1:
    st.subheader("Lista de Huéspedes")
    
    # Paginación
    col1, col2 = st.columns([3, 1])
    with col2:
        page = st.number_input("Página", min_value=1, value=1, step=1)
    
    limit = 20
    offset = (page - 1) * limit
    
    try:
        guests = svc.list_guests(limit=limit, offset=offset)
        
        if guests:
            # Mostrar huéspedes en una tabla
            for guest in guests:
                with st.container():
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                    
                    with col1:
                        st.write(f"**{guest['full_name']}**")
                        if guest.get('email'):
                            st.caption(f"📧 {guest['email']}")
                    
                    with col2:
                        if guest.get('phone'):
                            st.write(f"📱 {guest['phone']}")
                        else:
                            st.write("📱 No registrado")
                    
                    with col3:
                        created = guest['created_at']
                        if isinstance(created, str):
                            created = datetime.fromisoformat(created.replace('Z', '+00:00'))
                        st.caption(f"Registrado: {created.strftime('%d/%m/%Y')}")
                    
                    with col4:
                        # Botón para editar (expandir para mostrar formulario)
                        if st.button("✏️", key=f"edit_{guest['id']}", help="Editar huésped"):
                            st.session_state[f"editing_{guest['id']}"] = True
                    
                    # Formulario de edición (si está activado)
                    if st.session_state.get(f"editing_{guest['id']}", False):
                        with st.form(f"edit_form_{guest['id']}"):
                            st.write(f"**Editando: {guest['full_name']}**")
                            
                            new_name = st.text_input("Nombre completo", value=guest['full_name'])
                            new_email = st.text_input("Email", value=guest.get('email', '') or '')
                            new_phone = st.text_input("Teléfono", value=guest.get('phone', '') or '')
                            
                            col_save, col_cancel = st.columns(2)
                            with col_save:
                                if st.form_submit_button("💾 Guardar", use_container_width=True):
                                    try:
                                        svc.update_guest(
                                            guest['id'], 
                                            full_name=new_name if new_name != guest['full_name'] else None,
                                            email=new_email if new_email != (guest.get('email') or '') else None,
                                            phone=new_phone if new_phone != (guest.get('phone') or '') else None
                                        )
                                        st.success("✅ Huésped actualizado correctamente")
                                        st.session_state[f"editing_{guest['id']}"] = False
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"❌ Error al actualizar: {str(e)}")
                            
                            with col_cancel:
                                if st.form_submit_button("❌ Cancelar", use_container_width=True):
                                    st.session_state[f"editing_{guest['id']}"] = False
                                    st.rerun()
                    
                    st.divider()
        else:
            st.info("📝 No hay huéspedes registrados aún.")
            
    except Exception as e:
        st.error(f"❌ Error al cargar huéspedes: {str(e)}")

# Tab 2: Crear nuevo huésped
with tab2:
    st.subheader("Registrar Nuevo Huésped")
    
    with st.form("new_guest_form"):
        full_name = st.text_input("Nombre completo *", placeholder="Ej: Juan Pérez García")
        email = st.text_input("Email", placeholder="Ej: juan.perez@email.com")
        phone = st.text_input("Teléfono", placeholder="Ej: +51 999 888 777")
        
        # Preferencias opcionales
        st.write("**Preferencias (opcional)**")
        col1, col2 = st.columns(2)
        with col1:
            room_preference = st.selectbox(
                "Tipo de habitación preferida",
                options=["", "Standard", "Suite", "Deluxe"],
                index=0
            )
            dietary_restrictions = st.text_input("Restricciones dietéticas", placeholder="Ej: Vegetariano, Sin gluten")
        
        with col2:
            special_requests = st.text_area(
                "Solicitudes especiales", 
                placeholder="Ej: Habitación en piso alto, cama extra",
                height=100
            )
        
        submitted = st.form_submit_button("➕ Registrar Huésped", use_container_width=True)
        
        if submitted:
            if not full_name.strip():
                st.error("❌ El nombre completo es obligatorio")
            else:
                try:
                    # Construir preferencias
                    preferences = {}
                    if room_preference:
                        preferences['room_preference'] = room_preference
                    if dietary_restrictions:
                        preferences['dietary_restrictions'] = dietary_restrictions
                    if special_requests:
                        preferences['special_requests'] = special_requests
                    
                    guest_id = svc.create_guest(
                        full_name=full_name.strip(),
                        email=email.strip() if email.strip() else None,
                        phone=phone.strip() if phone.strip() else None,
                        preferences=preferences if preferences else None
                    )
                    
                    st.success(f"✅ Huésped registrado correctamente")
                    st.info(f"🆔 ID del huésped: `{guest_id}`")
                    
                    # Limpiar formulario
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ Error al registrar huésped: {str(e)}")

# Tab 3: Buscar huésped
with tab3:
    st.subheader("Buscar Huésped")
    
    search_query = st.text_input(
        "🔍 Buscar por nombre o email", 
        placeholder="Escribe el nombre o email del huésped..."
    )
    
    if search_query:
        try:
            results = svc.search_guests(search_query)
            
            if results:
                st.write(f"**Resultados encontrados: {len(results)}**")
                
                for guest in results:
                    with st.container():
                        col1, col2, col3 = st.columns([3, 2, 2])
                        
                        with col1:
                            st.write(f"**{guest['full_name']}**")
                            if guest.get('email'):
                                st.caption(f"📧 {guest['email']}")
                        
                        with col2:
                            if guest.get('phone'):
                                st.write(f"📱 {guest['phone']}")
                            else:
                                st.write("📱 No registrado")
                        
                        with col3:
                            st.code(guest['id'], language=None)
                            if st.button("📋 Copiar ID", key=f"copy_{guest['id']}"):
                                st.write("ID copiado al portapapeles")
                        
                        # Mostrar preferencias si existen
                        if guest.get('preferences'):
                            with st.expander("Ver preferencias"):
                                st.json(guest['preferences'])
                        
                        st.divider()
            else:
                st.info(f"🔍 No se encontraron huéspedes que coincidan con '{search_query}'")
                
        except Exception as e:
            st.error(f"❌ Error en la búsqueda: {str(e)}")

# Información adicional
with st.expander("ℹ️ Información de uso"):
    st.markdown("""
    **Gestión de Huéspedes:**
    
    - **Lista**: Visualiza todos los huéspedes registrados con paginación
    - **Nuevo**: Registra un nuevo huésped con información básica y preferencias
    - **Buscar**: Encuentra huéspedes rápidamente por nombre o email
    - **Editar**: Haz clic en el botón ✏️ para modificar la información de un huésped
    
    **Notas importantes:**
    - El nombre completo es obligatorio
    - El email y teléfono son opcionales pero recomendados
    - Las preferencias ayudan a personalizar la experiencia del huésped
    - El ID del huésped se usa para crear reservas
    """)