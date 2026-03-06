# How It Works — Agentic AI Travel Planner

A plain-English walkthrough of every step the system takes, from user input to final report.

---

## 1. Big Picture

This system answers one question: **"Given a work week, what are the best 3 days to travel from A to B, and what is the fastest commute on each of those days?"**

It combines two data sources:
- **NWS (api.weather.gov)** — free US government weather forecasts, no API key required. The flow is: geocode the city → get the NWS grid point → fetch 7-day forecast periods.
- **Tavily** — a web search API that returns live search results. Used for everything else: transit alerts, travel disturbances, NJ Transit/PATH/subway/bus status, and destination news.

There are three ways to run the system:

| Mode | Agent | What it does | LLM calls |
|------|-------|-------------|-----------|
| Week only | `week_trip_scout.py` | Picks best 3 travel days | 4–8 (ReAct loop) |
| Commute only | `route_scout.py` | Ranks commute options for one date | 6–12 (ReAct loop) |
| **Recommended** | `trip_orchestrator.py` | Does both + HTML report | **exactly 2** |

The orchestrator is recommended because it runs the same analysis as the two standalone agents combined, but uses a batch approach that cuts LLM calls from ~15 down to 2.

---

## 2. What is an "API Request" to the LLM?

Every `llm.invoke()` call is one HTTPS POST to the model provider (Gemini, Claude, OpenAI, etc.). What gets sent in that POST:

1. **System prompt** — the agent's persona and report format instructions (resent every time)
2. **Full conversation history** — every prior message and every tool result from this run (grows with each call)
3. **Tool definitions** — the JSON schema for every tool the agent can use (resent every time)

The model responds with **either** a tool call instruction **or** a final text answer — never both in the same response. This is enforced by the underlying protocol: if the model wants to call a tool, it returns a structured `tool_calls` object with no final text. The framework executes the tool, appends the result, and sends everything back.

This is why a single run can show 15 requests in the Gemini dashboard or Anthropic console: each tool decision is one round-trip.

---

## 3. The ReAct Loop (how standalone agents work)

ReAct stands for **Reason → Act → Observe → Reason again**. LangGraph's `create_react_agent` implements this as a state machine:

```
User message
    ↓
[LLM Call #1]  ← system prompt + user message + tool definitions
    ↓
"I should call search_weather"  ← tool call instruction (not final text)
    ↓
Tool executes → result appended to history
    ↓
[LLM Call #2]  ← system prompt + user message + tool result + tool definitions
    ↓
"I should call tavily_search"
    ↓
... (repeats) ...
    ↓
[LLM Call #N]  ← LLM writes final answer with no tool calls → loop exits
    ↓
Final text output
```

**Why each tool call = a new API call:** The model cannot "decide" to call a tool and simultaneously process the result — it must return the tool call, the framework runs the tool, and then the model is invoked again with the new information.

**Why later calls are larger than earlier calls:** Every call resends the full conversation history. Call #1 might carry 1,721 input tokens (system prompt + user message). Call #2 carries those same tokens plus the tool result — potentially 14,282 tokens if the weather response is large. Token counts grow monotonically within a run.

**When it stops:** When the model writes a final answer that contains no `tool_calls`. The LangGraph loop detects this and returns the final message as the result.

---

## 4. Tool Filtering — Why Each Agent Has Its Own Tool Set

Both agents are built from the same global `TOOLS` list, but each filters it to a named subset:

```python
# week_trip_scout.py
TRAVEL_AGENT_TOOL_NAMES = [
    "search_weather",
    "tavily_search",
    "search_travel_disturbances",
    "send_email"
]

# route_scout.py
COMMUTE_AGENT_TOOL_NAMES = [
    "check_nj_transit_status", "check_path_status", "check_nyc_subway_status",
    "check_traffic_conditions", "get_bus_options", "get_commute_cost_comparison",
    "get_commute_schedule_info", "analyze_weather_impact", "send_email"
]
```

