from .base import policy_check
from app.repositories.pg_repo import PgRepo


class BillingService:
    def __init__(self, repo: PgRepo):
        self.repo = repo


    @policy_check('billing.charge')
    def post_charge(self, reservation_id, concept, amount, tax_code, user_id):
        self.repo.post_charge(reservation_id, concept, amount, tax_code, user_id)


    @policy_check('billing.pay')
    def register_payment(self, reservation_id, method, amount, currency, user_id):
        self.repo.register_payment(reservation_id, method, amount, currency, user_id)


    @policy_check('billing.view')
    def checkout(self, reservation_id, extra, user_id):
        return self.repo.checkout(reservation_id, extra, user_id)