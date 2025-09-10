# Use slim, then add LibreOffice for DOCX->PDF
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# OS deps: LibreOffice + fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-writer \
      fonts-dejavu \
      locales \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Render will honor PORT; default 10000
ENV PORT=10000
CMD ["gunicorn", "-b", "0.0.0.0:10000", "app:app"]
