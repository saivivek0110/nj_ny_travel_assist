#!/usr/bin/env python3
"""
Trip Orchestrator — parent agent coordinating Week Trip Scout + Route Scout
Combines Weekly Travel Selection with Daily Commute Optimization
"""
import sys
import os
import re
import json
import time
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage, SystemMessage

from config.settings import Config
from agents.week_trip_scout import get_week_dates
from tools.email_tools import send_email, is_email_configured
from metrics import get_metrics_tracker

from tools.timetable_cache import get_timetables
from tools.commute_tools import (
    check_nj_transit_status, check_path_status, check_nyc_subway_status,
    check_traffic_conditions, get_bus_options, get_commute_cost_comparison,
    get_commute_schedule_info, analyze_weather_impact,
)
from prompts.travel_prompts import WEEK_TRIP_SCOUT_SYSTEM_PROMPT



def _extract_tokens(response) -> tuple:
    """Extract (input_tokens, output_tokens) from an LLM response."""
    if hasattr(response, 'usage_metadata') and response.usage_metadata:
        u = response.usage_metadata
        return u.get('input_tokens', 0), u.get('output_tokens', 0)
    if hasattr(response, 'response_metadata'):
        tu = response.response_metadata.get('token_usage', {})
        return tu.get('prompt_tokens', 0), tu.get('completion_tokens', 0)
    return 0, 0


_BATCH_COMMUTE_SYSTEM_PROMPT = (
    "You are a commute analyst. Evaluate all available transit options and pick the SINGLE BEST one for each date.\n\n"
    "Rules:\n"
    "- Output EXACTLY ONE block per date — one recommendation, not multiple options\n"
    "- Each block must start with ===DATE: YYYY-MM-DD=== and end with ===END===\n"
    "- No other text before the first block or after the last block\n"
    "- Do NOT output a weekly summary or cost totals\n"
    "- Do NOT repeat the same text across days — each day must be distinct\n\n"
    "Each block must contain:\n"
    "RECOMMENDED: [Service name + specific line/route]\n"
    "MORNING: departs [origin] at HH:MM → arrives [destination] ~HH:MM\n"
    "EVENING: departs [destination] at HH:MM → arrives [origin] ~HH:MM\n"
    "FARE: [official link ONLY — absolutely no dollar amounts]\n"
    "  NJ Transit rail → https://www.njtransit.com/fares\n"
    "  NJ Transit bus → https://www.njtransit.com/bus-fare-charts\n"
    "  PATH → https://www.panynj.gov/path/en/fares.html\n"
    "  Coach USA → https://web.coachusa.com/suburban\n"
    "  Driving → https://www.ezpassnj.com\n"
    "NOTE: [day-specific disruptions only — omit if nothing notable]\n"
)


