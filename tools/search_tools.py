"""
Search tools for Travel Agent
- search_weather: Real NWS (api.weather.gov) data — free, no API key, authoritative
- search_travel_disturbances: Tavily web search
- tavily_search: General Tavily web search
"""
import httpx
from datetime import datetime
from langchain.tools import tool
from langchain_tavily import TavilySearch


# ---------------------------------------------------------------------------
# NWS helpers (private)
# ---------------------------------------------------------------------------

_NWS_HEADERS = {
    "User-Agent": "TravelAgentBot/1.0",
    "Accept": "application/geo+json",
}


def _geocode(location: str) -> tuple[float, float]:
    """Convert a US location name to (lat, lon) via Nominatim (OpenStreetMap)."""
    resp = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": location, "format": "json", "limit": 1, "countrycodes": "us"},
        headers={"User-Agent": "TravelAgentBot/1.0"},
        timeout=10.0,
    )
    resp.raise_for_status()
    hits = resp.json()
    if not hits:
        raise ValueError(f"Could not geocode '{location}' — not a recognised US location")
    return float(hits[0]["lat"]), float(hits[0]["lon"])


def _nws_periods(lat: float, lon: float) -> list[dict]:
    """Fetch 7-day forecast periods from NWS for a given lat/lon."""
    # Step 1 — resolve grid point
    points = httpx.get(
        f"https://api.weather.gov/points/{lat:.4f},{lon:.4f}",
        headers=_NWS_HEADERS,
        timeout=10.0,
    )
    points.raise_for_status()
    forecast_url = points.json()["properties"]["forecast"]

    # Step 2 — fetch forecast
    fc = httpx.get(forecast_url, headers=_NWS_HEADERS, timeout=10.0)
    fc.raise_for_status()
    return fc.json()["properties"]["periods"]


def _format_nws(location: str, lat: float, lon: float, periods: list[dict]) -> str:
    """Format NWS periods into a clean per-day string with High/Low/Avg and condition flags."""
    lines = [f"NWS Official Forecast — {location} ({lat:.3f}°N, {lon:.3f}°W):"]

    # NWS alternates day / night periods — pair them by index
    i = 0
    while i < len(periods):
        day_p = periods[i] if periods[i]["isDaytime"] else None
        if day_p is None:
            i += 1
            continue

        night_p = periods[i + 1] if (i + 1 < len(periods) and not periods[i + 1]["isDaytime"]) else None

        dt = datetime.fromisoformat(day_p["startTime"]).strftime("%A %Y-%m-%d")
        high = day_p["temperature"]
        unit = day_p["temperatureUnit"]
        low = night_p["temperature"] if night_p else None
        avg = f"{(high + low) // 2}°{unit}" if low is not None else "N/A"
        low_str = f"{low}°{unit}" if low is not None else "N/A"

        precip_val = day_p.get("probabilityOfPrecipitation", {}).get("value")
        precip = f", Precip {precip_val}%" if precip_val else ""

        # Condition flags
        forecast_text = (day_p.get("shortForecast", "") + " " + day_p.get("detailedForecast", "")).lower()
        flags = []
        if any(w in forecast_text for w in ["rain", "shower", "drizzle", "thunderstorm"]):
            flags.append("🌧️ Rain")
        if any(w in forecast_text for w in ["snow", "flurr", "blizzard", "sleet", "wintry", "ice"]):
            flags.append("❄️ Snow")
        if high >= 90:
            flags.append("🔥 Heat")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""

        lines.append(
            f"  {dt}: {day_p['shortForecast']}, "
            f"High {high}°{unit} / Low {low_str} / Avg {avg}, "
            f"Wind {day_p['windSpeed']} {day_p['windDirection']}"
            f"{precip}{flag_str}"
        )

        i += 2 if night_p else 1

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_weather(location: str) -> str:
    """
    Gets the official 7-day weather forecast for a US location directly from
    the National Weather Service (NWS / api.weather.gov).
    Free, no API key required, authoritative government data.
    Automatically falls back to web search for non-US locations or API issues.

    Args:
        location: City or location name (e.g., "New York, NY", "North Brunswick, NJ")

    Returns:
        Day-by-day weather forecast with temperature, conditions, wind, and precipitation
    """
    # --- Primary: NWS (free, structured, authoritative) ---
    try:
        lat, lon = _geocode(location)
        periods = _nws_periods(lat, lon)
        return _format_nws(location, lat, lon, periods)
    except Exception as nws_err:
        # --- Fallback: Tavily web search (non-US or NWS outage) ---
        try:
            search = TavilySearch(max_results=3)
            results = search.invoke(f"weather forecast {location} next 7 days site:weather.gov OR site:weather.com")
            return f"[NWS unavailable: {nws_err}]\n{str(results)}"
        except Exception as e:
            return f"❌ Weather fetch failed: {str(e)}"


@tool
def search_travel_disturbances(location: str) -> str:
    """
    Searches for travel disturbances, strikes, delays, and events in a location.

    Args:
        location: City or location name

    Returns:
        Information about travel disturbances and disruptions
    """
    try:
        search = TavilySearch(max_results=5)
        results = search.invoke(f"travel disturbances strikes delays events {location}")
        return str(results)
    except Exception as e:
        return f"❌ Disturbance search failed: {str(e)}"


@tool
def tavily_search(query: str) -> str:
    """
    Performs a general internet search using Tavily API.
    Use for news, events, or anything not covered by dedicated tools.

    Args:
        query: Search query

    Returns:
        Search results as a formatted string
    """
    try:
        search = TavilySearch(max_results=5)
        results = search.invoke(query)
        return str(results)
    except Exception as e:
        return f"❌ Search failed: {str(e)}"
