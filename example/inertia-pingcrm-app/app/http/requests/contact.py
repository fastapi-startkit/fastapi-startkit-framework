from pydantic import BaseModel
from typing import Optional


class ContactListRequest:
    def __init__(self, search: str = "", page: int = 1, limit: int = 10):
        self.search = search
        self.page = page
        self.limit = limit


class ContactStoreRequest(BaseModel):
    first_name: str
    last_name: str
    organization_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None


class ContactUpdateRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    organization_id: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
