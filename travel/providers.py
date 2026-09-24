"""Provider contracts and a permit-aware catalog. No network access occurs here."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from typing import Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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
            ("discovery links and trend candidates",),
            ("approved TikTok product and scope", "user authorization where required"),
            "https://developers.tiktok.com/doc/",
            "Discovery content cannot establish opening hours, prices, availability, or timetable facts.",
        ),
        ProviderCapability(
            "tabelog", "食べログ", "official_connection_required",
            ("restaurant candidate references",),
            ("a documented, permitted official or licensed connection",),
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


GOOGLE_PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_ROUTES_URL = "https://routes.googleapis.com/directions/v2:computeRoutes"


def _post_json(url, headers, payload, timeout_seconds=15):
    """Minimal standard-library transport. The caller supplies the credential."""
    request = Request(url, data=json.dumps(payload).encode("utf-8"),
                      headers=headers, method="POST")
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310: fixed official URLs
        return json.loads(response.read().decode("utf-8"))


class GoogleMapsAdapter:
    """Official Google Maps REST requests with injected transport for testing.

    The key exists only in this object and is sent in a request header. It is
    never returned, persisted, or written to a log by this module.
    """

    def __init__(self, api_key=None, transport=_post_json):
        self._api_key = api_key if isinstance(api_key, str) and api_key.strip() else None
        self._transport = transport

    def _call(self, url, field_mask, payload):
        if self._api_key is None:
            return ProviderResult("unconfigured", provider="google_maps", version="v1")
        headers = {"Content-Type": "application/json", "X-Goog-Api-Key": self._api_key,
                   "X-Goog-FieldMask": field_mask}
        try:
            value = self._transport(url, headers, payload)
        except (HTTPError, URLError, TimeoutError, ValueError, OSError):
            return ProviderResult("unavailable", provider="google_maps", version="v1")
        if not isinstance(value, dict):
            return ProviderResult("invalid", provider="google_maps", version="v1")
        return ProviderResult("available", value, provider="google_maps", version="v1")

    def search_places(self, text_query, language_code="ja", max_result_count=10):
        if not isinstance(text_query, str) or not text_query.strip():
            raise ValueError("text_query must be nonempty")
        if not isinstance(language_code, str) or not language_code.strip():
            raise ValueError("language_code must be nonempty")
        if type(max_result_count) is not int or not 1 <= max_result_count <= 20:
            raise ValueError("max_result_count must be an integer from 1 to 20")
        return self._call(
            GOOGLE_PLACES_TEXT_SEARCH_URL,
            "places.id,places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.googleMapsUri",
            {"textQuery": text_query.strip(), "languageCode": language_code.strip(),
             "maxResultCount": max_result_count},
        )

    def compute_route(self, origin, destination, travel_mode="TRANSIT", language_code="ja"):
        if not all(isinstance(value, str) and value.strip()
                   for value in (origin, destination, travel_mode, language_code)):
            raise ValueError("origin, destination, travel_mode and language_code must be nonempty")
        if travel_mode not in {"TRANSIT", "DRIVE", "WALK", "BICYCLE", "TWO_WHEELER"}:
            raise ValueError("travel_mode is not supported")
        return self._call(
            GOOGLE_ROUTES_URL,
            "routes.duration,routes.distanceMeters,routes.legs.steps.transitDetails,routes.legs.localizedValues",
            {"origin": {"address": origin.strip()}, "destination": {"address": destination.strip()},
             "travelMode": travel_mode, "languageCode": language_code.strip()},
        )


def google_places_evidence(result, retrieved_at=None, freshness_hours=24):
    """Convert a Places response to unverified evidence, never itinerary facts.

    Confirmation remains an explicit research-review step.  This transformer
    neither upgrades verification state nor invents a missing place URL.
    """
    if not isinstance(result, ProviderResult) or result.provider != "google_maps":
        raise ValueError("result must be a Google Maps ProviderResult")
    if result.state != "available":
        return []
    if not isinstance(result.value, dict) or not isinstance(result.value.get("places", []), list):
        raise ValueError("available Places result must contain a places list")
    if type(freshness_hours) is not int or not 1 <= freshness_hours <= 168:
        raise ValueError("freshness_hours must be an integer from 1 to 168")
    moment = retrieved_at or datetime.now(timezone.utc)
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ValueError("retrieved_at must be a timezone-aware datetime")
    retrieved = moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    expires = (moment.astimezone(timezone.utc) + timedelta(hours=freshness_hours)).isoformat().replace("+00:00", "Z")
    evidence = []
    for place in result.value["places"]:
        if not isinstance(place, dict):
            continue
        name = place.get("displayName")
        if isinstance(name, dict):
            name = name.get("text")
        url = place.get("googleMapsUri")
        if not isinstance(name, str) or not name.strip() or not isinstance(url, str) or not url.strip():
            continue
        facts = {key: place[key] for key in ("id", "formattedAddress", "rating", "userRatingCount", "googleMapsUri")
                 if key in place}
        evidence.append({"agent": "provider", "source_type": "Google", "url": url,
                         "title": name.strip(), "facts": facts, "retrieved_at": retrieved,
                         "expires_at": expires, "verification_status": "unverified"})
    return evidence

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
