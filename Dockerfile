# syntax=docker/dockerfile:1
#
# Multi-stage build (Milestone 24).
#
# Stage 1 (builder) installs Python dependencies into an isolated
# location; stage 2 (runtime) copies only that installed-package
# directory across, never the build toolchain, apt cache, or pip cache
# that produced it. Two concrete effects: a smaller final image, and no
# compiler/build-essential tools present in the image that actually
# serves traffic — nothing to abuse if this container is ever
# compromised.

# ---------- Stage 1: builder ----------
FROM python:3.12-slim AS builder

WORKDIR /app

# Copy ONLY the dependency manifest first. Docker caches layers by their
# inputs — as long as requirements.txt doesn't change, this layer (and
# every layer after it, up to the next COPY) is reused on every rebuild,
# so editing application code doesn't force a full dependency reinstall.
COPY requirements.txt ./

RUN pip install --no-cache-dir --user -r requirements.txt

# ---------- Stage 2: runtime ----------
FROM python:3.12-slim AS runtime

# Run as a non-root user. Nothing in this app needs root, and a
# container running as root turns any future code-execution bug into an
# immediate host-level privilege escalation risk — this single block
# removes that risk class entirely.
RUN groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --create-home --shell /bin/bash appuser

# Create the mount point for the named volume (docker-compose.yml's
# asset_intelligence_data:/data) and hand it to appuser BEFORE the
# volume ever mounts there. This matters because Docker only initializes
# a brand-new named volume's ownership/permissions from whatever already
# exists at that path in the image at the moment of first mount — an
# empty, root-owned /data (the default with no RUN here at all) means
# appuser can never write to it, and every SQLite open fails with
# "unable to open database file" no matter what DATABASE_URL says.
RUN mkdir -p /data && chown appuser:appuser /data

WORKDIR /app

# Only the installed packages come from the builder stage — not its
# build-time layers.
COPY --from=builder /root/.local /home/appuser/.local

# Application code. .dockerignore (see that file) keeps this from
# pulling in tests/, docs/, .venv/, .git/, or any local .env.
COPY --chown=appuser:appuser . .

ENV PATH=/home/appuser/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# Hits the real /health endpoint (api/main.py) — a liveness check with
# zero dependency on the database, exactly so this HEALTHCHECK reflects
# "is the process up," not "is the database also reachable." A DB-down
# scenario should be visible in the app's own logs, not disguised as a
# container restart loop.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

# Run pending Alembic migrations, THEN start the API — never the other
# way around, so the container never serves traffic against a schema
# that doesn't match the code. `exec` replaces the shell process with
# uvicorn (PID 1) instead of running it as a child process, which
# matters for correct SIGTERM handling: Docker/Kubernetes sends SIGTERM
# to PID 1 on shutdown, and without exec that signal would hit the shell
# script, not uvicorn, and graceful shutdown wouldn't happen.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn api.main:app --host 0.0.0.0 --port 8000"]
