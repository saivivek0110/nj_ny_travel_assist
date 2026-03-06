"""
Commute-specific tools for NJ-NYC transit analysis
Tools for checking transit status, traffic, and cost information.
Queries use Config.ORIGIN_LOCATION / DESTINATION_LOCATION so they match the user's actual route.
"""
from langchain.tools import tool
from tools.search_tools import tavily_search, _geocode, _nws_periods, _format_nws
from config.settings import Config

_ORIGIN = Config.ORIGIN_LOCATION
_DEST = Config.DESTINATION_LOCATION


@tool
def check_nj_transit_status() -> str:
    """
    Checks current NJ Transit status and disruptions.
    Searches for:
    - Service alerts and delays
    - Northeast Corridor (NEC) status (New Brunswick to Penn Station route)
    - Real-time disruptions

    Returns:
        NJ Transit status information
    """
    try:
        search = tavily_search.invoke(f"NJ Transit service status disruptions delays {_ORIGIN} {_DEST} today")
        return f"NJ Transit Status:\n{search}"
    except Exception as e:
        return f"❌ Failed to check NJ Transit: {str(e)}"


@tool
def check_path_status() -> str:
    """
    Checks PATH (Port Authority Trans-Hudson) status.
    Searches for:
    - PATH train service alerts
    - Delays and disruptions
    - Station closures

    Returns:
        PATH status information
    """
    try:
        search = tavily_search.invoke(f"PATH train service status alerts disruptions delays {_ORIGIN} {_DEST} today")
        return f"PATH Status:\n{search}"
    except Exception as e:
        return f"❌ Failed to check PATH: {str(e)}"


@tool
def check_nyc_subway_status() -> str:
    """
    Checks NYC Subway status for the final leg of commute.
    Searches for:
    - A/C line status (common from Penn Station)
    - Subway delays and service changes
    - Station accessibility

    Returns:
        NYC Subway status information
    """
    try:
        search = tavily_search.invoke(f"NYC subway status service alerts MTA delays {_DEST} today")
        return f"NYC Subway Status:\n{search}"
    except Exception as e:
        return f"❌ Failed to check Subway: {str(e)}"


@tool
def check_traffic_conditions() -> str:
    """
    Checks current traffic conditions for car commute option.
    Searches for:
    - Route 1 traffic (US Route 1, New Brunswick to NYC)
    - Garden State Parkway conditions
    - Tolls and traffic alerts
    - Real-time congestion

    Returns:
        Traffic conditions and routing information
    """
    try:
        search = tavily_search.invoke(f"car traffic conditions tolls {_ORIGIN} to {_DEST} today")
        return f"Traffic Conditions:\n{search}"
    except Exception as e:
        return f"❌ Failed to check traffic: {str(e)}"


@tool
def get_bus_options() -> str:
    """
    Searches for bus options from New Brunswick to NYC.
    Looks for:
    - Direct bus services (Greyhound, Megabus, etc.)
    - Local NJ Transit buses to Newark/NYC
    - Service schedules and delays

    Returns:
        Available bus options and status
    """
    try:
        search = tavily_search.invoke(f"bus coach options schedules routes {_ORIGIN} to {_DEST} delays")
        return f"Bus Options:\n{search}"
    except Exception as e:
        return f"❌ Failed to check bus options: {str(e)}"


@tool
def get_commute_cost_comparison() -> str:
    """
    Gathers cost information for all commute options.
    Searches for:
    - NJ Transit ticket prices (monthly passes, daily rates)
    - PATH fares
    - Bus costs
    - Parking costs in NYC
    - Car fuel/toll estimates

    Returns:
        Cost comparison data
    """
    try:
        search = tavily_search.invoke(f"commute cost fare price {_ORIGIN} to {_DEST} NJ Transit PATH bus car parking tolls 2025 2026")
        return f"Cost Information:\n{search}"
    except Exception as e:
        return f"❌ Failed to get cost information: {str(e)}"


@tool
def get_commute_schedule_info() -> str:
    """
    Gets schedule information for all transport modes.
    Searches for:
    - NJ Transit Northeast Corridor schedule
    - Frequency and timing
    - Peak vs off-peak times
    - Travel duration estimates

    Returns:
        Schedule and timing information
    """
    try:
        search = tavily_search.invoke(f"transit schedule frequency travel time peak hours {_ORIGIN} to {_DEST}")
        return f"Schedule Information:\n{search}"
    except Exception as e:
        return f"❌ Failed to get schedule info: {str(e)}"


@tool
def analyze_weather_impact() -> str:
    """
    Gets real weather conditions for the NJ-NYC commute corridor directly from
    the National Weather Service (NWS). Free, no API key, authoritative data.

    Returns:
        Current weather conditions and any severe weather alerts for the route
    """
    try:
        # Fetch NWS data for both ends of the commute corridor
        orig_lat, orig_lon = _geocode(_ORIGIN)
        dest_lat, dest_lon = _geocode(_DEST)

        orig_periods = _nws_periods(orig_lat, orig_lon)
        dest_periods = _nws_periods(dest_lat, dest_lon)

        nj_report = _format_nws(_ORIGIN, orig_lat, orig_lon, orig_periods)
        nyc_report = _format_nws(_DEST, dest_lat, dest_lon, dest_periods)

        # Pull out any hazardous weather alerts from the detailed forecasts
        alerts = []
        for p in orig_periods[:4] + dest_periods[:4]:
            detail = p.get("detailedForecast", "").lower()
            if any(w in detail for w in ["warning", "advisory", "watch", "hazard", "storm", "snow", "ice", "flood"]):
                alerts.append(f"⚠️  {p['name']}: {p['detailedForecast'][:120]}...")

        alert_section = "\nAlerts:\n" + "\n".join(alerts) if alerts else "\nNo active weather alerts."
        return f"Weather Impact for Commute Corridor:\n\n{nj_report}\n\n{nyc_report}{alert_section}"

    except Exception as nws_err:
        # Fallback to Tavily
        try:
            result = tavily_search.invoke(f"{_ORIGIN} {_DEST} weather today severe weather alerts commute")
            return f"[NWS unavailable: {nws_err}]\nWeather Impact:\n{result}"
        except Exception as e:
            return f"❌ Failed to check weather: {str(e)}"
