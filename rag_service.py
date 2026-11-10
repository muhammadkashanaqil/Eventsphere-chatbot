# # import os
# # import json

# # from dotenv import load_dotenv
# # from supabase import create_client, Client
# # from google import genai
# # from google.genai import types


# # # =========================================================
# # # ENVIRONMENT
# # # =========================================================

# # load_dotenv()


# # SUPABASE_URL = os.getenv("SUPABASE_URL")
# # SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
# # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# # if not SUPABASE_URL:
# #     raise RuntimeError("SUPABASE_URL is missing")

# # if not SUPABASE_SECRET_KEY:
# #     raise RuntimeError("SUPABASE_SECRET_KEY is missing")

# # if not GEMINI_API_KEY:
# #     raise RuntimeError("GEMINI_API_KEY is missing")


# # # =========================================================
# # # CLIENTS
# # # =========================================================

# # supabase: Client = create_client(
# #     SUPABASE_URL,
# #     SUPABASE_SECRET_KEY
# # )


# # gemini_client = genai.Client(
# #     api_key=GEMINI_API_KEY
# # )


# # # =========================================================
# # # BUILD EVENT CHUNKS
# # # =========================================================

# # def build_event_chunks(
# #         event_data: dict
# # ) -> list[dict]:

# #     chunks = []

# #     for section, value in event_data.items():

# #         if value is None:
# #             continue

# #         # -------------------------------------------------
# #         # Lists:
# #         # tickets, agenda, sponsors, etc.
# #         # -------------------------------------------------

# #         if isinstance(value, list):

# #             for index, item in enumerate(value):

# #                 content = json.dumps(
# #                     item,
# #                     ensure_ascii=False,
# #                     default=str
# #                 )

# #                 if content not in (
# #                     "{}",
# #                     "[]",
# #                     "null",
# #                     '""'
# #                 ):

# #                     chunks.append({
# #                         "section":
# #                             f"{section}_{index + 1}",

# #                         "content":
# #                             content
# #                     })

# #         # -------------------------------------------------
# #         # Normal object/value
# #         # -------------------------------------------------

# #         else:

# #             content = json.dumps(
# #                 value,
# #                 ensure_ascii=False,
# #                 default=str
# #             )

# #             if content not in (
# #                 "{}",
# #                 "[]",
# #                 "null",
# #                 '""'
# #             ):

# #                 chunks.append({
# #                     "section": section,
# #                     "content": content
# #                 })

# #     return chunks


# # # =========================================================
# # # TEMPORARY SLUG EXTRACTOR
# # #
# # # event_id is now the real RAG identity.
# # #
# # # We keep event_slug temporarily because your existing
# # # event_knowledge table still has an event_slug column.
# # #
# # # Later we can remove this when the migration is complete.
# # # =========================================================

# # def extract_event_slug(
# #         event_data: dict
# # ) -> str | None:

# #     # -----------------------------------------------------
# #     # Try top-level values first
# #     # -----------------------------------------------------

# #     for key in (
# #         "event_slug",
# #         "eventSlug",
# #         "slug",
# #         "slug_url",
# #         "slugUrl"
# #     ):

# #         value = event_data.get(key)

# #         if value:
# #             return str(value)


# #     # -----------------------------------------------------
# #     # Your PublicEventResponse has landingPageDesign
# #     # -----------------------------------------------------

# #     landing_page = (
# #         event_data.get("landingPageDesign")
# #         or event_data.get("landing_page_design")
# #         or {}
# #     )


# #     if isinstance(landing_page, dict):

# #         for key in (
# #             "customSlug",
# #             "custom_slug",
# #             "slug",
# #             "slugUrl",
# #             "slug_url"
# #         ):

# #             value = landing_page.get(key)

# #             if value:
# #                 return str(value)


# #     # -----------------------------------------------------
# #     # Also check eventDetails just in case
# #     # -----------------------------------------------------

# #     event_details = (
# #         event_data.get("eventDetails")
# #         or event_data.get("event_details")
# #         or {}
# #     )


# #     if isinstance(event_details, dict):

# #         for key in (
# #             "slug",
# #             "eventSlug",
# #             "event_slug"
# #         ):

# #             value = event_details.get(key)

# #             if value:
# #                 return str(value)


# #     return None


# # # =========================================================
# # # CREATE ONE QUERY EMBEDDING
# # #
# # # Used when visitor sends a message.
# # # =========================================================

# # def create_query_embedding(
# #         question: str
# # ) -> list[float]:

# #     text = (
# #         "task: retrieval query\n"
# #         f"query: {question}"
# #     )


# #     result = gemini_client.models.embed_content(
# #         model="gemini-embedding-2",
# #         contents=text,
# #         config=types.EmbedContentConfig(
# #             output_dimensionality=768
# #         )
# #     )


# #     if not result.embeddings:

# #         raise RuntimeError(
# #             "Gemini returned no query embedding"
# #         )


# #     return result.embeddings[0].values


# # # =========================================================
# # # BATCH CREATE EVENT EMBEDDINGS
# # #
# # # ONE Gemini API request for all event chunks.
# # # =========================================================

# # def create_document_embeddings(
# #         texts: list[str]
# # ) -> list[list[float]]:

# #     if not texts:
# #         return []


# #     contents = [

# #         types.Content(
# #             parts=[
# #                 types.Part.from_text(
# #                     text=text
# #                 )
# #             ]
# #         )

# #         for text in texts
# #     ]


# #     result = gemini_client.models.embed_content(
# #         model="gemini-embedding-2",
# #         contents=contents,
# #         config=types.EmbedContentConfig(
# #             output_dimensionality=768
# #         )
# #     )


# #     if not result.embeddings:

# #         raise RuntimeError(
# #             "Gemini returned no document embeddings"
# #         )


# #     embeddings = [

# #         embedding.values

# #         for embedding
# #         in result.embeddings
# #     ]


# #     if len(embeddings) != len(texts):

# #         raise RuntimeError(
# #             "Embedding count does not match "
# #             "event chunk count"
# #         )


# #     return embeddings


# # # =========================================================
# # # INDEX / RE-INDEX ONE EVENT
# # #
# # # IMPORTANT:
# # # event_id is now the permanent RAG identifier.
# # #
# # # Only event_knowledge is modified.
# # # Existing EventSphere tables are NOT modified.
# # # =========================================================

# # def index_event_knowledge(
# #         event_id: str,
# #         event_data: dict,
# #         event_slug: str | None = None
# # ) -> int:

# #     # -----------------------------------------------------
# #     # Make sure event ID exists
# #     # -----------------------------------------------------

# #     if not event_id:

# #         raise ValueError(
# #             "event_id is required for RAG indexing"
# #         )


# #     event_id = str(event_id)


# #     # -----------------------------------------------------
# #     # Resolve slug only for temporary compatibility
# #     # -----------------------------------------------------

# #     if not event_slug:

# #         event_slug = extract_event_slug(
# #             event_data
# #         )


# #     if not event_slug:

# #         raise RuntimeError(
# #             "Could not determine event_slug from event_data. "
# #             "Pass event_slug temporarily while the old "
# #             "event_slug column still exists."
# #         )


# #     # -----------------------------------------------------
# #     # Split PublicEventResponse into chunks
# #     # -----------------------------------------------------

# #     chunks = build_event_chunks(
# #         event_data
# #     )


# #     if not chunks:
# #         return 0


# #     # -----------------------------------------------------
# #     # Prepare all embedding text
# #     #
# #     # Notice:
# #     # We use EVENT ID, not slug, in the semantic document.
# #     # -----------------------------------------------------

# #     embedding_texts = []


# #     for chunk in chunks:

# #         text = (
# #             "task: retrieval document\n"
# #             f"event_id: {event_id}\n"
# #             f"section: {chunk['section']}\n"
# #             f"content: {chunk['content']}"
# #         )

# #         embedding_texts.append(
# #             text
# #         )


# #     # -----------------------------------------------------
# #     # ONE Gemini request for ALL chunks
# #     # -----------------------------------------------------

# #     embeddings = create_document_embeddings(
# #         embedding_texts
# #     )


# #     # -----------------------------------------------------
# #     # Build rows BEFORE deleting old RAG data
# #     # -----------------------------------------------------

# #     rows = []


# #     for chunk, embedding in zip(
# #         chunks,
# #         embeddings
# #     ):

# #         rows.append({

# #             # NEW permanent identity
# #             "event_id": event_id,

# #             # TEMPORARY compatibility field
# #             "event_slug": event_slug,

# #             "section":
# #                 chunk["section"],

# #             "content":
# #                 chunk["content"],

# #             "embedding":
# #                 embedding
# #         })


# #     # -----------------------------------------------------
# #     # Delete previous RAG knowledge for THIS EVENT ID ONLY
# #     # -----------------------------------------------------

# #     (
# #         supabase
# #         .table("event_knowledge")
# #         .delete()
# #         .eq(
# #             "event_id",
# #             event_id
# #         )
# #         .execute()
# #     )


# #     # -----------------------------------------------------
# #     # Store new event knowledge
# #     # -----------------------------------------------------

# #     (
# #         supabase
# #         .table("event_knowledge")
# #         .insert(rows)
# #         .execute()
# #     )


# #     return len(rows)


# # # =========================================================
# # # VECTOR SEARCH
# # #
# # # IMPORTANT:
# # # Search is now restricted by EVENT ID.
# # #
# # # OLD:
# # # target_event_slug
# # #
# # # NEW:
# # # target_event_id
# # # =========================================================

# # def search_event_knowledge(
# #         event_id: str,
# #         question: str,
# #         match_count: int = 4
# # ) -> list[dict]:

# #     if not event_id:

# #         raise ValueError(
# #             "event_id is required for RAG search"
# #         )


# #     if not question or not question.strip():

# #         raise ValueError(
# #             "question cannot be empty"
# #         )


# #     event_id = str(event_id)


# #     # -----------------------------------------------------
# #     # Convert question into vector
# #     # -----------------------------------------------------

# #     query_embedding = create_query_embedding(
# #         question
# #     )


# #     # -----------------------------------------------------
# #     # Call NEW event-ID based PostgreSQL function
# #     # -----------------------------------------------------

# #     response = supabase.rpc(
# #         "match_event_knowledge_by_event_id",
# #         {
# #             "query_embedding":
# #                 query_embedding,

# #             "target_event_id":
# #                 event_id,

# #             "match_count":
# #                 match_count
# #         }
# #     ).execute()


# #     return response.data or []


# # # =========================================================
# # # CHAT HISTORY
# # #
# # # session_id identifies ONE conversation.
# # #
# # # event_id ensures the conversation belongs to
# # # the correct EventSphere event.
# # # =========================================================

# # def get_chat_history(
# #         event_id: str,
# #         session_id: str,
# #         limit: int = 8
# # ) -> list[dict]:

# #     if not event_id:
# #         raise ValueError(
# #             "event_id is required"
# #         )


# #     if not session_id:
# #         raise ValueError(
# #             "session_id is required"
# #         )


# #     # -----------------------------------------------------
# #     # Get newest messages first so LIMIT gets the
# #     # most recent conversation.
# #     # -----------------------------------------------------

# #     response = (
# #         supabase
# #         .table("chat_messages")
# #         .select(
# #             "role,content,created_at"
# #         )
# #         .eq(
# #             "event_id",
# #             str(event_id)
# #         )
# #         .eq(
# #             "session_id",
# #             str(session_id)
# #         )
# #         .order(
# #             "created_at",
# #             desc=True
# #         )
# #         .limit(limit)
# #         .execute()
# #     )


# #     messages = response.data or []


# #     # -----------------------------------------------------
# #     # Gemini should read conversation:
# #     #
# #     # oldest
# #     # ↓
# #     # newest
# #     #
# #     # not newest -> oldest.
# #     # -----------------------------------------------------

# #     messages.reverse()


# #     return messages


# # # =========================================================
# # # SAVE ONE CHAT MESSAGE
# # #
# # # role must be:
# # #
# # # user
# # # assistant
# # # =========================================================

# # def save_chat_message(
# #         event_id: str,
# #         session_id: str,
# #         role: str,
# #         content: str
# # ) -> None:

# #     if role not in (
# #         "user",
# #         "assistant"
# #     ):

# #         raise ValueError(
# #             "role must be 'user' or 'assistant'"
# #         )


# #     if not content or not content.strip():

# #         return


# #     (
# #         supabase
# #         .table("chat_messages")
# #         .insert({
# #             "event_id":
# #                 str(event_id),

# #             "session_id":
# #                 str(session_id),

# #             "role":
# #                 role,

# #             "content":
# #                 content
# #         })
# #         .execute()
# #     )


# # # =========================================================
# # # OPTIONAL:
# # # CHECK WHETHER EVENT ALREADY HAS RAG DATA
# # # =========================================================

# # def has_event_knowledge(
# #         event_id: str
# # ) -> bool:

# #     response = (
# #         supabase
# #         .table("event_knowledge")
# #         .select("id")
# #         .eq(
# #             "event_id",
# #             str(event_id)
# #         )
# #         .limit(1)
# #         .execute()
# #     )


