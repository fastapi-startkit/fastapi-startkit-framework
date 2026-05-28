from typing import Optional
from fastapi_startkit.masoniteorm.models import Model


class Organization(Model):
    """Organization Model."""

    __table__ = "organizations"

    id: int
    account_id: int
    name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    region: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]
