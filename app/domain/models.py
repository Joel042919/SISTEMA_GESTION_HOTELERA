from pydantic import BaseModel, Field
from typing import Optional, List


class Guest(BaseModel):
    id: Optional[str]
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None


class ReservationQuote(BaseModel):
    nights: int
    base_total: float
    promo_discount: float
    tax_total: float
    grand_total: float
    nightly: list