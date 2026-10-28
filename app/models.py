from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class CreateUserRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    temporary_password: str = Field(min_length=10, max_length=128)
    role: Literal["student", "admin"] = "student"
    attempts_allowed: int = Field(default=1, ge=1, le=20)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return " ".join(value.split())


class BulkUserItem(CreateUserRequest):
    role: Literal["student"] = "student"


class BulkUsersRequest(BaseModel):
    users: list[BulkUserItem] = Field(min_length=1, max_length=100)


class ResetPasswordRequest(BaseModel):
    temporary_password: str = Field(min_length=10, max_length=128)


class StatusRequest(BaseModel):
    status: Literal["active", "disabled"]


class AttemptsRequest(BaseModel):
    attempts_allowed: int = Field(ge=1, le=20)


class UpdateUserRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=100)
    email: EmailStr | None = None
    role: Literal["student", "admin"] | None = None

    @field_validator("name")
    @classmethod
    def clean_optional_name(cls, value: str | None) -> str | None:
        return " ".join(value.split()) if value is not None else None


class TeacherOverrideRequest(BaseModel):
    teacher_level: Literal["", "Below A2", "A2", "B1", "B2", "Teacher review required"] = ""
    teacher_notes: str = Field(default="", max_length=5000)
