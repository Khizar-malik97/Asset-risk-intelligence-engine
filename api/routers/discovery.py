"""Discovery-related API endpoints.

Two operations, matching the two services built in Milestones 15 and 16:
running discovery (finding/persisting assets from configured providers)
and reconciliation (merging the duplicates discovery is expected to
produce). Kept as separate, explicit POST actions rather than combined —
a caller may reasonably want to run discovery without immediately
reconciling, e.g. to inspect raw provider output first.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_discovery_service, get_reconciliation_service
from schemas.responses import DiscoveryRunResponse, ReconciliationRunResponse
from services.discovery.discovery_service import DiscoveryService
from services.discovery.reconciliation import ReconciliationService

router = APIRouter(prefix="/discovery", tags=["discovery"])


@router.post("/run", response_model=DiscoveryRunResponse)
def run_discovery(
    service: DiscoveryService = Depends(get_discovery_service),
) -> DiscoveryRunResponse:
    """Run every configured discovery provider and persist what they find.

    With no providers configured (the Milestone 19 default — see
    api/dependencies.py::get_discovery_providers), this is a valid no-op:
    returns an empty result rather than an error.
    """
    result = service.run_discovery()
    return DiscoveryRunResponse.model_validate(result)


@router.post("/reconcile", response_model=ReconciliationRunResponse)
def reconcile_discovered_assets(
    service: ReconciliationService = Depends(get_reconciliation_service),
) -> ReconciliationRunResponse:
    """Merge duplicate asset records sharing an identifier into one
    canonical record each. Safe to call anytime — a no-op if there are no
    duplicates to merge (Milestone 16 is idempotent by design)."""
    result = service.reconcile_all()
    return ReconciliationRunResponse.model_validate(result)
