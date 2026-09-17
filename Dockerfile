# ==============================================================================
# Mutual Fund FAQ Assistant (Groww Facts-Only RAG) - Docker Containerfile
# Multi-stage/Layered Production Build with Non-Root Security and Built-in Healthcheck
# ==============================================================================

FROM python:3.10-slim AS runtime

# Set environment flags
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8501 \
    PYTHONPATH=/app

# Install runtime utilities (curl for container healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user
RUN useradd -m -u 10001 -s /bin/bash appuser

WORKDIR /app

# Install Python dependencies first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source, data catalog, chunks, vector database, and frontend assets
COPY src/ ./src/
COPY data/ ./data/
COPY tests/ ./tests/

# Set ownership to unprivileged user
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose default HTTP port
EXPOSE 8501

# Container healthcheck querying the active scheme registry API
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8501}/api/funds || exit 1

# Launch the production HTTP web application (dynamically reading $PORT or defaulting to 8501)
CMD ["python3", "src/app.py", "--host", "0.0.0.0"]
