FROM python:3.13-slim

WORKDIR /app

# Tizim paketlarini o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Talablarni o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyiha kodlarini nusxalash
COPY . .

# Ma'lumotlar papkasi mavjudligini ta'minlash
RUN mkdir -p data

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
