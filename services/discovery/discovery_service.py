"""Discovery Service.

Orchestrates one or more DiscoveryProviderInterface implementations,
persisting every discovered asset directly via the repository — NOT
through AssetInventoryService.register_asset(), which rejects duplicate
identifiers (correct for manual entry, wrong here: multiple discovery
providers are expected to report overlapping assets, which Discovery
Reconciliation, Milestone 16, will merge afterward).
"""

from dataclasses import dataclass

from logging_.logger import get_logger
from models.asset import Asset
from models.enums import DiscoverySource
from repositories.interfaces import AssetRepositoryInterface
from services.discovery.interfaces import DiscoveryProviderInterface

logger = get_logger(__name__)


@dataclass(frozen=True)
class DiscoveryRunResult:
    """Summary of one run_discovery() call.

    Attributes:
        assets: Every asset persisted during this run, across all providers.
        assets_by_provider: Count of assets discovered per provider name,
            for logging/observability — which provider found what.
    """

    assets: list[Asset]
    assets_by_provider: dict[str, int]


class DiscoveryService:
    """Runs configured discovery providers and persists their results."""

    def __init__(
        self,
        providers: list[DiscoveryProviderInterface],
        repository: AssetRepositoryInterface,
    ) -> None:
        self._providers = providers
        self._repository = repository

    def run_discovery(self) -> DiscoveryRunResult:
        """Run every configured provider and persist everything discovered.

        Every result's discovery_source is forced to DISCOVERY_PROVIDER
        here, centrally — regardless of what an individual provider set —
        so mislabeling is structurally impossible, not just a convention
        providers are expected to follow.
        """
        all_assets: list[Asset] = []
        counts_by_provider: dict[str, int] = {}

        for provider in self._providers:
            discovered = provider.discover()
            counts_by_provider[provider.name] = len(discovered)
            logger.info(
                "Discovery provider run complete",
                extra={"provider": provider.name, "assets_found": len(discovered)},
            )

            for asset in discovered:
                asset.discovery_source = DiscoverySource.DISCOVERY_PROVIDER
                saved = self._repository.add(asset)
                all_assets.append(saved)

        logger.info(
            "Discovery run complete",
            extra={
                "total_assets_persisted": len(all_assets),
                "provider_count": len(self._providers),
            },
        )

        return DiscoveryRunResult(assets=all_assets, assets_by_provider=counts_by_provider)
