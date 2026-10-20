import uuid
from typing import Annotated

from pydantic import BaseModel, StringConstraints

QuestionText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class ChatRequest(BaseModel):
    message: QuestionText
    chat_id: uuid.UUID | None = None