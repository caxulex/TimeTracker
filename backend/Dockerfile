# ============================================
# TIME TRACKER - Backend Dockerfile
# Production-ready Python FastAPI application
# ============================================
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security (or use existing)
RUN if ! id -u appuser > /dev/null 2>&1; then \
        useradd -m -u 1001 -s /bin/bash appuser; \
    fi && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8080

# Health check - use curl with Host header to pass TrustedHostMiddleware
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f -H "Host: localhost" http://127.0.0.1:8080/health || exit 1

# Run the application
# --proxy-headers: trust X-Forwarded-For / X-Forwarded-Proto from the
#   reverse proxy. Without this flag uvicorn ignores forwarded headers
#   entirely, defeating the app-level TRUSTED_PROXIES setting.
# --forwarded-allow-ips="*": Caddy runs on the host and connects via the
#   Docker bridge gateway, which appears inside the container as a
#   non-loopback address that varies by deployment. Restricting to
#   "127.0.0.1" would silently drop the forwarded headers. Defense in
#   depth: docker-compose.prod.yml binds this port to 127.0.0.1 on the
#   host, so only the Caddy reverse proxy can reach the container in
#   the first place.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips=*"]
