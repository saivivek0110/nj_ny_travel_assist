"""
Timetable Cache — fetches transit schedules via targeted Tavily searches,
caches locally for 7 days. Timetables rarely change week-to-week, so this
avoids burning Tavily quota on repeat runs.

Cache file: cache/timetables.json
Cache TTL:  7 days (configurable via TIMETABLE_CACHE_DAYS env var)
Cache key:  "{origin}|{destination}"
"""
import json
import os
from datetime import datetime, timedelta

from langchain_tavily import TavilySearch

CACHE_FILE = os.path.join("cache", "timetables.json")
CACHE_TTL_DAYS = int(os.getenv("TIMETABLE_CACHE_DAYS", "7"))

def _build_queries(origin: str, destination: str) -> list:
    """Build targeted timetable + fare queries for the specific route."""
    # Extract short city name for cleaner queries (e.g. "Edison, NJ" → "Edison")
    origin_city = origin.split(",")[0].strip()
    return [
        f"train schedule timetable departure times {origin} to {destination} all lines",
        f"bus schedule {origin} to {destination} departure arrival times coach",
        f"PATH train schedule timetable frequency hours New Jersey New York",
        f"transit train schedule {origin} {destination} train numbers stops",
        f"NJ Transit rail fare {origin_city} Penn Station New York one way price dollar 2025 2026",
        f"NJ Transit {origin_city} station zone rail ticket price one-way 10-trip monthly 2025 2026",
        f"NJ Transit monthly pass cost zone {origin_city} commuter rail 2025 2026",
        "PATH fare price single trip 2025 2026",
        f"Suburban Transit Coach USA bus fare {origin_city} New York Port Authority price 2025 2026",
    ]


def _is_fresh(cached_at: str) -> bool:
    ts = datetime.fromisoformat(cached_at)
    return datetime.now() - ts < timedelta(days=CACHE_TTL_DAYS)


def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_cache(cache: dict) -> None:
    os.makedirs("cache", exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)


def get_timetables(origin: str, destination: str) -> str:
    """
    Return timetable/schedule data for origin -> destination.
    Uses local cache if < 7 days old, otherwise fetches fresh via Tavily.

    Returns a formatted string ready to inject into an LLM prompt.
    """
    cache_key = f"{origin}|{destination}"
    cache = _load_cache()

    if cache_key in cache and _is_fresh(cache[cache_key]["cached_at"]):
        age_hours = (datetime.now() - datetime.fromisoformat(cache[cache_key]["cached_at"])).seconds // 3600
        print(f"  📋 Using cached timetables ({age_hours}h old, refreshes after {CACHE_TTL_DAYS} days)")
        return cache[cache_key]["data"]

    print(f"  🌐 Fetching fresh timetables for {origin} → {destination}...")
    search = TavilySearch(max_results=5)
    sections = []

    for query in _build_queries(origin, destination):
        try:
            result = search.invoke(query)
            sections.append(f"--- {query} ---\n{result}")
        except Exception as e:
            sections.append(f"--- {query} ---\n[fetch failed: {e}]")

    combined = "\n\n".join(sections)
    cached_at = datetime.now().isoformat()

    cache[cache_key] = {"cached_at": cached_at, "data": combined}
    _save_cache(cache)

    expires = (datetime.now() + timedelta(days=CACHE_TTL_DAYS)).strftime("%Y-%m-%d")
    print(f"  ✅ Timetables cached to {CACHE_FILE} (valid until {expires})")
    return combined


def clear_timetable_cache(origin: str = None, destination: str = None) -> None:
    """
    Clear cache for a specific route (or all routes if no args given).
    """
    if origin is None and destination is None:
        if os.path.exists(CACHE_FILE):
            os.remove(CACHE_FILE)
            print(f"  🗑️  Cleared all timetable cache ({CACHE_FILE})")
        return

    cache_key = f"{origin}|{destination}"
    cache = _load_cache()
    if cache_key in cache:
        del cache[cache_key]
        _save_cache(cache)
        print(f"  🗑️  Cleared timetable cache for {cache_key}")
    else:
        print(f"  ℹ️  No cache found for {cache_key}")
