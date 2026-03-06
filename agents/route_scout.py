#!/usr/bin/env python3
"""
Route Scout — optimizes commute routes and timing for each travel day
Analyzes real-time transit conditions and recommends the best commute option
"""
import sys
import os
import argparse
from datetime import datetime
import time
import uuid

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from config.settings import Config
from prompts.travel_prompts import ROUTE_SCOUT_SYSTEM_PROMPT
from tools import TOOLS
from metrics import get_metrics_tracker, MetricsFileFormat

# Restrict route scout to only commute-specific tools
COMMUTE_AGENT_TOOL_NAMES = [
    "check_nj_transit_status",
    "check_path_status",
    "check_nyc_subway_status",
    "check_traffic_conditions",
    "get_bus_options",
    "get_commute_cost_comparison",
    "get_commute_schedule_info",
    "analyze_weather_impact",
    "send_email",
]
COMMUTE_AGENT_TOOLS = [t for t in TOOLS if t.name in COMMUTE_AGENT_TOOL_NAMES]


def create_route_scout(llm, verbose: bool = True):
    """
    Creates and configures the Route Scout using LangGraph.

    Args:
        llm: Language model instance
        verbose: Whether to stream agent reasoning steps

    Returns:
        Compiled LangGraph react agent
    """
    return create_react_agent(
        model=llm,
        tools=COMMUTE_AGENT_TOOLS,
        prompt=ROUTE_SCOUT_SYSTEM_PROMPT,
    )


def analyze_commute(
    source: str = None,
    destination: str = None,
    recipient_email: str = None,
    analyze_for_date: str = None,
    verbose: bool = True,
    preferred_mode: str = None,
    auto_send_email: bool = True,
    return_data: bool = False
):
    """
    Main function to analyze commute options

    Args:
        source: Origin city/location
        destination: Destination city/location
        recipient_email: Email to send analysis to
        analyze_for_date: Specific date to analyze for (defaults to today)
        verbose: Print agent reasoning
        preferred_mode: User's preferred transport mode (informational)
        auto_send_email: Whether to send email automatically
        return_data: Whether to return the analysis text
    """
    if source is None:
        source = Config.ORIGIN_LOCATION
    if destination is None:
        destination = Config.DESTINATION_LOCATION

    if recipient_email is None:
        recipient_email = Config.DEFAULT_EMAIL

    if analyze_for_date is None:
        analyze_for_date = datetime.now().strftime('%Y-%m-%d')

    print("\n" + "=" * 80)
    print(f"🚇 ROUTE SCOUT - {source} → {destination}")
    print("=" * 80)
    print(f"📍 Route: {source} → {destination}")
    print(f"📧 Email: {recipient_email}")
    print(f"📅 Analysis Date: {analyze_for_date}")
    if preferred_mode:
        print(f"💡 Your Preference: {preferred_mode}")
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
            source_city=source,
            destination_city=destination,
            week_start_date=analyze_for_date,
        )

        # Validate configuration
        Config.validate()
        Config.print_config()

        # Initialize LLM
        print("🤖 Initializing AI Model...")
        llm = Config.get_llm()

        # Create agent
        print("🔧 Setting up Route Scout...\n")
        agent = create_route_scout(llm, verbose=verbose)

        # Create user message with instructions
        user_preference = ""
        if preferred_mode:
            user_preference = f"\n\nUser's preference: {preferred_mode} (but analyze all options)"

        # Determine email instruction
        email_instruction = f"10. Send a detailed email analysis to {recipient_email}"
        if not auto_send_email:
            email_instruction = "10. Generate a detailed analysis report (do not send email yet)"

        user_message = f"""Analyze all commute options from {source} to {destination} on {analyze_for_date}.
{email_instruction}

Follow the report format defined in your instructions.{user_preference}"""

        # Run the agent
        print("🚀 Analyzing commute options...\n")

        # Track prompt size for optimization analysis
        prompt_size = len(user_message)
        invoke_input = {"messages": [HumanMessage(content=user_message)]}
        invoke_config = {"recursion_limit": Config.MAX_ITERATIONS * 2}

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
        except Exception as e:
            print(f"❌ Agent execution error: {e}")
            import traceback
            traceback.print_exc()
            result = {'output': f"Error during agent execution: {e}"}

        final_content = ""
        # The final response is in the last message of the 'messages' list.
        if isinstance(result, dict) and 'messages' in result and result['messages']:
            last_message = result['messages'][-1]
            if hasattr(last_message, 'content'):
                content = last_message.content
                # Content can be a string or a list of blocks (e.g., text, code).
                if isinstance(content, list):
                    final_content = "\n".join(
                        part.get('text', '') if isinstance(part, dict) else str(part)
                        for part in content
                    )
                else:
                    final_content = str(content)
        elif isinstance(result, dict) and 'output' in result:  # Fallback for other structures
            final_content = result.get('output', '')

        # Display results
        print("\n" + "=" * 80)
        print("✅ ANALYSIS COMPLETE")
        print("=" * 80)
        print(final_content or '(No output generated)')
        print("=" * 80 + "\n")

        # Record metrics
        duration = time.time() - start_time
        metrics.end_run(duration_seconds=duration, success=True)
        metrics.display_metrics(detailed=True)
        metrics.save_metrics(MetricsFileFormat.JSON)

        if return_data:
            return final_content

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
    """Command-line interface for Route Scout"""
    parser = argparse.ArgumentParser(
        description="Route Scout - Real-time analysis for NJ-NYC commuting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python agents/route_scout.py --email "your@email.com"
  python agents/route_scout.py -e "work@company.com" --verbose
  python agents/route_scout.py --email "you@gmail.com" --date "2026-03-01"
  python agents/route_scout.py --prefer "nj_transit" --verbose
        """
    )

    parser.add_argument(
        "-s", "--source",
        type=str,
        default=None,
        help=f"Origin location (default: {Config.ORIGIN_LOCATION})"
    )

    parser.add_argument(
        "-d", "--destination",
        type=str,
        default=None,
        help=f"Destination location (default: {Config.DESTINATION_LOCATION})"
    )

    parser.add_argument(
        "-e", "--email",
        type=str,
        default=Config.DEFAULT_EMAIL,
        help=f"Email for analysis report (default: {Config.DEFAULT_EMAIL})"
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Date to analyze for (YYYY-MM-DD, default: today)"
    )

    parser.add_argument(
        "--prefer",
        type=str,
        choices=["nj_transit", "path", "bus", "subway", "car"],
        default=Config.DEFAULT_TRANSPORT_MODE,
        help=f"Your preferred transport mode (default: {Config.DEFAULT_TRANSPORT_MODE})"
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
    analyze_commute(
        source=args.source,
        destination=args.destination,
        recipient_email=args.email,
        analyze_for_date=args.date,
        verbose=verbose,
        preferred_mode=args.prefer
    )


if __name__ == "__main__":
    main()