def _batch_commute_analysis(
    source: str,
    destination: str,
    best_days: list,
    morning_time: str = "07:00-10:00",
    evening_time: str = "16:00-20:00",
) -> dict:
    """
    Fetch all transit data ONCE, then analyze all days in a single LLM call.

    Before: N days × (8 Tavily + 2 LLM) = 24 Tavily + 6 LLM calls
    After:  8 Tavily + 1 LLM call
    """
    # --- Phase 1: Fetch all tool data directly (no LLM needed) ---
    print("  📡 Fetching transit data once for all days...")
    _commute_tools = [
        ("NJ Transit Status",  check_nj_transit_status,    {}),
        ("PATH Status",        check_path_status,           {}),
        ("NYC Subway Status",  check_nyc_subway_status,     {}),
        ("Traffic Conditions", check_traffic_conditions,    {}),
        ("Bus Options",        get_bus_options,             {}),
        ("Cost Comparison",    get_commute_cost_comparison, {}),
        ("Schedule Info",      get_commute_schedule_info,   {}),
        ("Weather Impact",     analyze_weather_impact,      {}),
    ]
    tracker = get_metrics_tracker()

    # --- Phase 0: Load timetables from cache (free after first run) ---
    print("  🗓️  Loading timetable schedules (cached or fresh)...")
    timetable_block = get_timetables(source, destination)

    raw = {}
    for label, tool_fn, kwargs in _commute_tools:
        raw[label] = tool_fn.invoke(kwargs)
        tracker.record_tool_call(tool_fn.name)
        time.sleep(1.1)  # stay under Tavily ~1 req/sec limit
    data_block = "\n\n".join(f"=== {k} ===\n{v}" for k, v in raw.items())
    print(f"  📦 data_block: {len(data_block):,} chars  (~{len(data_block)//4:,} tokens)")
    dates_list = "\n".join(f"- {d}" for d in best_days)

    # --- Phase 2: Single LLM call for all days ---
    print(f"  🤖 Single LLM call to analyze {len(best_days)} days at once...")
    llm = Config.get_llm()
    messages = [
        SystemMessage(content=_BATCH_COMMUTE_SYSTEM_PROMPT),
        HumanMessage(content=f"""Analyze commute from {source} to {destination} for each date below.

Dates:
{dates_list}

TIME WINDOWS (only suggest departures within these ranges):
- Morning departure from {source}: {morning_time} (24h format)
- Evening return from {destination}: {evening_time} (24h format)

Output EXACTLY ONE block per date. Pick the single best transit option.
IMPORTANT: FARE line must be an official website link ONLY — no dollar amounts whatsoever.
Keep each day distinct — do not repeat the same plan across days.
Do NOT add a weekly summary after the dates.

=== TIMETABLE + FARE DATA (cached, stable) ===
{timetable_block}

=== LIVE STATUS (current disruptions) ===
{data_block}

Format EXACTLY as (one block per date, nothing else):
===DATE: YYYY-MM-DD===
RECOMMENDED: [service + line]
MORNING: departs {source} at HH:MM → arrives {destination} ~HH:MM
EVENING: departs {destination} at HH:MM → arrives {source} ~HH:MM
FARE: [official URL only]
NOTE: [disruptions if any]
===END==="""),
    ]
    try:
        response = llm.invoke(messages)
    except Exception as e:
        from config.settings import _handle_llm_error
        _handle_llm_error(e)
    in_tok, out_tok = _extract_tokens(response)
    tracker.record_llm_call(input_tokens=in_tok, output_tokens=out_tok, prompt_size=len(data_block))
    full_text = response.content

    # --- Phase 3: Split response by date marker ---
    commute_reports = {}
    for day in best_days:
        # Handle both ===DATE: YYYY-MM-DD=== and ===YYYY-MM-DD=== formats
        pattern = rf'===(?:DATE:\s*)?{re.escape(day)}===\s*(.*?)\s*===END==='
        match = re.search(pattern, full_text, re.DOTALL)
        if match:
            commute_reports[day] = match.group(1).strip()
        else:
            print(f"  ⚠️  No match found for {day} in LLM response — check format markers")
            commute_reports[day] = f"[Parse error: no plan found for {day}. Raw response below]\n\n{full_text}"

    return commute_reports


