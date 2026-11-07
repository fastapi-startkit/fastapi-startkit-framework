from typing import Annotated

from fastapi_startkit.validation import Email, Field, FormRequest


class RegisterRequest(FormRequest):
    name: Annotated[str, Field().required().string()]
    email: Annotated[str, Email().required().unique("users")]
    password: Annotated[str, Field().required().string().min(8)]
