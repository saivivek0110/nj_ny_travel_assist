"""
Tools module for Travel Agent
Exports all available tools for travel and commute analysis
"""
from tools.search_tools import tavily_search, search_weather, search_travel_disturbances
from tools.email_tools import send_email, check_last_sent_email
from tools.commute_tools import (
    check_nj_transit_status,
    check_path_status,
    check_nyc_subway_status,
    check_traffic_conditions,
    get_bus_options,
    get_commute_cost_comparison,
    get_commute_schedule_info,
    analyze_weather_impact,
)

# List of all available tools for Travel Agent
# Prioritized for travel planning: search tools first, transportation analysis, then email
TOOLS = [
    # Search tools (primary information gathering)
    tavily_search,
    search_weather,
    search_travel_disturbances,

    # Transportation analysis tools
    check_nj_transit_status,
    check_path_status,
    check_nyc_subway_status,
    check_traffic_conditions,
    get_bus_options,
    get_commute_cost_comparison,
    get_commute_schedule_info,
    analyze_weather_impact,

    # Communication tools
    send_email,
    check_last_sent_email,
]

__all__ = [
    'tavily_search',
    'search_weather',
    'search_travel_disturbances',
    'send_email',
    'check_last_sent_email',
    'check_nj_transit_status',
    'check_path_status',
    'check_nyc_subway_status',
    'check_traffic_conditions',
    'get_bus_options',
    'get_commute_cost_comparison',
    'get_commute_schedule_info',
    'analyze_weather_impact',
    'TOOLS',
]