# #     return bool(
# #         response.data
# #     )
















# # import os
# # import json

# # from dotenv import load_dotenv
# # from supabase import create_client, Client
# # from google import genai
# # from google.genai import types


# # # =========================================================
# # # ENVIRONMENT
# # # =========================================================

# # load_dotenv()


# # SUPABASE_URL = os.getenv("SUPABASE_URL")
# # SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
# # GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


# # if not SUPABASE_URL:
# #     raise RuntimeError("SUPABASE_URL is missing")

# # if not SUPABASE_SECRET_KEY:
# #     raise RuntimeError("SUPABASE_SECRET_KEY is missing")

# # if not GEMINI_API_KEY:
# #     raise RuntimeError("GEMINI_API_KEY is missing")


# # # =========================================================
# # # CLIENTS
# # # =========================================================

# # supabase: Client = create_client(
# #     SUPABASE_URL,
# #     SUPABASE_SECRET_KEY
# # )


# # gemini_client = genai.Client(
# #     api_key=GEMINI_API_KEY,
# #     http_options=types.HttpOptions(
# #         timeout=20000,  # 20 seconds
# #         retry_options=types.HttpRetryOptions(
# #             attempts=1
# #         )
# #     )
# # )


# # # =========================================================
# # # BUILD EVENT CHUNKS
# # # =========================================================

# # def build_event_chunks(
# #         event_data: dict
# # ) -> list[dict]:

# #     chunks = []

# #     for section, value in event_data.items():

# #         if value is None:
# #             continue

# #         # -------------------------------------------------
# #         # Lists:
# #         # tickets, agenda, sponsors, etc.
# #         # -------------------------------------------------

# #         if isinstance(value, list):

# #             for index, item in enumerate(value):

# #                 content = json.dumps(
# #                     item,
# #                     ensure_ascii=False,
# #                     default=str
# #                 )

# #                 if content not in (
# #                     "{}",
# #                     "[]",
# #                     "null",
# #                     '""'
# #                 ):

# #                     chunks.append({
# #                         "section":
# #                             f"{section}_{index + 1}",

# #                         "content":
# #                             content
# #                     })

# #         # -------------------------------------------------
# #         # Normal object/value
# #         # -------------------------------------------------

# #         else:

# #             content = json.dumps(
# #                 value,
# #                 ensure_ascii=False,
# #                 default=str
# #             )

# #             if content not in (
# #                 "{}",
# #                 "[]",
# #                 "null",
# #                 '""'
# #             ):

# #                 chunks.append({
# #                     "section": section,
# #                     "content": content
# #                 })

# #     return chunks


# # # =========================================================
# # # TEMPORARY SLUG EXTRACTOR
# # #
# # # event_id is now the real RAG identity.
# # #
# # # We keep event_slug temporarily because your existing
# # # event_knowledge table still has an event_slug column.
# # #
# # # Later we can remove this when the migration is complete.
# # # =========================================================

# # def extract_event_slug(
# #         event_data: dict
# # ) -> str | None:

# #     # -----------------------------------------------------
# #     # Try top-level values first
# #     # -----------------------------------------------------

# #     for key in (
# #         "event_slug",
# #         "eventSlug",
# #         "slug",
# #         "slug_url",
# #         "slugUrl"
# #     ):

# #         value = event_data.get(key)

# #         if value:
# #             return str(value)


# #     # -----------------------------------------------------
# #     # Your PublicEventResponse has landingPageDesign
# #     # -----------------------------------------------------

# #     landing_page = (
# #         event_data.get("landingPageDesign")
# #         or event_data.get("landing_page_design")
# #         or {}
# #     )


# #     if isinstance(landing_page, dict):

# #         for key in (
# #             "customSlug",
# #             "custom_slug",
# #             "slug",
# #             "slugUrl",
# #             "slug_url"
# #         ):

# #             value = landing_page.get(key)

# #             if value:
# #                 return str(value)


# #     # -----------------------------------------------------
# #     # Also check eventDetails just in case
# #     # -----------------------------------------------------

# #     event_details = (
# #         event_data.get("eventDetails")
# #         or event_data.get("event_details")
# #         or {}
# #     )


# #     if isinstance(event_details, dict):

# #         for key in (
# #             "slug",
# #             "eventSlug",
# #             "event_slug"
# #         ):

# #             value = event_details.get(key)

# #             if value:
# #                 return str(value)


# #     return None


# # # =========================================================
# # # CREATE ONE QUERY EMBEDDING
# # #
# # # Used when visitor sends a message.
# # # =========================================================

# # def create_query_embedding(
# #         question: str
# # ) -> list[float]:

# #     text = (
# #         "task: retrieval query\n"
# #         f"query: {question}"
# #     )


# #     result = gemini_client.models.embed_content(
# #         model="gemini-embedding-2",
# #         contents=text,
# #         config=types.EmbedContentConfig(
# #             output_dimensionality=768
# #         )
# #     )


# #     if not result.embeddings:

# #         raise RuntimeError(
# #             "Gemini returned no query embedding"
# #         )


# #     return result.embeddings[0].values


# # # =========================================================
# # # BATCH CREATE EVENT EMBEDDINGS
# # #
# # # ONE Gemini API request for all event chunks.
# # # =========================================================

# # def create_document_embeddings(
# #         texts: list[str]
# # ) -> list[list[float]]:

# #     if not texts:
# #         return []


# #     contents = [

# #         types.Content(
# #             parts=[
# #                 types.Part.from_text(
# #                     text=text
# #                 )
# #             ]
# #         )

# #         for text in texts
# #     ]


# #     result = gemini_client.models.embed_content(
# #         model="gemini-embedding-2",
# #         contents=contents,
# #         config=types.EmbedContentConfig(
# #             output_dimensionality=768
# #         )
# #     )


# #     if not result.embeddings:

# #         raise RuntimeError(
# #             "Gemini returned no document embeddings"
# #         )


# #     embeddings = [

# #         embedding.values

# #         for embedding
# #         in result.embeddings
# #     ]


# #     if len(embeddings) != len(texts):

# #         raise RuntimeError(
# #             "Embedding count does not match "
# #             "event chunk count"
# #         )


# #     return embeddings


# # # =========================================================
# # # INDEX / RE-INDEX ONE EVENT
# # #
# # # IMPORTANT:
# # # event_id is now the permanent RAG identifier.
# # #
# # # Only event_knowledge is modified.
# # # Existing EventSphere tables are NOT modified.
# # # =========================================================

# # def index_event_knowledge(
# #         event_id: str,
# #         event_data: dict,
# #         event_slug: str | None = None
# # ) -> int:

