from .base import policy_check
from app.repositories.pg_repo import PgRepo
from typing import Optional, List, Dict


class GuestsService:
    """Servicio para gestionar operaciones CRUD de huéspedes"""
    
    def __init__(self, repo: PgRepo):
        self.repo = repo

    @policy_check('users.manage')  # Usando permiso existente para gestión
    def create_guest(self, full_name: str, email: Optional[str] = None, 
                    phone: Optional[str] = None, preferences: Optional[Dict] = None) -> str:
        """Crear un nuevo huésped"""
        return self.repo.create_guest(full_name, email, phone, preferences)

    @policy_check('reservations.view')  # Permiso para ver huéspedes al hacer reservas
    def list_guests(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Listar huéspedes con paginación"""
        return self.repo.list_guests(limit, offset)

    @policy_check('reservations.view')
    def get_guest(self, guest_id: str) -> Optional[Dict]:
        """Obtener un huésped por su ID"""
        return self.repo.get_guest(guest_id)

    @policy_check('users.manage')
    def update_guest(self, guest_id: str, full_name: Optional[str] = None, 
                    email: Optional[str] = None, phone: Optional[str] = None, 
                    preferences: Optional[Dict] = None):
        """Actualizar información de un huésped"""
        self.repo.update_guest(guest_id, full_name, email, phone, preferences)

    @policy_check('reservations.view')
    def search_guests(self, query: str) -> List[Dict]:
        """Buscar huéspedes por nombre o email"""
        # Por simplicidad, filtramos en memoria. En producción sería mejor hacer la búsqueda en BD
        all_guests = self.repo.list_guests(limit=1000)  # Límite alto para búsqueda
        query_lower = query.lower()
        
        return [
            guest for guest in all_guests 
            if query_lower in (guest.get('full_name', '') or '').lower() or 
               query_lower in (guest.get('email', '') or '').lower()
        ]