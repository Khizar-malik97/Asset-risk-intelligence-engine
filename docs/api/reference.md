# API Reference — Asset Intelligence Module

This is a static, hand-maintained companion to the **live, interactive**
API documentation. It's here for quick reference and for anyone who wants to
read the contract without running the app. The source of truth for exact
request/response shapes is always the running app's generated docs:

- **Swagger UI:** `GET /docs`
- **ReDoc:** `GET /redoc`
- **Raw OpenAPI schema:** `GET /openapi.json`

Those three are generated directly from the FastAPI route definitions and
Pydantic schemas in `api/routers/` and `schemas/` — they cannot drift out of
sync with the actual code the way this file theoretically could. If anything
here ever disagrees with `/docs`, trust `/docs` and flag the discrepancy.

All routes below are relative to the app root (no global path prefix; see
`api/main.py`). There is no authentication layer in this module — see
[`../scope.md`](../scope.md) for why (a platform-level gateway is assumed to
sit in front of it).

## Contents

- [Health](#health)
- [Assets](#assets)
- [Exposure signals](#exposure-signals)
- [Risk & confidence](#risk--confidence)
- [Discovery](#discovery)
- [Export](#export)
- [Errors](#errors)
- [Enums reference](#enums-reference)

---

## Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Liveness check. No dependency on the database — reflects only "is the process up". Returns `{"status": "ok"}`. |

---

## Assets

Base path: `/assets`. Covers generic assets, hosts, and users uniformly —
`AssetResponse` is one flattened shape for all three (host- and user-specific
fields are `null` where they don't apply).

### Registration

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/assets` | `AssetRegistrationRequest` | Register a generic asset. `201` + `AssetResponse`. `409 duplicate_asset` if the identifier is already registered. |
| `POST` | `/assets/hosts` | `HostRegistrationRequest` | Register a host. `201` + `AssetResponse`. |
| `POST` | `/assets/users` | `UserRegistrationRequest` | Register a user account. `201` + `AssetResponse`. |

All registration bodies share `identifier` (required, 1–255 chars,
whitespace-trimmed, must not be blank), `category` (defaults to
`uncategorized`), and `is_critical` (defaults to `false`).
`HostRegistrationRequest` additionally accepts `ip_address` (validated as a
real IPv4/IPv6 address if present), `operating_system`, and
`is_internet_facing`. `UserRegistrationRequest` additionally accepts
`is_privileged` and `department`.

### Retrieval & search

| Method | Path | Description |
|---|---|---|
| `GET` | `/assets` | Search/list assets. All query parameters below are optional and combine with **AND** semantics; omit all of them to list everything. |
| `GET` | `/assets/critical` | List every asset flagged business-critical. |
| `GET` | `/assets/hosts` | List every host asset. |
| `GET` | `/assets/users` | List every user-account asset. |
| `GET` | `/assets/{asset_id}` | Retrieve a single asset by id. `404 not_found` if missing. |
| `DELETE` | `/assets/{asset_id}` | Delete an asset. `204` on success, `404 not_found` if missing. |

`GET /assets` query parameters: `category`, `is_critical`, `asset_type`,
`text` (substring match against identifier), `exposure_signal_type`,
`risk_level`. Note: filtering by `risk_level` computes risk scores on demand
for the candidate set, since scores are never persisted (see
[risk scoring](../README.md#risk-scoring-in-detail)).

### Criticality & category

| Method | Path | Description |
|---|---|---|
| `PUT` | `/assets/{asset_id}/critical` | Flag an asset critical. Idempotent. |
| `DELETE` | `/assets/{asset_id}/critical` | Remove the critical flag. |
| `PATCH` | `/assets/{asset_id}/category` | Body: `{"category": "..."}`. Set an asset's category. |

---

## Exposure signals

| Method | Path | Description |
|---|---|---|
| `POST` | `/assets/{asset_id}/exposure-signals` | Attach a signal to an asset. Body: `ExposureSignalAttachRequest` (`signal_type`, `severity`, `description` 1–500 chars). `201` + `ExposureSignalResponse`. `404 not_found` if the asset doesn't exist. |
| `GET` | `/assets/{asset_id}/exposure-signals` | List every signal attached to an asset, most recent first. |
| `DELETE` | `/exposure-signals/{signal_id}` | Remove a signal by its own id. `204` on success, `404 not_found` if missing. |

---

## Risk & confidence

| Method | Path | Description |
|---|---|---|
| `GET` | `/assets/{asset_id}/risk` | Compute and return the asset's current `RiskScoreResponse`: total score, `RiskLevel`, and the full list of per-factor results (`factor_name`, `weight_applied`, `triggered`, `reason`). Always computed fresh, never cached. |
| `GET` | `/assets/{asset_id}/confidence` | Compute and return the asset's `ConfidenceScoreResponse` — a separate 0–100 trust signal (source reliability + recency), independent of risk. |

Both `404 not_found` if the asset doesn't exist. See
[Risk scoring, in detail](../README.md#risk-scoring-in-detail) in the
developer guide for the full model, current weights, and thresholds.

---

## Discovery

Base path: `/discovery`. Two explicit actions rather than one combined
endpoint, so a caller can inspect raw provider output before reconciling.

| Method | Path | Description |
|---|---|---|
| `POST` | `/discovery/run` | Run every configured discovery provider and persist what they find. Returns `DiscoveryRunResponse` (`assets`, `assets_by_provider` count breakdown). No providers configured by default — a valid no-op returning an empty result (see `api/dependencies.py::get_discovery_providers`). |
| `POST` | `/discovery/reconcile` | Merge duplicate asset records (same identifier, multiple sources) into one canonical record each. Returns `ReconciliationRunResponse` (`groups_reconciled`, `total_duplicates_removed`). Safe to call anytime — a no-op if there's nothing to merge. |

---

## Export

| Method | Path | Description |
|---|---|---|
| `GET` | `/export/assets` | Export the inventory (or a filtered subset) as one JSON document. Same filter parameters as `GET /assets` (`category`, `is_critical`, `asset_type`, `text`, `exposure_signal_type`, `risk_level`). Returns `ExportResponse`: `schema_version`, `exported_at`, `asset_count`, `assets` (list of `AssetExportSchema`). |

`AssetExportSchema` deliberately mirrors `AssetResponse` field-for-field today
but is a separately versioned contract — see `schemas/export.py`'s docstring
for why they're not the same class.

---

## Errors

Every error response, from every endpoint, has this shape:

```json
{
  "error": {
    "code": "asset_not_found",
    "message": "No asset found with id=...",
    "details": { "asset_id": "..." }
  }
}
```

| HTTP status | `code` | Raised when |
|---|---|---|
| `400` | `invalid_request` | A request is well-formed but violates a business rule only the service layer can check (e.g. `risk_level` filter used without a risk engine configured). |
| `404` | `not_found` (`asset_not_found`, `exposure_signal_not_found`) | The requested resource id doesn't exist. |
| `409` | `conflict` (`duplicate_asset`) | Registering an asset whose identifier is already in the inventory. |
| `422` | `validation_error` | Request body/query failed Pydantic validation (missing field, wrong type, failed a custom validator like `identifier_must_not_be_blank`). `details.errors` carries FastAPI's full validation error list. |
| `500` | `internal_error` | An unhandled server-side bug. The real exception is logged server-side only; the response body never leaks internals (stack traces, file paths, query text). |

This is enforced centrally by three handlers in `api/main.py` rather than
per-route logic — see that file's docstring for the reasoning.

---

## Enums reference

Source of truth: `models/enums.py` and `models/exposure_signal.py`.

**`AssetType`** — `generic`, `host`, `user`

**`AssetCategory`** — `server`, `workstation`, `domain_controller`,
`database_server`, `network_device`, `endpoint`, `service_account`,
`standard_user_account`, `privileged_user_account`, `uncategorized`

**`DiscoverySource`** — `manual`, `discovery_provider`

**`RiskLevel`** — `low`, `medium`, `high`, `critical`

**`ExposureSignalType`** — `internet_facing`, `unpatched_vulnerability`,
`open_admin_port`, `weak_authentication`, `end_of_life_software`

**`ExposureSeverity`** — `low`, `medium`, `high`, `critical`