# #     # -----------------------------------------------------
# #     # Make sure event ID exists
# #     # -----------------------------------------------------

# #     if not event_id:

# #         raise ValueError(
# #             "event_id is required for RAG indexing"
# #         )


# #     event_id = str(event_id)


# #     # -----------------------------------------------------
# #     # Resolve slug only for temporary compatibility
# #     # -----------------------------------------------------

# #     if not event_slug:

# #         event_slug = extract_event_slug(
# #             event_data
# #         )


# #     if not event_slug:

# #         raise RuntimeError(
# #             "Could not determine event_slug from event_data. "
# #             "Pass event_slug temporarily while the old "
# #             "event_slug column still exists."
# #         )


# #     # -----------------------------------------------------
# #     # Split PublicEventResponse into chunks
# #     # -----------------------------------------------------

# #     chunks = build_event_chunks(
# #         event_data
# #     )


# #     if not chunks:
# #         return 0


# #     # -----------------------------------------------------
# #     # Prepare all embedding text
# #     #
# #     # Notice:
# #     # We use EVENT ID, not slug, in the semantic document.
# #     # -----------------------------------------------------

# #     embedding_texts = []


# #     for chunk in chunks:

# #         text = (
# #             "task: retrieval document\n"
# #             f"event_id: {event_id}\n"
# #             f"section: {chunk['section']}\n"
# #             f"content: {chunk['content']}"
# #         )

# #         embedding_texts.append(
# #             text
# #         )


# #     # -----------------------------------------------------
# #     # ONE Gemini request for ALL chunks
# #     # -----------------------------------------------------

# #     embeddings = create_document_embeddings(
# #         embedding_texts
# #     )


# #     # -----------------------------------------------------
# #     # Build rows BEFORE deleting old RAG data
# #     # -----------------------------------------------------

# #     rows = []


# #     for chunk, embedding in zip(
# #         chunks,
# #         embeddings
# #     ):

# #         rows.append({

# #             # NEW permanent identity
# #             "event_id": event_id,

# #             # TEMPORARY compatibility field
# #             "event_slug": event_slug,

# #             "section":
# #                 chunk["section"],

# #             "content":
# #                 chunk["content"],

# #             "embedding":
# #                 embedding
# #         })


# #     # -----------------------------------------------------
# #     # Delete previous RAG knowledge for THIS EVENT ID ONLY
# #     # -----------------------------------------------------

# #     (
# #         supabase
# #         .table("event_knowledge")
# #         .delete()
# #         .eq(
# #             "event_id",
# #             event_id
# #         )
# #         .execute()
# #     )


# #     # -----------------------------------------------------
# #     # Store new event knowledge
# #     # -----------------------------------------------------

# #     (
# #         supabase
# #         .table("event_knowledge")
# #         .insert(rows)
# #         .execute()
# #     )


# #     return len(rows)


# # # =========================================================
# # # VECTOR SEARCH
# # #
# # # IMPORTANT:
# # # Search is now restricted by EVENT ID.
# # #
# # # OLD:
# # # target_event_slug
# # #
# # # NEW:
# # # target_event_id
# # # =========================================================

# # def search_event_knowledge(
# #         event_id: str,
# #         question: str,
# #         match_count: int = 4
# # ) -> list[dict]:

# #     if not event_id:

# #         raise ValueError(
# #             "event_id is required for RAG search"
# #         )


# #     if not question or not question.strip():

# #         raise ValueError(
# #             "question cannot be empty"
# #         )


# #     event_id = str(event_id)


# #     # -----------------------------------------------------
# #     # Convert question into vector
# #     # -----------------------------------------------------

# #     query_embedding = create_query_embedding(
# #         question
# #     )


# #     # -----------------------------------------------------
# #     # Call NEW event-ID based PostgreSQL function
# #     # -----------------------------------------------------

# #     response = supabase.rpc(
# #         "match_event_knowledge_by_event_id",
# #         {
# #             "query_embedding":
# #                 query_embedding,

# #             "target_event_id":
# #                 event_id,

# #             "match_count":
# #                 match_count
# #         }
# #     ).execute()


# #     return response.data or []


# # # =========================================================
# # # CHAT HISTORY
# # #
# # # session_id identifies ONE conversation.
# # #
# # # event_id ensures the conversation belongs to
# # # the correct EventSphere event.
# # # =========================================================

# # def get_chat_history(
# #         event_id: str,
# #         session_id: str,
# #         limit: int = 8
# # ) -> list[dict]:

# #     if not event_id:
# #         raise ValueError(
# #             "event_id is required"
# #         )


# #     if not session_id:
# #         raise ValueError(
# #             "session_id is required"
# #         )


# #     # -----------------------------------------------------
# #     # Get newest messages first so LIMIT gets the
# #     # most recent conversation.
# #     # -----------------------------------------------------

# #     response = (
# #         supabase
# #         .table("chat_messages")
# #         .select(
# #             "role,content,created_at"
# #         )
# #         .eq(
# #             "event_id",
# #             str(event_id)
# #         )
# #         .eq(
# #             "session_id",
# #             str(session_id)
# #         )
# #         .order(
# #             "created_at",
# #             desc=True
# #         )
# #         .limit(limit)
# #         .execute()
# #     )


# #     messages = response.data or []


# #     # -----------------------------------------------------
# #     # Gemini should read conversation:
# #     #
# #     # oldest
# #     # ↓
# #     # newest
# #     #
# #     # not newest -> oldest.
# #     # -----------------------------------------------------

# #     messages.reverse()


# #     return messages


# # # =========================================================
# # # SAVE ONE CHAT MESSAGE
# # #
# # # role must be:
# # #
# # # user
# # # assistant
# # # =========================================================

# # def save_chat_message(
# #         event_id: str,
# #         session_id: str,
# #         role: str,
# #         content: str
# # ) -> None:

# #     if role not in (
# #         "user",
# #         "assistant"
# #     ):

# #         raise ValueError(
# #             "role must be 'user' or 'assistant'"
# #         )


# #     if not content or not content.strip():

# #         return


# #     (
# #         supabase
# #         .table("chat_messages")
# #         .insert({
# #             "event_id":
# #                 str(event_id),

# #             "session_id":
# #                 str(session_id),

# #             "role":
# #                 role,

# #             "content":
# #                 content
# #         })
# #         .execute()
# #     )


# # # =========================================================
# # # OPTIONAL:
# # # CHECK WHETHER EVENT ALREADY HAS RAG DATA
# # # =========================================================

# # def has_event_knowledge(
# #         event_id: str
# # ) -> bool:

