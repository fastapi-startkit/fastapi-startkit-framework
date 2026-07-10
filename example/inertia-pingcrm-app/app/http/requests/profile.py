from fastapi_startkit.fastapi import RequestModel


class ProfileUpdateRequest(RequestModel):
    first_name: str
    last_name: str
    email: str
    password: str = ""
