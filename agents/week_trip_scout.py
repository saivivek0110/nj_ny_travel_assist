#!/usr/bin/env python3
"""
Week Trip Scout — picks the best 3 days to travel in a week
Analyzes an entire work week (Mon-Fri) and recommends the best 3 days for business travel
"""
import sys
import os
import argparse
from datetime import datetime, timedelta
import json
import re

# Add project root to path (portable across systems)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from config.settings import Config
from prompts.travel_prompts import WEEK_TRIP_SCOUT_SYSTEM_PROMPT
from tools import TOOLS
from metrics import get_metrics_tracker, MetricsFileFormat

# Define the specific tools for the Week Trip Scout to prevent misuse of real-time tools
TRAVEL_AGENT_TOOL_NAMES = [
    "search_weather",
    "tavily_search",
    "search_travel_disturbances",
    "send_email"
]
TRAVEL_AGENT_TOOLS = [t for t in TOOLS if t.name in TRAVEL_AGENT_TOOL_NAMES]
import time
import uuid


def get_week_dates(week_start_date: str) -> dict:
    """
    Get Monday-Friday dates for a given week

    Args:
        week_start_date: Date in format YYYY-MM-DD (will use Monday of that week)

    Returns:
        Dictionary with dates for Mon-Fri
    """
    try:
        # Parse the date
        start_date = datetime.strptime(week_start_date, '%Y-%m-%d')

        # Find Monday of that week (0 = Monday, 6 = Sunday)
        days_since_monday = start_date.weekday()
        monday = start_date - timedelta(days=days_since_monday)

        # Generate Mon-Fri
        dates = {}
        days_map = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday'}

        for i in range(5):  # Mon-Fri (0-4)
            day_date = monday + timedelta(days=i)
            day_name = days_map[i]
            dates[day_name] = day_date.strftime('%Y-%m-%d')

        # Store the input date info for reference
        dates['_input_date'] = week_start_date
        dates['_monday'] = monday.strftime('%Y-%m-%d')

        return dates

    except ValueError:
        return None


def format_week_range(week_dates: dict) -> str:
    """Format week dates nicely"""
    return f"{week_dates['Monday']} to {week_dates['Friday']}"


def create_week_trip_scout(llm, verbose: bool = True):
    """
    Creates and configures the Week Trip Scout using LangGraph.

    Args:
        llm: Language model instance
        verbose: Whether to stream agent reasoning steps

    Returns:
        Compiled LangGraph react agent
    """
    return create_react_agent(
        model=llm,
        tools=TRAVEL_AGENT_TOOLS,
        prompt=WEEK_TRIP_SCOUT_SYSTEM_PROMPT,
    )