def _batch_week_analysis(
    source: str,
    destination: str,
    week_start_date: str,
) -> tuple:
    """
    Pre-fetch all travel data once, then single LLM call to pick best 3 days.
    ~4x fewer LLM calls than a ReAct agent loop.

    Returns:
        (travel_report_text, recommended_dates_list)
    """
    from tools.search_tools import search_weather, search_travel_disturbances, tavily_search

    week_dates = get_week_dates(week_start_date)
    monday = week_dates["Monday"]
    friday = week_dates["Friday"]

    # Phase 1: fetch all data — NO LLM
    print("  📡 Fetching travel data (weather + disturbances)...")
    _week_tools = [
        ("Weather Forecast",    search_weather,             {"location": destination}),
        ("Travel Disturbances", search_travel_disturbances, {"location": destination}),
        ("Transport News",      tavily_search,              {"query": f"transit delays {source} {destination} {monday} to {friday}"}),
        ("Destination News",    tavily_search,              {"query": f"travel news {destination} {monday}"}),
    ]
    tracker = get_metrics_tracker()
    raw = {}
    for label, tool_fn, kwargs in _week_tools:
        raw[label] = tool_fn.invoke(kwargs)
        tracker.record_tool_call(tool_fn.name)
        time.sleep(1.1)  # stay under Tavily ~1 req/sec limit
    data_block = "\n\n".join(f"=== {k} ===\n{v}" for k, v in raw.items())
    print(f"  📦 data_block: {len(data_block):,} chars  (~{len(data_block)//4:,} tokens)")

    # Phase 2: single LLM call — analyze pre-fetched data
    print("  🤖 Single LLM call to pick best 3 days...")
    llm = Config.get_llm()
    messages = [
        SystemMessage(content=WEEK_TRIP_SCOUT_SYSTEM_PROMPT),
        HumanMessage(content=f"""Plan business trip from {source} to {destination}.
Week: {monday} (Mon) to {friday} (Fri).

Pre-fetched data below — use it to rank Mon–Fri and pick the best 3 days.

{data_block}

End your response with exactly this JSON block and nothing after it:
```json
{{"recommended_dates": ["YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD"]}}
```"""),
    ]
    try:
        response = llm.invoke(messages)
    except Exception as e:
        from config.settings import _handle_llm_error
        _handle_llm_error(e)
    in_tok, out_tok = _extract_tokens(response)
    tracker.record_llm_call(input_tokens=in_tok, output_tokens=out_tok, prompt_size=len(data_block))
    travel_report = response.content

    # Parse recommended_dates from JSON block
    recommended_dates = []
    try:
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', travel_report, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group(1))
            recommended_dates = data.get("recommended_dates", [])

        if not recommended_dates:
            json_match = re.search(r'\{\s*"recommended_dates"\s*:\s*(\[.*?\])\s*\}', travel_report, re.DOTALL)
            if json_match:
                recommended_dates = json.loads(json_match.group(1))

        if not recommended_dates:
            json_match = re.search(r'"recommended_dates"\s*:\s*(\["[^"]+(?:",\s*"[^"]+)*"\])', travel_report)
            if json_match:
                recommended_dates = json.loads(json_match.group(1))
    except Exception as e:
        print(f"⚠️  Could not parse recommended dates JSON: {e}")

    return travel_report, recommended_dates


def _strip_json_block(text: str) -> str:
    """Remove JSON artifacts from agent output — both fenced and raw."""
    # Remove fenced ```json ... ``` blocks
    text = re.sub(r'```json.*?```', '', text, flags=re.DOTALL)
    # Remove raw {"recommended_dates": [...]} objects
    text = re.sub(r'\{[\s\n]*"recommended_dates"[^}]+\}', '', text, flags=re.DOTALL)
    return text.strip()


def _markdown_table_to_html(text: str) -> str:
    """Convert markdown pipe tables to styled HTML tables. Non-table text passed through unchanged."""
    lines = text.split('\n')
    result = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Detect start of a markdown table (line with | at start/end or multiple |)
        if '|' in line and line.strip().startswith('|'):
            table_lines = []
            while i < len(lines) and '|' in lines[i] and lines[i].strip().startswith('|'):
                table_lines.append(lines[i])
                i += 1
            # Build HTML table
            html = ['<table style="width:100%;border-collapse:collapse;font-size:13px;margin:12px 0;">']
            is_header = True
            for row in table_lines:
                # Skip separator rows (|---|---|)
                cells = [c.strip() for c in row.strip().strip('|').split('|')]
                if all(re.match(r'^[-:]+$', c) for c in cells if c):
                    is_header = False
                    continue
                tag = 'th' if is_header else 'td'
                style = (
                    'background:#1565c0;color:white;padding:8px 12px;text-align:left;font-weight:600;'
                    if is_header else
                    'padding:7px 12px;border-bottom:1px solid #e0e0e0;'
                )
                html.append('<tr>')
                for cell in cells:
                    html.append(f'<{tag} style="{style}">{cell}</{tag}>')
                html.append('</tr>')
                if is_header:
                    is_header = False
            html.append('</table>')
            result.append('\n'.join(html))
        else:
            result.append(line)
            i += 1
    return '\n'.join(result)


