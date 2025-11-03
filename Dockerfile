FROM python:3.11-slim

# Install system dependencies for OCRmyPDF
RUN apt-get update && apt-get install -y \
    ghostscript \
    tesseract-ocr \
    tesseract-ocr-eng \
    libleptonica-dev \
    libtesseract-dev \
    qpdf \
    unpaper \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Copy requirements and install Python dependencies
COPY requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

# Copy application code
COPY ./app /code/app

# Expose port
EXPOSE 8001

# Run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
