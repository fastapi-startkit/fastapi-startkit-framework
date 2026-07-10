from typing import Optional
from fastapi_startkit.masoniteorm.models import Model


class Contact(Model):
    """Contact Model."""

    __table__ = "contacts"

    id: int
    account_id: int
    organization_id: Optional[int]
    first_name: str
    last_name: str
    email: Optional[str]
    phone: Optional[str]
    address: Optional[str]
    city: Optional[str]
    region: Optional[str]
    country: Optional[str]
    postal_code: Optional[str]

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"
