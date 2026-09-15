"""Provider contracts and a permit-aware catalog. No network access occurs here."""

from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class ProviderResult:
    state: str
    value: object = None
    provider: str = "fixture"
    version: str = "fixture-v1"


@dataclass(frozen=True)
class ProviderCapability:
    """A source integration that can be shown safely before credentials exist."""

    id: str
    name: str
    state: str
    purposes: tuple[str, ...]
    setup: tuple[str, ...]
    documentation_url: str
    constraint: str


def provider_catalog():
    """Return public setup metadata only; never expose credentials or fetch data.

    A catalog entry is deliberately not a claim that the provider is currently
    usable.  Live requests require a separately configured, terms-compliant
    adapter and are recorded as evidence before they can enter an itinerary.
    """
    return (
        ProviderCapability(
            "google_places", "Google Maps Places API", "configuration_required",
            ("restaurant and attraction discovery", "place details and ratings"),
            ("Google Cloud project", "Places API enabled", "restricted API key"),
            "https://developers.google.com/maps/documentation/places/web-service/text-search",
            "Use returned data with required attribution and applicable Google Maps Platform policies.",
        ),
        ProviderCapability(
            "google_routes", "Google Maps Routes API", "configuration_required",
            ("route duration", "transit, walking, taxi and rental-car route options"),
            ("Google Cloud project", "Routes API enabled", "restricted API key"),
            "https://developers.google.com/maps/documentation/routes/compute_route_directions",
            "Request only fields needed for the plan and save retrieval time and source evidence.",
        ),
        ProviderCapability(
            "official_gtfs", "Official GTFS / GTFS-Realtime", "feed_selection_required",
            ("route name", "station", "published timetable", "service alerts"),
            ("operator-published GTFS URL", "feed validity window", "licence review"),
            "https://gtfs.org/documentation/schedule/reference/",
            "Only use a feed published by the operator or an authorized publisher; validate its active dates.",
        ),
        ProviderCapability(
            "odpt", "公共交通オープンデータセンター (ODPT)", "configuration_required",
            ("Japanese public transport reference data",),
            ("ODPT developer account", "access token", "operator coverage check"),
            "https://developer.odpt.org/",
            "Use only covered operators and preserve the source and retrieval time for each timetable fact.",
        ),
        ProviderCapability(
            "tiktok", "TikTok official APIs", "approval_required",
            ("discovery links and trend candidates"),
            ("approved TikTok product and scope", "user authorization where required"),
            "https://developers.tiktok.com/doc/",
            "Discovery content cannot establish opening hours, prices, availability, or timetable facts.",
        ),
        ProviderCapability(
            "tabelog", "食べログ", "official_connection_required",
            ("restaurant candidate references"),
            ("a documented, permitted official or licensed connection"),
            "https://tabelog.com/",
            "Do not scrape or automate access. Keep unconfigured until a permitted connection is documented.",
        ),
    )


def public_provider_catalog():
    """Serialize catalog metadata for the local UI without secret values."""
    return [{"id": item.id, "name": item.name, "state": item.state,
             "purposes": list(item.purposes), "setup": list(item.setup),
             "documentation_url": item.documentation_url, "constraint": item.constraint}
            for item in provider_catalog()]


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