# #     response = (
# #         supabase
# #         .table("event_knowledge")
# #         .select("id")
# #         .eq(
# #             "event_id",
# #             str(event_id)
# #         )
# #         .limit(1)
# #         .execute()
# #     )


# #     return bool(
# #         response.data
# #     )












# import os
# import json
# import time

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
# # SUPABASE CLIENT
# # =========================================================

# supabase: Client = create_client(
#     SUPABASE_URL,
#     SUPABASE_SECRET_KEY
# )


# # =========================================================
# # GEMINI CLIENTS
# #
# # We intentionally use TWO clients.
# #
# # Query client:
# #   Used during normal visitor chat.
# #   Must fail fast.
# #
# # Index client:
# #   Used only when event is published/updated.
# #   Can have a little more time.
# # =========================================================

# gemini_query_client = genai.Client(
#     api_key=GEMINI_API_KEY,
#     http_options=types.HttpOptions(
#         timeout=12000,  # 12 seconds
#         retry_options=types.HttpRetryOptions(
#             attempts=1  # original request only, no retries
#         )
#     )
# )


# gemini_index_client = genai.Client(
#     api_key=GEMINI_API_KEY,
#     http_options=types.HttpOptions(
#         timeout=30000,  # indexing can take longer
#         retry_options=types.HttpRetryOptions(
#             attempts=1
#         )
#     )
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
#                         "{}",
#                         "[]",
#                         "null",
#                         '""'
#                 ):

#                     chunks.append({
#                         "section":
#                             f"{section}_{index + 1}",

#                         "content":
#                             content
#                     })

#         # -------------------------------------------------
#         # Single object/value
#         # -------------------------------------------------

#         else:

#             content = json.dumps(
#                 value,
#                 ensure_ascii=False,
#                 default=str
#             )

#             if content not in (
#                     "{}",
#                     "[]",
#                     "null",
#                     '""'
#             ):

#                 chunks.append({
#                     "section": section,
#                     "content": content
#                 })

#     return chunks


# # =========================================================
# # TEMPORARY SLUG EXTRACTOR
# #
# # event_id is now the actual RAG identity.
# #
# # event_slug is kept temporarily because your current
# # event_knowledge table still contains event_slug.
# # =========================================================

# def extract_event_slug(
#         event_data: dict
# ) -> str | None:

#     # -----------------------------------------------------
#     # Top-level possible slug fields
#     # -----------------------------------------------------

#     for key in (
#             "event_slug",
#             "eventSlug",
#             "slug",
#             "slug_url",
#             "slugUrl"
#     ):

#         value = event_data.get(key)

#         if value:
#             return str(value)


#     # -----------------------------------------------------
#     # Landing page
#     # -----------------------------------------------------

#     landing_page = (
#             event_data.get("landingPageDesign")
#             or event_data.get("landing_page_design")
#             or {}
#     )

#     if isinstance(landing_page, dict):

#         for key in (
#                 "customSlug",
#                 "custom_slug",
#                 "slug",
#                 "slugUrl",
#                 "slug_url"
#         ):

#             value = landing_page.get(key)

#             if value:
#                 return str(value)


#     # -----------------------------------------------------
#     # Event details fallback
#     # -----------------------------------------------------

#     event_details = (
#             event_data.get("eventDetails")
#             or event_data.get("event_details")
#             or {}
#     )

#     if isinstance(event_details, dict):

#         for key in (
#                 "slug",
#                 "eventSlug",
#                 "event_slug"
#         ):

#             value = event_details.get(key)

#             if value:
#                 return str(value)

#     return None


# # =========================================================
# # CREATE QUERY EMBEDDING
# #
# # HOT PATH:
# # called for every chatbot question.
# #
# # This should fail quickly rather than letting Vercel
# # sit for minutes.
# # =========================================================

# def create_query_embedding(
#         question: str
# ) -> list[float]:

#     if not question or not question.strip():
#         raise ValueError(
#             "Question cannot be empty"
#         )

#     start = time.perf_counter()

#     text = (
#         "task: retrieval query\n"
#         f"query: {question}"
#     )

#     result = gemini_query_client.models.embed_content(
#         model="gemini-embedding-2",
#         contents=text,
#         config=types.EmbedContentConfig(
#             output_dimensionality=768
#         )
#     )

#     elapsed = time.perf_counter() - start

#     print(
#         f"[RAG] Query embedding: "
#         f"{elapsed:.2f}s"
#     )

#     if not result.embeddings:
#         raise RuntimeError(
#             "Gemini returned no query embedding"
#         )

#     return result.embeddings[0].values


# # =========================================================
# # BATCH EVENT EMBEDDINGS
# #
# # Called during publish/update.
# #
# # ONE Gemini request for all event chunks.
# # =========================================================

# def create_document_embeddings(
#         texts: list[str]
# ) -> list[list[float]]:

#     if not texts:
#         return []

#     start = time.perf_counter()

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

#     result = gemini_index_client.models.embed_content(
#         model="gemini-embedding-2",
#         contents=contents,
#         config=types.EmbedContentConfig(
#             output_dimensionality=768
#         )
#     )

#     elapsed = time.perf_counter() - start

#     print(
#         f"[RAG] Batch embedding "
#         f"{len(texts)} chunks: "
#         f"{elapsed:.2f}s"
#     )

#     if not result.embeddings:

#         raise RuntimeError(
#             "Gemini returned no document embeddings"
#         )

#     embeddings = [
#         embedding.values
#         for embedding in result.embeddings
#     ]

#     if len(embeddings) != len(texts):

#         raise RuntimeError(
#             "Embedding count does not match "
#             "event chunk count"
#         )

#     return embeddings


# # =========================================================
# # INDEX / REINDEX EVENT
# #
# # event_id = permanent identity.
# #
# # Only modifies event_knowledge.
# # Does NOT modify your production EventSphere tables.
# # =========================================================

# def index_event_knowledge(
#         event_id: str,
#         event_data: dict,
#         event_slug: str | None = None
# ) -> int:

#     total_start = time.perf_counter()

#     if not event_id:

#         raise ValueError(
#             "event_id is required for RAG indexing"
#         )

#     event_id = str(event_id)


#     # -----------------------------------------------------
#     # Slug only for temporary DB compatibility
#     # -----------------------------------------------------

#     if not event_slug:

#         event_slug = extract_event_slug(
#             event_data
#         )

#     if not event_slug:

#         raise RuntimeError(
#             "Could not determine event_slug. "
#             "Pass event_slug while the old "
#             "event_slug column still exists."
#         )


