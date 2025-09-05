from .base import policy_check
from app.repositories.pg_repo import PgRepo


class ReservationsService:
    def __init__(self, repo: PgRepo):
        self.repo = repo


    @policy_check('reservations.create')
    def quote(self, property_id, room_type_id, start, end, guests, promo):
        return self.repo.quote_price(property_id, room_type_id, start, end, guests, promo)


    @policy_check('reservations.create')
    def create(self, property_id, guest_id, room_type_id, dates, promo, user_id):
        return self.repo.create_reservation(property_id, guest_id, room_type_id, dates, promo, user_id)


    @policy_check('reservations.assign_room')
    def assign_room(self, reservation_id, room_id, user_id):
        self.repo.assign_room(reservation_id, room_id, user_id)

    @policy_check('reservations.list')
    def list_reservations(self, property_id, start_date=None, end_date=None, status=None, guest_search=None, limit=50, offset=0):
        """Lista reservas con filtros opcionales"""
        return self.repo.list_reservations(property_id, start_date, end_date, status, guest_search, limit, offset)

    @policy_check('reservations.view')
    def get_reservation(self, reservation_id):
        """Obtiene una reserva específica"""
        return self.repo.get_reservation(reservation_id)

    @policy_check('reservations.cancel')
    def cancel_reservation(self, reservation_id: str, user_id: str) -> None:
        """Cancelar una reserva"""
        return self.repo.cancel_reservation(reservation_id, user_id)
    
    @policy_check('reservations.update')
    def update_reservation(self, reservation_id: str, user_id: str, 
                          start_date: str = None, end_date: str = None, 
                          promo_code: str = None) -> None:
        """Actualizar información de una reserva"""
        return self.repo.update_reservation(reservation_id, user_id, start_date, end_date, promo_code)
    
    @policy_check('reservations.update')
    def update_reservation_status(self, reservation_id: str, new_status: str, 
                                 user_id: str, notes: str = None) -> None:
        """Cambiar estado de una reserva"""
        return self.repo.update_reservation_status(reservation_id, new_status, user_id, notes)