def _build_html_email(
    source_city: str,
    destination_city: str,
    week_start_date: str,
    recipient_email: str,
    travel_report: str,
    commute_reports: dict,
    best_days: list,
) -> str:
    """Generate a clean HTML email from agent reports."""
    clean_travel = _markdown_table_to_html(_strip_json_block(travel_report))

    # Recommended days badges
    badge_colors = ["#34a853", "#1a73e8", "#f9ab00"]
    badge_labels = ["BEST DAY", "2ND BEST", "3RD BEST"]
    days_badges = ""
    for i, day in enumerate(best_days):
        color = badge_colors[i] if i < len(badge_colors) else "#666"
        label = badge_labels[i] if i < len(badge_labels) else f"#{i+1}"
        days_badges += f"""
        <div style="display:inline-block;background:{color};color:white;
                    padding:9px 18px;border-radius:20px;margin:5px;
                    font-weight:bold;font-size:13px;letter-spacing:0.3px;">
          {day} &nbsp;<span style="font-size:10px;opacity:0.85;
          text-transform:uppercase;">{label}</span>
        </div>"""

    # Commute day cards
    commute_cards = ""
    for day in best_days:
        report = commute_reports.get(day, "No data available.")
        is_error = any(w in report.lower() for w in ["error", "failed", "no commute data", "resource_exhausted", "quota"])
        border = "#ea4335" if is_error else "#34a853"
        icon = "⚠️" if is_error else "✅"
        commute_cards += f"""
        <div style="border:1px solid #e0e0e0;border-left:5px solid {border};
                    border-radius:6px;margin:16px 0;overflow:hidden;">
          <div style="background:#f8f9fa;padding:12px 18px;
                      border-bottom:1px solid #e0e0e0;">
            <strong style="color:#333;font-size:14px;">{icon} Commute Plan — {day}</strong>
          </div>
          <div style="padding:16px 18px;">
            <pre style="white-space:pre-wrap;font-family:Arial,sans-serif;
                        font-size:13px;line-height:1.7;margin:0;color:#333;">{report}</pre>
          </div>
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;max-width:820px;margin:0 auto;
             color:#333;padding:24px;background:#fff;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1565c0,#0d47a1);color:white;
              padding:28px 32px;border-radius:10px 10px 0 0;">
    <h1 style="margin:0;font-size:24px;font-weight:700;letter-spacing:-0.3px;">
      ✈️ Integrated Travel &amp; Commute Plan
    </h1>
    <p style="margin:8px 0 0 0;font-size:15px;opacity:0.88;">
      {source_city} &rarr; {destination_city}
    </p>
  </div>

  <!-- Meta bar -->
  <div style="background:#e3f2fd;padding:11px 20px;border-radius:0 0 8px 8px;
              margin-bottom:24px;font-size:13px;color:#555;">
    📅 Week of &nbsp;<strong>{week_start_date}</strong>
    &nbsp;&nbsp;|&nbsp;&nbsp;
    📧 {recipient_email}
  </div>

  <!-- Recommended days -->
  <div style="background:#f8f9fa;border:1px solid #e0e0e0;border-radius:8px;
              padding:18px;margin-bottom:28px;text-align:center;">
    <p style="margin:0 0 12px 0;font-weight:600;color:#444;
              font-size:12px;text-transform:uppercase;letter-spacing:1px;">
      Top 3 Recommended Travel Days
    </p>
    {days_badges}
  </div>

  <!-- Part 1 -->
  <h2 style="color:#1565c0;border-bottom:2px solid #e3f2fd;
             padding-bottom:8px;font-size:18px;">
    📋 Part 1 — Weekly Travel Analysis
  </h2>
  <div style="border:1px solid #e0e0e0;border-radius:6px;
              padding:20px;background:#fafafa;margin-bottom:28px;
              font-family:Arial,sans-serif;font-size:13px;line-height:1.75;color:#333;
              white-space:pre-wrap;">
    {clean_travel}
  </div>

  <!-- Part 2 -->
  <h2 style="color:#1565c0;border-bottom:2px solid #e3f2fd;
             padding-bottom:8px;font-size:18px;">
    🚇 Part 2 — Daily Commute Plans
  </h2>
  {commute_cards}

  <!-- Footer -->
  <div style="margin-top:32px;padding:14px;background:#f1f3f4;
              border-radius:6px;font-size:11px;color:#999;text-align:center;">
    Generated by Agentic AI Trip Orchestrator
  </div>

</body>
</html>"""