Why this matters: if the Week Trip Scout had access to `check_nj_transit_status`, the model might call it redundantly (that data is already covered by `search_travel_disturbances`). If the Route Scout had access to `search_weather`, it might re-fetch weather instead of using `analyze_weather_impact` which fetches weather for both endpoints. Tool filtering keeps each agent focused and prevents unnecessary API calls.

---

## 5. Week Trip Scout — Step by Step

**Entry point:** `analyze_travel_week()` in `agents/week_trip_scout.py`

**Inputs:** source city, destination city, week_start_date (any date — code snaps to Monday), recipient email

**Setup:**
1. `get_week_dates()` converts the input date to Mon–Fri dates for that week
2. `create_week_trip_scout()` calls `create_react_agent(model=llm, tools=TRAVEL_AGENT_TOOLS, prompt=WEEK_TRIP_SCOUT_SYSTEM_PROMPT)`
3. A detailed user message is assembled listing the week range and requesting the standard report format

**ReAct loop begins** (4 tools available):

| Step | What the LLM decides | What happens |
|------|---------------------|-------------|
| Call #1 | Call `search_weather` for destination | NWS: geocode → grid point → 7-day forecast |
| Call #2 | Call `search_travel_disturbances` | Tavily: strikes, delays, events near destination |
| Call #3 | Call `tavily_search` for NJ Transit delays | Tavily: transit news for the week |
| Call #4 | Call `tavily_search` for destination news | Tavily: any events that affect travel |
| Call #5+ | LLM has enough data → writes final report | Loop exits |

**Output parsing:** The user message instructs the LLM to end its response with exactly:
```json
{"recommended_dates": ["YYYY-MM-DD", "YYYY-MM-DD", "YYYY-MM-DD"]}
```
Three regex patterns attempt to extract this block from the final content — fenced code block first, then bare JSON object, then just the array. The extracted dates are returned if `return_data=True`.

**Email:** If `auto_send_email=True` (default), the LLM is instructed to call `send_email` as step 7 of its process. `send_email` uses Gmail OAuth — if `token.json` is absent, it returns a graceful skip message.

---

## 6. Route Scout — Step by Step

**Entry point:** `analyze_commute()` in `agents/route_scout.py`

**Inputs:** source, destination, date (defaults to today), optional preferred_mode

**Setup:**
1. `create_route_scout()` calls `create_react_agent` with 9 commute tools
2. User message is assembled: "Analyze all commute options from {source} to {destination} on {date}"

**ReAct loop begins** (9 tools available):

The LLM decides which tools to call based on the route. For an NJ → NYC route it typically calls all 8 data tools:

| Tool | What it fetches |
|------|----------------|
| `check_nj_transit_status` | Northeast Corridor alerts via Tavily |
| `check_path_status` | PATH train service status via Tavily |
| `check_nyc_subway_status` | MTA subway alerts via Tavily |
| `check_traffic_conditions` | Route 1/GSP congestion via Tavily |
| `get_bus_options` | Bus schedules/delays via Tavily |
| `get_commute_cost_comparison` | Fare comparison across modes via Tavily |
| `get_commute_schedule_info` | Departure frequency, peak hours via Tavily |
| `analyze_weather_impact` | NWS weather for both endpoints |

After gathering all data, the LLM writes the final ranked commute report using the `ROUTE_SCOUT_SYSTEM_PROMPT` format:
- `RANK 1 (BEST)` → recommended option with departure times
- `RANK 2 (GOOD)` → backup option
- `RANK 3+ (AVOID)` → options to skip and why

No JSON parsing — the output is the final text, used directly as the commute report.

---

## 7. Trip Orchestrator — Step by Step (Batch Mode)

**Entry point:** `run_integrated_plan()` in `agents/trip_orchestrator.py`

