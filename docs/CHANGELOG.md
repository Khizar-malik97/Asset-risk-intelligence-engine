# Changelog — Module 12: Asset Intelligence Module

All notable changes to this module, organized by milestone. This module
followed a strict one-milestone-at-a-time build process (see the project
roadmap) — every entry below was fully tested and reviewed before the next
began.

## M0–M4 — Foundation
Requirements and architecture documented (`docs/requirements.md`,
`docs/scope.md`, `docs/architecture.md`); development environment
(Git, virtual environment, `black`/`ruff`, pre-commit); project structure
and Pydantic-based settings (`config/settings.py`); structured logging
(`logging_/`, named to avoid shadowing the stdlib `logging` module).

## M5 — Core Domain Models
`Asset`, `Host`, `User` domain models with validation (empty/whitespace
identifiers rejected).

## M6 — Database Design & Logging Infrastructure
SQLAlchemy ORM with joined-table inheritance (`models/orm/`), Alembic
migrations, structured log formatter.

## M7 — Asset Repository Layer
`AssetRepositoryInterface` + `SQLAlchemyAssetRepository`, full CRUD behind
an abstraction the service layer depends on, not the concrete database.

## M8 — Asset Inventory Service
`AssetInventoryService` — the business-logic orchestration layer:
register/get/update/delete, with duplicate-identifier rejection.

## M9 — Settings Hardening & Type Safety
`SECRET_KEY` required with no default, minimum length enforced; full
mypy `--strict` compliance established across the codebase.

## M10 — Categories & Critical Asset Management
`AssetCategory` enum, critical-asset flagging (`flag_as_critical` /
`unflag_as_critical`), category-based listing.

## M11 — Exposure Signals
`ExposureSignal` model + repository + service — structured, timestamped
records of an asset's attack-surface facts (internet-facing, unpatched
vulnerabilities, etc.), attached many-to-one against an asset.

## M12 — Risk Factor Framework
Decorator-based factor registry (`@register_factor`) with YAML-driven
weights (`config/risk_weights.yaml`) — new factors register themselves
purely by being imported, with registry↔config validated bidirectionally
at startup.

## M13 — Explainable Risk Scoring Engine
`RiskScoringEngine` — sums every registered factor's contribution,
maps the total to a `RiskLevel` via configurable thresholds
(`config/risk_thresholds.yaml`), and returns the full per-factor
breakdown as the score's explanation. Deterministic and reproducible by
design — no ML, no black box.

## M14 — Confidence Scoring
`ConfidenceScoringEngine` — a separate 0–100 trust signal (source
reliability + recency decay), deliberately never blended into the risk
score.

## M15 — Discovery Provider Framework
`DiscoveryProviderInterface` + `StaticDiscoveryProvider`, `DiscoveryService`
to run configured providers and persist what they find.

## M16 — Discovery Reconciliation
`ReconciliationService` — merges duplicate asset records sharing an
identifier into one canonical record (most-recently-seen wins, earliest
`first_seen` and any `is_critical=true` are preserved). Idempotent.

## M17 — Host & User Inventory Specialization
`HostInventoryService` / `UserInventoryService` — thin, type-scoped
wrappers so callers working specifically with hosts or users never need
to `isinstance`-check results themselves.

## M18 — Search & Filtering
`AssetSearchService` — category, criticality, asset type, and text
filters pushed down to SQL on the real repository; exposure-signal and
risk-level filters composed on top (the latter necessarily computed in
Python, since risk is never persisted).

## M19 — REST API Layer
Full FastAPI surface: registration (generic/host/user), retrieval,
search, critical/category management, exposure signals, risk, confidence,
discovery trigger and reconciliation — all behind dependency-injected
services (`api/dependencies.py`).

## M20 — Exception Handling & Error Standardization
`utils/exceptions.py`'s `AppError` hierarchy (`NotFoundError` /
`ConflictError` / `InvalidRequestError`); exactly three global handlers in
`api/main.py` produce one consistent envelope —
`{"error": {"code", "message", "details"}}` — for every failure mode,
including FastAPI's own validation errors and an unhandled-exception
catch-all that never leaks internals.

## M21 — JSON Export
`GET /export/assets` — versioned (`schema_version`), filterable (same
filters as search) bulk export, via a schema deliberately decoupled from
the live API response shape so a future API change can't silently break
an already-saved export file.

## M22 — Integration Testing Suite
Full-lifecycle scenarios through the real API (register → flag critical →
attach signal → score → search → export; discover → reconcile → verify
one canonical record) plus six real, specific coverage gaps found and
closed (duplicated validators only tested on one of three schema classes,
a YAML boolean weight silently coercing via Python's `bool`-is-`int`,
the repository interface's default `search()` never exercised with
`asset_type`).

## M23 — Performance Testing
Documented baseline (`docs/performance_baseline.md`) for bulk insert,
filtered search, export, and risk scoring at 500-asset scale; a
`performance` pytest marker keeps these excluded from the everyday test
run.

## M24 — Docker & Environment Configuration
Multi-stage `Dockerfile` (non-root user, migrations-run-before-serve,
DB-independent healthcheck), `docker-compose.yml` with a named volume for
SQLite persistence. Fixed a real permissions bug during verification: the
non-root user had no ownership of the volume mount point, causing every
SQLite open to fail — fixed and documented in `docs/docker.md`'s
troubleshooting section.

## M25 — Documentation
Developer guide (`docs/README.md`) and hand-maintained API reference
(`docs/api/reference.md`) as companions to the live, generated Swagger UI
(`/docs`) and ReDoc (`/redoc`) — verified against the real config values
and schema constraints, not just written from memory.

## M26 — Integration APIs & Production Readiness
Read-only `/integration/*` endpoints for Modules 2, 8, and 9 — a lean
`AssetContext` shape (identity, criticality, risk, confidence), batched
lookup (`POST /integration/assets/context`, up to 500 ids), and aggregate
inventory counts (`GET /integration/summary`) for a dashboard consumer.
Final production-readiness review (`docs/production_readiness_checklist.md`).

**Module declared production-ready. Project complete.**
