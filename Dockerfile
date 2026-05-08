FROM python:3.11-slim

WORKDIR /app

# Install OS-level deps needed by sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 && rm -rf /var/lib/apt/lists/*

COPY prototype/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the full source tree
COPY prototype/ ./prototype/

WORKDIR /app/prototype

# Pre-cache the embedding model so first request isn't slow
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 7860

CMD ["uvicorn", "src.hackathon_agent.app:app", "--host", "0.0.0.0", "--port", "7860"]
