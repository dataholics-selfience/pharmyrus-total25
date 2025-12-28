FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .
COPY google_patents_crawler.py .
COPY inpi_crawler.py .

# Railway uses PORT env variable
ENV PORT=8000

# Run with PORT from environment
CMD uvicorn main:app --host 0.0.0.0 --port $PORT
