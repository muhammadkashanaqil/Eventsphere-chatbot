from fastapi import FastAPI, HTTPException

from models import (
    ChatRequest,
    ChatResponse,
    IndexEventRequest,
    IndexEventResponse
)

from chatbot import generate_event_answer

from rag_service import (
    index_event_knowledge
)


app = FastAPI(
    title="EventSphere RAG Chatbot",
    version="2.0.0"
)


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "service": "EventSphere RAG Chatbot",
        "status": "running",
        "version": "2.0.0"
    }


# =========================================================
# HEALTH
# =========================================================

@app.get("/health")
def health():

    return {
        "status": "healthy"
    }


# =========================================================
# INDEX / RE-INDEX EVENT
#
# Called when organizer publishes or updates an event.
#
# NOT called when visitor chats.
# =========================================================

@app.post(
    "/index-event",
    response_model=IndexEventResponse
)
def index_event(
    request: IndexEventRequest
):

    try:

        chunks = index_event_knowledge(
            event_id=str(request.event_id),
            event_slug=request.event_slug,
            event_data=request.event_data
        )

        return IndexEventResponse(
            status="indexed",
            event_id=request.event_id,
            chunks=chunks
        )

    except Exception as e:

        print(
            f"INDEX ERROR [{request.event_id}]: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Failed to index event: {str(e)}"
        )


# =========================================================
# CHAT
#
# IMPORTANT:
# No event indexing happens here.
# =========================================================

@app.post(
    "/chat",
    response_model=ChatResponse
)
def chat(request: ChatRequest):

    try:

        answer = generate_event_answer(
            event_id=str(request.event_id),
            session_id=str(request.session_id),
            user_message=request.message
        )

        return ChatResponse(
            answer=answer,
            session_id=request.session_id
        )

    except Exception as e:

        print(
            f"CHAT ERROR [{request.event_id}]: {e}"
        )

        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )