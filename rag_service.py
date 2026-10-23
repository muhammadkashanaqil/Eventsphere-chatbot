# import os
# import json

# from dotenv import load_dotenv
# from supabase import create_client, Client
# from google import genai
# from google.genai import types


# # =========================================================
# # ENVIRONMENT
# # =========================================================

# load_dotenv()


# SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# if not SUPABASE_URL:
#     raise RuntimeError("SUPABASE_URL is missing")

# if not SUPABASE_SECRET_KEY:
#     raise RuntimeError("SUPABASE_SECRET_KEY is missing")

# if not GEMINI_API_KEY:
#     raise RuntimeError("GEMINI_API_KEY is missing")


# # =========================================================
# # CLIENTS
# # =========================================================

# supabase: Client = create_client(
#     SUPABASE_URL,
#     SUPABASE_SECRET_KEY
# )


# gemini_client = genai.Client(
#     api_key=GEMINI_API_KEY
# )


# # =========================================================
# # BUILD EVENT CHUNKS
# # =========================================================

# def build_event_chunks(
#         event_data: dict
# ) -> list[dict]:

#     chunks = []

#     for section, value in event_data.items():

#         if value is None:
#             continue

#         # -------------------------------------------------
#         # Lists:
#         # tickets, agenda, sponsors, etc.
#         # -------------------------------------------------

#         if isinstance(value, list):

#             for index, item in enumerate(value):

#                 content = json.dumps(
#                     item,
#                     ensure_ascii=False,
#                     default=str
#                 )

#                 if content not in (
#                     "{}",
#                     "[]",
#                     "null",
#                     '""'
#                 ):

#                     chunks.append({
#                         "section":
#                             f"{section}_{index + 1}",

#                         "content":
#                             content
#                     })

#         # -------------------------------------------------
#         # Normal object/value
#         # -------------------------------------------------

#         else:

#             content = json.dumps(
#                 value,
#                 ensure_ascii=False,
#                 default=str
#             )

#             if content not in (
#                 "{}",
#                 "[]",
#                 "null",
#                 '""'
#             ):

#                 chunks.append({
#                     "section": section,
#                     "content": content
#                 })

#     return chunks


# # =========================================================
# # TEMPORARY SLUG EXTRACTOR
# #
# # event_id is now the real RAG identity.
# #
# # We keep event_slug temporarily because your existing
# # event_knowledge table still has an event_slug column.
# #
# # Later we can remove this when the migration is complete.
# # =========================================================

# def extract_event_slug(
#         event_data: dict
# ) -> str | None:

#     # -----------------------------------------------------
#     # Try top-level values first
#     # -----------------------------------------------------

#     for key in (
#         "event_slug",
#         "eventSlug",
#         "slug",
#         "slug_url",
#         "slugUrl"
#     ):

#         value = event_data.get(key)

#         if value:
#             return str(value)


#     # -----------------------------------------------------
#     # Your PublicEventResponse has landingPageDesign
#     # -----------------------------------------------------

#     landing_page = (
#         event_data.get("landingPageDesign")
#         or event_data.get("landing_page_design")
#         or {}
#     )


#     if isinstance(landing_page, dict):

#         for key in (
#             "customSlug",
#             "custom_slug",
#             "slug",
#             "slugUrl",
#             "slug_url"
#         ):

#             value = landing_page.get(key)

#             if value:
#                 return str(value)


#     # -----------------------------------------------------
#     # Also check eventDetails just in case
#     # -----------------------------------------------------

#     event_details = (
#         event_data.get("eventDetails")
#         or event_data.get("event_details")
#         or {}
#     )


#     if isinstance(event_details, dict):

#         for key in (
#             "slug",
#             "eventSlug",
#             "event_slug"
#         ):

#             value = event_details.get(key)

#             if value:
#                 return str(value)


#     return None


# # =========================================================
# # CREATE ONE QUERY EMBEDDING
# #
# # Used when visitor sends a message.
# # =========================================================

# def create_query_embedding(
#         question: str
# ) -> list[float]:

#     text = (
#         "task: retrieval query\n"
#         f"query: {question}"
#     )


#     result = gemini_client.models.embed_content(
#         model="gemini-embedding-2",
#         contents=text,
#         config=types.EmbedContentConfig(
#             output_dimensionality=768
#         )
#     )


