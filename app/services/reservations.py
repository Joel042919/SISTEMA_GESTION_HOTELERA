from .base import policy_check
from app.repositories.pg_repo import PgRepo


class ReservationsService:
    def __init__(self, repo: PgRepo):
        self.repo = repo


    @policy_check('reservations.create')
    def quote(self, property_id, room_type_id, start, end, guests, promo):
        return self.repo.quote_price(property_id, room_type_id, start, end, guests, promo)


    @policy_check('reservations.create')
    def create(self, property_id, guest_id, dates,selected_room_ids, promo, user_id):
        return self.repo.create_reservation(property_id, guest_id, dates,selected_room_ids, promo, user_id)


    @policy_check('reservations.assign_room')
    def assign_room(self, reservation_id, room_id, user_id):
        self.repo.assign_room(reservation_id, room_id, user_id)
        
        
    @policy_check('reservations.search_reservation_by_dni_guest')
    def search_reservation(self, propiedad_id:str, dniGuest:str):
        return self.repo.search_reservation(propiedad_id,dniGuest)
    
    @policy_check('reservations.search_guest_data')
    def search_guest_reservation(self, reservation_id:str):
        return self.repo.search_guest_reservation(reservation_id)
    
    @policy_check('reservations.get_rooms')
    def get_rooms_reservations(self, reservation_id:str):
        return self.repo.get_rooms_reservations(reservation_id)
    
    @policy_check('reservations.get_financials')
    def get_reservation_financials(self, reservation_id:str):
        return self.repo.get_reservation_financials(reservation_id)
    
    @policy_check('reservations.check_in')
    def check_in(self, reservation_id:str,pay_method:str,user_id:str):
        return self.repo.check_in(reservation_id,pay_method,user_id)
    