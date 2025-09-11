from app.core.db import PgSession
from typing import Optional,List,Tuple,Dict
import pandas as pd
from decimal import Decimal

class PgRepo:
<<<<<<< HEAD
    # --- DASHBOARD ---
    def daily_kpis(self, property_id: str, the_date: str):
=======
    def quote_price(self, property_id:str, room_type_id:str, start:str, end:str, guests:int, promo:Optional[str]):
>>>>>>> d1211c539bdfdfa1792f6acac0f7a72d1438d3ff
        with PgSession() as db:
            row = db.call("pms.fn_daily_kpis", (property_id, the_date))
            if not row:
                return None
            # retorna: d, rooms_total, rooms_occupied, occupancy, adr, revpar, room_revenue, extra_revenue, payments, invoices, checkins, checkouts
            return {
<<<<<<< HEAD
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
=======
                'nights': row[0], 'base_total': float(row[1] or 0), 'promo_discount': float(row[2] or 0),
                'tax_total': float(row[3] or 0), 'grand_total': float(row[4] or 0), 'nightly': row[5]
            }


    def create_reservation(self, property_id:str, guest_id:str, dates:List[str],selected_room_ids:List[str], promo:Optional[str], user_id:str)->tuple[str,Decimal]:
        with PgSession() as db:
            row = db.call('pms.sp_create_reservation_with_rooms', (property_id, guest_id, dates,selected_room_ids, promo, user_id))
            return row[0],row[1]

    def create_guests(self,full_name:str,dni:str,phone:str,email:Optional[str],preferences:Optional[dict])->tuple[str,str]:
        with PgSession() as db:
            row = db.call('pms.sp_create_guests', (full_name, dni, phone, email, preferences))
            return row


    def assign_room(self, reservation_id:str, room_id:str, user_id:str):
>>>>>>> d1211c539bdfdfa1792f6acac0f7a72d1438d3ff
        with PgSession() as db:
            db.call_void("pms.sp_post_charge", (reservation_id, concept, amount, tax_code, user_id))

    def register_payment(self, reservation_id: str, method: str, amount: float, currency: str, user_id: str):
        with PgSession() as db:
            # tu SP: (uuid, text, numeric, text, uuid)
            db.call_void("pms.sp_register_payment", (reservation_id, method, amount, currency, user_id))

    def close_cash(self, property_id: str, the_date: str, user_id: str) -> str:
        with PgSession() as db:
<<<<<<< HEAD
            row = db.call("pms.sp_close_cash", (property_id, the_date, user_id))
            return str(row[0]) if row else None
