"""
Metrics Tracking System for Travel Agent
Tracks tool usage, LLM calls, token usage, and performance statistics
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


# Industry-standard cost table (USD per 1K tokens)
COST_PER_1K_TOKENS = {
    "claude-haiku-4-5-20251001":  {"input": 0.00025,  "output": 0.00125},
    "gemini-2.0-flash":           {"input": 0.000075, "output": 0.0003},
    "gemini-2.0-flash-lite":      {"input": 0.000075, "output": 0.0003},
    "gpt-4o-mini":                {"input": 0.00015,  "output": 0.0006},
    "gpt-4.1-nano":               {"input": 0.0001,   "output": 0.0004},
    "gpt-4.1-mini":               {"input": 0.0004,   "output": 0.0016},
    "mistral-small-latest":       {"input": 0.0002,   "output": 0.0006},
    "command-r-plus":             {"input": 0.0003,   "output": 0.0015},
}


class MetricsFileFormat(Enum):
    """Supported metrics file formats"""
    JSON = "json"
    CSV = "csv"
    TEXT = "text"


@dataclass
class ToolMetrics:
    """Metrics for individual tool usage"""
    name: str
    calls: int = 0
    successes: int = 0
    failures: int = 0
    total_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    tool_failure_rate: float = 0.0


@dataclass
class LLMMetrics:
    """Metrics for LLM usage"""
    provider: str
    model: str
    total_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    avg_tokens_per_llm_call: float = 0.0


@dataclass
class LLMCallMetrics:
    """Metrics for individual LLM call"""
    step: int
    input_tokens: int
    output_tokens: int
    timestamp: str = None
    tool_triggered: Optional[str] = None


@dataclass
class AgentRunMetrics:
    """Complete metrics for a single agent run"""
    run_id: str
    timestamp: str
    llm_provider: str
    llm_model: str
    source_city: str
    destination_city: str
    week_start_date: str
    duration_seconds: float = 0.0
    tool_calls: int = 0
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tools_used: Dict[str, int] = None
    success: bool = True
    error_message: Optional[str] = None
    llm_call_details: List[Dict[str, Any]] = None
    # Industry-standard fields (additive)
    cost_usd: float = 0.0
    error_category: str = "none"  # none | rate_limit | auth_error | tool_failure | timeout

    def __post_init__(self):
        if self.tools_used is None:
            self.tools_used = {}
        if self.llm_call_details is None:
            self.llm_call_details = []


class MetricsTracker:
    """
    Tracks and manages metrics for the Travel Agent
    """

    def __init__(self, metrics_dir: str = "metrics"):
        self.metrics_dir = metrics_dir
        self.current_run: Optional[AgentRunMetrics] = None
        self.tool_metrics: Dict[str, ToolMetrics] = {}
        self.llm_metrics: Dict[str, LLMMetrics] = {}
        self.all_runs: List[AgentRunMetrics] = []

        os.makedirs(metrics_dir, exist_ok=True)
        self.load_historical_metrics()

    def load_historical_metrics(self):
        """Load historical metrics from file"""
        metrics_file = os.path.join(self.metrics_dir, "runs.json")
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, 'r') as f:
                    data = json.load(f)
                    self.all_runs = [
                        AgentRunMetrics(**run) for run in data.get('runs', [])
                    ]
            except Exception as e:
                print(f"⚠️ Warning: Could not load historical metrics: {e}")

    def start_run(self, run_id: str, llm_provider: str, llm_model: str,
                  source_city: str, destination_city: str, week_start_date: str):
        """Start tracking a new agent run"""
        self.current_run = AgentRunMetrics(
            run_id=run_id,
            timestamp=datetime.now().isoformat(),
            llm_provider=llm_provider,
            llm_model=llm_model,
            source_city=source_city,
            destination_city=destination_city,
            week_start_date=week_start_date,
        )

    def record_tool_call(self, tool_name: str, success: bool = True,
                        execution_time: float = 0.0):
        """Record a tool call"""
        if self.current_run:
            self.current_run.tool_calls += 1
            self.current_run.tools_used[tool_name] = \
                self.current_run.tools_used.get(tool_name, 0) + 1

        if tool_name not in self.tool_metrics:
            self.tool_metrics[tool_name] = ToolMetrics(name=tool_name)

        metrics = self.tool_metrics[tool_name]
        metrics.calls += 1
        if success:
            metrics.successes += 1
        else:
            metrics.failures += 1

        metrics.total_execution_time += execution_time
        if metrics.calls > 0:
            metrics.avg_execution_time = metrics.total_execution_time / metrics.calls
            metrics.tool_failure_rate = metrics.failures / metrics.calls

    def record_llm_call(self, input_tokens: int = 0, output_tokens: int = 0,
                       tool_triggered: Optional[str] = None, prompt_size: int = 0):
        """Record LLM call and token usage with detailed tracking"""
        if not self.current_run:
            return

        self.current_run.llm_calls += 1
        self.current_run.input_tokens += input_tokens
        self.current_run.output_tokens += output_tokens
        self.current_run.total_tokens += input_tokens + output_tokens

        # Track detailed call information
        call_detail = {
            "call_number": self.current_run.llm_calls,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
            "tool_triggered": tool_triggered,
            "prompt_size_chars": prompt_size,
            "timestamp": datetime.now().isoformat(),
            "tokens_per_char": input_tokens / prompt_size if prompt_size > 0 else 0,
        }
        self.current_run.llm_call_details.append(call_detail)

        # Update LLM metrics
        llm_key = f"{self.current_run.llm_provider}:{self.current_run.llm_model}"
        if llm_key not in self.llm_metrics:
            self.llm_metrics[llm_key] = LLMMetrics(
                provider=self.current_run.llm_provider,
                model=self.current_run.llm_model
            )

        llm_metric = self.llm_metrics[llm_key]
        llm_metric.total_calls += 1
        llm_metric.total_input_tokens += input_tokens
        llm_metric.total_output_tokens += output_tokens
        llm_metric.total_tokens = llm_metric.total_input_tokens + llm_metric.total_output_tokens
        if llm_metric.total_calls > 0:
            llm_metric.avg_tokens_per_llm_call = llm_metric.total_tokens / llm_metric.total_calls

        # Compute incremental cost for this call
        if self.current_run:
            pricing = COST_PER_1K_TOKENS.get(self.current_run.llm_model, {})
            if pricing:
                self.current_run.cost_usd += (
                    input_tokens / 1000 * pricing.get("input", 0) +
                    output_tokens / 1000 * pricing.get("output", 0)
                )

    def end_run(self, duration_seconds: float = 0.0, success: bool = True,
                error_message: Optional[str] = None):
        """End the current agent run"""
        if self.current_run:
            self.current_run.duration_seconds = duration_seconds
            self.current_run.success = success
            self.current_run.error_message = error_message
            self.all_runs.append(self.current_run)
            self.current_run = None

    def get_run_metrics(self) -> Optional[AgentRunMetrics]:
        """Get metrics for current run"""
        return self.current_run

    def get_tool_metrics(self) -> Dict[str, ToolMetrics]:
        """Get all tool metrics"""
        return self.tool_metrics

    def get_llm_metrics(self) -> Dict[str, LLMMetrics]:
        """Get all LLM metrics"""
        return self.llm_metrics

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get overall statistics"""
        total_runs = len(self.all_runs)
        successful_runs = sum(1 for run in self.all_runs if run.success)
        total_tool_calls = sum(run.tool_calls for run in self.all_runs)
        total_llm_calls = sum(run.llm_calls for run in self.all_runs)
        total_tokens = sum(run.total_tokens for run in self.all_runs)
        total_time = sum(run.duration_seconds for run in self.all_runs)

        return {
            "total_runs": total_runs,
            "successful_runs": successful_runs,
            "failed_runs": total_runs - successful_runs,
            "success_rate": (successful_runs / total_runs * 100) if total_runs > 0 else 0,
            "total_tool_calls": total_tool_calls,
            "total_llm_calls": total_llm_calls,
            "total_tokens_used": total_tokens,
            "total_execution_time_seconds": total_time,
            "avg_execution_time_seconds": total_time / total_runs if total_runs > 0 else 0,
        }

    def display_metrics(self, detailed: bool = True):
        """Display formatted metrics output"""
        run_to_display = self.current_run
        if not run_to_display and self.all_runs:
            # If no active run, display the last completed one
            run_to_display = self.all_runs[-1]

        if not run_to_display:
            print("❌ No active run to display metrics for")
            return

        print("\n" + "=" * 100)
        print("📊 TRIP AGENT METRICS REPORT")
        print("=" * 100)

        # Run Information
        print(f"\n🔍 RUN INFORMATION:")
        print(f"  Run ID:              {run_to_display.run_id}")
        print(f"  Timestamp:           {run_to_display.timestamp}")
        print(f"  Duration:            {run_to_display.duration_seconds:.2f}s")
        print(f"  Status:              {'✅ Success' if run_to_display.success else '❌ Failed'}")
        if run_to_display.error_message:
            print(f"  Error:               {run_to_display.error_message}")

        # Trip Information
        print(f"\n🌍 TRIP INFORMATION:")
        print(f"  From:                {run_to_display.source_city}")
        print(f"  To:                  {run_to_display.destination_city}")
        print(f"  Week:                {run_to_display.week_start_date}")

        # LLM Information
        print(f"\n🤖 LLM INFORMATION:")
        print(f"  Provider:            {run_to_display.llm_provider}")
        print(f"  Model:               {run_to_display.llm_model}")
        print(f"  Total Calls:         {run_to_display.llm_calls}")
        print(f"  Input Tokens:        {run_to_display.input_tokens:,}")
        print(f"  Output Tokens:       {run_to_display.output_tokens:,}")
        print(f"  Total Tokens:        {run_to_display.total_tokens:,}")

        # Tool Usage
        if run_to_display.tools_used:
            print(f"\n🔧 TOOL USAGE:")
            print(f"  Total Tool Calls:    {run_to_display.tool_calls}")
            for tool_name, count in sorted(
                run_to_display.tools_used.items(),
                key=lambda x: x[1],
                reverse=True
            ):
                print(f"    • {tool_name}: {count} call(s)")

        # Detailed LLM Call Breakdown
        if detailed and run_to_display.llm_call_details:
            print(f"\n📊 LLM CALL BREAKDOWN:")
            for call in run_to_display.llm_call_details:
                print(f"\n  Call #{call['call_number']}:")
                print(f"    Triggered by:      {call['tool_triggered'] or 'Initial'}")
                print(f"    Input Tokens:      {call['input_tokens']:,}")
                print(f"    Output Tokens:     {call['output_tokens']:,}")
                print(f"    Total Tokens:      {call['total_tokens']:,}")
                if call['prompt_size_chars'] > 0:
                    print(f"    Prompt Size:       {call['prompt_size_chars']:,} chars")
                    print(f"    Efficiency:        {call['tokens_per_char']:.2f} tokens/char")

        # Detailed Tool Metrics
        if detailed:
            print(f"\n📈 DETAILED TOOL METRICS:")
            for tool_name, metrics in sorted(self.tool_metrics.items()):
                success_rate = (metrics.successes / metrics.calls * 100) if metrics.calls > 0 else 0
                print(f"\n  {tool_name}:")
                print(f"    Total Calls:       {metrics.calls}")
                print(f"    Successes:         {metrics.successes}")
                print(f"    Failures:          {metrics.failures}")
                print(f"    Success Rate:      {success_rate:.1f}%")
                print(f"    Total Time:        {metrics.total_execution_time:.2f}s")
                print(f"    Avg Time/Call:     {metrics.avg_execution_time:.2f}s")

        # Optimization Suggestions
        if detailed:
            print(f"\n💡 OPTIMIZATION SUGGESTIONS:")
            if run_to_display.input_tokens > 20000:
                print(f"  • High input token usage ({run_to_display.input_tokens:,})")
                print(f"    → Consider shortening system prompts or user messages")
                print(f"    → Use more specific/concise tool descriptions")
                print(f"    → Reduce example data in prompts")

            if run_to_display.llm_calls > 5:
                print(f"  • Multiple LLM calls ({run_to_display.llm_calls})")
                print(f"    → Consider batch processing tool results")
                print(f"    → Reduce intermediate reasoning steps")

            avg_tokens_per_call = run_to_display.total_tokens / run_to_display.llm_calls if run_to_display.llm_calls > 0 else 0
            if avg_tokens_per_call > 10000:
                print(f"  • High tokens per call ({avg_tokens_per_call:,.0f})")
                print(f"    → Summarize tool results before passing to LLM")
                print(f"    → Use prompt caching for repeated patterns")

        print("\n" + "=" * 100 + "\n")

    def save_metrics(self, format: MetricsFileFormat = MetricsFileFormat.JSON):
        """Save metrics to file"""
        if format == MetricsFileFormat.JSON:
            self._save_json()
        elif format == MetricsFileFormat.CSV:
            self._save_csv()
        elif format == MetricsFileFormat.TEXT:
            self._save_text()

    def _save_json(self):
        """Save metrics as JSON"""
        metrics_file = os.path.join(self.metrics_dir, "runs.json")
        data = {
            "generated_at": datetime.now().isoformat(),
            "total_runs": len(self.all_runs),
            "stats_summary": self.get_stats_summary(),
            "runs": [asdict(run) for run in self.all_runs],
            "tool_metrics": {
                name: asdict(metrics) for name, metrics in self.tool_metrics.items()
            },
            "llm_metrics": {
                name: asdict(metrics) for name, metrics in self.llm_metrics.items()
            },
        }

        with open(metrics_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"✅ Metrics saved to: {metrics_file}")

    def _save_csv(self):
        """Save metrics as CSV"""
        import csv
        metrics_file = os.path.join(self.metrics_dir, "runs.csv")

        if not self.all_runs:
            print("⚠️ No runs to save")
            return

        with open(metrics_file, 'w', newline='') as f:
            fieldnames = [
                'run_id', 'timestamp', 'llm_provider', 'llm_model',
                'source_city', 'destination_city', 'week_start_date',
                'duration_seconds', 'tool_calls', 'llm_calls',
                'input_tokens', 'output_tokens', 'total_tokens', 'success'
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for run in self.all_runs:
                row = {k: v for k, v in asdict(run).items() if k in fieldnames}
                writer.writerow(row)

        print(f"✅ Metrics saved to: {metrics_file}")

    def _save_text(self):
        """Save metrics as formatted text"""
        metrics_file = os.path.join(self.metrics_dir, "runs.txt")

        with open(metrics_file, 'w') as f:
            f.write("=" * 100 + "\n")
            f.write("TRIP AGENT METRICS SUMMARY\n")
            f.write("=" * 100 + "\n\n")

            stats = self.get_stats_summary()
            f.write("OVERALL STATISTICS:\n")
            for key, value in stats.items():
                f.write(f"  {key}: {value}\n")

            f.write("\n" + "-" * 100 + "\n")
            f.write("PER-RUN DETAILS:\n\n")

            for run in self.all_runs:
                f.write(f"Run ID: {run.run_id}\n")
                f.write(f"  Timestamp: {run.timestamp}\n")
                f.write(f"  Trip: {run.source_city} → {run.destination_city}\n")
                f.write(f"  LLM: {run.llm_provider} ({run.llm_model})\n")
                f.write(f"  Duration: {run.duration_seconds:.2f}s\n")
                f.write(f"  Status: {'Success' if run.success else 'Failed'}\n")
                f.write(f"  Tool Calls: {run.tool_calls}\n")
                f.write(f"  LLM Calls: {run.llm_calls}\n")
                f.write(f"  Tokens: {run.total_tokens} (Input: {run.input_tokens}, Output: {run.output_tokens})\n")
                f.write("\n")

        print(f"✅ Metrics saved to: {metrics_file}")


# Global metrics tracker instance
_metrics_tracker: Optional[MetricsTracker] = None


def get_metrics_tracker(metrics_dir: str = "metrics") -> MetricsTracker:
    """Get or create the global metrics tracker"""
    global _metrics_tracker
    if _metrics_tracker is None:
        _metrics_tracker = MetricsTracker(metrics_dir)
    return _metrics_tracker
