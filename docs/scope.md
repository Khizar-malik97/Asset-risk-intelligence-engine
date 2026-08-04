# Module 12 — Asset Intelligence Module: Scope

## In Scope
- Asset, host, and user inventory management (CRUD)
- Manual asset registration
- Pluggable automatic discovery framework + one reference provider
- Discovery reconciliation / deduplication logic
- Asset categorization and critical-asset flagging
- Exposure signal modeling
- Rule-based, explainable risk scoring engine and risk levels
- Confidence scoring (data quality/trust, separate from risk)
- Search and filtering
- REST API for all of the above
- JSON export
- Read-only integration endpoints for Modules 2, 8, 9
- Structured logging, configuration management, Docker packaging
- Unit, integration, and performance testing

## Out of Scope (for Module 12)
- Actual network scanning / active discovery engines (Milestone 15 builds the *framework* and one simple reference provider — real scanning integrations are a future module or future work, not this module)
- Machine-learning-based risk prediction of any kind
- The Universal Log Collector itself (Module 1) — Module 12 only defines the interface Module 1 will later plug into
- The Event Correlation Engine (Module 2), Detection Quality Engine (Module 8), or Executive Dashboard (Module 9) implementations — Module 12 only exposes data *to* them
- User authentication / authorization for the platform as a whole (assumed to be handled by a platform-level auth layer, not rebuilt here)
- Multi-tenancy (single-tenant assumption for this module's initial build)
- Real-time streaming ingestion (initial version is request/response + batch discovery, not a streaming pipeline)

## Assumptions
- A platform-level API gateway/auth layer exists or will exist separately; Module 12's API assumes it sits behind that gateway.
- Initial deployment target is a single-tenant SOC environment; multi-tenancy would be a future enhancement, not part of this build.
- "Enterprise asset volume" for performance baselining will be defined concretely in Milestone 23, in agreement with you, based on realistic target environments.

## Open Questions (to revisit if they become relevant)
- Exact performance/scale targets (deferred to Milestone 23)
- Which specific discovery provider(s) beyond the reference implementation are actually needed for your environment (deferred until Milestone 15, once priorities are clearer)
