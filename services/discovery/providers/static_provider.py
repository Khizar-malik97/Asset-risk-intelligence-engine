"""A reference DiscoveryProviderInterface implementation.

Simulates a simple discovery feed (e.g. an agent check-in report or a
static asset list) by returning a fixed, pre-supplied list of assets.
Real, active-scanning providers are explicitly out of scope for this
module (see docs/scope.md) — this establishes the plug-in pattern that a
future real provider, or Module 1 (Log Collector), will implement the
same way.
"""

from models.asset import Asset
from services.discovery.interfaces import DiscoveryProviderInterface


class StaticDiscoveryProvider(DiscoveryProviderInterface):
    """Returns a fixed, pre-supplied list of assets on every discover() call.

    Useful both as a real (if simple) provider — e.g. reading a static
    asset list from a config file or simple feed — and as the reference
    implementation proving the provider interface works end to end.
    """

    def __init__(self, name: str, assets: list[Asset]) -> None:
        self.name = name
        self._assets = assets

    def discover(self) -> list[Asset]:
        return list(self._assets)
