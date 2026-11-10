# # from typing import Any
# # from pydantic import BaseModel


# # class ChatRequest(BaseModel):
# #     event_slug: str
# #     message: str
# #     session_id: str | None = None


# # class ChatResponse(BaseModel):
# #     answer: str
# #     session_id: str | None = None


# # class IndexEventRequest(BaseModel):
# #     event_slug: str
# #     event_data: dict[str, Any]


# # class IndexEventResponse(BaseModel):
# #     status: str
# #     event_slug: str
# #     chunks: int


# from uuid import UUID
# from typing import Any
# from pydantic import BaseModel


# class ChatRequest(BaseModel):
#     event_id: UUID
#     message: str
#     session_id: UUID


# class ChatResponse(BaseModel):
#     answer: str
#     session_id: UUID


# class IndexEventRequest(BaseModel):
#     event_id: UUID
#     event_data: dict[str, Any]
    
    
    
# class IndexEventResponse(BaseModel):
#     status: str
#     event_id: UUID
#     chunks: int



from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    event_id: UUID
    message: str = Field(min_length=1, max_length=500)
    session_id: UUID

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        # collapse whitespace so "  hi   there " and "hi there" are treated the same
        value = " ".join(value.split())
        if not value:
            raise ValueError("message cannot be empty")
        return value


class ChatResponse(BaseModel):
    answer: str
    session_id: UUID


class IndexEventRequest(BaseModel):
    event_id: UUID
    event_data: dict[str, Any]
    # Java still sends event_slug ("temporary compatibility"). It MUST be a field here,
    # otherwise request.event_slug raises AttributeError and every index call fails.
    event_slug: str | None = None


class IndexEventResponse(BaseModel):
    status: str
    event_id: UUID
    chunks: int
