# Module 12 — Asset Risk Intelligence Engine: Architecture & Technology Selection
*(intended repo path: `docs/architecture.md`)*

## 1. Architecture Pattern

**Chosen pattern: Layered / Clean Architecture**

```
┌─────────────────────────────────────────────┐
│                   API Layer                   │  FastAPI routers, request/response schemas
├─────────────────────────────────────────────┤
│               Service Layer                   │  Orchestration, use-cases
├───────────────┬───────────────┬───────────────┤
│  Risk Engine   │ Discovery /    │ Inventory     │  Domain logic
│                │ Reconciliation │ Management    │
├───────────────┴───────────────┴───────────────┤
│              Repository Layer                 │  Storage abstraction (interface + impl)
├─────────────────────────────────────────────┤
│         Database (SQLite → PostgreSQL)         │
└─────────────────────────────────────────────┘
```

### Alternatives Considered

| Alternative | Why rejected |
|---|---|
| Event-driven microservice mesh | Adds message-broker infra and eventual-consistency complexity before the domain model is validated. Can be layered on top later if needed. |
| Single-file / script-style build | Fails testability (NFR-2) and modularity (NFR-4) requirements immediately. |

### Why Layered Wins Here
- Each layer is unit-testable with the layer beneath it mocked (NFR-2).
- Business rules (risk scoring, reconciliation) stay independent of storage choice (NFR-4, NFR-10).
- The repository interface gives a clean seam to swap SQLite for Postgres without touching services (NFR-6).

## 2. Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.12+ | Modern type hints, matches the rest of the platform |
| Web framework | FastAPI | Native Pydantic integration, dependency injection, automatic OpenAPI docs (FR-17, NFR-9) |
| Data validation | Pydantic v2 | One validation engine for both API schemas and settings (NFR-8) |
| ORM | SQLAlchemy | Mature, testable, portable between SQLite and Postgres |
| Migrations | Alembic | Versioned schema evolution from M6 onward |
| Database (dev) | SQLite | Zero-infra, fast test runs |
| Database (prod path) | PostgreSQL | Schema designed to be Postgres-portable from day one (assumption A-2) |
| Testing | Pytest | Standard Python testing, strong fixture support for mocked repositories |
| Formatting | Black | Enforces NFR-3 |
| Linting | Ruff | Fast; replaces flake8 + isort |
| Type checking | mypy | Enforces NFR-3 |
| Packaging | Docker | Required by NFR-6 |

**Alternative considered — hand-written SQL instead of an ORM:** rejected. SQLAlchemy provides the DB-portability requirement (A-2) largely for free, at the cost of a modest learning curve, acceptable given the documentation requirement (NFR-9).

## 3. Data Flow (High Level)

```
Manual registration ──┐
                       ├──▶ Inventory Service ──▶ Repository ──▶ Database
Discovery provider ────┘         │
                                  ▼
                          Risk Engine (factors → score → level → confidence)
                                  │
                                  ▼
                     REST API  ──▶  consumers (Modules 2 / 8 / 9)
```

## 4. Architecture Decision Records (ADRs)

### ADR-001: Layered Architecture over Event-Driven
**Decision:** Use a layered architecture (API → Service → Domain Engines → Repository → DB).
**Reasoning:** Simpler to build, test, and reason about at this stage; an event-driven layer can be added on top later (e.g. for Module 1 integration) without restructuring the core.
**Status:** Accepted.

### ADR-002: SQLAlchemy + Alembic over Raw SQL
**Decision:** Use SQLAlchemy as the ORM and Alembic for migrations.
**Reasoning:** Portability between SQLite (dev) and PostgreSQL (prod path) and built-in testability outweigh the learning curve of hand-written SQL.
**Status:** Accepted.

### ADR-003: Rule-Based Risk Scoring, Never ML
**Decision:** All risk scoring is a deterministic sum of named, weighted factors.
**Reasoning:** Mandated by NFR-1 (explainability/reproducibility); also removes the need for model auditing, versioning, or drift monitoring entirely.
**Status:** Accepted — non-negotiable per project rules.

### ADR-004: SQLite for Development, Postgres-Compatible Schema from Day One
**Decision:** Develop against SQLite; avoid any SQLite-only or Postgres-only features in the schema.
**Reasoning:** Avoids a risky "big rewrite" of the persistence layer later (assumption A-2 in scope.md).
**Status:** Accepted.

### ADR-005: API Schemas Kept Separate from ORM Models
**Decision:** Pydantic request/response schemas are distinct classes from SQLAlchemy ORM models.
**Reasoning:** The external API contract (FR-17) can evolve independently of internal storage representation (NFR-4, NFR-10).
**Status:** Accepted.

## 5. Traceability to Requirements

Every requirement from `docs/requirements.md` maps to a layer or component in this architecture:

| Requirement group | Architecture component |
|---|---|
| FR-1 to FR-5 (Inventory) | Inventory Management engine + Repository |
| FR-6, FR-7 (Categories/Criticality) | Inventory Management engine |
| FR-8, FR-9 (Exposure Signals) | Inventory Management engine (signal attachment) |
| FR-10 to FR-14 (Risk Intelligence) | Risk Engine |
| FR-15, FR-16 (Search) | Service layer (search/filter service) |
| FR-17, FR-18 (API/Export) | API layer |
| FR-19 (Platform Integration) | API layer (dedicated integration routes) |
| All NFRs | Enforced across all layers via tooling (Black/Ruff/mypy/Pytest) and the layered design itself |

## 6. Open Items Carried Forward

- Exact risk-weight values and thresholds are deferred to M12/M13 (Risk Factor Framework, Scoring Engine) — this document fixes the *architecture* for scoring, not the *numbers*.
- Exact Postgres connection/deployment details deferred to M24 (Docker & Env Config).
