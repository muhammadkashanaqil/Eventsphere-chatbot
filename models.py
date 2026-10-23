# from typing import Any
# from pydantic import BaseModel


# class ChatRequest(BaseModel):
#     event_slug: str
#     message: str
#     session_id: str | None = None


# class ChatResponse(BaseModel):
#     answer: str
#     session_id: str | None = None


# class IndexEventRequest(BaseModel):
#     event_slug: str
#     event_data: dict[str, Any]


# class IndexEventResponse(BaseModel):
#     status: str
#     event_slug: str
#     chunks: int


from uuid import UUID
from typing import Any
from pydantic import BaseModel


class ChatRequest(BaseModel):
    event_id: UUID
    message: str
    session_id: UUID


class ChatResponse(BaseModel):
    answer: str
    session_id: UUID


class IndexEventRequest(BaseModel):
    event_id: UUID
    event_data: dict[str, Any]
    
    
    
class IndexEventResponse(BaseModel):
    status: str
    event_id: UUID
    chunks: int