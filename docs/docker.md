# Docker — Milestone 24

Containerized run for Module 12. One service (`api`), not two — see the
comment block at the top of `docker-compose.yml` for why this doesn't
include a separate database container: the app runs on SQLite (an
embedded, in-process database, not a server process), so there's no
second service to actually containerize. Persistence across restarts is
handled by a named Docker volume instead.

## Prerequisites

- Docker Desktop (includes `docker compose`) installed and running.

## First run

```powershell
# Generate a real secret (never reuse this example value)
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set it for this PowerShell session
$env:SECRET_KEY = "<paste the generated value here>"

# Build and start
docker compose build
docker compose up -d
```

`docker compose up` will refuse to start with a clear error if
`SECRET_KEY` isn't set — that's `docker-compose.yml`'s
`${SECRET_KEY:?...}` syntax, the same fail-fast philosophy
`config/settings.py` already uses for the non-containerized app.

## Verifying it's actually working

```powershell
# 1. Container health (waits for Docker's own HEALTHCHECK to report healthy)
docker compose ps

# 2. Liveness endpoint directly
Invoke-RestMethod http://localhost:8000/health
# Expected: @{status=ok}

# 3. Register a real asset through the running container
Invoke-RestMethod -Method Post http://localhost:8000/assets `
    -ContentType "application/json" `
    -Body '{"identifier": "docker-verify-01"}'
# Expected: a full AssetResponse JSON object back, with a generated id

# 4. Swagger UI — open in a browser
start http://localhost:8000/docs
```

If step 3 works, the full stack is proven end-to-end: the container
started, ran its Alembic migrations against the volume-backed SQLite
file (see `Dockerfile`'s `CMD`), and the API successfully wrote through
to it.

A Linux/macOS/WSL/Git-Bash equivalent of steps 1–4 is scripted in
`scripts/docker_smoke_test.sh`, if you'd rather run one command than
four.

## Stopping

```powershell
docker compose down
```

This stops the container but **keeps the named volume** (and therefore
your data) — `docker compose down` alone never deletes your inventory.

To wipe everything, including the persisted database, add `-v`:

```powershell
docker compose down -v
```

## Logs

```powershell
docker compose logs -f api
```

## Rebuilding after a code change

```powershell
docker compose up -d --build
```

## Moving to Postgres later

`config/database.py` already conditionally handles SQLite vs. Postgres
connection arguments — switching databases is a configuration change,
not a code change. When that's actually needed:

1. Add `psycopg2-binary` to `requirements.txt`.
2. Uncomment the `postgres` service block in `docker-compose.yml`.
3. Point `DATABASE_URL` at it, e.g.
   `postgresql://asset_intelligence:${POSTGRES_PASSWORD}@postgres:5432/asset_intelligence`.
4. Rebuild (`docker compose up -d --build`) — the same `alembic upgrade
   head` step in the Dockerfile's `CMD` will create the schema on
   Postgres exactly the same way it does on SQLite today.

Not done now because it would be untested config nobody's asked for yet
— documented here so it's a known, deliberate next step rather than a
surprise.

## Troubleshooting

### `sqlite3.OperationalError: unable to open database file` on startup

If `docker compose logs api` shows this during the `alembic upgrade
head` step, and the container keeps restarting, it's a filesystem
permissions problem, not a code or migration problem: the `appuser`
the container runs as (Milestone 24's non-root user) doesn't have write
access to `/data`, where the named volume mounts.

This was actually hit and fixed during Milestone 24 development — the
original `Dockerfile` created the non-root user but never created `/data`
and handed it to that user before the volume mounted there. The fix is
in the `Dockerfile`: a `RUN mkdir -p /data && chown appuser:appuser
/data` line, placed *before* `WORKDIR /app`, so Docker initializes the
brand-new named volume's ownership from that pre-chowned directory the
first time it mounts. If you ever see this error again after modifying
the `Dockerfile`, check that this line still runs before anything else
touches `/data`, and rebuild.

If you already ran into this with an old image, the broken volume needs
to be recreated, not just rebuilt — a `chown` change in the image
doesn't retroactively fix an already-existing named volume:

```powershell
docker compose down -v   # -v removes the volume too, not just the container
docker compose up -d --build
```