#     # -----------------------------------------------------
#     # Build chunks
#     # -----------------------------------------------------

#     chunks = build_event_chunks(
#         event_data
#     )

#     if not chunks:
#         return 0


#     # -----------------------------------------------------
#     # Prepare embedding texts
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
#     # ONE embedding API call
#     # -----------------------------------------------------

#     embeddings = create_document_embeddings(
#         embedding_texts
#     )


#     # -----------------------------------------------------
#     # Build DB rows BEFORE deleting previous data
#     # -----------------------------------------------------

#     rows = []

#     for chunk, embedding in zip(
#             chunks,
#             embeddings
#     ):

#         rows.append({

#             "event_id":
#                 event_id,

#             # temporary compatibility
#             "event_slug":
#                 event_slug,

#             "section":
#                 chunk["section"],

#             "content":
#                 chunk["content"],

#             "embedding":
#                 embedding
#         })


#     # -----------------------------------------------------
#     # Delete existing RAG rows for THIS EVENT ONLY
#     # -----------------------------------------------------

#     delete_start = time.perf_counter()

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

#     print(
#         f"[RAG] Delete old knowledge: "
#         f"{time.perf_counter() - delete_start:.2f}s"
#     )


#     # -----------------------------------------------------
#     # Insert all new rows in ONE request
#     # -----------------------------------------------------

#     insert_start = time.perf_counter()

#     (
#         supabase
#         .table("event_knowledge")
#         .insert(rows)
#         .execute()
#     )

#     print(
#         f"[RAG] Insert knowledge: "
#         f"{time.perf_counter() - insert_start:.2f}s"
#     )


#     print(
#         f"[RAG] Total indexing: "
#         f"{time.perf_counter() - total_start:.2f}s"
#     )

#     return len(rows)


# # =========================================================
# # VECTOR SEARCH
# #
# # IMPORTANT:
# # event_id based.
# #
# # Default = TOP 3 chunks.
# # Previously 4.
# #
# # Smaller Gemini prompt = faster response.
# # =========================================================

# def search_event_knowledge(
#         event_id: str,
#         question: str,
#         match_count: int = 3
# ) -> list[dict]:

#     total_start = time.perf_counter()

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
#     # Query embedding
#     # -----------------------------------------------------

#     query_embedding = create_query_embedding(
#         question
#     )


#     # -----------------------------------------------------
#     # Vector DB search
#     # -----------------------------------------------------

#     rpc_start = time.perf_counter()

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

#     print(
#         f"[RAG] Supabase vector search: "
#         f"{time.perf_counter() - rpc_start:.2f}s"
#     )

#     print(
#         f"[RAG] Total RAG search: "
#         f"{time.perf_counter() - total_start:.2f}s"
#     )

#     return response.data or []


# # =========================================================
# # CHAT HISTORY
# #
# # OPTIMIZED:
# # only return last 4 messages by default.
# #
# # Example:
# #
# # User: What are ticket prices?
# # Assistant: ...
# # User: Which one is cheapest?
# # Assistant: ...
# #
# # That's enough context for most follow-ups.
# # =========================================================

# def get_chat_history(
#         event_id: str,
#         session_id: str,
#         limit: int = 4
# ) -> list[dict]:

#     start = time.perf_counter()

#     if not event_id:

#         raise ValueError(
#             "event_id is required"
#         )

#     if not session_id:

#         raise ValueError(
#             "session_id is required"
#         )


#     # -----------------------------------------------------
#     # Newest first so LIMIT gives us latest messages.
#     #
#     # We don't need created_at in the returned result.
#     # -----------------------------------------------------

#     response = (
#         supabase
#         .table("chat_messages")
#         .select(
#             "role,content"
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


#     # Gemini should read oldest -> newest
#     messages.reverse()


#     print(
#         f"[CHAT] Load {len(messages)} history messages: "
#         f"{time.perf_counter() - start:.2f}s"
#     )

#     return messages


# # =========================================================
# # SAVE FULL CHAT TURN
# #
# # OPTIMIZED:
# # User + assistant are inserted together.
# #
# # OLD:
# # 2 Supabase network calls
# #
# # NEW:
# # 1 Supabase network call
# # =========================================================

# def save_chat_turn(
#         event_id: str,
#         session_id: str,
#         user_message: str,
#         assistant_message: str
# ) -> None:

#     if not user_message:
#         return

#     if not assistant_message:
#         return

#     start = time.perf_counter()

#     rows = [
#         {
#             "event_id":
#                 str(event_id),

#             "session_id":
#                 str(session_id),

#             "role":
#                 "user",

#             "content":
#                 user_message
#         },
#         {
#             "event_id":
#                 str(event_id),

#             "session_id":
#                 str(session_id),

#             "role":
#                 "assistant",

#             "content":
#                 assistant_message
#         }
#     ]

#     (
#         supabase
#         .table("chat_messages")
#         .insert(rows)
#         .execute()
#     )

#     print(
#         f"[CHAT] Save full turn: "
#         f"{time.perf_counter() - start:.2f}s"
#     )


# # =========================================================
# # OLD SINGLE-MESSAGE FUNCTION
# #
# # Keep this temporarily so older chatbot.py code does not
# # break immediately.
# #
# # Once chatbot.py uses save_chat_turn(), you can remove it.
# # =========================================================

# def save_chat_message(
#         event_id: str,
#         session_id: str,
#         role: str,
#         content: str
# ) -> None:

#     if role not in (
#             "user",
#             "assistant"
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
# # CHECK WHETHER EVENT HAS RAG DATA
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






"""
rag_service.py  -  data layer

Talks to Supabase (event_knowledge, chat_messages) and Gemini embeddings.

What changed compared with the old 2,200 line file
--------------------------------------------------
* ~1,250 lines of commented-out old code removed.
* SMALL EVENTS SKIP RAG: if an event's knowledge is small (tickets, schedule, venue...)
  it is loaded once, cached, and put straight into the prompt.
  -> no embedding API call and no vector search on most questions.
* Caches (in-process, TTL based): event knowledge, query embeddings,
  chat history per session, and answers to repeated first questions.
* Re-indexing is zero-downtime: insert new rows first, delete the old rows after,
  guarded by a per-event lock (old code deleted first, so chat saw an empty event
  for a moment, and two concurrent indexes could leave duplicate rows).
* Embeddings are sent in batches of 100 so a big event cannot exceed API limits.
"""

import json
import logging
import os
import threading
import time
from collections import OrderedDict

from dotenv import load_dotenv
from google import genai
from google.genai import types
from supabase import Client, create_client

load_dotenv()

log = logging.getLogger("rag")


