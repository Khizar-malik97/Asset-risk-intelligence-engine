# Module 12 — Asset Intelligence Module: Requirements

## 1. Purpose
Provide the AXERONIX XDR Copilot platform with a single, authoritative source of asset context: inventory, criticality, exposure, and explainable risk — consumable by other modules.

## 2. Functional Requirements

| ID | Requirement |
|---|---|
| FR-1 | The system shall maintain an inventory of assets, including hosts and users. |
| FR-2 | The system shall support manual registration of assets. |
| FR-3 | The system shall support automatic discovery of assets via pluggable discovery providers. |
| FR-4 | The system shall reconcile asset records from multiple discovery sources into one canonical record. |
| FR-5 | The system shall allow assets to be categorized (e.g., server, endpoint, user). |
| FR-6 | The system shall allow assets to be flagged as critical ("crown jewel"). |
| FR-7 | The system shall record exposure signals (e.g., internet-facing, open ports, known vulnerable services) per asset. |
| FR-8 | The system shall calculate a risk score for each asset using an explainable, rule-based (non-ML) formula. |
| FR-9 | The system shall map risk scores to discrete risk levels (Low/Medium/High/Critical). |
| FR-10 | The system shall provide a factor-by-factor explanation for every computed risk score. |
| FR-11 | The system shall calculate a confidence score, independent of risk score, reflecting data source reliability and recency. |
| FR-12 | The system shall support search and filtering of assets by category, risk level, exposure, and critical flag. |
| FR-13 | The system shall expose all inventory, discovery, risk, and search functionality via a REST API. |
| FR-14 | The system shall support bulk JSON export of the inventory (full or filtered). |
| FR-15 | The system shall expose read-only integration endpoints for Modules 2, 8, and 9. |

## 3. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-1 | All risk scores must be deterministic and reproducible — identical inputs always produce identical outputs. |
| NFR-2 | The system must not use machine learning or opaque models anywhere in the risk-scoring path. |
| NFR-3 | The codebase must be modular, SOLID-compliant, PEP8-compliant, and type-safe. |
| NFR-4 | Every component must have unit and/or integration test coverage before being considered complete. |
| NFR-5 | The system must be deployable via Docker with environment-variable-based configuration. |
| NFR-6 | The system must log all mutations and score calculations in structured, correlation-ID-aware format. |
| NFR-7 | The architecture must support future integration with Module 1 (Log Collector) as an additional discovery provider without core changes. |
| NFR-8 | The system must handle a realistic enterprise asset volume (target baseline to be confirmed in Milestone 23 — Performance Testing) without unacceptable latency. |

## 4. Primary Users / Consumers
- SOC analysts (via API/dashboard, indirectly through Module 9)
- Module 2 (Event Correlation Engine) — consumes asset context to enrich alerts
- Module 8 (Detection Quality Engine) — consumes asset context for detection tuning
- Module 9 (Executive Dashboard) — consumes aggregate risk/criticality data

## 5. Success Criteria
Module 12 is considered functionally complete when:
- All functional requirements (FR-1 through FR-15) are implemented and tested
- All non-functional requirements are demonstrably satisfied
- The module can run standalone via Docker and answer real queries about asset risk with a full explanation
