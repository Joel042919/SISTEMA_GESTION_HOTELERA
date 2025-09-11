from .base import policy_check
from app.repositories.pg_repo import PgRepo
from typing import Optional

class GuestsHotelService:
    def __init__(self, repo: PgRepo):
        self.repo = repo
    
    @policy_check('guests.crear')
    def create_guests(self,full_name:str,dni:str,phone:str,email:Optional[str],preferences:Optional[dict]):
        return self.repo.create_guests(full_name,dni,phone,email,preferences)
    
    @policy_check('guests.buscar')
    def search_guest_by_dni(self,dni:str):
        return self.repo.search_guest_by_dni(dni)


