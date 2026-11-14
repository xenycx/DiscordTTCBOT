FROM python:3.12-slim

# Map label fonts are bundled in ttc/fonts (Noto, SIL OFL 1.1).
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PYTHONUNBUFFERED=1 TILE_CACHE_DIR=/app/cache/tiles
VOLUME ["/app/cache"]
CMD ["python", "bot.py"]
