from fastapi import FastAPI, HTTPException

from models import ChatRequest, ChatResponse
from chatbot import generate_event_answer


app = FastAPI(
    title="EventSphere AI Chatbot",
    version="1.0.0"
)


@app.get("/")
def root():
    return {
        "service": "EventSphere AI Chatbot",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):

    try:

        answer = generate_event_answer(
            event_data=request.event_data,
            user_message=request.message
        )

        return ChatResponse(
            answer=answer,
            session_id=request.session_id
        )

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )