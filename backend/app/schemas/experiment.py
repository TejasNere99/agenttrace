from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import ApiSchema, ObjectIdString


class ExperimentCreate(ApiSchema):
    name: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=3000)
    run_ids: list[ObjectIdString] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be blank")
        return value

    @field_validator("run_ids")
    @classmethod
    def no_duplicate_runs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("run_ids cannot contain duplicates")
        return value


class ExperimentResponse(ApiSchema):
    id: ObjectIdString
    name: str
    description: str | None = None
    run_ids: list[ObjectIdString] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
