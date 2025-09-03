from app.repositories.pg_repo import PgRepo
from .base import policy_check


class ReportsService:
    def __init__(self, repo: PgRepo):
        self.repo = repo


@policy_check('reports.view')
def daily(self, property_id: str, date: str):
    return self.repo.report_daily(property_id, date)