#     if not result.embeddings:

#         raise RuntimeError(
#             "Gemini returned no query embedding"
#         )


#     return result.embeddings[0].values


# # =========================================================
# # BATCH CREATE EVENT EMBEDDINGS
# #
# # ONE Gemini API request for all event chunks.
# # =========================================================

# def create_document_embeddings(
#         texts: list[str]
# ) -> list[list[float]]:

#     if not texts:
#         return []


#     contents = [

#         types.Content(
#             parts=[
#                 types.Part.from_text(
#                     text=text
#                 )
#             ]
#         )

#         for text in texts
#     ]


#     result = gemini_client.models.embed_content(
#         model="gemini-embedding-2",
#         contents=contents,
#         config=types.EmbedContentConfig(
#             output_dimensionality=768
#         )
#     )


#     if not result.embeddings:

#         raise RuntimeError(
#             "Gemini returned no document embeddings"
#         )


#     embeddings = [

#         embedding.values

#         for embedding
#         in result.embeddings
#     ]


#     if len(embeddings) != len(texts):

#         raise RuntimeError(
#             "Embedding count does not match "
#             "event chunk count"
#         )


#     return embeddings


# # =========================================================
# # INDEX / RE-INDEX ONE EVENT
# #
# # IMPORTANT:
# # event_id is now the permanent RAG identifier.
# #
# # Only event_knowledge is modified.
# # Existing EventSphere tables are NOT modified.
# # =========================================================

# def index_event_knowledge(
#         event_id: str,
#         event_data: dict,
#         event_slug: str | None = None
# ) -> int:

#     # -----------------------------------------------------
#     # Make sure event ID exists
#     # -----------------------------------------------------

#     if not event_id:

#         raise ValueError(
#             "event_id is required for RAG indexing"
#         )


#     event_id = str(event_id)


#     # -----------------------------------------------------
#     # Resolve slug only for temporary compatibility
#     # -----------------------------------------------------

#     if not event_slug:

#         event_slug = extract_event_slug(
#             event_data
#         )


#     if not event_slug:

#         raise RuntimeError(
#             "Could not determine event_slug from event_data. "
#             "Pass event_slug temporarily while the old "
#             "event_slug column still exists."
#         )


#     # -----------------------------------------------------
#     # Split PublicEventResponse into chunks
#     # -----------------------------------------------------

#     chunks = build_event_chunks(
#         event_data
#     )


#     if not chunks:
#         return 0


#     # -----------------------------------------------------
#     # Prepare all embedding text
#     #
#     # Notice:
#     # We use EVENT ID, not slug, in the semantic document.
#     # -----------------------------------------------------

#     embedding_texts = []


#     for chunk in chunks:

#         text = (
#             "task: retrieval document\n"
#             f"event_id: {event_id}\n"
#             f"section: {chunk['section']}\n"
#             f"content: {chunk['content']}"
#         )

#         embedding_texts.append(
#             text
#         )


#     # -----------------------------------------------------
#     # ONE Gemini request for ALL chunks
#     # -----------------------------------------------------

#     embeddings = create_document_embeddings(
#         embedding_texts
#     )


#     # -----------------------------------------------------
#     # Build rows BEFORE deleting old RAG data
#     # -----------------------------------------------------

#     rows = []


#     for chunk, embedding in zip(
#         chunks,
#         embeddings
#     ):

#         rows.append({

#             # NEW permanent identity
#             "event_id": event_id,

#             # TEMPORARY compatibility field
#             "event_slug": event_slug,

#             "section":
#                 chunk["section"],

#             "content":
#                 chunk["content"],

#             "embedding":
#                 embedding
#         })


#     # -----------------------------------------------------
#     # Delete previous RAG knowledge for THIS EVENT ID ONLY
#     # -----------------------------------------------------

#     (
#         supabase
#         .table("event_knowledge")
#         .delete()
#         .eq(
#             "event_id",
#             event_id
#         )
#         .execute()
#     )


#     # -----------------------------------------------------
#     # Store new event knowledge
#     # -----------------------------------------------------

#     (
#         supabase
#         .table("event_knowledge")
#         .insert(rows)
#         .execute()
#     )


