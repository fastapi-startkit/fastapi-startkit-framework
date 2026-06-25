from enum import StrEnum

from pydantic import BaseModel


class Route(StrEnum):
    JOB_SEARCH: str
    CHAT: str
