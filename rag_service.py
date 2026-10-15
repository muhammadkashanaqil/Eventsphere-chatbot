import os
import json

from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types


load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing")

if not SUPABASE_SECRET_KEY:
    raise RuntimeError("SUPABASE_SECRET_KEY is missing")

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is missing")


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY
)


gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


# =========================================================
# BUILD EVENT CHUNKS
# =========================================================

def build_event_chunks(event_data: dict) -> list[dict]:

    chunks = []

    for section, value in event_data.items():

        if value is None:
            continue

        # Example:
        # tickets, agenda, sponsors, etc.
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


# =========================================================
# CREATE ONE QUERY EMBEDDING
# Used during /chat
# =========================================================

def create_query_embedding(
        question: str
) -> list[float]:

    text = (
        "task: retrieval query | "
        f"query: {question}"
    )

    result = gemini_client.models.embed_content(
        model="gemini-embedding-2",
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=768
        )
    )

    if not result.embeddings:
        raise RuntimeError(
            "Gemini returned no query embedding"
        )

    return result.embeddings[0].values


# =========================================================
# BATCH CREATE EVENT EMBEDDINGS
#
# IMPORTANT:
# ONE Gemini request for all event chunks.
# =========================================================

def create_document_embeddings(
        texts: list[str]
) -> list[list[float]]:

    if not texts:
        return []

    # Each Content object produces its own embedding,
    # while still being sent in one API request.
    contents = [

        types.Content(
            parts=[
                types.Part.from_text(
                    text=text
                )
            ]
        )

        for text in texts
    ]

    result = gemini_client.models.embed_content(
        model="gemini-embedding-2",
        contents=contents,
        config=types.EmbedContentConfig(
            output_dimensionality=768
        )
    )

    if not result.embeddings:
        raise RuntimeError(
            "Gemini returned no document embeddings"
        )

    embeddings = [
        embedding.values
        for embedding in result.embeddings
    ]

    if len(embeddings) != len(texts):
        raise RuntimeError(
            "Embedding count does not match chunk count"
        )

    return embeddings


# =========================================================
# INDEX / RE-INDEX ONE EVENT
#
# This ONLY modifies event_knowledge.
# It does NOT touch your existing tables.
# =========================================================

def index_event_knowledge(
        event_slug: str,
        event_data: dict
) -> int:

    chunks = build_event_chunks(
        event_data
    )

    if not chunks:
        return 0


    # -----------------------------------------------------
    # Prepare all text first
    # -----------------------------------------------------

    embedding_texts = []

    for chunk in chunks:

        text = (
            "task: retrieval document\n"
            f"event: {event_slug}\n"
            f"section: {chunk['section']}\n"
            f"content: {chunk['content']}"
        )

        embedding_texts.append(text)


    # -----------------------------------------------------
    # ONE Gemini call for ALL chunks
    # -----------------------------------------------------

    embeddings = create_document_embeddings(
        embedding_texts
    )


    # -----------------------------------------------------
    # Build rows before changing DB
    # -----------------------------------------------------

    rows = []

    for chunk, embedding in zip(
        chunks,
        embeddings
    ):

        rows.append({
            "event_slug": event_slug,
            "section": chunk["section"],
            "content": chunk["content"],
            "embedding": embedding
        })


    # -----------------------------------------------------
    # Only delete OLD RAG knowledge for THIS event
    # -----------------------------------------------------

    (
        supabase
        .table("event_knowledge")
        .delete()
        .eq("event_slug", event_slug)
        .execute()
    )


    # -----------------------------------------------------
    # Store new RAG knowledge
    # -----------------------------------------------------

    (
        supabase
        .table("event_knowledge")
        .insert(rows)
        .execute()
    )


    return len(rows)


# =========================================================
# VECTOR SEARCH
# =========================================================

def search_event_knowledge(
        event_slug: str,
        question: str,
        match_count: int = 4
) -> list[dict]:

    query_embedding = create_query_embedding(
        question
    )

    response = supabase.rpc(
        "match_event_knowledge",
        {
            "query_embedding": query_embedding,
            "target_event_slug": event_slug,
            "match_count": match_count
        }
    ).execute()

    return response.data or []