"""The Discovery Provider contract.

Any source of automatically-discovered assets — a simulated feed today, a
real network scanner or agent check-in later, and eventually Module 1
(Universal Log Collector) — implements this interface. DiscoveryService
(discovery_service.py) knows nothing about *how* a provider finds assets,
only that it can ask it to.
"""

from abc import ABC, abstractmethod

from models.asset import Asset


class DiscoveryProviderInterface(ABC):
    """Contract every discovery provider must implement.

    Attributes:
        name: Unique, human-readable identifier for this provider, used in
            logging so a run can be traced back to its source.
    """

    name: str

    @abstractmethod
    def discover(self) -> list[Asset]:
        """Return every asset this provider currently reports.

        Implementations should NOT set discovery_source themselves —
        DiscoveryService overrides it centrally on every result, so a
        provider can't accidentally mislabel its own output as manual entry.

        Should not raise for "found nothing" (return an empty list); raise
        only for genuine provider failure (e.g. an unreachable data source).
        """
