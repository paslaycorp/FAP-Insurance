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

# Create build/runtime user
RUN groupadd -r fap && useradd -r -g fap fap

# Copy only installed packages from builder
COPY --from=builder /root/.local /home/fap/.local
ENV PATH=/home/fap/.local/bin:$PATH

# Copy the complete application module set required by api.py.
# Explicitly copying only a subset of root modules causes production
# containers to fail at import time as new assurance/oracle modules land.
COPY --chown=fap:fap *.py ./

# Switch to non-root
USER fap

# Render supplies PORT for web services. Keep a local default for
# reproducible container execution outside Render.
ENV PORT=8000

# Healthcheck follows the same runtime port as the application.
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/health')" || exit 1

# Render may assign the public service port dynamically. Bind to the
# platform-provided PORT rather than hard-coding 8000.
EXPOSE 8000

CMD ["sh", "-c", "uvicorn api:app --host 0.0.0.0 --port ${PORT:-8000}"]
