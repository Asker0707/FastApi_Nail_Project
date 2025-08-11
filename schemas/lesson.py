from uuid import UUID

from pydantic import BaseModel


class LessonResponse(BaseModel):
    id: UUID
    title: str
    video_path: str | None = None
    text_content: str | None = None

    model_config = {"from_attributes": True}
