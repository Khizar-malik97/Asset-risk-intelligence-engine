#!/usr/bin/env python3
"""Standalone performance baseline runner (Milestone 23).

Runs the same operations as tests/performance/test_performance_baseline.py
but as a plain script, not a pytest run — so you get a clean, readable
report you can paste straight into docs/performance_baseline.md after
re-running it on your own machine. pytest's own -s output works too, but
this avoids pytest's collection/setup noise for a report you're going to
hand-copy into documentation.

Usage:
    python scripts/run_performance_baseline.py
"""

import logging
import os
import time
from collections.abc import Generator
from datetime import UTC, datetime
from statistics import mean, median

# Standalone script, not run under pytest, so tests/conftest.py's
# SECRET_KEY-before-import trick doesn't apply automatically here — set
# it the same way, for the same reason (config/settings.py requires it
# with no default, and raises at import time otherwise).
os.environ.setdefault("SECRET_KEY", "perf-baseline-script-do-not-use-in-production")

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from api.dependencies import get_session  # noqa: E402
from api.main import app  # noqa: E402
from models.enums import AssetCategory, DiscoverySource  # noqa: E402
from models.orm.asset_orm import HostORM  # noqa: E402
from models.orm.base import Base  # noqa: E402

# The app's own structured logging (Milestone 4) logs every request at
# INFO — useful in production, just noise in a report meant to be read.
# Silencing it here doesn't touch the app's real logging config.
logging.getLogger().setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

BULK_ASSET_COUNT = 500
API_REGISTRATION_COUNT = 200


def main() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_session() -> Generator[Session, None, None]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = override_get_session
    client = TestClient(app)

    print("=" * 60)
    print("AXERONIX Module 12 — Performance Baseline")
    print(f"Run at: {datetime.now(UTC).isoformat()}")
    print("=" * 60)

    # 1. Bulk ORM insert
    session = session_factory()
    started = time.perf_counter()
    for i in range(BULK_ASSET_COUNT):
        session.add(
            HostORM(
                identifier=f"perf-host-{i:05d}",
                category=AssetCategory.SERVER if i % 2 == 0 else AssetCategory.WORKSTATION,
                is_critical=(i % 10 == 0),
                discovery_source=DiscoverySource.MANUAL,
                first_seen=datetime.now(UTC),
                last_seen=datetime.now(UTC),
                ip_address=f"10.0.{i // 256}.{i % 256}",
                is_internet_facing=(i % 3 == 0),
            )
        )
    session.commit()
    session.close()
    bulk_insert_seconds = time.perf_counter() - started
    print(f"\n1. Bulk insert {BULK_ASSET_COUNT} hosts (ORM, one commit)")
    print(f"   {bulk_insert_seconds:.3f}s total")

    # 2. Read-path benchmarks at scale
    started = time.perf_counter()
    response = client.get("/assets")
    list_all_seconds = time.perf_counter() - started
    print(f"\n2. GET /assets ({BULK_ASSET_COUNT} rows, no filter)")
    print(f"   {list_all_seconds * 1000:.2f}ms, {len(response.json())} returned")

    started = time.perf_counter()
    response = client.get(
        "/assets", params={"category": "server", "is_critical": True, "text": "perf-host"}
    )
    filtered_seconds = time.perf_counter() - started
    print(f"\n3. GET /assets?category&is_critical&text ({BULK_ASSET_COUNT} rows)")
    print(f"   {filtered_seconds * 1000:.2f}ms, {len(response.json())} matched")

    started = time.perf_counter()
    response = client.get("/export/assets")
    export_seconds = time.perf_counter() - started
    print(f"\n4. GET /export/assets ({BULK_ASSET_COUNT} rows)")
    print(f"   {export_seconds * 1000:.2f}ms, {response.json()['asset_count']} exported")

    # 3. API registration cost (smaller count, resets on a fresh DB
    # would be cleaner, but overlapping identifiers are fine — different
    # prefix from the bulk-inserted hosts above)
    durations = []
    for i in range(API_REGISTRATION_COUNT):
        started = time.perf_counter()
        client.post("/assets", json={"identifier": f"api-perf-{i:05d}"})
        durations.append(time.perf_counter() - started)
    total_registration_seconds = sum(durations)
    print(f"\n5. Register {API_REGISTRATION_COUNT} assets via API (one at a time)")
    print(f"   total={total_registration_seconds:.3f}s")
    print(
        f"   mean={mean(durations) * 1000:.2f}ms  median={median(durations) * 1000:.2f}ms  "
        f"max={max(durations) * 1000:.2f}ms"
    )

    # 4. Risk scoring latency
    created = client.post(
        "/assets/hosts",
        json={"identifier": "perf-risk-01", "category": "server", "is_internet_facing": True},
    ).json()
    asset_id = created["id"]
    client.put(f"/assets/{asset_id}/critical")
    client.post(
        f"/assets/{asset_id}/exposure-signals",
        json={"signal_type": "internet_facing", "severity": "high", "description": "Public"},
    )
    started = time.perf_counter()
    client.get(f"/assets/{asset_id}/risk")
    risk_seconds = time.perf_counter() - started
    print("\n6. GET /assets/{id}/risk (1 asset, 1 signal, 2 factors triggered)")
    print(f"   {risk_seconds * 1000:.2f}ms")

    print("\n" + "=" * 60)
    print("Copy the numbers above into docs/performance_baseline.md")
    print("=" * 60)


if __name__ == "__main__":
    main()
