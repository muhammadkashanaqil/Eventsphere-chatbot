# from fastapi import FastAPI, HTTPException

# from models import (
#     ChatRequest,
#     ChatResponse,
#     IndexEventRequest,
#     IndexEventResponse
# )

# from chatbot import generate_event_answer

# from rag_service import (
#     index_event_knowledge
# )


# from rag_service import (
#     get_chat_history,
#     search_event_knowledge
# )

# app = FastAPI(
#     title="EventSphere RAG Chatbot",
#     version="2.0.0"
# )


# # =========================================================
# # ROOT
# # =========================================================

# @app.get("/")
# def root():

#     return {
#         "service": "EventSphere RAG Chatbot",
#         "status": "running",
#         "version": "2.0.0"
#     }


# # =========================================================
# # HEALTH
# # =========================================================

# @app.get("/health")
# def health():

#     return {
#         "status": "healthy"
#     }


# # =========================================================
# # INDEX / RE-INDEX EVENT
# #
# # Called when organizer publishes or updates an event.
# #
# # NOT called when visitor chats.
# # =========================================================

# @app.post(
#     "/index-event",
#     response_model=IndexEventResponse
# )
# def index_event(
#     request: IndexEventRequest
# ):

#     try:

#         chunks = index_event_knowledge(
#             event_id=str(request.event_id),
#             event_slug=request.event_slug,
#             event_data=request.event_data
#         )

#         return IndexEventResponse(
#             status="indexed",
#             event_id=request.event_id,
#             chunks=chunks
#         )

#     except Exception as e:

#         print(
#             f"INDEX ERROR [{request.event_id}]: {e}"
#         )

#         raise HTTPException(
#             status_code=500,
#             detail=f"Failed to index event: {str(e)}"
#         )


# # =========================================================
# # CHAT
# #
# # IMPORTANT:
# # No event indexing happens here.
# # =========================================================

# @app.post(
#     "/chat",
#     response_model=ChatResponse
# )
# def chat(request: ChatRequest):

#     try:

#         answer = generate_event_answer(
#             event_id=str(request.event_id),
#             session_id=str(request.session_id),
#             user_message=request.message
#         )

#         return ChatResponse(
#             answer=answer,
#             session_id=request.session_id
#         )

#     except Exception as e:

#         print(
#             f"CHAT ERROR [{request.event_id}]: {e}"
#         )

#         raise HTTPException(
#             status_code=500,
#             detail=f"Chat failed: {str(e)}"
#         )
        
        
# @app.post("/debug-rag")
# def debug_rag(request: ChatRequest):

#     history = get_chat_history(
#         event_id=str(request.event_id),
#         session_id=str(request.session_id),
#         limit=4
#     )

#     matches = search_event_knowledge(
#         event_id=str(request.event_id),
#         question=request.message,
#         match_count=3
#     )

#     return {
#         "history": history,
#         "matches": matches
#     }







"""
main.py  -  FastAPI service called by the Java backend.

Endpoints
---------
POST /index-event   Java calls this when an event is published/updated
POST /chat          full answer in one response (kept as a fallback)
POST /chat/stream   answer streamed word by word (Server-Sent Events)  <- use this
GET  /health

Security: every endpoint except / and /health needs the header
    X-Internal-Key: <CHATBOT_API_KEY>
Without it, anyone who finds this URL could index fake data or burn your Gemini quota.
"""

import hmac
import json
import logging
import os

from dotenv import load_dotenv
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("api")

from chatbot import generate_event_answer, stream_event_answer  # noqa: E402
from models import (  # noqa: E402
    ChatRequest,
    ChatResponse,
    IndexEventRequest,
    IndexEventResponse,
)
from rag_service import (  # noqa: E402
    get_chat_history,
    index_event_knowledge,
    save_chat_turn,
    search_event_knowledge,
)

CHATBOT_API_KEY = os.getenv("CHATBOT_API_KEY", "")

if not CHATBOT_API_KEY:
    log.warning("CHATBOT_API_KEY is empty - the API is OPEN. Fine for local dev, never in production.")


def require_internal_key(x_internal_key: str | None = Header(default=None)) -> None:
    if not CHATBOT_API_KEY:
        return  # local development
    if not x_internal_key or not hmac.compare_digest(x_internal_key, CHATBOT_API_KEY):
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI(title="EventSphere RAG Chatbot", version="3.0.0")

auth = [Depends(require_internal_key)]


# =========================================================
# HEALTH
# =========================================================

@app.get("/")
def root():
    return {"service": "EventSphere RAG Chatbot", "status": "running", "version": "3.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}


# =========================================================
# INDEX / RE-INDEX  (organizer publishes or edits an event)
# =========================================================

@app.post("/index-event", response_model=IndexEventResponse, dependencies=auth)
def index_event(request: IndexEventRequest):
    try:
        chunks = index_event_knowledge(
            event_id=str(request.event_id),
            event_data=request.event_data,
            event_slug=request.event_slug,
        )
        return IndexEventResponse(status="indexed", event_id=request.event_id, chunks=chunks)

    except Exception:
        log.exception("INDEX ERROR [%s]", request.event_id)
        raise HTTPException(status_code=500, detail="Failed to index event")


# =========================================================
# CHAT - full answer (fallback)
# =========================================================

def _save_turn_task(event_id: str, session_id: str, user_message: str, answer: str) -> None:
    try:
        save_chat_turn(event_id, session_id, user_message, answer)
    except Exception:
        log.exception("Could not save chat history")


@app.post("/chat", response_model=ChatResponse, dependencies=auth)
def chat(request: ChatRequest, background: BackgroundTasks):
    try:
        event_id = str(request.event_id)
        session_id = str(request.session_id)

        answer, cleaned = generate_event_answer(event_id, session_id, request.message)

        # Saved AFTER the response is sent, so it adds no waiting time.
        # background.add_task(_save_turn_task, event_id, session_id, cleaned, answer)

        _save_turn_task(event_id, session_id, cleaned, answer)
        
        return ChatResponse(answer=answer, session_id=request.session_id)

    except Exception:
        log.exception("CHAT ERROR [%s]", request.event_id)
        raise HTTPException(status_code=500, detail="Chat failed")


# =========================================================
# CHAT - streaming (Server-Sent Events)
#
# Every event is one line:   data: {...json...}
#   {"t": "some text"}                      a piece of the answer
#   {"done": true, "session_id": "..."}     finished
#   {"error": "message"}                    failed before/while answering
# =========================================================

def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@app.post("/chat/stream", dependencies=auth)
def chat_stream(request: ChatRequest):

    def event_stream():
        try:
            for text in stream_event_answer(
                event_id=str(request.event_id),
                session_id=str(request.session_id),
                user_message=request.message,
            ):
                yield _sse({"t": text})

            yield _sse({"done": True, "session_id": str(request.session_id)})

        except Exception:
            log.exception("STREAM ERROR [%s]", request.event_id)
            yield _sse({"error": "The assistant is unavailable right now. Please try again."})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # tell proxies (nginx etc.) not to buffer
        },
    )


# =========================================================
# DEBUG (off by default, still needs the key)
# =========================================================

if os.getenv("DEBUG_RAG") == "1":

    @app.post("/debug-rag", dependencies=auth)
    def debug_rag(request: ChatRequest):
        return {
            "history": get_chat_history(str(request.event_id), str(request.session_id), limit=4),
            "matches": search_event_knowledge(str(request.event_id), request.message, match_count=3),
        }