# =========================================================
# SETTINGS
# =========================================================

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is missing")
    return value


SUPABASE_URL = _require("SUPABASE_URL")
SUPABASE_SECRET_KEY = _require("SUPABASE_SECRET_KEY")
GEMINI_API_KEY = _require("GEMINI_API_KEY")

EMBED_MODEL = os.getenv("EMBED_MODEL", "gemini-embedding-2")
EMBED_DIM = int(os.getenv("EMBED_DIM", "768"))
EMBED_BATCH_SIZE = 100

# If an event has <= this many chunks AND <= this many characters, skip RAG entirely.
FULL_CONTEXT_MAX_CHUNKS = int(os.getenv("FULL_CONTEXT_MAX_CHUNKS", "80"))
FULL_CONTEXT_MAX_CHARS = int(os.getenv("FULL_CONTEXT_MAX_CHARS", "12000"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "4"))

HISTORY_LIMIT = 4  # messages sent to the model


# =========================================================
# CLIENTS  (created once, reused for every request)
# =========================================================

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

# Chat path: fail fast, never retry (a retry doubles the wait).
gemini_query_client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=12000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)

# Index path: runs in the background, can be slower.
gemini_index_client = genai.Client(
    api_key=GEMINI_API_KEY,
    http_options=types.HttpOptions(
        timeout=30000,
        retry_options=types.HttpRetryOptions(attempts=1),
    ),
)


# =========================================================
# TINY TTL CACHE (thread safe, no extra dependency)
# =========================================================

class TTLCache:
    """Small in-memory cache. Values must not be None."""

    def __init__(self, ttl_seconds: float, max_items: int = 1000):
        self.ttl = ttl_seconds
        self.max_items = max_items
        self._data: "OrderedDict[str, tuple[float, object]]" = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: str):
        now = time.monotonic()
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at < now:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: str, value) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def delete_prefix(self, prefix: str) -> None:
        with self._lock:
            for key in [k for k in self._data if k.startswith(prefix)]:
                del self._data[key]


# NOTE: these caches live inside ONE Python process. With several workers/instances
# each has its own copy, so TTLs are kept short enough that stale data fixes itself.
_chunks_cache = TTLCache(ttl_seconds=300, max_items=500)       # event knowledge
_embedding_cache = TTLCache(ttl_seconds=3600, max_items=2000)  # question -> vector
_history_cache = TTLCache(ttl_seconds=1800, max_items=2000)    # session -> last messages
_answer_cache = TTLCache(ttl_seconds=600, max_items=1000)      # repeated first questions

_index_locks: dict[str, threading.Lock] = {}
_index_locks_guard = threading.Lock()


def _get_index_lock(event_id: str) -> threading.Lock:
    with _index_locks_guard:
        lock = _index_locks.get(event_id)
        if lock is None:
            lock = threading.Lock()
            _index_locks[event_id] = lock
        return lock


# =========================================================
# BUILD EVENT CHUNKS  (unchanged logic)
# =========================================================

_EMPTY_JSON = ("{}", "[]", "null", '""')


def build_event_chunks(event_data: dict) -> list[dict]:
    chunks: list[dict] = []

    for section, value in event_data.items():
        if value is None:
            continue

        if isinstance(value, list):
            for index, item in enumerate(value):
                content = json.dumps(item, ensure_ascii=False, default=str)
                if content not in _EMPTY_JSON:
                    chunks.append({"section": f"{section}_{index + 1}", "content": content})
        else:
            content = json.dumps(value, ensure_ascii=False, default=str)
            if content not in _EMPTY_JSON:
                chunks.append({"section": section, "content": content})

    return chunks


def extract_event_slug(event_data: dict) -> str | None:
    """Temporary: the event_knowledge table still has an event_slug column."""

    for key in ("event_slug", "eventSlug", "slug", "slug_url", "slugUrl"):
        value = event_data.get(key)
        if value:
            return str(value)

    landing_page = event_data.get("landingPageDesign") or event_data.get("landing_page_design") or {}
    if isinstance(landing_page, dict):
        for key in ("customSlug", "custom_slug", "slug", "slugUrl", "slug_url"):
            value = landing_page.get(key)
            if value:
                return str(value)

    event_details = event_data.get("eventDetails") or event_data.get("event_details") or {}
    if isinstance(event_details, dict):
        for key in ("slug", "eventSlug", "event_slug"):
            value = event_details.get(key)
            if value:
                return str(value)

    return None


# =========================================================
# EMBEDDINGS
# =========================================================

def create_query_embedding(question: str) -> list[float]:
    """HOT PATH (only used for big events). Cached per question text."""

    if not question or not question.strip():
        raise ValueError("Question cannot be empty")

    cached = _embedding_cache.get(question)
    if cached is not None:
        return cached

    start = time.perf_counter()

    result = gemini_query_client.models.embed_content(
        model=EMBED_MODEL,
        contents=f"task: retrieval query\nquery: {question}",
        config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
    )

    if not result.embeddings:
        raise RuntimeError("Gemini returned no query embedding")

    vector = result.embeddings[0].values
    _embedding_cache.set(question, vector)

    log.info("query embedding %.2fs", time.perf_counter() - start)
    return vector


def create_document_embeddings(texts: list[str]) -> list[list[float]]:
    """Called on publish/update only. Batches of 100 per API request."""

    if not texts:
        return []

    start = time.perf_counter()
    vectors: list[list[float]] = []

    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]

        contents = [
            types.Content(parts=[types.Part.from_text(text=text)])
            for text in batch
        ]

        result = gemini_index_client.models.embed_content(
            model=EMBED_MODEL,
            contents=contents,
            config=types.EmbedContentConfig(output_dimensionality=EMBED_DIM),
        )

        if not result.embeddings or len(result.embeddings) != len(batch):
            raise RuntimeError("Embedding count does not match chunk count")

        vectors.extend(e.values for e in result.embeddings)

    log.info("document embeddings: %d chunks in %.2fs", len(texts), time.perf_counter() - start)
    return vectors


# =========================================================
# INDEX / RE-INDEX EVENT
# =========================================================

