from app.repositories.pg_repo import PgRepo

class BillingService:
    def __init__(self, repo: PgRepo):
        self.repo = repo

    def post_charge(self, reservation_id, concept, amount, tax_code, user_id):
        self.repo.post_charge(reservation_id, concept, amount, tax_code, user_id)

    def register_payment(self, reservation_id, method, amount, currency, user_id):
        self.repo.register_payment(reservation_id, method, amount, currency, user_id)

    def close_cash(self, property_id, the_date, user_id):
        return self.repo.close_cash(property_id, the_date, user_id)