=======
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
            
    def list_room_types(self,property_id:str)->List[Tuple[str,str]]:
        """
        Devuelve lista [(id, name)] de tipos de habitación de la propiedad.
        """
        with PgSession() as db:
            db.cur.execute(
                """
                SELECT id::text, name
                FROM pms.room_types
                WHERE property_id = %s
                ORDER BY name
                """,
                (property_id,)
            )
            rows = db.cur.fetchall() or []
            return [(r[0], r[1]) for r in rows]
    
    def list_rooms_available(self, property_id:str,startDate:str,endDate:str)->pd.DataFrame:
        """
        Devuelve lista [(id,code,type,capacity_adults,capacity_children,amenities)] de las habitaciones disponibles
        """
        with PgSession() as db:
            db.cur.execute(
                """
                SELECT
                    r.id::text             AS id,
                    r.code                 AS code,
                    rt.name                AS type,
                    rt.capacity_adults     AS capacity_adults,
                    rt.capacity_children   AS capacity_children,
                    rt.amenities::text     AS amenities
                FROM pms.rooms r
                JOIN pms.room_types rt
                ON rt.id = r.room_type_id
                WHERE r.property_id = %s
                AND r.status <> 'out_of_order'  -- o = 'available' si así lo quieres
                AND NOT EXISTS (
                    SELECT 1
                    FROM pms.reservation_rooms rr
                    JOIN pms.reservations res ON res.id = rr.reservation_id
                    WHERE rr.room_id = r.id
                    AND res.status IN ('pending','confirmed','checked_in')
                    -- SOLAPE: startA < endB AND endA > startB
                    AND res.start_date < %s   -- endDate
                    AND res.end_date   > %s   -- startDate
                )
                ORDER BY rt.name, r.code;
                """,
                (property_id,endDate,startDate)
            )
            rows = db.cur.fetchall() or []
            df = pd.DataFrame(rows, columns=[
                "id","code","type","capacity_adults","capacity_children","amenities"
            ])
            return df
        
    def search_guest_by_dni(self,dni:str)->Optional[tuple[str,str]]:
        with PgSession() as db:
            row = db.call('pms.search_guest_by_dni',(dni,))
            return row
    
    def search_reservation(self, propiedadId:str,dniGuest:str)->str:
        with PgSession() as db:
            rows = db.call('pms.fn_find_pending_reservation_by_dni',(propiedadId,dniGuest))
            return rows[0]
        
    def search_guest_reservation(self, reservation_id:str)->Optional[dict]:
        with PgSession() as db:
            db.cur.execute(
                """
                SELECT r.id::text AS reservation_id, g.full_name, g.dni,
                       r.start_date, r.end_date, r.status
                FROM pms.reservations r
                JOIN pms.guests g ON g.id = r.guest_id
                WHERE r.id=%s
                """
                ,(reservation_id,)
            )
            row = db.cur.fetchone()
            if row is None:
                return None
            cols = [desc[0] for desc in db.cur.description]
            return dict(zip(cols, row))
    
    def get_rooms_reservations(self, reservation_id:str)->List[Dict]:
        with PgSession() as db:
            db.cur.execute(
                """
                SELECT room_code, room_type, subtotal_room AS price, currency
                FROM pms.fn_reservation_room_breakdown(%s)
                ORDER BY room_code
                """
                ,(reservation_id,)
            )
            
            rows = db.cur.fetchall()
            cols = [desc[0] for desc in db.cur.description]  # nombres de columnas
            return [dict(zip(cols, r)) for r in rows]
    
    
    def get_reservation_financials(self, reservation_id:str)->Optional[dict]:
        with PgSession() as db:
            db.cur.execute(
                """
                SELECT * from pms.fn_reservation_financials(%s)
                """
                ,(reservation_id,)
            )
            rows = db.cur.fetchall()
            if not rows:
                return None
            row = rows[0]
            cols = [desc[0] for desc in db.cur.description]
            return dict(zip(cols,row))
        
    def check_in(self, reservation_id:str,pay_method:str,user_id:str)->Optional[dict]:
        with PgSession() as db:
            db.cur.execute(
                """
                select * from pms.sp_check_in(%s,%s,%s)
                """
                ,(reservation_id,pay_method,user_id)
            )
            rows = db.cur.fetchall()
            if not rows:
                return None
            row = rows[0]
            cols = [desc[0] for desc in db.cur.description]
            return dict(zip(cols,row))
        
    def check_out(self, reservation_id:str,pay_method:str,user_id:str)->Optional[dict]:
        with PgSession() as db:
            db.cur.execute(
                """
                select * from pms.sp_check_out(%s,%s,%s)
                """
                ,(reservation_id,pay_method,user_id)
            )
            rows = db.cur.fetchall()
            if not rows:
                return None
            row = rows[0]
            cols = [desc[0] for desc in db.cur.description]
            return dict(zip(cols,row)) 
        
    def find_checkedin_reservation_by_dni(self,property_id:str,dni:str)->str:
        with PgSession() as db:
            db.cur.execute(
                """SELECT pms.fn_find_checkedin_reservation_by_dni(%s,%s) AS res_id"""
                , (property_id, dni)
            )
            row = db.cur.fetchone()
            if row and row[0]:
                return row[0]   # res_id como str
            return None
        
    def list_roles(self) -> List[Tuple[str, str]]:
        """
        Devuelve [(role_id, role_name)]
        """
        with PgSession() as db:
            db.cur.execute("SELECT id::text, name FROM pms.roles ORDER BY name;")
            return [(r[0], r[1]) for r in (db.cur.fetchall() or [])]
    
    
    def list_users_with_roles(self, property_id: str) -> List[Dict]:
        """
        Lista usuarios y sus roles (agregados) para la propiedad dada.
        """
        with PgSession() as db:
            db.cur.execute(
                """
                SELECT
                u.id::text AS id,
                u.email,
                u.full_name,
                u.is_active,
                COALESCE(
                    array_agg(DISTINCT r.name) FILTER (WHERE r.id IS NOT NULL),
                    '{}'
                ) AS roles
                FROM pms.users u
                LEFT JOIN pms.user_roles ur ON ur.user_id = u.id AND ur.property_id = %s
                LEFT JOIN pms.roles r ON r.id = ur.role_id
                GROUP BY u.id, u.email, u.full_name, u.is_active
                ORDER BY u.full_name, u.email;
                """,
                (property_id,)
            )
            rows = db.cur.fetchall() or []
            cols = [d[0] for d in db.cur.description]
            return [dict(zip(cols, r)) for r in rows]

    def get_user_with_roles(self, user_id: str, property_id: str) -> Optional[Dict]:
        with PgSession() as db:
            db.cur.execute(
                """
                SELECT
                  u.id::text AS id,
                  u.email,
                  u.full_name,
                  u.is_active,
                  COALESCE(array_agg(DISTINCT r.id::text)
                    FILTER (WHERE r.id IS NOT NULL), '{}') AS role_ids
                FROM pms.users u
                LEFT JOIN pms.user_roles ur ON ur.user_id = u.id AND ur.property_id = %s
                LEFT JOIN pms.roles r ON r.id = ur.role_id
                WHERE u.id = %s
                GROUP BY u.id, u.email, u.full_name, u.is_active
                """,
                (property_id, user_id)
            )
            row = db.cur.fetchone()
            if not row:
                return None
            cols = [d[0] for d in db.cur.description]
            return dict(zip(cols, row))
        
    def create_user(self, email: str, full_name: str, password_hash: str, is_active: bool=True) -> str:
        with PgSession() as db:
            db.cur.execute(
                """
                INSERT INTO pms.users(email, full_name, password_hash, is_active)
                VALUES (%s, %s, %s, %s)
                RETURNING id::text;
                """,
                (email, full_name, password_hash, is_active)
            )
            return db.cur.fetchone()[0]

    def update_user(self, user_id: str, email: str, full_name: str,
                    password_hash: Optional[str], is_active: bool) -> None:
        with PgSession() as db:
            if password_hash:
                db.cur.execute(
                    """
                    UPDATE pms.users
                    SET email=%s, full_name=%s, password_hash=%s, is_active=%s
                    WHERE id=%s
                    """,
                    (email, full_name, password_hash, is_active, user_id)
                )
            else:
                db.cur.execute(
                    """
                    UPDATE pms.users
                    SET email=%s, full_name=%s, is_active=%s
                    WHERE id=%s
                    """,
                    (email, full_name, is_active, user_id)
                )

    def set_user_active(self, user_id: str, is_active: bool) -> None:
        with PgSession() as db:
            db.cur.execute(
                "UPDATE pms.users SET is_active=%s WHERE id=%s",
                (is_active, user_id)
            )
            
    def replace_user_roles(self, user_id: str, role_ids: List[str], property_id: str) -> None:
        with PgSession() as db:
            # limpia asignaciones actuales para la propiedad
            db.cur.execute(
                "DELETE FROM pms.user_roles WHERE user_id=%s AND property_id=%s",
                (user_id, property_id)
            )
            if role_ids:
                db.cur.executemany(
                    """
                    INSERT INTO pms.user_roles(user_id, role_id, property_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    [(user_id, rid, property_id) for rid in role_ids]
                )



            
        
       

>>>>>>> d1211c539bdfdfa1792f6acac0f7a72d1438d3ff