def _print_run_summary(total_duration: float, email_status: str, best_days: list):
    """Print a clean end-of-run summary box reading from MetricsTracker."""
    tracker = get_metrics_tracker()
    # Prefer the active current_run; fall back to last completed run
    run = tracker.current_run or (tracker.all_runs[-1] if tracker.all_runs else None)

    llm_calls = run.llm_calls if run else 0
    tool_calls = run.tool_calls if run else 0
    input_tokens = run.input_tokens if run else 0
    output_tokens = run.output_tokens if run else 0
    total_tokens = run.total_tokens if run else 0
    model = run.llm_model if run else "unknown"
    cost_usd = getattr(run, 'cost_usd', 0.0) if run else 0.0

    days_str = ", ".join(best_days) if best_days else "N/A"

    W = 52  # inner width (between ║ chars)

    def row(label, value):
        content = f"  {label:<14}:  {value}"
        return "║" + content.ljust(W) + "║"

    print("\n╔" + "═" * W + "╗")
    print("║" + "RUN SUMMARY".center(W) + "║")
    print("╠" + "═" * W + "╣")
    print(row("Duration", f"{total_duration:.1f}s"))
    print(row("LLM Calls", f"{llm_calls}   ({model})"))
    print(row("Tool Calls", str(tool_calls)))
    token_detail = f"{total_tokens:,}  (in: {input_tokens:,} / out: {output_tokens:,})"
    print(row("Tokens Used", token_detail))
    print(row("Est. Cost", f"~${cost_usd:.4f}"))
    print(row("Email", email_status))
    print(row("Best Days", days_str))
    print("╚" + "═" * W + "╝\n")


