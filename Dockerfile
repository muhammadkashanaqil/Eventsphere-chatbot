# Always-on container: no cold starts, connections and caches stay warm.
# Deploy it (Render / Railway / Fly.io / Cloud Run with min-instances=1) in the SAME REGION as your Supabase project.
FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./

EXPOSE 8000
# 2 workers: one can answer while the other is indexing. Caches are per worker (TTLs are short on purpose).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
