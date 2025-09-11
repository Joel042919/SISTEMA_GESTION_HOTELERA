from app.repositories.pg_repo import PgRepo

class RoomsService:
    def __init__(self, repo: PgRepo):
        self.repo = repo

    def set_status(self, room_id: str, new_status: str, user_id: str):
        self.repo.set_room_status(room_id, new_status, user_id)
