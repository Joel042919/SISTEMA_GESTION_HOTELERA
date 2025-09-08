from .base import policy_check
from app.repositories.pg_repo import PgRepo
from typing import List,Tuple

class RoomsService:
    def __init__(self, repo: PgRepo):
        self.repo = repo
    
    @policy_check('rooms.view')
    def list_room_types(self,property_id:str)->List[Tuple[str,str]]:
        return self.repo.list_room_types(property_id)
    
    @policy_check('rooms.viewAvailable')
    def list_rooms_available(self,property_id:str,startDate:str,endDate:str)->List[Tuple[str,str]]:
        return self.repo.list_rooms_available(property_id,startDate,endDate)

    @policy_check('rooms.update_status')
    def set_status(self, room_id, status, user_id):
        self.repo.set_room_status(room_id, status, user_id)