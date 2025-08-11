from pydantic import BaseModel
from typing import List


class LastLessonItem(BaseModel):
    title: str
    date: str


class ProfileDataResponse(BaseModel):
    full_name: str
    email: str
    progress_percent: float
    completed_lessons: int
    total_lessons: int
    last_lessons: List[LastLessonItem]
