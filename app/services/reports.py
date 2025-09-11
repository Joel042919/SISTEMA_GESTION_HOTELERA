from app.repositories.pg_repo import PgRepo

class ReportsService:
    def __init__(self, repo: PgRepo):
        self.repo = repo

    def daily(self, property_id: str, the_date: str):
        return self.repo.daily_kpis(property_id, the_date)
