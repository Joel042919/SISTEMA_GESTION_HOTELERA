from typing import List, Optional, Dict
from .base import policy_check
from app.repositories.pg_repo import PgRepo
from app.core.security import hash_password

class UsersService:
    def __init__(self, repo: PgRepo):
        self.repo = repo

    # ----- Roles -----
    @policy_check('users.roles.list')
    def list_roles(self) -> List[tuple]:
        return self.repo.list_roles()

    # ----- CRUD usuarios -----
    @policy_check('users.list')
    def list_users(self, property_id: str) -> List[Dict]:
        return self.repo.list_users_with_roles(property_id)

    @policy_check('users.get')
    def get_user(self, user_id: str, property_id: str) -> Optional[Dict]:
        return self.repo.get_user_with_roles(user_id, property_id)

    @policy_check('users.create')
    def create_user(self, email: str, full_name: str, plain_password: str,
                    is_active: bool, role_ids: List[str], property_id: str) -> str:
        pwd_hash = hash_password(plain_password)
        uid = self.repo.create_user(email, full_name, pwd_hash, is_active)
        self.repo.replace_user_roles(uid, role_ids, property_id)
        return uid

    @policy_check('users.update')
    def update_user(self, user_id: str, email: str, full_name: str,
                    maybe_plain_password: Optional[str],
                    is_active: bool, role_ids: List[str], property_id: str) -> None:
        pwd_hash = None
        if maybe_plain_password and maybe_plain_password.strip():
            pwd_hash = hash_password(maybe_plain_password.strip())
        self.repo.update_user(user_id, email, full_name, pwd_hash, is_active)
        self.repo.replace_user_roles(user_id, role_ids, property_id)

    @policy_check('users.set_active')
    def set_active(self, user_id: str, is_active: bool) -> None:
        self.repo.set_user_active(user_id, is_active)
