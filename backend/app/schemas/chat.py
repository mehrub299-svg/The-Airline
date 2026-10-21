import uuid
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
DocumentIds = Annotated[list[uuid.UUID], Field(min_length=1, max_length=50)]


class ChatRequest(BaseModel):
    message: QuestionText
    chat_id: uuid.UUID | None = None
    document_ids: DocumentIds | None = None  # omitted = answer from all documents


class ChatSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    created_at: datetime