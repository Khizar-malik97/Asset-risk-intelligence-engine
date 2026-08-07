"""FastAPI dependency providers.

Centralizes how every service gets its collaborators constructed, so
routers only ever depend on service types via `Depends(...)` and never
construct a repository, session, or engine themselves. This mirrors the
Dependency Inversion Principle already used throughout the service layer
(see docs/architecture.md ADR-002) — the API layer is just one more
consumer of that same pattern, not a special case.

Two things worth understanding about the caching choices below:
  - Per-request dependencies (sessions, repositories, most services) are
    plain functions — FastAPI constructs a fresh one per request and
    reuses it within that single request's dependency graph.
  - The Risk Scoring Engine is the one expensive exception: it parses two
    YAML config files and builds every registered factor on construction.
    None of that changes between requests, so it's wrapped in
    @lru_cache — built once per process, matching the same caching
    pattern config/settings.py already uses for Settings.
"""

from collections.abc import Generator
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db_session
from config.settings import settings
from repositories.asset_repository import SQLAlchemyAssetRepository
from repositories.exposure_signal_repository import (
    ExposureSignalRepositoryInterface,
    SQLAlchemyExposureSignalRepository,
)
from repositories.interfaces import AssetRepositoryInterface
from services.discovery.discovery_service import DiscoveryService
from services.discovery.interfaces import DiscoveryProviderInterface
from services.discovery.reconciliation import ReconciliationService
from services.inventory.exposure_signal_service import ExposureSignalService
from services.inventory.host_inventory_service import HostInventoryService
from services.inventory.inventory_service import AssetInventoryService
from services.inventory.search import AssetSearchService
from services.inventory.user_inventory_service import UserInventoryService
from services.risk_engine.confidence import ConfidenceScoringEngine
from services.risk_engine.scoring import RiskScoringEngine
from services.risk_engine.thresholds import load_risk_thresholds
from services.risk_engine.weights import build_factors, load_risk_weights


def get_session() -> Generator[Session, None, None]:
    """Yield a request-scoped database session.

    Thin wrapper around config.database.get_db_session so routers depend
    on something living in api/, not reaching into config/ directly —
    keeps the dependency graph's entry point in one place.
    """
    yield from get_db_session()


def get_asset_repository(
    session: Session = Depends(get_session),
) -> AssetRepositoryInterface:
    return SQLAlchemyAssetRepository(session)


def get_exposure_signal_repository(
    session: Session = Depends(get_session),
) -> ExposureSignalRepositoryInterface:
    return SQLAlchemyExposureSignalRepository(session)


def get_inventory_service(
    repository: AssetRepositoryInterface = Depends(get_asset_repository),
) -> AssetInventoryService:
    return AssetInventoryService(repository)


def get_host_inventory_service(
    repository: AssetRepositoryInterface = Depends(get_asset_repository),
) -> HostInventoryService:
    return HostInventoryService(repository)


def get_user_inventory_service(
    repository: AssetRepositoryInterface = Depends(get_asset_repository),
) -> UserInventoryService:
    return UserInventoryService(repository)


def get_exposure_signal_service(
    repository: ExposureSignalRepositoryInterface = Depends(get_exposure_signal_repository),
) -> ExposureSignalService:
    return ExposureSignalService(repository)


@lru_cache
def get_risk_scoring_engine() -> RiskScoringEngine:
    weights = load_risk_weights(settings.risk_weights_config_path)
    factors = build_factors(weights)
    thresholds = load_risk_thresholds(settings.risk_thresholds_config_path)
    return RiskScoringEngine(factors=factors, thresholds=thresholds)


@lru_cache
def get_confidence_scoring_engine() -> ConfidenceScoringEngine:
    return ConfidenceScoringEngine()


def get_search_service(
    asset_repository: AssetRepositoryInterface = Depends(get_asset_repository),
    exposure_signal_repository: ExposureSignalRepositoryInterface = Depends(
        get_exposure_signal_repository
    ),
    risk_scoring_engine: RiskScoringEngine = Depends(get_risk_scoring_engine),
) -> AssetSearchService:
    return AssetSearchService(
        asset_repository=asset_repository,
        exposure_signal_repository=exposure_signal_repository,
        risk_scoring_engine=risk_scoring_engine,
    )


def get_discovery_providers() -> list[DiscoveryProviderInterface]:
    """Providers DiscoveryService.run_discovery() will invoke.

    Empty by default: StaticDiscoveryProvider (the only provider that
    exists so far, Milestone 15) needs a pre-supplied asset list with no
    sensible default for a real deployment — it exists to prove the
    provider interface works, not as something to run unconfigured
    against production. A real deployment would override this dependency
    (or extend it) once an actual provider — e.g. Module 1's Log Collector
    — exists to plug in.
    """
    return []


def get_discovery_service(
    repository: AssetRepositoryInterface = Depends(get_asset_repository),
    providers: list[DiscoveryProviderInterface] = Depends(get_discovery_providers),
) -> DiscoveryService:
    return DiscoveryService(providers=providers, repository=repository)


def get_reconciliation_service(
    repository: AssetRepositoryInterface = Depends(get_asset_repository),
) -> ReconciliationService:
    return ReconciliationService(repository)
