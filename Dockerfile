FROM python:3.11-slim

# Polices DejaVu : utilisées par le moteur pour les symboles absents des polices de base
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core fonts-dejavu-extra \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT}"]
