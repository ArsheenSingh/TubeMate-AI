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
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app.py .
COPY rate_limited_llm.py .  
COPY yt_chat_rag_using_langchain.py .
COPY transcript_helper.py .

# Environment variable for the port
ENV PORT=5000
ENV PYTHONUNBUFFERED=1
ENV WEBSHARE_PROXY_USERNAME="pajswpqh"
ENV WEBSHARE_PROXY_PASSWORD="nkmavgiwldpd"

# Expose port
EXPOSE 5000

# Command to run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5000", "--timeout-keep-alive", "300"]

