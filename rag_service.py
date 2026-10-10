import os
import json


from supabase import create_client, Client
from google import genai
from google.genai import types


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)


gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


def create_embedding(text: str) -> list[float]:
    result = gemini_client.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=768
        )
    )

    return result.embeddings[0].values

def search_event_knowledge(
    event_slug: str,
    question: str,
    match_count: int = 5
):
    query_embedding = create_embedding(question)

    response = supabase.rpc(
        "match_event_knowledge",
        {
            "query_embedding": query_embedding,
            "target_event_slug": event_slug,
            "match_count": match_count
        }
    ).execute()

    return response.data



def build_event_chunks(event_data: dict) -> list[dict]:
    chunks = []

    for section, value in event_data.items():

        if value is None:
            continue

        # If section contains a list, such as tickets or agenda
        if isinstance(value, list):

            for index, item in enumerate(value):

                content = json.dumps(
                    item,
                    ensure_ascii=False,
                    default=str
                )

                if content not in ("{}", "[]", "null"):
                    chunks.append({
                        "section": f"{section}_{index + 1}",
                        "content": content
                    })

        else:

            content = json.dumps(
                value,
                ensure_ascii=False,
                default=str
            )

            if content not in ("{}", "[]", "null"):
                chunks.append({
                    "section": section,
                    "content": content
                })

    return chunks

def has_event_knowledge(event_slug: str) -> bool:

    response = (
        supabase
        .table("event_knowledge")
        .select("id")
        .eq("event_slug", event_slug)
        .limit(1)
        .execute()
    )

    return len(response.data) > 0

def index_event_knowledge(
    event_slug: str,
    event_data: dict
) -> int:

    chunks = build_event_chunks(event_data)

    if not chunks:
        return 0

    # IMPORTANT:
    # This ONLY touches our new RAG table.
    # It does not touch events, tickets, users, orders, etc.
    (
        supabase
        .table("event_knowledge")
        .delete()
        .eq("event_slug", event_slug)
        .execute()
    )

    rows = []

    for chunk in chunks:

        embedding_text = (
            f"Event: {event_slug}\n"
            f"Section: {chunk['section']}\n"
            f"Content: {chunk['content']}"
        )

        embedding = create_embedding(
            embedding_text
        )

        rows.append({
            "event_slug": event_slug,
            "section": chunk["section"],
            "content": chunk["content"],
            "embedding": embedding
        })

    (
        supabase
        .table("event_knowledge")
        .insert(rows)
        .execute()
    )

    return len(rows)