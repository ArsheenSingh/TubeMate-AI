FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    libssl-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY rate_limited_llm.py .  
COPY yt_chat_rag_using_langchain.py .
COPY transcript_helper.py .

# Environment variables
ENV PORT=5000
ENV PYTHONUNBUFFERED=1
# Updated proxy credentials for rotating proxy
ENV WEBSHARE_PROXY_USERNAME="pajswpqh-rotate"
ENV WEBSHARE_PROXY_PASSWORD="nkmavgiwldpd"

# Expose port
EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=15s --start-period=10s \
    CMD curl -f http://localhost:5000/health || exit 1
# Command to run the application with increased timeout
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000", "--timeout-keep-alive", "300"]