def index_event_knowledge(
        event_id: str,
        event_data: dict,
        event_slug: str | None = None,
) -> int:

    total_start = time.perf_counter()

    if not event_id:
        raise ValueError("event_id is required for RAG indexing")

    event_id = str(event_id)

    event_slug = event_slug or extract_event_slug(event_data)
    if not event_slug:
        raise RuntimeError(
            "Could not determine event_slug. Pass event_slug while the old "
            "event_slug column still exists."
        )

    chunks = build_event_chunks(event_data)
    if not chunks:
        return 0

    embedding_texts = [
        f"task: retrieval document\n"
        f"event_id: {event_id}\n"
        f"section: {chunk['section']}\n"
        f"content: {chunk['content']}"
        for chunk in chunks
    ]

    # Slow network call - done OUTSIDE the lock so other work is not blocked.
    embeddings = create_document_embeddings(embedding_texts)

    rows = [
        {
            "event_id": event_id,
            "event_slug": event_slug,  # temporary compatibility
            "section": chunk["section"],
            "content": chunk["content"],
            "embedding": embedding,
        }
        for chunk, embedding in zip(chunks, embeddings)
    ]

    # Zero-downtime swap:
    #   1) remember the old row ids
    #   2) insert the new rows
    #   3) delete ONLY the old rows
    # Visitors never see an empty event, and the lock stops two indexes
    # of the same event running at the same time (which used to create duplicates).
    with _get_index_lock(event_id):
        old = (
            supabase.table("event_knowledge")
            .select("id")
            .eq("event_id", event_id)
            .execute()
        ).data or []
        old_ids = [row["id"] for row in old]

        supabase.table("event_knowledge").insert(rows).execute()

        for i in range(0, len(old_ids), 200):
            (
                supabase.table("event_knowledge")
                .delete()
                .in_("id", old_ids[i:i + 200])
                .execute()
            )

    # Knowledge changed -> forget everything cached for this event.
    _chunks_cache.delete(event_id)
    _answer_cache.delete_prefix(f"{event_id}:")

    log.info("indexed event %s: %d chunks in %.2fs", event_id, len(rows), time.perf_counter() - total_start)
    return len(rows)


# =========================================================
# EVENT CONTEXT  (small event -> everything, big event -> vector search)
# =========================================================

def load_event_chunks(event_id: str) -> dict:
    """
    One Supabase call, then cached for 5 minutes.

    Returns {"empty": bool, "small": bool, "chunks": [{"section","content"}]}
    "small" is True when the whole event fits comfortably in the prompt.
    """

    event_id = str(event_id)

    cached = _chunks_cache.get(event_id)
    if cached is not None:
        return cached

    start = time.perf_counter()

    rows = (
        supabase.table("event_knowledge")
        .select("section,content")
        .eq("event_id", event_id)
        .order("id")
        .limit(FULL_CONTEXT_MAX_CHUNKS + 1)
        .execute()
    ).data or []

    total_chars = sum(len(row["content"]) for row in rows)
    small = len(rows) <= FULL_CONTEXT_MAX_CHUNKS and total_chars <= FULL_CONTEXT_MAX_CHARS

    entry = {
        "empty": not rows,
        "small": small,
        "chunks": rows if small else [],
    }

    _chunks_cache.set(event_id, entry)
    log.info("loaded event knowledge %.2fs (%d chunks, %d chars, small=%s)",
             time.perf_counter() - start, len(rows), total_chars, small)
    return entry


def search_event_knowledge(
        event_id: str,
        question: str,
        match_count: int = RAG_TOP_K,
) -> list[dict]:
    """Vector search. Only used when an event is too big for the prompt."""

    if not event_id:
        raise ValueError("event_id is required for RAG search")

    query_embedding = create_query_embedding(question)

    start = time.perf_counter()

    response = supabase.rpc(
        "match_event_knowledge_by_event_id",
        {
            "query_embedding": query_embedding,
            "target_event_id": str(event_id),
            "match_count": match_count,
        },
    ).execute()

    log.info("vector search %.2fs", time.perf_counter() - start)
    return response.data or []


def get_event_context(event_id: str, retrieval_query: str) -> tuple[list[dict], str]:
    """
    Returns (chunks, mode) where mode is "empty", "full" or "rag".
    "full" = whole event put in the prompt (no embedding, no vector search).
    """

    entry = load_event_chunks(event_id)

    if entry["empty"]:
        return [], "empty"

    if entry["small"]:
        return entry["chunks"], "full"

    return search_event_knowledge(event_id, retrieval_query, RAG_TOP_K), "rag"


# =========================================================
# CHAT HISTORY  (cached per session, written through)
# =========================================================

def _history_key(event_id: str, session_id: str) -> str:
    return f"{event_id}:{session_id}"


def get_chat_history(
        event_id: str,
        session_id: str,
        limit: int = HISTORY_LIMIT,
) -> list[dict]:

    if not event_id:
        raise ValueError("event_id is required")
    if not session_id:
        raise ValueError("session_id is required")

    key = _history_key(event_id, session_id)

    cached = _history_cache.get(key)
    if cached is not None:
        return cached[-limit:]

    start = time.perf_counter()

    messages = (
        supabase.table("chat_messages")
        .select("role,content")
        .eq("event_id", str(event_id))
        .eq("session_id", str(session_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    ).data or []

    messages.reverse()  # oldest -> newest for the model

    _history_cache.set(key, messages)
    log.info("history from DB %.2fs (%d msgs)", time.perf_counter() - start, len(messages))
    return messages


def remember_turn(event_id: str, session_id: str, user_message: str, assistant_message: str) -> None:
    """Update the in-memory history immediately; the DB write can happen later."""

    key = _history_key(event_id, session_id)
    cached = _history_cache.get(key)
    if cached is None:
        return  # cold cache: the next request simply reloads from the DB

    updated = cached + [
        {"role": "user", "content": user_message},
        {"role": "assistant", "content": assistant_message},
    ]
    _history_cache.set(key, updated[-HISTORY_LIMIT * 2:])


def save_chat_turn(
        event_id: str,
        session_id: str,
        user_message: str,
        assistant_message: str,
) -> None:
    """ONE insert for both messages."""

    if not user_message or not assistant_message:
        return

    start = time.perf_counter()

    rows = [
        {"event_id": str(event_id), "session_id": str(session_id),
         "role": "user", "content": user_message},
        {"event_id": str(event_id), "session_id": str(session_id),
         "role": "assistant", "content": assistant_message},
    ]

    supabase.table("chat_messages").insert(rows).execute()
    log.info("saved chat turn %.2fs", time.perf_counter() - start)


# =========================================================
# ANSWER CACHE  (only for first questions of a session)
# =========================================================

def _answer_key(event_id: str, question: str) -> str:
    normalized = " ".join(question.lower().split()).rstrip("?!. ")
    return f"{event_id}:{normalized}"


def get_cached_answer(event_id: str, question: str) -> str | None:
    return _answer_cache.get(_answer_key(str(event_id), question))


def set_cached_answer(event_id: str, question: str, answer: str) -> None:
    _answer_cache.set(_answer_key(str(event_id), question), answer)
