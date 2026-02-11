# Mailtagger Docker Image
# Multi-stage build for Gmail email categorizer with local LLM support

FROM python:3.11-slim as base

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Create app directory
WORKDIR /app

# Install system dependencies (minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gmail_categorizer.py email_index.py prompt_service.py .

# Create data directory for persistent storage
RUN mkdir -p /app/data && \
    chmod 755 /app/data

# Create non-root user for security
RUN useradd -m -u 1000 -s /bin/bash mailtagger && \
    chown -R mailtagger:mailtagger /app

# Switch to non-root user
USER mailtagger

# Health check
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python3 -c "import sys; sys.exit(0)" || exit 1

# Default command: daemon mode with credentials in /app/data
CMD ["python3", "gmail_categorizer.py", "--daemon", "--credentials-path", "/app/data"]

