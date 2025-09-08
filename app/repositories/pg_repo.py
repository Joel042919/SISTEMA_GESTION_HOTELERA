from app.core.db import PgSession
from typing import Optional,List,Tuple
import pandas as pd



class PgRepo:
    def quote_price(self, property_id:str, room_type_id:str, start:str, end:str, guests:int, promo:Optional[str]):
        with PgSession() as db:
            row = db.call('pms.sp_quote_price', (property_id, room_type_id, start, end, guests, promo))
            if not row:
                return None
            return {
                'nights': row[0], 'base_total': float(row[1] or 0), 'promo_discount': float(row[2] or 0),
                'tax_total': float(row[3] or 0), 'grand_total': float(row[4] or 0), 'nightly': row[5]
            }


    def create_reservation(self, property_id:str, guest_id:str, room_type_id:str, dates:List[str], promo:Optional[str], user_id:str)->str:
        with PgSession() as db:
            row = db.call('pms.sp_create_reservation', (property_id, guest_id, room_type_id, dates, promo, user_id))
            return row[0]

    def create_guests(self,full_name:str,dni:str,phone:str,email:Optional[str],preferences:Optional[dict])->tuple[str,str]:
        with PgSession() as db:
            row = db.call('pms.sp_create_guests', (full_name, dni, phone, email, preferences))
            return row


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
                SELECT r.id::text                AS id,
                       r.code                    AS code,
                       rt.name                   AS type,
                       rt.capacity_adults        AS capacity_adults,
                       rt.capacity_children      AS capacity_children,
                       (rt.amenities)::text      AS amenities
                FROM pms.rooms r
                INNER JOIN pms.room_types rt ON r.room_type_id = rt.id
                inner join pms.reservation_rooms rero on rero.room_id=r.id 
                inner join pms.reservations res on res.id=rero.reservation_id
                WHERE r.status = 'available'
                  AND r.property_id = %s and not (res.end_date>=%s and res.start_date<=%s)
                ORDER BY rt.name, r.code;
                """,
                (property_id,startDate,endDate)
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