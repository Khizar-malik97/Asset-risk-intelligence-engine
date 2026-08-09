# Module 12 — Asset Intelligence Module: Developer Guide

This is the onboarding document for the Asset Intelligence Module — Module 12 of
the AXERONIX XDR Copilot platform. If you are new to this codebase, start here.
It links out to the deeper documents (architecture, requirements, API reference)
rather than repeating them, so read it top to bottom once and use it as a map
afterwards.

## What this module does

The Asset Intelligence Module answers one question for the rest of the platform:
**which assets matter, and how exposed are they right now?**

It maintains a canonical inventory of assets (generic assets, hosts, and users),
tracks which are business-critical, records structured exposure signals about
them (internet-facing, unpatched vulnerabilities, etc.), and computes an
**explainable** risk score for each one — a transparent sum of named, weighted
factors that anyone can audit and reproduce by hand. See the root
[`README.md`](../README.md) for the product-level pitch and design philosophy.

## Where to look for what

| You want to... | Go to |
|---|---|
| Understand *why* it's built this way | [`architecture.md`](architecture.md) — layering, tech stack, ADRs |
| Understand *what* it's required to do | [`requirements.md`](requirements.md) and [`scope.md`](scope.md) |
| Call the API | [`api/reference.md`](api/reference.md), or run the app and open `/docs` (Swagger UI) / `/redoc` |
| Run it in Docker | [`docker.md`](docker.md) |
| See measured performance | [`performance_baseline.md`](performance_baseline.md) |
| Understand risk scoring specifically | [Risk scoring, in detail](#risk-scoring-in-detail) below |
| Set up a local dev environment | [Local development](#local-development) below |

## Project layout

```
api/            FastAPI app, routers, dependency injection, error handling
config/         Settings, database engine, risk weight/threshold YAML
models/         Domain models (Asset, Host, User, ExposureSignal) + ORM mappings
schemas/        Pydantic request/response schemas (the API's actual contract)
repositories/   Data-access layer, behind an abstract interface (Milestone 7)
services/       Business logic: inventory, discovery, risk_engine, export
logging_/       Structured logging setup (named logging_ to avoid shadowing stdlib)
migrations/     Alembic migrations
utils/          Small shared utilities (exceptions, datetime helpers)
scripts/        Standalone scripts (performance baseline runner, Docker smoke test)
tests/          unit/, integration/, performance/, fakes/
docs/           This directory
```

The dependency direction is strict and one-way:

```
api  →  services  →  repositories (interface)  →  repositories (SQLAlchemy impl)
                                                          ↓
                                                       models/orm
```

Nothing below `services/` imports FastAPI, and nothing above `repositories/`
imports SQLAlchemy. See [`architecture.md`](architecture.md) for the full
rationale (ADR-002 covers the repository pattern specifically).

## Local development

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 3. Copy and fill in environment config
cp .env.example .env
# at minimum, set SECRET_KEY — config/settings.py refuses to start without it

# 4. Apply database migrations
alembic upgrade head

# 5. Run the test suite
pytest

# 6. Run the app
uvicorn api.main:app --reload
```

With the app running, open **http://127.0.0.1:8000/docs** for interactive
Swagger UI, or **http://127.0.0.1:8000/redoc** for ReDoc — both are generated
live from the FastAPI route definitions and Pydantic schemas, so they can
never drift out of sync with the actual code the way a hand-written spec can.
`GET /health` is a dependency-free liveness check.

Formatting and linting (`black`, `ruff`) and a pre-commit config are set up per
[Milestone 2](../ "M2 — Development Environment Setup"); run `pre-commit
install` once after cloning to get them enforced automatically on commit.

## Risk scoring, in detail

This is the module's core value proposition, so it's worth a closer look here
even though [`architecture.md`](architecture.md) and the code's own docstrings
(`services/risk_engine/`) cover it too.

**The model is deliberately rule-based, not machine-learned.** Every score must
be reproducible by a human with a calculator and the two YAML config files
below — no black boxes, per this module's design philosophy.

1. **Factors** (`services/risk_engine/factors.py`) — each factor inspects one
   named, specific signal about an asset (its `is_critical` flag, its exposure
   signals, its type) and returns a `RiskFactorResult`: whether it triggered,
   how many points it contributed, and a plain-English reason. New factors
   register themselves via the `@register_factor` decorator
   (`services/risk_engine/registry.py`) purely by being imported — no other
   file needs to change to add one.
2. **Weights** (`config/risk_weights.yaml`) — how many points each factor is
   worth. Editing this file retunes scoring with no code change. Every
   registered factor must have an entry here and vice versa — both directions
   are validated at process startup (`services/risk_engine/weights.py`), so a
   typo or a forgotten entry fails loudly at boot, not silently at scoring
   time.
3. **Scoring** (`services/risk_engine/scoring.py`) — sums every factor's
   contribution into a total score, then maps that score to a discrete
   `RiskLevel` (`low` / `medium` / `high` / `critical`) using the ascending
   thresholds in `config/risk_thresholds.yaml`. The full list of
   `RiskFactorResult`s is returned alongside the score as its explanation —
   this is what `GET /assets/{id}/risk` returns.

**Current factors and weights** (from `config/risk_weights.yaml` — this file is
the source of truth; the table below is a snapshot, not a substitute for
reading it):

| Factor | Weight | Triggers when |
|---|---|---|
| `critical_asset_flag` | 30 | Asset is manually flagged business-critical |
| `internet_facing` | 25 | Asset has an `INTERNET_FACING` exposure signal |
| `unpatched_vulnerability` | 15 (×1 per signal, capped at 3) | Asset has one or more `UNPATCHED_VULNERABILITY` signals |
| `privileged_account` | 20 | Asset is a User with `is_privileged = true` |

**Current risk level thresholds** (from `config/risk_thresholds.yaml`): a score
maps to the *highest* level whose threshold it meets or exceeds.

| Level | Minimum score |
|---|---|
| `low` | 0 |
| `medium` | 20 |
| `high` | 50 |
| `critical` | 80 |

**Confidence scoring is intentionally separate** (`services/risk_engine/
confidence.py`, `GET /assets/{id}/confidence`). It answers "how much should I
trust this score?" based on data-source reliability and recency — never
blended into the risk score itself, so "risky" and "uncertain" can never be
confused with each other. See Milestone 14's rationale in the project roadmap
for why that separation is a deliberate design decision, not an oversight.

## Error handling contract

Every error response, from every endpoint, has the same shape:

```json
{
  "error": {
    "code": "asset_not_found",
    "message": "No asset found with id=...",
    "details": { "asset_id": "..." }
  }
}
```

`code` is stable and safe to branch on programmatically; `message` is safe to
show a human; `details` is optional structured context. This is enforced by
exactly three handlers in `api/main.py`, not one handler per exception type —
see that file's module docstring for why, and
[`api/reference.md`](api/reference.md#errors) for the full list of `code`
values currently in use.

## A note on scope

This module deliberately does **not** do active network scanning, machine
learning, authentication, or multi-tenancy — see
[`scope.md`](scope.md#out-of-scope-for-module-12) for the full out-of-scope
list and why each item is excluded. If you're wondering why a capability isn't
here, check there before assuming it was missed.
