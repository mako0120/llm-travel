"""Small, policy-aware adapters for no-key public travel research sources.

These adapters are deliberately narrow. They make a user-triggered request,
identify this local research prototype, and return evidence candidates. They
never turn a public result into a current timetable, price, rating, opening
hour, or reservation fact.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from travel.providers import ProviderResult


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
WIKIMEDIA_SEARCH_URL = "https://ja.wikipedia.org/w/rest.php/v1/search/page"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
USER_AGENT = "llm-travel-research-prototype/0.1 (local, contact: operator)"


class NominatimRateLimiter:
    """Serialize public Nominatim calls to the policy's one-request-per-second cap."""

    def __init__(self, clock=time.monotonic, sleeper=time.sleep, minimum_interval_seconds=1.0):
        self._clock = clock
        self._sleep = sleeper
        self._minimum_interval = minimum_interval_seconds
        self._last_request_at = None
        self._lock = threading.Lock()

    def acquire(self):
        with self._lock:
            now = self._clock()
            delay = 0.0 if self._last_request_at is None else max(0.0, self._minimum_interval - (now - self._last_request_at))
            if delay:
                self._sleep(delay)
                now += delay
            self._last_request_at = now


_NOMINATIM_RATE_LIMITER = NominatimRateLimiter()


def _get_json(url, timeout_seconds=10):
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout_seconds) as response:  # nosec B310: module constants only
        return json.loads(response.read().decode("utf-8"))


@dataclass(frozen=True)
class PublicSourcePolicy:
    id: str
    name: str
    state: str
    purpose: str
    constraint: str
    documentation_url: str
    commercial_use: str


def public_source_catalog():
    """List only sources that can run without a key in this prototype."""
    return (
        PublicSourcePolicy(
            "nominatim", "OpenStreetMap Nominatim", "available_no_key",
            "A user-entered destination's approximate coordinates",
            "One user-triggered query at a time; at most 1 request/second; attribution required; no autocomplete or bulk POI collection.",
            "https://operations.osmfoundation.org/policies/nominatim/",
            "self_host_or_provider_required",
        ),
        PublicSourcePolicy(
            "wikimedia", "Wikimedia REST API", "available_no_key",
            "Destination context and discovery leads",
            "Send an identifying User-Agent; obey rate limits and each result's license. This is never proof of current travel operations.",
            "https://www.mediawiki.org/wiki/API:REST_API/Policies",
            "license_and_rate_review_required",
        ),
        PublicSourcePolicy(
            "open_meteo", "Open-Meteo Forecast API", "available_no_key",
            "Hourly weather forecast for an already geocoded destination",
            "Use only for a user-requested date within the provider forecast horizon. Forecasts remain estimates and must not be presented as observed weather.",
            "https://open-meteo.com/en/docs",
            "commercial_subscription_required",
        ),
        PublicSourcePolicy(
            "official_gtfs", "事業者公開 GTFS / GTFS-JP", "feed_selection_required",
            "Published route names, stops, service calendars and timetable rows",
            "An operator-published feed URL, applicable dates, license and freshness check are required before displaying a timetable.",
            "https://www.gtfs.jp/developpers-guide/format-reference.html",
            "operator_license_review_required",
        ),
    )


class NominatimAdapter:
    """Single, explicitly requested geocode lookup with an injectable transport."""

    def __init__(self, transport=_get_json, rate_limiter=_NOMINATIM_RATE_LIMITER):
        self._transport = transport
        self._rate_limiter = rate_limiter

    def search_destination(self, destination):
        if not isinstance(destination, str) or not destination.strip():
            raise ValueError("destination must be a nonempty string")
        query = urlencode({"q": destination.strip(), "format": "jsonv2", "limit": "1", "accept-language": "ja"})
        try:
            self._rate_limiter.acquire()
            value = self._transport(f"{NOMINATIM_URL}?{query}")
        except (HTTPError, URLError, TimeoutError, ValueError, OSError):
            return ProviderResult("unavailable", provider="nominatim", version="v1")
        if not isinstance(value, list):
            return ProviderResult("invalid", provider="nominatim", version="v1")
        return ProviderResult("available", value, provider="nominatim", version="v1")


class WikimediaAdapter:
    """Search destination context; result snippets remain unverified research leads."""

    def __init__(self, transport=_get_json):
        self._transport = transport

    def search_destination(self, destination, limit=5):
        if not isinstance(destination, str) or not destination.strip():
            raise ValueError("destination must be a nonempty string")
        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("limit must be an integer from 1 to 10")
        query = urlencode({"q": destination.strip(), "limit": str(limit)})
        try:
            value = self._transport(f"{WIKIMEDIA_SEARCH_URL}?{query}")
        except (HTTPError, URLError, TimeoutError, ValueError, OSError):
            return ProviderResult("unavailable", provider="wikimedia", version="v1")
        if not isinstance(value, dict) or not isinstance(value.get("pages"), list):
            return ProviderResult("invalid", provider="wikimedia", version="v1")
        return ProviderResult("available", value, provider="wikimedia", version="v1")


