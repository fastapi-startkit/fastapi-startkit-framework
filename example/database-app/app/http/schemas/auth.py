from pydantic import BaseModel, EmailStr, Field


class StudentRegistrationRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)


class TeacherRegistrationRequest(StudentRegistrationRequest):
    country: str = Field(..., min_length=2)
    phone_number: str
    headline: str = Field(..., min_length=5, max_length=255)
    description: str = Field(..., min_length=50)
    video_url: str
    hourly_rate: int = Field(..., gt=0)
    languages_spoken: list[str]
    subjects: list[str]
