import os

from dotenv import load_dotenv
from google import genai
from dotenv import load_dotenv
from google.genai import types

from rag_service import (
    search_event_knowledge,
    get_chat_history,
    save_chat_message
)


load_dotenv()


GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing"
    )


client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=20000,  # 20 seconds
        retry_options=types.HttpRetryOptions(
            attempts=1
        )
    )
)


def generate_event_answer(
    event_id: str,
    session_id: str,
    user_message: str
) -> str:

    # -----------------------------------------
    # 1. Load previous conversation
    # -----------------------------------------

    history = get_chat_history(
    event_id=event_id,
    session_id=session_id,
    limit=4
)
    if history:

        history_text = "\n".join(
            f"{item['role'].upper()}: {item['content']}"
            for item in history
        )

    else:

        history_text = "No previous conversation."


    # -----------------------------------------
    # 2. Make retrieval query context-aware
    # -----------------------------------------

    recent_history = history[-2:]

    recent_history_text = "\n".join(
    f"{item['role']}: {item['content']}"
    for item in recent_history
)

    retrieval_query = f"""
Context:
{recent_history_text}

Question:
{user_message}
"""


    # -----------------------------------------
    # 3. RAG search by EVENT ID
    # -----------------------------------------

    matches = search_event_knowledge(
    event_id=event_id,
    question=retrieval_query,
    match_count=3
)


    if not matches:

        answer = (
            "I don't have enough information "
            "about this event."
        )

        save_chat_message(
            event_id,
            session_id,
            "user",
            user_message
        )

        save_chat_message(
            event_id,
            session_id,
            "assistant",
            answer
        )

        return answer


    # -----------------------------------------
    # 4. Build retrieved event context
    # -----------------------------------------

    context = "\n\n".join(

        f"Section: {item['section']}\n"
        f"Information: {item['content']}"

        for item in matches
    )


    # -----------------------------------------
    # 5. Give Gemini BOTH contexts
    # -----------------------------------------

    prompt = f"""
You are the official EventSphere AI Event Assistant.

EVENT ID:
{event_id}

PREVIOUS CONVERSATION:
{history_text}

RETRIEVED EVENT INFORMATION:
{context}

CURRENT USER MESSAGE:
{user_message}

RULES:

1. Use the retrieved event information for factual answers.
2. Use previous conversation to understand references such as:
   "it", "they", "there", "that ticket", "what about VIP".
3. Never invent ticket prices.
4. Never invent dates or times.
5. Never invent locations.
6. Never invent schedules or policies.
7. If information is unavailable, clearly say so.
8. Keep answers concise and helpful.
9. Respond in the user's language when possible.
"""


    interaction = client.interactions.create(
    model="gemini-3.5-flash-lite",
    input=prompt,
    generation_config={
        "thinking_level": "minimal"
    }
)

    answer = interaction.output_text


    if not answer:

        answer = (
            "I couldn't generate an answer right now."
        )


    # -----------------------------------------
    # 6. Store conversation
    # -----------------------------------------

    save_chat_message(
        event_id,
        session_id,
        "user",
        user_message
    )

    save_chat_message(
        event_id,
        session_id,
        "assistant",
        answer
    )


    return answer



import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types

from rag_service import (
    search_event_knowledge,
    get_chat_history,
    save_chat_turn
)


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing"
    )


# =========================================================
# GEMINI CLIENT
#
# IMPORTANT:
# Fast timeout + NO retries.
#
# We do not want Gemini hanging for 2-3 minutes.
# =========================================================

client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=15000,  # 15 seconds
        retry_options=types.HttpRetryOptions(
            attempts=1
        )
    )
)


# =========================================================
# GENERATE EVENT ANSWER
# =========================================================