def run_integrated_plan(
    source_city: str,
    destination_city: str,
    week_start_date: str,
    recipient_email: str,
    morning_time: str = "07:00-10:00",
    evening_time: str = "16:00-20:00",
):
    import uuid
    total_start = time.time()
    email_status = "⚠️ not sent"
    best_days = []

    # Start metrics tracking for this run
    tracker = get_metrics_tracker()
    llm = Config.get_llm()
    llm_model = getattr(llm, 'model_name', None) or getattr(llm, 'model', 'unknown')
    llm_provider = Config.LLM_PROVIDER.lower()
    tracker.start_run(
        run_id=uuid.uuid4().hex[:8],
        llm_provider=llm_provider,
        llm_model=llm_model,
        source_city=source_city,
        destination_city=destination_city,
        week_start_date=week_start_date,
    )

    print("\n" + "=" * 80)
    print("🤖 TRIP ORCHESTRATOR (Parent Agent)")
    print("=" * 80)
    print(f"🎯 Goal: Plan best days for {source_city} -> {destination_city}")
    print(f"📅 Week: {week_start_date}")
    print("=" * 80 + "\n")

    # --- STEP 1: Week Trip Scout → best days ---
    print("\n" + "🔹" * 40)
    print("STEP 1: Analyzing Week to find Best Travel Days")
    print("🔹" * 40 + "\n")

    travel_report, best_days = _batch_week_analysis(
        source=source_city,
        destination=destination_city,
        week_start_date=week_start_date,
    )

    if not best_days:
        print("❌ Could not determine best days from Week Trip Scout. Exiting.")
        total_duration = time.time() - total_start
        tracker.end_run(duration_seconds=total_duration, success=False, error_message="No best days found")
        tracker.save_metrics()
        _print_run_summary(total_duration, email_status, best_days)
        return

    print(f"\n✅ Week Trip Scout identified best days: {best_days}")

    # --- STEP 2: Batch Commute Analysis (1 LLM call for all days) ---
    print("\n" + "🔹" * 40)
    print("STEP 2: Batch Commute Analysis (all days in one shot)")
    print("🔹" * 40 + "\n")
    print(f"  ⚡ Batching {len(best_days)} days → 8 Tavily + 1 LLM (was {len(best_days)*8} Tavily + {len(best_days)*2} LLM)")

    try:
        commute_reports = _batch_commute_analysis(
            source=source_city,
            destination=destination_city,
            best_days=best_days,
            morning_time=morning_time,
            evening_time=evening_time,
        )
    except Exception as e:
        print(f"⚠️ Batch commute analysis failed: {e}")
        commute_reports = {day: f"Analysis failed: {e}" for day in best_days}

    # --- STEP 3: Build HTML report and send/save ---
    print("\n" + "🔹" * 40)
    print("STEP 3: Generating Final Consolidated Report")
    print("🔹" * 40 + "\n")

    html_body = _build_html_email(
        source_city=source_city,
        destination_city=destination_city,
        week_start_date=week_start_date,
        recipient_email=recipient_email,
        travel_report=travel_report,
        commute_reports=commute_reports,
        best_days=best_days,
    )

    if is_email_configured():
        print("\n📤 Sending Consolidated Email...")
        try:
            email_subject = f"✈️ Travel Plan: {source_city} → {destination_city} (Week of {week_start_date})"
            result = send_email.func(email_subject, html_body, recipient_email)
            print(f"✅ {result}")
            email_status = "✅ sent"
        except Exception as e:
            print(f"❌ Failed to send final email: {e}")
            email_status = f"❌ failed: {e}"
    else:
        report_path = f"report_{week_start_date}.html"
        with open(report_path, "w") as f:
            f.write(html_body)
        print(f"📋 Gmail not configured — report saved to {report_path}")
        email_status = f"💾 saved to {report_path}"

    print("\n" + "=" * 80)
    print("✅ INTEGRATED PLANNING COMPLETE")
    print("=" * 80 + "\n")

    total_duration = time.time() - total_start
    tracker.end_run(duration_seconds=total_duration, success=True)
    tracker.save_metrics()

    _print_run_summary(total_duration, email_status, best_days)


def main():
    parser = argparse.ArgumentParser(description="Trip Orchestrator — Integrated Travel & Commute Planner")
    parser.add_argument("-s", "--source", default="North Brunswick, NJ", help="Source City")
    parser.add_argument("-d", "--destination", default="New York Penn Station", help="Destination City")
    parser.add_argument("-w", "--week", required=True, help="Week Start Date (YYYY-MM-DD)")
    parser.add_argument("-e", "--email", default=Config.DEFAULT_EMAIL, help="Recipient Email")
    parser.add_argument(
        "-mt", "--morning-time",
        default="07:00-10:00",
        help="Morning departure window HH:MM-HH:MM (default: 07:00-10:00)",
    )
    parser.add_argument(
        "-et", "--evening-time",
        default="16:00-20:00",
        help="Evening return window HH:MM-HH:MM (default: 16:00-20:00)",
    )

    args = parser.parse_args()

    run_integrated_plan(
        source_city=args.source,
        destination_city=args.destination,
        week_start_date=args.week,
        recipient_email=args.email,
        morning_time=args.morning_time,
        evening_time=args.evening_time,
    )


if __name__ == "__main__":
    main()
