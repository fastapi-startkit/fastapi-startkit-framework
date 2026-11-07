from typing import Annotated

from fastapi_startkit.validation import Email, Field, FormRequest


class LoginRequest(FormRequest):
    email: Annotated[str, Email().required()]
    password: Annotated[str, Field().required().string()]