class OpenMeteoAdapter:
    """A small no-key forecast lookup for coordinates from an explicit geocode."""

    def __init__(self, transport=_get_json):
        self._transport = transport

    def forecast(self, latitude, longitude):
        if type(latitude) not in {int, float} or type(longitude) not in {int, float}:
            raise ValueError("latitude and longitude must be numbers")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("latitude or longitude is out of range")
        query = urlencode({"latitude": str(latitude), "longitude": str(longitude),
                           "hourly": "temperature_2m,precipitation_probability,weather_code",
                           "forecast_days": "7", "timezone": "Asia/Tokyo"})
        try:
            value = self._transport(f"{OPEN_METEO_FORECAST_URL}?{query}")
        except (HTTPError, URLError, TimeoutError, ValueError, OSError):
            return ProviderResult("unavailable", provider="open_meteo", version="v1")
        if not isinstance(value, dict) or not isinstance(value.get("hourly"), dict):
            return ProviderResult("invalid", provider="open_meteo", version="v1")
        return ProviderResult("available", value, provider="open_meteo", version="v1")


def public_result_evidence(result, retrieved_at=None, freshness_hours=24):
    """Create unverified evidence candidates from a public source result."""
    if not isinstance(result, ProviderResult) or result.provider not in {"nominatim", "wikimedia", "open_meteo"}:
        raise ValueError("result must be a supported public-source ProviderResult")
    if result.state != "available":
        return []
    if type(freshness_hours) is not int or not 1 <= freshness_hours <= 168:
        raise ValueError("freshness_hours must be an integer from 1 to 168")
    moment = retrieved_at or datetime.now(timezone.utc)
    if not isinstance(moment, datetime) or moment.tzinfo is None:
        raise ValueError("retrieved_at must be a timezone-aware datetime")
    retrieved = moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    expires = (moment.astimezone(timezone.utc) + timedelta(hours=freshness_hours)).isoformat().replace("+00:00", "Z")
    if result.provider == "nominatim":
        if not result.value:
            return []
        item = result.value[0]
        if not isinstance(item, dict) or not isinstance(item.get("display_name"), str) or not isinstance(item.get("osm_id"), int):
            return []
        return [{"agent": "provider", "source_type": "OpenStreetMap Nominatim", "url": f"https://www.openstreetmap.org/{item.get('osm_type', 'node')}/{item['osm_id']}",
                 "title": item["display_name"], "facts": {key: item[key] for key in ("lat", "lon", "type", "class", "osm_type", "osm_id") if key in item},
                 "retrieved_at": retrieved, "expires_at": expires, "verification_status": "unverified"}]
    if result.provider == "open_meteo":
        hourly = result.value.get("hourly", {})
        return [{"agent": "provider", "source_type": "Open-Meteo Forecast API", "url": "https://open-meteo.com/en/docs",
                 "title": "User-requested weather forecast", "facts": {"timezone": result.value.get("timezone"),
                 "hourly_variables": sorted(hourly.keys())}, "retrieved_at": retrieved, "expires_at": expires,
                 "verification_status": "unverified"}]
    evidence = []
    for page in result.value["pages"]:
        if not isinstance(page, dict) or not isinstance(page.get("title"), str) or not isinstance(page.get("key"), str):
            continue
        evidence.append({"agent": "provider", "source_type": "Wikimedia", "url": f"https://ja.wikipedia.org/wiki/{page['key']}",
                         "title": page["title"], "facts": {key: page[key] for key in ("description", "excerpt") if isinstance(page.get(key), str)},
                         "retrieved_at": retrieved, "expires_at": expires, "verification_status": "unverified"})
    return evidence


def collect_public_evidence(destination, nominatim=None, wikimedia=None, open_meteo=None):
    """Run the same bounded, no-key lookups /api/free-research performs.

    Shared by the web handler and the opt-in personal automation worker so
    both follow one code path. Every returned item stays unverified.
    """
    nominatim = nominatim or NominatimAdapter()
    wikimedia = wikimedia or WikimediaAdapter()
    open_meteo = open_meteo or OpenMeteoAdapter()
    geocode = nominatim.search_destination(destination)
    results = [geocode, wikimedia.search_destination(destination)]
    if geocode.state == "available" and geocode.value and isinstance(geocode.value[0], dict):
        place = geocode.value[0]
        try:
            results.append(open_meteo.forecast(float(place["lat"]), float(place["lon"])))
        except (KeyError, TypeError, ValueError):
            pass
    evidence = []
    for result in results:
        try:
            evidence.extend(public_result_evidence(result))
        except ValueError:
            continue
    return results, evidence
