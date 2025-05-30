FROM python:3.9-slim

WORKDIR /app


RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libssl-dev \
    libffi-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*


COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Pre-downloading NLTK data to avoid runtime downloads
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('stopwords', quiet=True)"


COPY app.py .
COPY rate_limited_llm.py .  
COPY yt_chat_rag_using_langchain.py .
COPY transcript_helper.py .


ENV PORT=5000
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1


EXPOSE 5000

# Optimized health check with longer intervals for slow startup
HEALTHCHECK --interval=45s --timeout=30s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1


CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000", "--timeout-keep-alive", "300", "--workers", "1"]

