FROM python:3.12-slim

# Fonts for map labels (Georgian + Latin)
RUN apt-get update && apt-get install -y --no-install-recommends \
        fonts-noto-core fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1 TILE_CACHE_DIR=/app/cache/tiles
VOLUME ["/app/cache"]
CMD ["python", "bot.py"]
