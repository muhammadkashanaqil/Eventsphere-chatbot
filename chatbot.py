import os
import json

from dotenv import load_dotenv
from google import genai


load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

from rag_service import (
    has_event_knowledge,
    index_event_knowledge,
    search_event_knowledge
)


def generate_event_answer(
    event_slug: str,
    event_data: dict,
    user_message: str
):

    # First time this event is used:
    # create its RAG knowledge automatically
    if not has_event_knowledge(event_slug):

        index_event_knowledge(
            event_slug,
            event_data
        )

    # Retrieve only relevant information
    matches = search_event_knowledge(
        event_slug=event_slug,
        question=user_message,
        match_count=5
    )

    if matches:

        context = "\n\n".join(
            f"Section: {item['section']}\n"
            f"{item['content']}"
            for item in matches
        )

    else:
        context = "No relevant event information was found."


    prompt = f"""
You are the official AI Event Assistant for EventSphere.

Answer using ONLY the retrieved event information below.

Do not invent:
- ticket prices
- dates
- times
- locations
- schedules
- sponsors
- policies

If the information is not available, clearly say that
you do not have that information.

CURRENT EVENT:
{event_slug}

RETRIEVED EVENT INFORMATION:

{context}

VISITOR QUESTION:

{user_message}
"""

    interaction = client.interactions.create(
        model="gemini-3.8-flash",
        input=prompt
    )

    return interaction.output_text