from typing import Optional

from pydantic import BaseModel


class Address(BaseModel):
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