#     return len(rows)


# # =========================================================
# # VECTOR SEARCH
# #
# # IMPORTANT:
# # Search is now restricted by EVENT ID.
# #
# # OLD:
# # target_event_slug
# #
# # NEW:
# # target_event_id
# # =========================================================

# def search_event_knowledge(
#         event_id: str,
#         question: str,
#         match_count: int = 4
# ) -> list[dict]:

#     if not event_id:

#         raise ValueError(
#             "event_id is required for RAG search"
#         )


#     if not question or not question.strip():

#         raise ValueError(
#             "question cannot be empty"
#         )


#     event_id = str(event_id)


#     # -----------------------------------------------------
#     # Convert question into vector
#     # -----------------------------------------------------

#     query_embedding = create_query_embedding(
#         question
#     )


#     # -----------------------------------------------------
#     # Call NEW event-ID based PostgreSQL function
#     # -----------------------------------------------------

#     response = supabase.rpc(
#         "match_event_knowledge_by_event_id",
#         {
#             "query_embedding":
#                 query_embedding,

#             "target_event_id":
#                 event_id,

#             "match_count":
#                 match_count
#         }
#     ).execute()


#     return response.data or []


# # =========================================================
# # CHAT HISTORY
# #
# # session_id identifies ONE conversation.
# #
# # event_id ensures the conversation belongs to
# # the correct EventSphere event.
# # =========================================================

# def get_chat_history(
#         event_id: str,
#         session_id: str,
#         limit: int = 8
# ) -> list[dict]:

#     if not event_id:
#         raise ValueError(
#             "event_id is required"
#         )


#     if not session_id:
#         raise ValueError(
#             "session_id is required"
#         )


#     # -----------------------------------------------------
#     # Get newest messages first so LIMIT gets the
#     # most recent conversation.
#     # -----------------------------------------------------

#     response = (
#         supabase
#         .table("chat_messages")
#         .select(
#             "role,content,created_at"
#         )
#         .eq(
#             "event_id",
#             str(event_id)
#         )
#         .eq(
#             "session_id",
#             str(session_id)
#         )
#         .order(
#             "created_at",
#             desc=True
#         )
#         .limit(limit)
#         .execute()
#     )


#     messages = response.data or []


#     # -----------------------------------------------------
#     # Gemini should read conversation:
#     #
#     # oldest
#     # ↓
#     # newest
#     #
#     # not newest -> oldest.
#     # -----------------------------------------------------

#     messages.reverse()


#     return messages


# # =========================================================
# # SAVE ONE CHAT MESSAGE
# #
# # role must be:
# #
# # user
# # assistant
# # =========================================================

# def save_chat_message(
#         event_id: str,
#         session_id: str,
#         role: str,
#         content: str
# ) -> None:

#     if role not in (
#         "user",
#         "assistant"
#     ):

#         raise ValueError(
#             "role must be 'user' or 'assistant'"
#         )


#     if not content or not content.strip():

#         return


#     (
#         supabase
#         .table("chat_messages")
#         .insert({
#             "event_id":
#                 str(event_id),

#             "session_id":
#                 str(session_id),

#             "role":
#                 role,

#             "content":
#                 content
#         })
#         .execute()
#     )


# # =========================================================
# # OPTIONAL:
# # CHECK WHETHER EVENT ALREADY HAS RAG DATA
# # =========================================================

# def has_event_knowledge(
#         event_id: str
# ) -> bool:

#     response = (
#         supabase
#         .table("event_knowledge")
#         .select("id")
#         .eq(
#             "event_id",
#             str(event_id)
#         )
#         .limit(1)
#         .execute()
#     )


#     return bool(
#         response.data
#     )
















import os
import json

from dotenv import load_dotenv
from supabase import create_client, Client
from google import genai
from google.genai import types


# =========================================================
# ENVIRONMENT
# =========================================================

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


# =========================================================
# CLIENTS
# =========================================================

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

