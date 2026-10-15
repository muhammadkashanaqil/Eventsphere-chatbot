import os

from dotenv import load_dotenv
from google import genai

from rag_service import search_event_knowledge


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
        event_slug: str,
        user_message: str
) -> str:

    # =====================================================
    # 1. Retrieve only relevant RAG knowledge
    # =====================================================

    matches = search_event_knowledge(
        event_slug=event_slug,
        question=user_message,
        match_count=4
    )


    # Event hasn't been indexed yet or no knowledge found.
    if not matches:

        return (
            "I don't have enough information about this "
            "event yet. Please contact the event organizer."
        )


    # =====================================================
    # 2. Build small context from retrieved chunks
    # =====================================================

    context_parts = []

    for item in matches:

        context_parts.append(
            f"""
Section: {item['section']}
Information:
{item['content']}
""".strip()
        )


    context = "\n\n".join(
        context_parts
    )


    # =====================================================
    # 3. Gemini only receives retrieved information
    # =====================================================

    prompt = f"""
You are the official AI Event Assistant for EventSphere.

Your job is to answer questions about ONE event.

EVENT:
{event_slug}

RULES:

1. Use ONLY the retrieved event information below.
2. Never invent ticket prices.
3. Never invent dates or times.
4. Never invent locations.
5. Never invent schedules.
6. Never invent sponsors.
7. Never invent policies.
8. If the answer cannot be found in the retrieved
   information, clearly say that the information
   is not available.
9. Keep your response concise and helpful.
10. Respond in the user's language when possible.

RETRIEVED EVENT INFORMATION:

{context}

VISITOR QUESTION:

{user_message}
"""


    # =====================================================
    # 4. Generate answer
    # =====================================================

    interaction = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt
    )


    answer = interaction.output_text


    if not answer:
        return (
            "I couldn't generate an answer right now. "
            "Please try again."
        )


    return answer