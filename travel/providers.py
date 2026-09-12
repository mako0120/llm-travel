"""Provider-neutral, fixture-only contracts. No network access occurs here."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ProviderResult:
    state: str
    value: object = None
    provider: str = "fixture"
    version: str = "fixture-v1"


class FixtureRouteProvider:
    """A deterministic route matrix used only for tests and offline development."""

    def __init__(self, matrix: Mapping[tuple[str, str], int] | None = None, configured=True):
        self._matrix = dict(matrix or {})
        self._configured = configured

    def route_minutes(self, origin, destination):
        if not self._configured:
            return ProviderResult("unconfigured")
        value = self._matrix.get((origin, destination))
        if value is None:
            return ProviderResult("unavailable")
        if type(value) is not int or value < 0:
            return ProviderResult("invalid")
        return ProviderResult("available", value)


class FixtureSourceProvider:
    """Returns supplied records as fixture provenance; it never fetches a URL."""

    def __init__(self, records=None, configured=True):
        self._records = dict(records or {})
        self._configured = configured

    def lookup(self, key):
        if not self._configured:
            return ProviderResult("unconfigured")
        value = self._records.get(key)
        return ProviderResult("available", value) if value is not None else ProviderResult("unavailable")
