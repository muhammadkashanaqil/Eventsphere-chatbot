import os

from dotenv import load_dotenv
from google import genai


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
    api_key=GEMINI_API_KEY
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
        limit=8
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

    retrieval_query = f"""
Previous conversation:
{history_text}

Current question:
{user_message}
"""


    # -----------------------------------------
    # 3. RAG search by EVENT ID
    # -----------------------------------------

    matches = search_event_knowledge(
        event_id=event_id,
        question=retrieval_query,
        match_count=4
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
        model="gemini-3.8-flash",
        input=prompt
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