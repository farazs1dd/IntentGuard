FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements_mvp.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements_mvp.txt

# Copy application code
COPY . .

# Create necessary directories
RUN useradd --create-home --uid 10001 app && \
    mkdir -p /app/data && chown app:app /app/data
USER app

# Expose port
EXPOSE 8001

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health', timeout=2)"

# Publish the container only on host loopback: -p 127.0.0.1:8001:8001.
CMD ["uvicorn", "composition_server:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
