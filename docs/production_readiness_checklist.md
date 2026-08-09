# Production Readiness Checklist — Module 12: Asset Intelligence Module

Final review, Milestone 26. Each item below was actually re-verified at
this milestone, not carried over unchecked from an earlier one — dates
and evidence are noted so this stays an honest record, not a formality.

## Tests

- [x] **Full regression suite green.** 325 tests passing (default run),
      0 failures. `pytest -v`
- [x] **Performance suite green.** 6/6 passing against documented
      regression-detection ceilings. `pytest -m performance -v -s`
- [x] **Type checking clean.** mypy `--strict`, 110 source files, 0 errors.
- [x] **Formatting and linting clean.** `black --check` and `ruff check`
      both pass with zero findings across the whole repo.
- [x] **Every milestone from M5 onward has both unit and integration
      test coverage** — not just the milestone that introduced a
      feature; M22 specifically closed real gaps found by reviewing
      coverage output line-by-line, not just chasing a percentage.

## Security

- [x] **No hardcoded secrets.** Grepped the full source tree for
      inline `SECRET_KEY` assignments outside `config/settings.py`
      (which reads it from environment) and `tests/` (which sets a
      throwaway value) — none found.
- [x] **`.env` is git-ignored**, and `.env.example` ships only an
      obviously-fake placeholder value with an inline comment on how to
      generate a real one.
- [x] **`SECRET_KEY` has no default anywhere** — `config/settings.py`
      raises at startup if it's missing or under 16 characters;
      `docker-compose.yml`'s `${SECRET_KEY:?...}` syntax refuses to
      start the container the same way.
- [x] **Docker image runs as a non-root user** (`appuser`, uid 1000) —
      established in M24, verified again here: `whoami` inside the
      running container returns `appuser`, not `root`.
- [x] **Error responses never leak internals.** The M20 catch-all
      handler logs the real exception server-side only; the client
      always gets a generic `internal_error` message, never a stack
      trace, file path, or query text.
- [x] **No SQL injection surface.** All queries go through SQLAlchemy's
      parameterized query builder (`repositories/asset_repository.py`)
      — no raw string-interpolated SQL anywhere in the codebase.

## Architecture & Code Quality

- [x] **Dependency direction is one-way and enforced by convention
      throughout**: `api` → `services` → `repositories` (interface) →
      `repositories` (SQLAlchemy implementation) → `models/orm`.
      Nothing below `services/` imports FastAPI; nothing above
      `repositories/` imports SQLAlchemy directly.
- [x] **Every module has a docstring explaining its purpose and, where
      relevant, the design decision behind it** — reviewed via a
      Python AST pass at M25 to confirm systematically, not just
      spot-checked. The only files without one are empty `__init__.py`
      package markers and the Alembic-generated `migrations/env.py`,
      which is standard boilerplate.
- [x] **Error handling is centralized**, not scattered per-route (M20).
- [x] **Risk scoring is deterministic and explainable by design** — no
      ML, every score reproducible from the same inputs, every factor
      named and independently testable (M12–M13's core requirement,
      still true at final review).

## API Contract

- [x] **Every error response, from every endpoint, shares one envelope
      shape** — `{"error": {"code", "message", "details"}}` — verified
      by a dedicated parametrized test
      (`tests/integration/test_error_handling.py`) that checks the
      *structure*, not just individual known error cases.
- [x] **OpenAPI/Swagger (`/docs`) and ReDoc (`/redoc`) are live and
      accurate** — generated directly from route definitions and
      Pydantic schemas, confirmed rendering correctly through a running
      Docker container in Chrome during M24 verification.
- [x] **Read-only integration contract for Modules 2, 8, 9 exists and
      is tested** (M26): `GET /integration/assets/{id}/context`,
      `POST /integration/assets/context` (batched, up to 500 ids),
      `GET /integration/summary`.

## Deployment

- [x] **`docker compose up` brings up a working, healthy module from a
      clean clone** — verified end-to-end on a real Windows/Docker
      Desktop/WSL2 setup during M24: health check passes, a real
      `POST /assets` write persists through the volume-backed SQLite
      file, Swagger UI renders correctly in Chrome.
- [x] **Database migrations run automatically on container start**,
      before the API begins serving traffic (`Dockerfile`'s `CMD`) —
      the container can never serve requests against a stale schema.
- [x] **A real deployment bug was found and fixed during verification,
      not just assumed away**: the non-root container user initially
      had no write access to the volume mount point, causing every
      SQLite open to fail. Fixed in the `Dockerfile` and documented in
      `docs/docker.md`'s troubleshooting section — this class of bug is
      now unlikely to resurface silently, since anyone hitting it again
      has a documented diagnosis and fix to check against first.
- [x] **Path to Postgres is documented, not silently missing.** SQLite
      is the shipped default (appropriate for this module's current
      scale); `config/database.py` already handles both dialects, and
      `docs/docker.md` documents the exact steps to switch when needed.

## Documentation

- [x] **A new engineer could onboard using only the docs** — developer
      guide (`docs/README.md`) covers local setup, project layout,
      dependency direction, and the risk-scoring model in detail;
      `docs/api/reference.md` covers every route; both were checked
      line-by-line against the real code and config during M25 (exact
      weight/threshold values, field length limits) rather than trusted
      on sight.
- [x] **This changelog** (`docs/CHANGELOG.md`) gives a milestone-by-
      milestone record of what was built and why.
- [x] **Out-of-scope items are explicit**, not silently absent —
      `docs/scope.md` documents that this module deliberately does not
      do active network scanning, machine learning, authentication, or
      multi-tenancy, and why each is excluded.

## Known, Documented Limitations (not blockers — deliberate scope)

- No authentication/authorization layer — a platform-level gateway is
  assumed to sit in front of this module (see `docs/scope.md`).
- No pagination on list endpoints yet — noted as a real, measured
  finding in `docs/performance_baseline.md` (unfiltered `GET /assets`
  cost scales with rows *returned*), not a surprise; the lever to pull
  if/when it matters at real scale.
- SQLite is the default database — appropriate for current scale;
  Postgres migration path is designed for and documented, not built,
  since building it now would be untested config nobody has asked for.
- Discovery currently ships one concrete provider
  (`StaticDiscoveryProvider`) — the interface is built for more, but
  only one is implemented, matching current integration needs.

## Sign-off

- [x] Full regression suite run one final time at this milestone: **325
      passed, 0 failed.**
- [x] This checklist reviewed and approved.

**Module 12 (Asset Intelligence Module) is declared production-ready.**
