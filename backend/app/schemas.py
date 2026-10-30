from typing import Literal

from pydantic import BaseModel, Field, field_validator


class LoginInput(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class UserInput(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=10, max_length=128)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        if not value.strip():
            raise ValueError("Имя не может быть пустым")
        return value.strip()


class NameInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value):
        if not value.strip():
            raise ValueError("Название не может быть пустым")
        return value.strip()


class FolderInput(NameInput):
    category: Literal["stress", "spelling", "grammar"]


class ListInput(NameInput):
    raw: str = Field(min_length=1, max_length=1024 * 1024)


class ParseInput(BaseModel):
    category: Literal["stress", "spelling", "grammar"]
    raw: str = Field(min_length=1, max_length=1024 * 1024)


class ProfileInput(NameInput):
    kind: Literal["student", "group"] = "student"
    note: str = Field(default="", max_length=1000)


class AttachInput(BaseModel):
    list_id: int


class SessionInput(BaseModel):
    list_id: int | None = None
    list_ids: list[int] = Field(default_factory=list, max_length=100)
    item_ids: list[int] = Field(min_length=1, max_length=3000)


class AdvanceInput(BaseModel):
    item_id: int


class AnswerInput(BaseModel):
    item_id: int
    choices: list[str | int] = Field(min_length=1, max_length=100)
