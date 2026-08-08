# Performance Baseline — Milestone 23

Documented baseline for Module 12's operations most likely to degrade as
the inventory grows. Regenerate this table on your own machine after any
change that touches the read path (search, export, risk scoring) or the
write path (registration), by running:

```powershell
python scripts/run_performance_baseline.py
```

or, for the same numbers plus pass/fail assertions against generous
regression-detection ceilings:

```powershell
pytest -m performance -v -s
```

## How to read this

These are **guardrails against a gross regression** (e.g. an
accidentally-reintroduced N+1 query, or search filtering falling back
from the SQL-pushed-down path to the Python-side default) — not a tight
performance SLA. The `MAX_*` thresholds in
`tests/performance/test_performance_baseline.py` are set well above the
measured sandbox numbers below specifically so this suite stays reliable
across different hardware, doesn't flake on a slower CI runner, and
still fails loudly if something gets meaningfully slower.

Dataset for every benchmark below: **500 hosts** in an in-memory SQLite
database (same `StaticPool` setup every other integration test uses),
unless noted otherwise.

## Last measured baseline

| Environment | Date |
|---|---|
| Development sandbox (reference only — re-run on your target machine) | 2026-08-08 |

| Operation | Result | Ceiling (regression guardrail) |
|---|---|---|
| Bulk insert 500 hosts (ORM, one commit) | 37ms | < 5.0s |
| `GET /assets` — 500 rows, no filter | 186ms | < 1.0s |
| `GET /assets` — combined filter (category + criticality + text), 500 rows, 50 matched | 23ms | < 1.0s |
| `GET /export/assets` — 500 rows | 171ms | < 1.0s |
| Register 200 assets via the real API, one at a time | 753ms total (mean 3.76ms, median 3.47ms, max 39ms per request) | < 10.0s total |
| `GET /assets/{id}/risk` — 1 asset, 1 exposure signal, 2 factors triggered | 6ms | < 0.1s |

## Observations worth noting (not action items)

- **Unfiltered `GET /assets` (186ms) is ~8x slower than the filtered
  query returning 50 rows (23ms)**, despite both hitting the same table.
  This scales with row *count returned*, not filter complexity — the
  cost is Pydantic response validation/serialization across 500
  `AssetResponse` objects, not the SQL query itself (the filtered query
  also touches all 500 rows in the WHERE clause, just returns fewer).
  Expected behavior, not a bug: an endpoint returning more JSON takes
  longer to build the response. Worth remembering if a future milestone
  adds pagination — that's the lever that would bring this down, not a
  query optimization.
- **Per-request registration latency (mean 3.76ms) is dominated by
  Python/HTTP-stack overhead, not the duplicate-identifier query** — the
  raw bulk ORM insert above shows 500 rows committing in 37ms total,
  i.e. under 0.1ms/row at the database layer alone.
- The SQL-pushed-down filters from Milestone 18 are doing their job:
  filtering 500 rows down to 50 (23ms) is *faster* than listing all 500
  unfiltered (186ms), because fewer rows means less to serialize back
  out — exactly the outcome that milestone was built to achieve.

## Re-baselining

If a future milestone changes the read or write path in a way that
meaningfully shifts these numbers (intentionally — e.g. adding
pagination, or unintentionally — a regression the test suite catches),
re-run the script above and update the table and date in this file.
