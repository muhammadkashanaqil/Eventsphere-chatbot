from dotenv import load_dotenv

load_dotenv()

from rag_service import supabase


response = (
    supabase
    .table("event_knowledge")
    .select("id,event_slug,section,content")
    .limit(5)
    .execute()
)

print(response.data)