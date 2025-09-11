from app.repositories.pg_repo import PgRepo

class ReportsService:
    def __init__(self, repo: PgRepo):
        self.repo = repo

<<<<<<< HEAD
    def daily(self, property_id: str, the_date: str):
        return self.repo.daily_kpis(property_id, the_date)
=======

    @policy_check('reports.view')
    def daily(self, property_id: str, date: str):
        return self.repo.report_daily(property_id, date)
>>>>>>> d1211c539bdfdfa1792f6acac0f7a72d1438d3ff