def build_event_chunks(
        event_data: dict
) -> list[dict]:

    chunks = []

    for section, value in event_data.items():

        if value is None:
            continue

        # -------------------------------------------------
        # Lists:
        # tickets, agenda, sponsors, etc.
        # -------------------------------------------------

        if isinstance(value, list):

            for index, item in enumerate(value):

                content = json.dumps(
                    item,
                    ensure_ascii=False,
                    default=str
                )

                if content not in (
                    "{}",
                    "[]",
                    "null",
                    '""'
                ):

                    chunks.append({
                        "section":
                            f"{section}_{index + 1}",

                        "content":
                            content
                    })

        # -------------------------------------------------
        # Normal object/value
        # -------------------------------------------------

        else:

            content = json.dumps(
                value,
                ensure_ascii=False,
                default=str
            )

            if content not in (
                "{}",
                "[]",
                "null",
                '""'
            ):

                chunks.append({
                    "section": section,
                    "content": content
                })

    return chunks


# =========================================================
# TEMPORARY SLUG EXTRACTOR
#
# event_id is now the real RAG identity.
#
# We keep event_slug temporarily because your existing
# event_knowledge table still has an event_slug column.
#
# Later we can remove this when the migration is complete.
# =========================================================

def extract_event_slug(
        event_data: dict
) -> str | None:

    # -----------------------------------------------------
    # Try top-level values first
    # -----------------------------------------------------

    for key in (
        "event_slug",
        "eventSlug",
        "slug",
        "slug_url",
        "slugUrl"
    ):

        value = event_data.get(key)

        if value:
            return str(value)


    # -----------------------------------------------------
    # Your PublicEventResponse has landingPageDesign
    # -----------------------------------------------------

    landing_page = (
        event_data.get("landingPageDesign")
        or event_data.get("landing_page_design")
        or {}
    )


    if isinstance(landing_page, dict):

        for key in (
            "customSlug",
            "custom_slug",
            "slug",
            "slugUrl",
            "slug_url"
        ):

            value = landing_page.get(key)

            if value:
                return str(value)


    # -----------------------------------------------------
    # Also check eventDetails just in case
    # -----------------------------------------------------

    event_details = (
        event_data.get("eventDetails")
        or event_data.get("event_details")
        or {}
    )


    if isinstance(event_details, dict):

        for key in (
            "slug",
            "eventSlug",
            "event_slug"
        ):

            value = event_details.get(key)

            if value:
                return str(value)


    return None


# =========================================================
# CREATE ONE QUERY EMBEDDING
#
# Used when visitor sends a message.
# =========================================================

def create_query_embedding(
        question: str
) -> list[float]:

    text = (
        "task: retrieval query\n"
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
# ONE Gemini API request for all event chunks.
# =========================================================

def create_document_embeddings(
        texts: list[str]
) -> list[list[float]]:

    if not texts:
        return []


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

        for embedding
        in result.embeddings
    ]


    if len(embeddings) != len(texts):

        raise RuntimeError(
            "Embedding count does not match "
            "event chunk count"
        )


    return embeddings


# =========================================================
# INDEX / RE-INDEX ONE EVENT
#
# IMPORTANT:
# event_id is now the permanent RAG identifier.
#
# Only event_knowledge is modified.
# Existing EventSphere tables are NOT modified.
# =========================================================

