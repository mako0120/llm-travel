"""Small, policy-aware adapters for no-key public travel research sources.

These adapters are deliberately narrow. They make a user-triggered request,
identify this local research prototype, and return evidence candidates. They
never turn a public result into a current timetable, price, rating, opening
hour, or reservation fact.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from travel.providers import ProviderResult


NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
WIKIMEDIA_SEARCH_URL = "https://ja.wikipedia.org/w/rest.php/v1/search/page"
USER_AGENT = "llm-travel-research-prototype/0.1 (local, contact: operator)"


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


def public_source_catalog():
    """List only sources that can run without a key in this prototype."""
    return (
        PublicSourcePolicy(
            "nominatim", "OpenStreetMap Nominatim", "available_no_key",
            "A user-entered destination's approximate coordinates",
            "One user-triggered query at a time; at most 1 request/second; attribution required; no autocomplete or bulk POI collection.",
            "https://operations.osmfoundation.org/policies/nominatim/",
        ),
        PublicSourcePolicy(
            "wikimedia", "Wikimedia REST API", "available_no_key",
            "Destination context and discovery leads",
            "Send an identifying User-Agent; obey rate limits and each result's license. This is never proof of current travel operations.",
            "https://www.mediawiki.org/wiki/API:REST_API/Policies",
        ),
        PublicSourcePolicy(
            "official_gtfs", "事業者公開 GTFS / GTFS-JP", "feed_selection_required",
            "Published route names, stops, service calendars and timetable rows",
            "An operator-published feed URL, applicable dates, license and freshness check are required before displaying a timetable.",
            "https://www.gtfs.jp/developpers-guide/format-reference.html",
        ),
    )


class NominatimAdapter:
    """Single, explicitly requested geocode lookup with an injectable transport."""

    def __init__(self, transport=_get_json):
        self._transport = transport

    def search_destination(self, destination):
        if not isinstance(destination, str) or not destination.strip():
            raise ValueError("destination must be a nonempty string")
        query = urlencode({"q": destination.strip(), "format": "jsonv2", "limit": "1", "accept-language": "ja"})
        try:
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


def public_result_evidence(result, retrieved_at=None, freshness_hours=24):
    """Create unverified evidence candidates from a public source result."""
    if not isinstance(result, ProviderResult) or result.provider not in {"nominatim", "wikimedia"}:
        raise ValueError("result must be a Nominatim or Wikimedia ProviderResult")
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
    evidence = []
    for page in result.value["pages"]:
        if not isinstance(page, dict) or not isinstance(page.get("title"), str) or not isinstance(page.get("key"), str):
            continue
        evidence.append({"agent": "provider", "source_type": "Wikimedia", "url": f"https://ja.wikipedia.org/wiki/{page['key']}",
                         "title": page["title"], "facts": {key: page[key] for key in ("description", "excerpt") if isinstance(page.get(key), str)},
                         "retrieved_at": retrieved, "expires_at": expires, "verification_status": "unverified"})
    return evidence
