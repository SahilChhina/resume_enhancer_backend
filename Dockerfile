# Dockerfile (replace yours with this)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# LibreOffice for DOCX->PDF + basic fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-writer \
      fonts-dejavu \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# IMPORTANT: bind to $PORT that Render injects at runtime
# Use a shell form so ${PORT} expands; default to 10000 locally.
CMD ["sh", "-c", "gunicorn --timeout 120 -w 2 -k gthread -b 0.0.0.0:${PORT:-10000} app:app"]