def index_event_knowledge(
        event_id: str,
        event_data: dict,
        event_slug: str | None = None
) -> int:

    # -----------------------------------------------------
    # Make sure event ID exists
    # -----------------------------------------------------

    if not event_id:

        raise ValueError(
            "event_id is required for RAG indexing"
        )


    event_id = str(event_id)


    # -----------------------------------------------------
    # Resolve slug only for temporary compatibility
    # -----------------------------------------------------

    if not event_slug:

        event_slug = extract_event_slug(
            event_data
        )


    if not event_slug:

        raise RuntimeError(
            "Could not determine event_slug from event_data. "
            "Pass event_slug temporarily while the old "
            "event_slug column still exists."
        )


    # -----------------------------------------------------
    # Split PublicEventResponse into chunks
    # -----------------------------------------------------

    chunks = build_event_chunks(
        event_data
    )


    if not chunks:
        return 0


    # -----------------------------------------------------
    # Prepare all embedding text
    #
    # Notice:
    # We use EVENT ID, not slug, in the semantic document.
    # -----------------------------------------------------

    embedding_texts = []


    for chunk in chunks:

        text = (
            "task: retrieval document\n"
            f"event_id: {event_id}\n"
            f"section: {chunk['section']}\n"
            f"content: {chunk['content']}"
        )

        embedding_texts.append(
            text
        )


    # -----------------------------------------------------
    # ONE Gemini request for ALL chunks
    # -----------------------------------------------------

    embeddings = create_document_embeddings(
        embedding_texts
    )


    # -----------------------------------------------------
    # Build rows BEFORE deleting old RAG data
    # -----------------------------------------------------

    rows = []


    for chunk, embedding in zip(
        chunks,
        embeddings
    ):

        rows.append({

            # NEW permanent identity
            "event_id": event_id,

            # TEMPORARY compatibility field
            "event_slug": event_slug,

            "section":
                chunk["section"],

            "content":
                chunk["content"],

            "embedding":
                embedding
        })


    # -----------------------------------------------------
    # Delete previous RAG knowledge for THIS EVENT ID ONLY
    # -----------------------------------------------------

    (
        supabase
        .table("event_knowledge")
        .delete()
        .eq(
            "event_id",
            event_id
        )
        .execute()
    )


    # -----------------------------------------------------
    # Store new event knowledge
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
#
# IMPORTANT:
# Search is now restricted by EVENT ID.
#
# OLD:
# target_event_slug
#
# NEW:
# target_event_id
# =========================================================

def search_event_knowledge(
        event_id: str,
        question: str,
        match_count: int = 4
) -> list[dict]:

    if not event_id:

        raise ValueError(
            "event_id is required for RAG search"
        )


    if not question or not question.strip():

        raise ValueError(
            "question cannot be empty"
        )


    event_id = str(event_id)


    # -----------------------------------------------------
    # Convert question into vector
    # -----------------------------------------------------

    query_embedding = create_query_embedding(
        question
    )


    # -----------------------------------------------------
    # Call NEW event-ID based PostgreSQL function
    # -----------------------------------------------------

    response = supabase.rpc(
        "match_event_knowledge_by_event_id",
        {
            "query_embedding":
                query_embedding,

            "target_event_id":
                event_id,

            "match_count":
                match_count
        }
    ).execute()


    return response.data or []


# =========================================================
# CHAT HISTORY
#
# session_id identifies ONE conversation.
#
# event_id ensures the conversation belongs to
# the correct EventSphere event.
# =========================================================

def get_chat_history(
        event_id: str,
        session_id: str,
        limit: int = 8
) -> list[dict]:

    if not event_id:
        raise ValueError(
            "event_id is required"
        )


    if not session_id:
        raise ValueError(
            "session_id is required"
        )


    # -----------------------------------------------------
    # Get newest messages first so LIMIT gets the
    # most recent conversation.
    # -----------------------------------------------------

    response = (
        supabase
        .table("chat_messages")
        .select(
            "role,content,created_at"
        )
        .eq(
            "event_id",
            str(event_id)
        )
        .eq(
            "session_id",
            str(session_id)
        )
        .order(
            "created_at",
            desc=True
        )
        .limit(limit)
        .execute()
    )


    messages = response.data or []


    # -----------------------------------------------------
    # Gemini should read conversation:
    #
    # oldest
    # ↓
    # newest
    #
    # not newest -> oldest.
    # -----------------------------------------------------

    messages.reverse()


    return messages


# =========================================================
# SAVE ONE CHAT MESSAGE
#
# role must be:
#
# user
# assistant
# =========================================================

def save_chat_message(
        event_id: str,
        session_id: str,
        role: str,
        content: str
) -> None:

    if role not in (
        "user",
        "assistant"
    ):

        raise ValueError(
            "role must be 'user' or 'assistant'"
        )


    if not content or not content.strip():

        return


    (
        supabase
        .table("chat_messages")
        .insert({
            "event_id":
                str(event_id),

            "session_id":
                str(session_id),

            "role":
                role,

            "content":
                content
        })
        .execute()
    )


# =========================================================
# OPTIONAL:
# CHECK WHETHER EVENT ALREADY HAS RAG DATA
# =========================================================

def has_event_knowledge(
        event_id: str
) -> bool:

    response = (
        supabase
        .table("event_knowledge")
        .select("id")
        .eq(
            "event_id",
            str(event_id)
        )
        .limit(1)
        .execute()
    )


    return bool(
        response.data
    )