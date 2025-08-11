from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class NoteIn(BaseModel):
    content: str


class NoteOut(BaseModel):
    id: UUID
    lesson_id: UUID
    content: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    detail: str
    id: str | None = None