def generate_event_answer(
        event_id: str,
        session_id: str,
        user_message: str
) -> str:

    total_start = time.perf_counter()

    print(
        f"[CHAT] Starting request "
        f"event={event_id} "
        f"session={session_id}"
    )


    # =====================================================
    # 1. LOAD CONVERSATION HISTORY
    #
    # Only last 4 messages.
    # =====================================================

    history_start = time.perf_counter()

    history = get_chat_history(
        event_id=event_id,
        session_id=session_id,
        limit=4
    )

    print(
        f"[CHAT] History step: "
        f"{time.perf_counter() - history_start:.2f}s"
    )


    # -----------------------------------------------------
    # Full short history for final Gemini prompt
    # -----------------------------------------------------

    if history:

        history_text = "\n".join(
            f"{item['role'].upper()}: "
            f"{item['content']}"
            for item in history
        )

    else:

        history_text = (
            "No previous conversation."
        )


    # =====================================================
    # 2. BUILD SMALL RETRIEVAL QUERY
    #
    # Do NOT embed the entire conversation.
    #
    # Only last 2 messages + current question.
    # =====================================================

    recent_history = history[-2:]


    if recent_history:

        recent_history_text = "\n".join(
            f"{item['role']}: "
            f"{item['content']}"
            for item in recent_history
        )

    else:

        recent_history_text = ""


    retrieval_query = (
        f"Recent conversation:\n"
        f"{recent_history_text}\n\n"
        f"Current question:\n"
        f"{user_message}"
    )


    # =====================================================
    # 3. RAG VECTOR SEARCH
    #
    # Only TOP 3 chunks.
    # =====================================================

    rag_start = time.perf_counter()

    matches = search_event_knowledge(
        event_id=event_id,
        question=retrieval_query,
        match_count=3
    )

    print(
        f"[CHAT] RAG step: "
        f"{time.perf_counter() - rag_start:.2f}s"
    )


    # =====================================================
    # 4. NO RAG RESULTS
    # =====================================================

    if not matches:

        answer = (
            "I don't have enough information "
            "about this event."
        )


        # One Supabase request instead of two
        save_start = time.perf_counter()

        save_chat_turn(
            event_id=event_id,
            session_id=session_id,
            user_message=user_message,
            assistant_message=answer
        )

        print(
            f"[CHAT] Save turn: "
            f"{time.perf_counter() - save_start:.2f}s"
        )

        print(
            f"[CHAT] TOTAL: "
            f"{time.perf_counter() - total_start:.2f}s"
        )

        return answer


    # =====================================================
    # 5. BUILD SMALL RAG CONTEXT
    # =====================================================

    context_parts = []


    for item in matches:

        context_parts.append(
            f"Section: {item['section']}\n"
            f"{item['content']}"
        )


    context = "\n\n".join(
        context_parts
    )


    # =====================================================
    # 6. BUILD FINAL GEMINI PROMPT
    #
    # Keep it short.
    # =====================================================

    prompt = f"""
You are the EventSphere AI Event Assistant.

Answer questions about this event using ONLY the event
information provided below.

EVENT INFORMATION:
{context}

RECENT CONVERSATION:
{history_text}

CURRENT QUESTION:
{user_message}

RULES:
- Use the event information for factual answers.
- Use conversation history only to understand references
  like "it", "they", "there", "that one", or "what about VIP".
- Never invent ticket prices.
- Never invent dates or times.
- Never invent locations.
- Never invent schedules.
- Never invent sponsors or policies.
- If the answer is not available, clearly say so.
- Keep the answer short and direct.
- Do not explain your reasoning.
- Respond in the user's language when possible.
""".strip()


    # =====================================================
    # 7. GEMINI GENERATION
    #
    # Flash-Lite + minimal thinking
    # =====================================================

    generation_start = time.perf_counter()


    try:

        interaction = client.interactions.create(
            model="gemini-3.5-flash-lite",
            input=prompt,
            generation_config={
                "thinking_level": "minimal",
                "max_output_tokens": 250
            }
        )


        print(
            f"[CHAT] Gemini generation: "
            f"{time.perf_counter() - generation_start:.2f}s"
        )


    except Exception as e:

        elapsed = (
            time.perf_counter()
            - generation_start
        )

        print(
            f"[CHAT] Gemini FAILED after "
            f"{elapsed:.2f}s: {e}"
        )

        # IMPORTANT:
        # Fail quickly so Java polling job becomes FAILED
        # instead of Vercel waiting until FUNCTION_TIMEOUT.
        raise RuntimeError(
            f"Gemini response timed out or failed: {e}"
        ) from e


    # =====================================================
    # 8. GET ANSWER
    # =====================================================

    answer = interaction.output_text


    if not answer:

        answer = (
            "I couldn't generate an answer "
            "right now."
        )


    answer = answer.strip()


    # =====================================================
    # 9. SAVE USER + ASSISTANT IN ONE DATABASE CALL
    # =====================================================

    save_start = time.perf_counter()


    try:

        save_chat_turn(
            event_id=event_id,
            session_id=session_id,
            user_message=user_message,
            assistant_message=answer
        )


        print(
            f"[CHAT] Save conversation: "
            f"{time.perf_counter() - save_start:.2f}s"
        )


    except Exception as e:

        # Chat answer succeeded, so don't destroy the
        # answer just because history storage failed.
        print(
            f"[CHAT] WARNING: "
            f"Could not save history: {e}"
        )


    # =====================================================
    # 10. TOTAL TIMING
    # =====================================================

    total_elapsed = (
        time.perf_counter()
        - total_start
    )


    print(
        f"[CHAT] TOTAL RESPONSE TIME: "
        f"{total_elapsed:.2f}s"
    )


    return answer