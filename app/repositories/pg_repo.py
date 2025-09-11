from app.core.db import PgSession

class PgRepo:
    # --- DASHBOARD ---
    def daily_kpis(self, property_id: str, the_date: str):
        with PgSession() as db:
            row = db.call("pms.fn_daily_kpis", (property_id, the_date))
            if not row:
                return None
            # retorna: d, rooms_total, rooms_occupied, occupancy, adr, revpar, room_revenue, extra_revenue, payments, invoices, checkins, checkouts
            return {
                "date": row[0],
                "rooms_total": row[1],
                "rooms_occupied": row[2],
                "occupancy": float(row[3] or 0),
                "adr": float(row[4] or 0),
                "revpar": float(row[5] or 0),
                "room_revenue": float(row[6] or 0),
                "extra_revenue": float(row[7] or 0),
                "payments": float(row[8] or 0),
                "invoices": float(row[9] or 0),
                "checkins": int(row[10] or 0),
                "checkouts": int(row[11] or 0),
            }
        
    # --- HABITACIONES ---
    def set_room_status(self, room_id: str, new_status: str, user_id: str):
        with PgSession() as db:
            # p_status es del tipo enum pms.room_status
            db.call_void("pms.sp_set_room_status", (room_id, new_status, user_id))
    
    # --- FACTURACIÓN / CAJA ---
    def post_charge(self, reservation_id: str, concept: str, amount: float, tax_code: str, user_id: str):
        with PgSession() as db:
            db.call_void("pms.sp_post_charge", (reservation_id, concept, amount, tax_code, user_id))

    def register_payment(self, reservation_id: str, method: str, amount: float, currency: str, user_id: str):
        with PgSession() as db:
            # tu SP: (uuid, text, numeric, text, uuid)
            db.call_void("pms.sp_register_payment", (reservation_id, method, amount, currency, user_id))

    def close_cash(self, property_id: str, the_date: str, user_id: str) -> str:
        with PgSession() as db:
            row = db.call("pms.sp_close_cash", (property_id, the_date, user_id))
            return str(row[0]) if row else None