def analyze_travel_week(
    source_city: str,
    destination_city: str,
    week_start_date: str,
    recipient_email: str = None,
    verbose: bool = True,
    preferred_transport: str = "nj_transit",
    auto_send_email: bool = True,
    return_data: bool = False
):
    """
    Main function to analyze travel for a specific week

    Args:
        source_city: Origin city for travel
        destination_city: Target city for travel
        week_start_date: Start date of week (any date in the week, will use Monday)
        recipient_email: Email to send analysis to
        verbose: Print agent reasoning
        auto_send_email: Whether to have the agent send the email directly
        return_data: Whether to return the analysis text and recommended dates
    """
    if recipient_email is None:
        recipient_email = Config.DEFAULT_EMAIL

    # Get week dates
    week_dates = get_week_dates(week_start_date)
    if not week_dates:
        print(f"❌ Invalid date format: '{week_start_date}'")
        print(f"   Required format: YYYY-MM-DD (e.g., 2026-03-09)")
        print(f"   The script will automatically use Monday of that week")
        sys.exit(1)

    week_range = format_week_range(week_dates)
    input_date = week_dates.pop('_input_date')
    monday_date = week_dates.pop('_monday')

    print("\n" + "=" * 80)
    print("🌍 WEEK TRIP SCOUT - Weekly Analysis")
    print("=" * 80)
    print(f"📍 From: {source_city}")
    print(f"📍 To: {destination_city}")

    # Show date conversion if input was not Monday
    if input_date != monday_date:
        print(f"📅 Requested: {input_date} → Analyzing week starting {monday_date}")
    else:
        print(f"📅 Week: {week_range}")

    print(f"📅 Range: {week_range}")
    print(f"   ├─ Monday: {week_dates['Monday']}")
    print(f"   ├─ Tuesday: {week_dates['Tuesday']}")
    print(f"   ├─ Wednesday: {week_dates['Wednesday']}")
    print(f"   ├─ Thursday: {week_dates['Thursday']}")
    print(f"   └─ Friday: {week_dates['Friday']}")
    print(f"📧 Email: {recipient_email}")
    print(f"🕐 Analyzed At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    try:
        # Initialize metrics tracker
        metrics = get_metrics_tracker("metrics")
        run_id = str(uuid.uuid4())[:8]
        start_time = time.time()
        metrics.start_run(
            run_id=run_id,
            llm_provider=Config.LLM_PROVIDER,
            llm_model=Config.CLAUDE_MODEL if Config.LLM_PROVIDER == "claude" else
                      (Config.OPENAI_MODEL if Config.LLM_PROVIDER == "openai" else Config.GEMINI_MODEL),
            source_city=source_city,
            destination_city=destination_city,
            week_start_date=week_start_date,
        )

        # Validate configuration
        Config.validate()
        Config.print_config()

        # Initialize LLM
        print("🤖 Initializing AI Model...")
        llm = Config.get_llm()

        # Create agent
        print("🔧 Setting up Week Trip Scout...\n")
        agent = create_week_trip_scout(llm, verbose=verbose)

        # Format transport preference
        transport_labels = {
            "nj_transit": "NJ Transit (Northeast Corridor Train)",
            "subway": "NYC Subway",
            "bus": "Bus",
            "car": "Car/Drive"
        }
        preferred_transport_label = transport_labels.get(preferred_transport, preferred_transport)

        # Determine email instruction based on flag
        email_instruction = f"7. Send a detailed email report to {recipient_email} with:"
        if not auto_send_email:
            email_instruction = "7. Generate a detailed report (do not send email yet) with:"

        # Create detailed user message with transportation analysis
        user_message = f"""I need to plan a business trip from {source_city} to {destination_city} during the week of {week_range} (Monday {week_dates['Monday']} to Friday {week_dates['Friday']}).

PREFERRED TRANSPORTATION: {preferred_transport_label}

Analyze Mon–Fri and follow your standard report format.

{email_instruction}

Be thorough - check current conditions, weather forecasts, news, and travel alerts for {destination_city} for each specific day. Consider transportation reliability heavily in your recommendations.

IMPORTANT: At the very end of your response, strictly output the top 3 recommended dates in this JSON format (and nothing else after it):
```json
{{
  "recommended_dates": ["YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD"]
}}
```"""

        # Run the agent
        print("🚀 Analyzing travel week...\n")

        # Track prompt size for optimization analysis
        prompt_size = len(user_message)
        invoke_input = {"messages": [HumanMessage(content=user_message)]}
        invoke_config = {"recursion_limit": Config.MAX_ITERATIONS * 2}
        final_content = ""

        try:
            if verbose:
                # Stream each step so the user sees agent reasoning in real time
                result = None
                for chunk in agent.stream(invoke_input, stream_mode="values", config=invoke_config):
                    chunk["messages"][-1].pretty_print()
                    result = chunk
            else:
                result = agent.invoke(invoke_input, config=invoke_config)

            # Extract metrics from result
            if isinstance(result, dict) and 'messages' in result:
                for msg in result['messages']:
                    # Count tool calls
                    if hasattr(msg, 'tool_calls') and msg.tool_calls:
                        for tool_call in msg.tool_calls:
                            tool_name = tool_call.get('name', 'unknown')
                            metrics.record_tool_call(tool_name, success=True)

                    # Extract token usage with detailed tracking
                    if hasattr(msg, 'usage_metadata') and msg.usage_metadata:
                        input_tokens = msg.usage_metadata.get('input_tokens', 0)
                        output_tokens = msg.usage_metadata.get('output_tokens', 0)
                        if input_tokens > 0 or output_tokens > 0:
                            metrics.record_llm_call(
                                input_tokens,
                                output_tokens,
                                tool_triggered=None,
                                prompt_size=prompt_size
                            )

            # Display final results
            print("\n" + "=" * 80)
            print("✅ ANALYSIS COMPLETE")
            print("=" * 80)

            final_content = ""
            # Extract and display the result
            if isinstance(result, dict) and 'messages' in result and result['messages']:
                # The final response is in the last message of the 'messages' list.
                last_message = result['messages'][-1]
                if hasattr(last_message, 'content'):
                    content = last_message.content
                    # Content can be a string or a list of blocks (e.g., text, code).
                    if isinstance(content, list):
                        # Join all text parts into a single string for parsing.
                        final_content = "\n".join(
                            part.get('text', '') if isinstance(part, dict) else str(part)
                            for part in content
                        )
                    else:
                        final_content = str(content)

                    print("\n📊 TRAVEL ANALYSIS REPORT:")
                    print("-" * 80)
                    print(final_content)
                    print("-" * 80)
                else:
                    print("(Last message has no content)")
            else:
                print("(No 'messages' or 'output' key found in agent result)")

        except Exception as e:
            from config.settings import _handle_llm_error
            try:
                _handle_llm_error(e)
            except RuntimeError as friendly:
                print(f"❌ {friendly}")
            except Exception:
                print(f"❌ Agent execution error: {e}")
                import traceback
                traceback.print_exc()

        print("=" * 80 + "\n")

        # Record metrics
        duration = time.time() - start_time
        metrics.end_run(duration_seconds=duration, success=True)
        metrics.display_metrics(detailed=True)
        metrics.save_metrics(MetricsFileFormat.JSON)

        if return_data:
            # Extract dates from JSON block — try multiple patterns for robustness
            recommended_dates = []
            try:
                # Pattern 1: fenced ```json { ... } ```
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', final_content, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group(1))
                    recommended_dates = data.get("recommended_dates", [])

                # Pattern 2: bare JSON object with recommended_dates key
                if not recommended_dates:
                    json_match = re.search(r'\{\s*"recommended_dates"\s*:\s*(\[.*?\])\s*\}', final_content, re.DOTALL)
                    if json_match:
                        recommended_dates = json.loads(json_match.group(1))

                # Pattern 3: just the array value after the key
                if not recommended_dates:
                    json_match = re.search(r'"recommended_dates"\s*:\s*(\["[^"]+(?:",\s*"[^"]+)*"\])', final_content)
                    if json_match:
                        recommended_dates = json.loads(json_match.group(1))

            except Exception as e:
                print(f"⚠️ Could not parse recommended dates JSON: {e}")

            if recommended_dates:
                print(f"✅ Extracted recommended dates: {recommended_dates}")
            else:
                print("⚠️ Could not extract recommended dates. Last 500 chars of agent output:")
                print(final_content[-500:] if len(final_content) > 500 else final_content)

            return final_content, recommended_dates

    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        if 'metrics' in locals():
            duration = time.time() - start_time
            metrics.end_run(duration_seconds=duration, success=False, error_message=str(e))
            metrics.save_metrics(MetricsFileFormat.JSON)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        if 'metrics' in locals():
            duration = time.time() - start_time
            metrics.end_run(duration_seconds=duration, success=False, error_message=str(e))
            metrics.save_metrics(MetricsFileFormat.JSON)
        sys.exit(1)


def main():
    """Command-line interface for Week Trip Scout"""
    parser = argparse.ArgumentParser(
        description="Week Trip Scout - Analyze entire work weeks to find the best days for business travel",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze week from North Brunswick to New York Penn Station (prefer NJ Transit)
  python agents/week_trip_scout.py -s "North Brunswick, NJ" -d "New York Penn Station" -w "2026-03-09"

  # Prefer subway, with email notification
  python agents/week_trip_scout.py -s "Boston" -d "New York" -w "2026-03-11" -e "your@email.com" -t subway

  # Prefer bus option
  python agents/week_trip_scout.py -d "Philadelphia" -w "2026-03-15" -t bus

  # All options with car preference
  python agents/week_trip_scout.py -s "North Brunswick, NJ" -d "New York Penn Station" -w "2026-03-09" -t car -e "user@email.com" --verbose

Transport Modes:
  -t nj_transit     NJ Transit Northeast Corridor (cheapest, most reliable)
  -t subway         NYC Subway (fast for NYC area)
  -t bus            Bus option (moderate cost)
  -t car            Drive yourself (most expensive - tolls, parking, gas)
        """
    )

    parser.add_argument(
        "-s", "--source",
        type=str,
        default="New York",
        help="Source city (e.g., 'New York', 'Boston') [default: New York]"
    )

    parser.add_argument(
        "-d", "--destination",
        type=str,
        required=True,
        help="Destination city (e.g., 'San Francisco', 'London')"
    )

    parser.add_argument(
        "-w", "--week",
        type=str,
        required=True,
        help="Week to analyze (YYYY-MM-DD format - any date in that week will use Monday of that week)"
    )

    parser.add_argument(
        "-e", "--email",
        type=str,
        default=Config.DEFAULT_EMAIL,
        help=f"Email for recommendations (default: {Config.DEFAULT_EMAIL})"
    )

    parser.add_argument(
        "-t", "--transport",
        type=str,
        choices=["nj_transit", "subway", "bus", "car"],
        default="nj_transit",
        help="Preferred transportation mode (default: nj_transit)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=Config.VERBOSE,
        help="Print detailed agent reasoning"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress agent reasoning output"
    )

    args = parser.parse_args()

    # Determine verbosity
    verbose = args.verbose and not args.quiet

    # Run analysis
    analyze_travel_week(
        source_city=args.source,
        destination_city=args.destination,
        week_start_date=args.week,
        recipient_email=args.email,
        verbose=verbose,
        preferred_transport=args.transport
    )


if __name__ == "__main__":
    main()
