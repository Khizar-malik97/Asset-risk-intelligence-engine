# Module 12 — Asset Intelligence Module: Scope
*(intended repo path: `docs/scope.md`)*

## 1. In Scope

- Generic Asset, Host, and User inventory management (manual + simulated automatic discovery).
- Asset categorization and critical-asset flagging.
- Exposure signal modeling and attachment.
- Rule-based, explainable risk scoring (weighted named factors, no ML).
- Discrete risk levels and a separate confidence score.
- Search/filtering over the inventory.
- A REST API exposing all of the above.
- JSON export of the inventory.
- Structured logging and environment-based configuration.
- Docker packaging for local/deployment use.
- A read-only integration contract for Modules 1, 2, 8, and 9 to consume.
- Unit, integration, and basic performance testing at every applicable milestone.

## 2. Explicitly Out of Scope (for this module, for now)

- **Real network/agent-based discovery** — this module will build a *provider framework* and one simulated provider. Building real network scanners, EDR agents, or cloud-resource scanners (AWS/Azure/GCP) is deferred to a future module or a later phase.
- **Machine learning or AI-based risk scoring** — explicitly excluded per project rules; scoring stays rule-based and explainable.
- **Authentication / authorization** — this module assumes it sits behind a platform-level gateway/auth layer (owned elsewhere in AXERONIX). No user login, RBAC, or API-key management will be built here. *(Flagging this as an explicit assumption — let me know if this module actually needs to own auth.)*
- **A user interface / dashboard** — visualization is Module 9's responsibility; this module only provides data via API/export.
- **Multi-tenancy** — single-tenant data model assumed; no per-customer/per-org partitioning.
- **Historical trend analysis / time-series risk tracking** — we store current state; tracking risk score history over time is a possible future enhancement, not part of this build.
- **Cloud-native asset types** (S3 buckets, cloud VMs, containers as first-class asset types) — the model is extensible enough to add these later, but they are not part of the initial implementation.

## 3. Assumptions

- A-1: Module 12 runs as its own service/package, callable via REST, independent of Modules 1/2/8/9's own build timelines.
- A-2: Development proceeds against SQLite locally, with the schema designed to also run on Postgres later — no Postgres-specific features will be used prematurely.
- A-3: "Simulated" discovery providers are acceptable stand-ins for real data sources until Module 1 exists; the provider interface is designed so a real provider can be swapped in without changing the reconciliation/inventory logic.

## 4. Explicit Non-Goals

Two things this module will *never* try to be, regardless of how far the roadmap extends:
- A general-purpose CMDB / IT asset management replacement.
- A vulnerability scanner. It *consumes* exposure signals (e.g. "CVE present") as input data — it does not scan for or discover CVEs itself.
