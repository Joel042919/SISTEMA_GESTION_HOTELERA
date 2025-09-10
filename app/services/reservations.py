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