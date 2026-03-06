#!/usr/bin/env python3
"""
Token Usage Analysis for Travel Agent
Detailed breakdown of where tokens are being consumed
"""
import sys
import os
import json
import argparse
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from metrics import MetricsTracker


def analyze_tokens(metrics_dir: str = "metrics", run_id: str = None):
    """Analyze token usage in detail"""
    tracker = MetricsTracker(metrics_dir)

    if not tracker.all_runs:
        print("❌ No metrics found")
        return

    # Get the latest run if not specified
    run = None
    if run_id:
        run = next((r for r in tracker.all_runs if r.run_id == run_id), None)
        if not run:
            print(f"❌ Run {run_id} not found")
            return
    else:
        run = tracker.all_runs[-1]

    print("\n" + "=" * 120)
    print("💾 TOKEN USAGE DETAILED ANALYSIS")
    print("=" * 120)

    print(f"\n📍 RUN INFORMATION:")
    print(f"  Run ID:              {run.run_id}")
    print(f"  Trip:                {run.source_city} → {run.destination_city}")
    print(f"  LLM:                 {run.llm_provider} ({run.llm_model})")
    print(f"  Duration:            {run.duration_seconds:.2f}s")

    print(f"\n📊 OVERALL TOKEN USAGE:")
    print(f"  Total Input Tokens:  {run.input_tokens:,}")
    print(f"  Total Output Tokens: {run.output_tokens:,}")
    print(f"  Total Tokens:        {run.total_tokens:,}")
    print(f"  Avg Tokens/LLM Call: {run.total_tokens / run.llm_calls if run.llm_calls > 0 else 0:,.0f}")

    # Analyze token per tool
    print(f"\n🔧 TOKENS BY TOOL CALLS:")
    if run.tools_used:
        for tool_name, call_count in sorted(run.tools_used.items(), key=lambda x: x[1], reverse=True):
            print(f"  {tool_name:30s}: {call_count} calls")

    # Detailed LLM call analysis
    if run.llm_call_details:
        print(f"\n🤖 LLM CALL SEQUENCE:")
        print(f"\n  {'Call':<6} {'Tool':<30} {'Input':<12} {'Output':<12} {'Total':<12} {'Efficiency':<12}")
        print(f"  {'-'*6} {'-'*30} {'-'*12} {'-'*12} {'-'*12} {'-'*12}")

        for call in run.llm_call_details:
            tool = call['tool_triggered'] or 'Initial'
            inp_tokens = call['input_tokens']
            out_tokens = call['output_tokens']
            total = call['total_tokens']
            efficiency = f"{call['tokens_per_char']:.3f}t/c" if call['prompt_size_chars'] > 0 else "N/A"

            print(f"  {call['call_number']:<6} {tool:<30} {inp_tokens:>10,} {out_tokens:>10,} {total:>10,} {efficiency:>10}")

        # Calculate growth
        print(f"\n  Token Usage Growth:")
        if len(run.llm_call_details) > 1:
            for i in range(1, len(run.llm_call_details)):
                prev_total = run.llm_call_details[i-1]['input_tokens']
                curr_total = run.llm_call_details[i]['input_tokens']
                growth = ((curr_total - prev_total) / prev_total * 100) if prev_total > 0 else 0
                print(f"    Call {i} → Call {i+1}: {growth:+.1f}% (Δ {curr_total - prev_total:+,} tokens)")

    # Optimization analysis
    print(f"\n💡 TOKEN OPTIMIZATION ANALYSIS:")

    # Check for high input tokens
    input_ratio = run.input_tokens / run.total_tokens * 100
    print(f"  Input/Total Ratio:   {input_ratio:.1f}%")
    if input_ratio > 80:
        print(f"    ⚠️  High input ratio - consider prompt optimization")
    elif input_ratio < 50:
        print(f"    ✅ Good balance between input and output")

    # Check for token efficiency
    if run.llm_call_details:
        avg_efficiency = sum(c['tokens_per_char'] for c in run.llm_call_details if c['prompt_size_chars'] > 0) / len([c for c in run.llm_call_details if c['prompt_size_chars'] > 0])
        print(f"  Avg Token/Char:      {avg_efficiency:.4f}")
        if avg_efficiency > 1:
            print(f"    ℹ️  Tokens are {avg_efficiency:.1f}x the character count (normal for language models)")

    # Suggestions
    print(f"\n📝 RECOMMENDATIONS:")
    if run.input_tokens > 30000:
        print(f"  1. REDUCE PROMPT SIZE")
        print(f"     • Shorten system prompt ({run.input_tokens:,} input tokens is high)")
        print(f"     • Use concise tool descriptions")
        print(f"     • Eliminate redundant examples")

    if run.llm_calls > 5:
        print(f"  2. REDUCE LLM CALLS")
        print(f"     • Current: {run.llm_calls} calls")
        print(f"     • Try batching tool results in fewer calls")

    if input_ratio > 85:
        print(f"  3. OPTIMIZE PROMPT")
        print(f"     • {input_ratio:.0f}% of tokens are input (context)")
        print(f"     • Reduce context window or make queries more specific")

    # Cost estimation (rough)
    print(f"\n💰 ESTIMATED COST:")
    print(f"  (Using approximate pricing)")
    if run.llm_provider == "claude":
        # Claude Haiku pricing: $0.80/$4 per 1M tokens
        input_cost = run.input_tokens / 1_000_000 * 0.80
        output_cost = run.output_tokens / 1_000_000 * 4.00
        total_cost = input_cost + output_cost
        print(f"  Claude Haiku: ${total_cost:.4f} ({run.input_tokens/1000:.1f}K in, {run.output_tokens/1000:.1f}K out)")
    elif run.llm_provider == "gemini":
        # Gemini pricing varies
        print(f"  Gemini: Check current pricing")
        print(f"          {run.input_tokens/1000:.1f}K input tokens, {run.output_tokens/1000:.1f}K output tokens")

    print("\n" + "=" * 120 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Analyze Token Usage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python metrics/analyze_tokens.py              # Analyze latest run
  python metrics/analyze_tokens.py --run 7c46a288  # Analyze specific run
  python metrics/analyze_tokens.py --metrics-dir ./metrics  # Custom metrics dir
        """
    )

    parser.add_argument(
        "--run",
        type=str,
        default=None,
        help="Specific run ID to analyze"
    )

    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="metrics",
        help="Path to metrics directory"
    )

    args = parser.parse_args()
    analyze_tokens(args.metrics_dir, args.run)
