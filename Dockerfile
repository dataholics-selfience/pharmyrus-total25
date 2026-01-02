# Pharmyrus v31.0 - Docker Image
FROM python:3.11-slim

# Metadata
LABEL maintainer="Pharmyrus Team"
LABEL version="31.0"
LABEL description="Patent & R&D Intelligence API"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 pharmyrus && \
    chown -R pharmyrus:pharmyrus /app
USER pharmyrus

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health')" || exit 1

# Run application
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
