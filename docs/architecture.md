# Module 12 — Asset Intelligence Module: Architecture

## 1. Architectural Pattern: Layered / Clean Architecture

```
+-------------------------------------------+
|          API Layer (FastAPI)               |  <- HTTP in/out only
+-------------------------------------------+
|     Service Layer (business logic)         |  <- orchestration, risk engine,
|                                             |     discovery, reconciliation
+-------------------------------------------+
|    Repository Layer (data access)          |  <- behind an interface
+-------------------------------------------+
|       Database (SQLAlchemy + DB)           |
+-------------------------------------------+
```

Each layer depends only on the layer directly beneath it. The Service Layer
depends on an abstract `AssetRepositoryInterface`, not a concrete database
implementation (Dependency Inversion Principle) — this lets us swap storage
without touching business logic.

### Alternatives Considered

| Alternative | Why Rejected |
|---|---|
| Fat model (logic on ORM models) | Harder to unit test in isolation; couples persistence and business logic |
| Microservices split per concern | Unnecessary complexity for a single module at this stage; can be split later if a layer needs independent scaling |
| Event-driven/message-queue architecture | No current requirement needs async event processing; adds infrastructure with no current payoff |

## 2. Technology Stack

| Concern | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Strong typing support, matches project stack |
| Web framework | FastAPI | Async-capable, auto-generates OpenAPI docs, native Pydantic integration |
| Validation | Pydantic v2 | Fast, integrates natively with FastAPI |
| ORM | SQLAlchemy 2.0 | Supports SQLite (dev) and PostgreSQL (prod) with the same code |
| Migrations | Alembic | Standard SQLAlchemy migration tool |
| Dev database | SQLite | Zero setup, fast test runs |
| Prod database | PostgreSQL | Production-grade concurrency and indexing |
| Testing | Pytest + pytest-cov | Fixture support, coverage reporting |
| Formatting/Linting | Black + Ruff | Fast, minimal config |
| Containerization | Docker + docker-compose | Consistent local/prod runtime |
| Config | Pydantic BaseSettings + .env | 12-factor config, type-validated |
| Logging | Python `logging` + JSON formatter | Structured logs without heavy dependencies |

No machine learning or AI libraries are included in this stack, per NFR-2.

## 3. System-Level Data Flow

```
Manual Registration --+
                       +--> Reconciliation --> Asset Repository --> Database
Discovery Providers ---+                              |
                                                        v
                                              Risk Engine (factors,
                                              scoring, confidence)
                                                        |
                                                        v
                                    REST API <-- Search/Filter/Export
                                        |
                                        v
                        Consumers: Module 2, Module 8, Module 9
```

## 4. Architecture Decision Records (ADRs)

### ADR-001: Layered Architecture with Repository Pattern
**Decision:** Use a layered architecture (API -> Service -> Repository -> DB)
with the repository pattern for data access.
**Rationale:** Testability, separation of concerns, and future flexibility
to change storage without touching business logic.
**Alternatives considered:** Fat-model design, microservices split.
**Status:** Accepted.

### ADR-002: SQLite for Dev/Test, PostgreSQL for Production
**Decision:** Use SQLAlchemy as the abstraction layer so the same code runs
against SQLite locally and PostgreSQL in production.
**Rationale:** Fast local iteration without sacrificing production-grade
concurrency and indexing later.
**Status:** Accepted.

### ADR-003: No ML/AI in Risk Scoring
**Decision:** The risk engine will be entirely rule-based and explainable.
**Rationale:** NFR-2 explicitly requires deterministic, explainable scoring;
ML models cannot guarantee reproducibility or a factor-by-factor explanation.
**Status:** Accepted.

### ADR-004: FastAPI as the Web Framework
**Decision:** Use FastAPI over Flask or Django.
**Rationale:** Native async support, automatic OpenAPI/Swagger generation
(needed for Milestone 25), first-class Pydantic integration for validation.
**Status:** Accepted.

## 5. Requirement Traceability

Every requirement from `requirements.md` maps to a layer/component in this
architecture:

| Requirement | Primary Component |
|---|---|
| FR-1 to FR-2 (inventory, manual registration) | Service Layer (Inventory Service), Repository Layer |
| FR-3 to FR-4 (discovery, reconciliation) | Service Layer (Discovery, Reconciliation) |
| FR-5 to FR-7 (categories, criticality, exposure) | Models + Service Layer |
| FR-8 to FR-11 (risk scoring, levels, explanation, confidence) | Risk Engine (Service Layer) |
| FR-12 (search/filter) | Service Layer (Search) + Repository queries |
| FR-13 (REST API) | API Layer |
| FR-14 (JSON export) | Service Layer (Export) + API Layer |
| FR-15 (integration endpoints) | API Layer (dedicated read-only routers) |
| NFR-1, NFR-2 (deterministic, no ML) | Risk Engine design (ADR-003) |
| NFR-3 (SOLID, PEP8, type-safe) | Enforced across all layers via Black/Ruff + interfaces |
| NFR-4 (testing) | Pytest suite across all layers |
| NFR-5 (Docker) | Containerization (Milestone 24) |
| NFR-6 (logging) | Logging Layer (Milestone 4) |
| NFR-7 (future Module 1 integration) | Discovery Provider interface (ADR-001 pattern) |
