# Module 12 — Asset Intelligence Module: Requirements
*(intended repo path: `docs/requirements.md`)*

## 1. Purpose

Module 12 provides the AXERONIX XDR Copilot platform with a canonical asset inventory,
critical-asset awareness, and an explainable risk score per asset, so that other modules
(correlation, detection quality, dashboards) can weigh events by the importance and exposure
of the asset they occurred on.

## 2. Stakeholders

| Stakeholder | Interest |
|---|---|
| SOC analyst (end user, via future Module 9 dashboard) | Needs to see which assets are critical/high-risk and why |
| Module 2 — Event Correlation Engine | Needs to query asset criticality/risk to prioritize incidents |
| Module 1 — Universal Log Collector | Will feed raw signals into asset discovery |
| Module 8 — Detection Quality Engine | May weight detection quality analysis by asset importance |
| Module 9 — Executive Dashboard | Consumes aggregate risk/criticality stats |
| You (developer/architect) | Owns build quality, maintainability, and correctness |

## 3. Functional Requirements

### 3.1 Asset Inventory
- FR-1: The system must maintain a canonical inventory of assets.
- FR-2: The system must support three asset kinds at minimum: generic Asset, Host, User.
- FR-3: The system must allow manual registration of an asset with required identifying fields.
- FR-4: The system must allow automatic discovery of assets from raw signals (simulated provider for now).
- FR-5: The system must detect and reconcile duplicate assets arriving from multiple sources.

### 3.2 Classification & Criticality
- FR-6: The system must support assigning an asset to a category (e.g. server, endpoint, domain controller).
- FR-7: The system must allow flagging/unflagging an asset as critical.

### 3.3 Exposure Signals
- FR-8: The system must allow attaching structured exposure signals to an asset (e.g. internet-facing, unpatched CVE present).
- FR-9: The system must allow retrieving all exposure signals for a given asset.

### 3.4 Risk Intelligence
- FR-10: The system must compute a risk score (0–100) per asset from named, weighted factors.
- FR-11: Every risk score must include a human-readable explanation of its contributing factors.
- FR-12: The system must bucket scores into discrete Risk Levels (e.g. LOW/MEDIUM/HIGH/CRITICAL).
- FR-13: The system must compute a Confidence score, separate from the risk score, reflecting data completeness/reliability.
- FR-14: Risk factors must be addable/configurable without changing scoring engine code.

### 3.5 Query & Access
- FR-15: The system must support filtering assets by category, criticality, risk level, and exposure tags.
- FR-16: The system must support basic text search over asset identifiers.
- FR-17: The system must expose all of the above through a REST API.
- FR-18: The system must support exporting the full (or filtered) inventory as JSON.

### 3.6 Platform Integration
- FR-19: The system must expose a stable, documented, read-only contract other modules can consume.

## 4. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | **Explainability** — no ML/AI in the risk engine; every score must be reproducible and traceable to named factors |
| NFR-2 | **Testability** — every component unit-testable in isolation; SOLID principles followed throughout |
| NFR-3 | **Code quality** — PEP8-compliant, type-safe (mypy-checked), formatted (Black), linted (Ruff) |
| NFR-4 | **Modularity** — clear separation of models/schemas/repositories/services/API layers; no layer skipping |
| NFR-5 | **Performance** — single-asset lookup should return well under 200ms; bulk operations tested at realistic scale (thousands of assets) before sign-off |
| NFR-6 | **Portability** — runs identically via Docker locally and (in principle) in a deployed environment |
| NFR-7 | **Configurability** — all environment-specific values (DB URL, risk weights/thresholds) come from configuration, never hardcoded |
| NFR-8 | **Security hygiene** — input validated at every boundary; no secrets committed to source control |
| NFR-9 | **Documentation** — every class, function, API endpoint, and config option documented in beginner-friendly language |
| NFR-10 | **Extensibility** — new asset types, exposure signal types, and risk factors addable without breaking existing behavior |

## 5. Success Criteria for the Module

The module is considered functionally complete when:
1. All FR-1 through FR-19 are implemented and tested.
2. All NFR-1 through NFR-10 are demonstrably satisfied (documented in the final review, per M26).
3. A downstream module could integrate against the documented API contract without reading Module 12's source code.
