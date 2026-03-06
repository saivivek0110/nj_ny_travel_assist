#!/usr/bin/env python3
"""
View Travel Agent Metrics
Display detailed metrics from saved metric files
"""
import sys
import os
import json
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrics import MetricsTracker


def view_metrics(metrics_dir: str = "metrics", last_n: int = None, detailed: bool = True):
    """View metrics from saved files"""
    tracker = MetricsTracker(metrics_dir)

    if not tracker.all_runs:
        print("❌ No metrics found")
        return

    print("\n" + "=" * 120)
    print("📊 TRIP AGENT METRICS DASHBOARD")
    print("=" * 120)

    # Show stats summary
    stats = tracker.get_stats_summary()
    print("\n📈 OVERALL STATISTICS:")
    print(f"  Total Runs:                {stats['total_runs']}")
    print(f"  Successful Runs:           {stats['successful_runs']}")
    print(f"  Failed Runs:               {stats['failed_runs']}")
    print(f"  Success Rate:              {stats['success_rate']:.1f}%")
    print(f"  Total Tool Calls:          {stats['total_tool_calls']}")
    print(f"  Total LLM Calls:           {stats['total_llm_calls']}")
    print(f"  Total Tokens Used:         {stats['total_tokens_used']:,}")
    print(f"  Total Execution Time:      {stats['total_execution_time_seconds']:.2f}s")
    print(f"  Average Execution Time:    {stats['avg_execution_time_seconds']:.2f}s")

    # Show LLM metrics
    print("\n🤖 LLM METRICS:")
    for llm_key, llm_metric in tracker.get_llm_metrics().items():
        print(f"\n  {llm_key}:")
        print(f"    Calls:                 {llm_metric.total_calls}")
        print(f"    Input Tokens:          {llm_metric.total_input_tokens:,}")
        print(f"    Output Tokens:         {llm_metric.total_output_tokens:,}")
        print(f"    Total Tokens:          {llm_metric.total_tokens:,}")

    # Show tool metrics
    print("\n🔧 TOOL METRICS:")
    for tool_name, tool_metric in sorted(tracker.get_tool_metrics().items()):
        success_rate = (tool_metric.successes / tool_metric.calls * 100) if tool_metric.calls > 0 else 0
        print(f"\n  {tool_name}:")
        print(f"    Calls:                 {tool_metric.calls}")
        print(f"    Successes:             {tool_metric.successes}")
        print(f"    Failures:              {tool_metric.failures}")
        print(f"    Success Rate:          {success_rate:.1f}%")
        print(f"    Total Time:            {tool_metric.total_execution_time:.2f}s")
        print(f"    Avg Time/Call:         {tool_metric.avg_execution_time:.2f}s")

    # Show recent runs
    print("\n📝 RECENT RUNS:")
    runs_to_show = tracker.all_runs[-last_n:] if last_n else tracker.all_runs

    for run in runs_to_show:
        status_icon = "✅" if run.success else "❌"
        print(f"\n  {status_icon} Run {run.run_id}")
        print(f"    Trip:                  {run.source_city} → {run.destination_city}")
        print(f"    LLM:                   {run.llm_provider} ({run.llm_model})")
        print(f"    Week:                  {run.week_start_date}")
        print(f"    Timestamp:             {run.timestamp}")
        print(f"    Duration:              {run.duration_seconds:.2f}s")
        print(f"    Tool Calls:            {run.tool_calls}")
        print(f"    LLM Calls:             {run.llm_calls}")
        print(f"    Tokens:                {run.total_tokens:,} (In: {run.input_tokens:,}, Out: {run.output_tokens:,})")
        if run.tools_used:
            print(f"    Tools Used:            {', '.join([f'{k}({v})' for k, v in run.tools_used.items()])}")

    print("\n" + "=" * 120 + "\n")


def export_metrics(metrics_dir: str = "metrics", format: str = "json"):
    """Export metrics in different formats"""
    tracker = MetricsTracker(metrics_dir)

    if format == "json":
        tracker.save_metrics()
    elif format == "csv":
        tracker.save_metrics()
    elif format == "text":
        tracker.save_metrics()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="View Travel Agent Metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python metrics/view_metrics.py                    # View all metrics
  python metrics/view_metrics.py --last 5           # View last 5 runs
  python metrics/view_metrics.py --export csv       # Export as CSV
  python metrics/view_metrics.py --metrics-dir ./metrics  # Use custom metrics directory
        """
    )

    parser.add_argument(
        "--last",
        type=int,
        default=None,
        help="Show only last N runs"
    )

    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="metrics",
        help="Path to metrics directory"
    )

    parser.add_argument(
        "--export",
        type=str,
        choices=["json", "csv", "text"],
        help="Export metrics in specified format"
    )

    args = parser.parse_args()

    if args.export:
        print(f"📤 Exporting metrics as {args.export.upper()}...")
        export_metrics(args.metrics_dir, args.export)
    else:
        view_metrics(args.metrics_dir, args.last)
