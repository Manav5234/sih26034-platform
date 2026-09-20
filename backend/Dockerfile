FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Tesseract + barcode system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libpng-dev \
    libjpeg-dev \
    libgomp1 \
    tesseract-ocr \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

# Tesseract Python wrapper
RUN pip install --no-cache-dir pytesseract

COPY backend/ .
COPY tests/sharp.png tests/blurry.png /fixtures/

EXPOSE 8000

# Apply schema migrations before serving so declaration region hints are
# persisted on a freshly deployed backend.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
