from uuid import UUID

from pydantic import BaseModel


class CourseCreate(BaseModel):
    title: str
    description: str


class CourseResponse(BaseModel):
    id: UUID
    title: str
    description: str | None = None

    model_config = {"from_attributes": True}
