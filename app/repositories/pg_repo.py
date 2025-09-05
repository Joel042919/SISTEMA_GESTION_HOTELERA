from app.core.db import PgSession


class PgRepo:
    def quote_price(self, property_id:str, room_type_id:str, start:str, end:str, guests:int, promo:str|None):
        with PgSession() as db:
            row = db.call('pms.sp_quote_price', (property_id, room_type_id, start, end, guests, promo))
            if not row:
                return None
            return {
            'nights': row[0], 'base_total': float(row[1] or 0), 'promo_discount': float(row[2] or 0),
            'tax_total': float(row[3] or 0), 'grand_total': float(row[4] or 0), 'nightly': row[5]
        }


    def create_reservation(self, property_id:str, guest_id:str, room_type_id:str, dates:list[str], promo:str|None, user_id:str)->str:
        with PgSession() as db:
            row = db.call('pms.sp_create_reservation', (property_id, guest_id, room_type_id, dates, promo, user_id))
            return row[0]


    def assign_room(self, reservation_id:str, room_id:str, user_id:str):
        with PgSession() as db:
            db.call_void('pms.sp_assign_room', (reservation_id, room_id, user_id))


    def set_room_status(self, room_id:str, status:str, user_id:str):
        with PgSession() as db:
            db.call_void('pms.sp_set_room_status', (room_id, status, user_id))


    def post_charge(self, reservation_id:str, concept:str, amount:float, tax_code:str, user_id:str):
        with PgSession() as db:
            db.call_void('pms.sp_post_charge', (reservation_id, concept, amount, tax_code, user_id))


    def register_payment(self, reservation_id:str, method:str, amount:float, currency:str, user_id:str):
        with PgSession() as db:
            db.call_void('pms.sp_register_payment', (reservation_id, method, amount, currency, user_id))


    def checkout(self, reservation_id:str, extra:dict, user_id:str)->str:
        with PgSession() as db:
            row = db.call('pms.sp_checkout', (reservation_id, extra, user_id))
            return row[0]


    def report_daily(self, property_id:str, date:str):
        with PgSession() as db:
            row = db.call('pms.sp_report_daily', (property_id, date))
            return {
            'date': row[0], 'rooms_total': row[1], 'rooms_occupied': row[2],
            'occupancy_pct': float(row[3] or 0), 'revenue': float(row[4] or 0),
            'adr': float(row[5] or 0), 'revpar': float(row[6] or 0)
            }


    # =========================================
    # Gestión de Huéspedes
    # =========================================
    def create_guest(self, full_name: str, email: str = None, phone: str = None, preferences: dict = None) -> str:
        """Crear un nuevo huésped y retornar su UUID"""
        import json
        with PgSession() as db:
            db.cur.execute(
                "INSERT INTO pms.guests (full_name, email, phone, preferences) VALUES (%s, %s, %s, %s) RETURNING id",
                (full_name, email, phone, json.dumps(preferences or {}))
            )
            row = db.cur.fetchone()
            return row[0]


    def list_guests(self, limit: int = 100, offset: int = 0):
        """Listar huéspedes con paginación"""
        with PgSession() as db:
            db.cur.execute(
                "SELECT id, full_name, email, phone, preferences, created_at FROM pms.guests ORDER BY created_at DESC LIMIT %s OFFSET %s",
                (limit, offset)
            )
            rows = db.cur.fetchall()
            return [{
                'id': row[0], 'full_name': row[1], 'email': row[2], 
                'phone': row[3], 'preferences': row[4] or {}, 'created_at': row[5]
            } for row in rows]


    def get_guest(self, guest_id: str):
        """Obtener un huésped por su ID"""
        with PgSession() as db:
            db.cur.execute(
                "SELECT id, full_name, email, phone, preferences, created_at FROM pms.guests WHERE id = %s",
                (guest_id,)
            )
            row = db.cur.fetchone()
            if row:
                return {
                    'id': row[0], 'full_name': row[1], 'email': row[2],
                    'phone': row[3], 'preferences': row[4] or {}, 'created_at': row[5]
                }
            return None


    def update_guest(self, guest_id: str, full_name: str = None, email: str = None, phone: str = None, preferences: dict = None):
        """Actualizar información de un huésped"""
        import json
        updates = []
        params = []
        
        if full_name is not None:
            updates.append("full_name = %s")
            params.append(full_name)
        if email is not None:
            updates.append("email = %s")
            params.append(email)
        if phone is not None:
            updates.append("phone = %s")
            params.append(phone)
        if preferences is not None:
            updates.append("preferences = %s")
            params.append(json.dumps(preferences))
            
        if updates:
            params.append(guest_id)
            with PgSession() as db:
                db.cur.execute(
                    f"UPDATE pms.guests SET {', '.join(updates)} WHERE id = %s",
                    params
                )

    # Métodos para reservas
    def list_reservations(self, property_id: str, start_date: str = None, end_date: str = None, 
                         status: str = None, guest_search: str = None, limit: int = 50, offset: int = 0):
        """Lista reservas con filtros opcionales"""
        with PgSession() as db:
            rows = db.cur.execute(
                "SELECT * FROM pms.sp_list_reservations(%s, %s, %s, %s, %s, %s, %s)",
                (property_id, start_date, end_date, status, guest_search, limit, offset)
            ).fetchall()
            
            reservations = []
            for row in rows:
                reservations.append({
                    'id': str(row[0]),
                    'guest_name': row[1],
                    'guest_email': row[2],
                    'guest_phone': row[3],
                    'room_type_name': row[4],
                    'room_number': row[5],
                    'start_date': row[6],
                    'end_date': row[7],
                    'status': row[8],
                    'total_amount': float(row[9] or 0),
                    'deposit_amount': float(row[10] or 0),
                    'promo_code': row[11],
                    'created_at': row[12]
                })
            return reservations

    def get_reservation(self, reservation_id: str):
        """Obtiene una reserva específica por ID"""
        with PgSession() as db:
            row = db.cur.execute(
                "SELECT * FROM pms.sp_get_reservation(%s)",
                (reservation_id,)
            ).fetchone()
            
            if not row:
                return None
                
            return {
                'id': str(row[0]),
                'property_id': str(row[1]),
                'guest_id': str(row[2]),
                'guest_name': row[3],
                'guest_email': row[4],
                'guest_phone': row[5],
                'guest_preferences': row[6],
                'room_type_id': str(row[7]),
                'room_type_name': row[8],
                'room_id': str(row[9]) if row[9] else None,
                'room_number': row[10],
                'start_date': row[11],
                'end_date': row[12],
                'status': row[13],
                'total_amount': float(row[14] or 0),
                'deposit_amount': float(row[15] or 0),
                'promo_code': row[16],
                'currency': row[17],
                'created_by': str(row[18]) if row[18] else None,
                'created_at': row[19]
            }

    def cancel_reservation(self, reservation_id: str, reason: str, user_id: str):
        """Cancela una reserva"""
        with PgSession() as db:
            db.call_void('pms.sp_cancel_reservation', (reservation_id, reason, user_id))
    
    def update_reservation(self, reservation_id: str, user_id: str, 
                          start_date: str = None, end_date: str = None, 
                          promo_code: str = None) -> None:
        """Actualizar información de una reserva"""
        with PgSession() as db:
            db.call_void('pms.sp_update_reservation', (reservation_id, user_id, start_date, end_date, promo_code))
    
    def update_reservation_status(self, reservation_id: str, new_status: str, 
                                 user_id: str, notes: str = None) -> None:
        """Cambiar estado de una reserva"""
        with PgSession() as db:
            db.call_void('pms.sp_update_reservation_status', (reservation_id, new_status, user_id, notes))