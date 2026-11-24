from datetime import datetime

from pydantic import Field, field_validator, model_validator

from app.schemas.common import ApiSchema, ObjectIdString


class ProjectCreate(ApiSchema):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value


class ProjectUpdate(ApiSchema):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @model_validator(mode="after")
    def require_patch_field(self) -> "ProjectUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one supported field must be provided")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("Name cannot be null")
        return self


class ProjectResponse(ApiSchema):
    id: ObjectIdString
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime
