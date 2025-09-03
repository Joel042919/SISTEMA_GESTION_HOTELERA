from .base import policy_check
from app.repositories.pg_repo import PgRepo


class RoomsService:
    def __init__(self, repo: PgRepo):
        self.repo = repo


    @policy_check('rooms.update_status')
    def set_status(self, room_id, status, user_id):
        self.repo.set_room_status(room_id, status, user_id)