**Why it exists:** In standalone mode, Week Trip Scout makes 4–8 LLM calls and Route Scout makes 6–12. For 3 travel days that's up to 44 LLM calls total. The orchestrator makes exactly **2 LLM calls** by pre-fetching all tool data directly (no LLM involvement in data gathering) and then calling the LLM once per phase with all data assembled.

**New CLI parameters (added recently):**
- `--cost-mode` — `per_trip` (default), `10_trip`, `monthly`, or `all`
- `-mt / --morning-time` — departure window from source (default: `07:00-10:00`)
- `-et / --evening-time` — return window from destination (default: `16:00-20:00`)

### STEP 1 — `_batch_week_analysis()`

```
4 tools called directly in sequence (no LLM):
  search_weather(destination)          → NWS 7-day forecast
  [sleep 1.1s]
  search_travel_disturbances(dest)     → Tavily disturbance search
  [sleep 1.1s]
  tavily_search("NJ Transit delays…")  → transit news
  [sleep 1.1s]
  tavily_search("travel news dest…")   → destination news
  [sleep 1.1s]

All 4 results assembled into data_block string

LLM Call #1:
  SystemMessage: WEEK_TRIP_SCOUT_SYSTEM_PROMPT
  HumanMessage:  "Here is the pre-fetched data. Pick best 3 days. End with JSON block."
  → Response: full travel report + {"recommended_dates": [...]}

Regex parses recommended_dates from JSON block
```

The 1.1s sleeps exist because Tavily enforces approximately 1 request/second. Skipping them causes 429 rate-limit errors.

### STEP 2 — `_batch_commute_analysis()`

```
Phase 0 — Timetable Cache (new):
  get_timetables(source, destination)
    → checks cache/timetables.json
    → if cache is fresh (< 7 days old): returns cached data instantly
    → if stale or missing: runs 9 Tavily queries for schedules + fares, saves to cache
  Result: timetable_block (stable schedule/fare data)

Phase 1 — Live status (8 tools, no LLM):
  check_nj_transit_status()    [sleep 1.1s]
  check_path_status()          [sleep 1.1s]
  check_nyc_subway_status()    [sleep 1.1s]
  check_traffic_conditions()   [sleep 1.1s]
  get_bus_options()            [sleep 1.1s]
  get_commute_cost_comparison()[sleep 1.1s]
  get_commute_schedule_info()  [sleep 1.1s]
  analyze_weather_impact()     [sleep 1.1s]
  Result: data_block (live disruptions + current status)

LLM Call #2:
  SystemMessage: _BATCH_COMMUTE_SYSTEM_PROMPT
  HumanMessage:  timetable_block + data_block + all 3 dates
                 + cost_mode (per_trip/10_trip/monthly)
                 + morning_time window + evening_time window
  → Response: per-date sections + weekly cost summary

Regex splits response by date marker (===DATE: YYYY-MM-DD===):
  commute_reports["2026-03-09"] = "MORNING: NJ Transit departs 08:12..."
  commute_reports["2026-03-11"] = "MORNING: NJ Transit departs 07:54..."
  commute_reports["2026-03-12"] = "MORNING: NJ Transit departs 08:12..."

weekly_cost_summary extracted from ===WEEKLY SUMMARY=== block
```

**Why timetable cache?** Schedules and fares don't change day-to-day. Without caching, every run burns 9 Tavily API calls just to re-fetch the same timetable. The cache saves those calls for up to 7 days.

The date-marker format (`===DATE: YYYY-MM-DD===` ... `===END===`) is enforced by the system prompt. Regex pattern: `r'===DATE:\s*{date}===\s*(.*?)\s*===END==='` with `re.DOTALL`. If a date's section is missing (model didn't follow format), it falls back to returning the entire response for that date.

### STEP 3 — Build HTML and deliver

