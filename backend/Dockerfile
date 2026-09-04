FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
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

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
