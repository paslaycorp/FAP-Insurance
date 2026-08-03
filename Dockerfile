# ═════════════════════════════════════════════════════════════
# FAP-Insurance — Production Dockerfile
# Multi-stage: builder → runtime. Minimal attack surface.
# ═════════════════════════════════════════════════════════════

# ── Stage 1: Builder ───────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build deps
RUN apt-get update && apt-get install -y --no-install-recommends gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Stage 2: Runtime ───────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="FAP-Insurance"
LABEL org.opencontainers.image.description="Fraud-resistant claim verification API"
LABEL org.opencontainers.image.version="0.3.0-grand-slam"

WORKDIR /app

# Create non-root user
RUN groupadd -r fap && useradd -r -g fap fap

# Copy only installed packages from builder
COPY --from=builder /root/.local /home/fap/.local
ENV PATH=/home/fap/.local/bin:$PATH

# Copy application code
COPY --chown=fap:fap api.py auth.py config.py logger.py models.py oracles.py ./

# Switch to non-root
USER fap

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

EXPOSE 8000

# Run
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