```
_build_html_email() assembles:
  - Header with source → destination
  - Top 3 recommended days as color-coded badges (green/blue/gold)
  - Part 1: full travel report (JSON block stripped, markdown tables → HTML)
  - Part 2: per-date commute cards
  - Part 3: weekly cost summary (if confirmed fares were found)
  - Part 2: per-date commute cards (red border if error detected, green if clean)

Delivery:
  if token.json exists → send_email.func(subject, html_body, recipient)
  else                 → write report_{week_start_date}.html to disk

_print_run_summary() reads MetricsTracker and prints:
  ╔═══════════════════════╗
  ║      RUN SUMMARY      ║
  ╠═══════════════════════╣
  ║ Duration    : 42.3s   ║
  ║ LLM Calls   : 2       ║
  ║ Tool Calls  : 12      ║
  ║ Tokens Used : 28,441  ║
  ║ Est. Cost   : ~$0.042 ║
  ╚═══════════════════════╝
```

---

## 8. Tools Reference Table

| Tool | File | Backend | Returns |
|------|------|---------|---------|
| `search_weather` | tools/search_tools.py | NWS api.weather.gov | 7-day forecast with temp/wind/precip per day; falls back to Tavily for non-US |
| `search_travel_disturbances` | tools/search_tools.py | Tavily | Strikes, delays, events near destination |
| `tavily_search` | tools/search_tools.py | Tavily | General web search results |
| `check_nj_transit_status` | tools/commute_tools.py | Tavily | NJ Transit Northeast Corridor alerts |
| `check_path_status` | tools/commute_tools.py | Tavily | PATH train service status |
| `check_nyc_subway_status` | tools/commute_tools.py | Tavily | NYC MTA subway alerts |
| `check_traffic_conditions` | tools/commute_tools.py | Tavily | Route 1/GSP congestion, toll info |
| `get_bus_options` | tools/commute_tools.py | Tavily | Bus schedules and delays |
| `get_commute_cost_comparison` | tools/commute_tools.py | Tavily | Fare comparison across all modes |
| `get_commute_schedule_info` | tools/commute_tools.py | Tavily | Schedule frequency, peak vs off-peak |
| `analyze_weather_impact` | tools/commute_tools.py | NWS × 2 | Weather for both source and destination endpoints |
| `send_email` | tools/email_tools.py | Gmail OAuth | Sends HTML report; gracefully skips if not configured |
| `get_timetables` | tools/timetable_cache.py | cache/timetables.json + Tavily (on miss) | Returns cached schedule + fare data; runs 9 Tavily queries if cache is stale (7-day TTL) |

**NWS flow (search_weather):** `_geocode(location)` → Nominatim → (lat, lon) → `_nws_periods(lat, lon)` → NWS `/points/{lat},{lon}` → gets `forecast` URL → NWS forecast endpoint → list of 14 period dicts → `_format_nws()` pairs day/night periods and formats per-day strings.

---

## 9. Metrics — What Gets Tracked

Every tool call and every LLM call is recorded by `MetricsTracker` (singleton via `get_metrics_tracker()` in `metrics/metrics.py`).

**Per LLM call:** input tokens, output tokens, which tool triggered the call, prompt size at time of call

**Per tool call:** tool name, success/fail, duration

**Per run summary (`AgentRunMetrics`):**
- `llm_calls` — total number of `llm.invoke()` calls
- `tool_calls` — total tool executions
- `input_tokens` / `output_tokens` / `total_tokens`
- `cost_usd` — calculated from `COST_PER_1K_TOKENS` pricing table (keyed by model name)
- `error_category` — classification if the run failed

**After each run:** `metrics.save_metrics(MetricsFileFormat.JSON)` appends to `metrics/runs.json`. The `analyze_tokens.py` and `view_metrics.py` scripts can read this file to compare runs across sessions.

**LLM metrics (`LLMMetrics`):**
- `avg_tokens_per_llm_call` — useful for spotting token bloat in the ReAct loop

**Tool metrics (`ToolMetrics`):**
- `tool_failure_rate` — fraction of tool calls that returned an error string

The `_print_run_summary()` in trip_orchestrator reads the last run from the tracker after the run completes and prints the summary box.
