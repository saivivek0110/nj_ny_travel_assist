# Agentic AI Travel Planner

An AI system that picks the **best days to travel** for a given week and generates **optimized commute plans** for each day — delivered as a single HTML email report (or saved locally if Gmail is not configured).

## Architecture

```
agents/trip_orchestrator.py   (orchestrator — coordinates everything)
├── agents/week_trip_scout.py (picks top 3 travel days from weather + news)
└── tools/commute_tools.py    (transit status, schedules, weather impact)
```

**Batch optimization:** all transit data is fetched once, then a single LLM call analyzes all 3 days simultaneously — replacing a per-day ReAct agent loop.

| Before | After |
|--------|-------|
| N days × (8 Tavily + 2 LLM) | 8 Tavily + 2 LLM total |
| ~24 Tavily + 6 LLM calls | ~12 Tavily + 2 LLM calls |

## What It Does

1. **Week Scout** — fetches real-time weather (NWS) and travel disturbances for the target week, ranks Mon–Fri, picks the best 3 days.
2. **Commute Analysis** — fetches transit status, schedules (cached 7 days), traffic, and weather impact once, then a single LLM call generates a commute plan for each recommended day.
3. **Timetable Cache** — transit schedules are cached locally for 7 days (`cache/timetables.json`), avoiding repeat Tavily calls for stable data.
4. **Report** — combines both analyses into a styled HTML email and sends via Gmail, or saves as `report_<date>.html` if Gmail is not configured.

## Prerequisites

- Python 3.10+
- API keys: any supported LLM + Tavily (web search)
- Gmail OAuth credentials (optional)

## Setup

### 1. Clone and create virtual environment

```bash
git clone <repo-url>
cd travelAgent
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and fill in your API keys:

```env
# LLM — provider auto-detected from model name prefix
LLM_MODEL=gpt-4.1-nano
LLM_API_KEY=sk-...

# Or use explicit provider style (legacy)
# LLM_PROVIDER=openai
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-4.1-nano

# Required for web search
TAVILY_API_KEY=tvly-...

# Your route
ORIGIN_LOCATION=Edison, NJ
DESTINATION_LOCATION=New York Penn Station

# Where to send reports (optional)
DEFAULT_EMAIL=your@email.com
```

### 3. (Optional) Set up Gmail OAuth

```bash
python3 utils/setup_auth.py
```

Opens a browser for Google OAuth. After authenticating, `token.json` is saved locally. You need a `credentials.json` from Google Cloud Console (Gmail API, Desktop OAuth app).

**Gmail is optional** — if not configured, the HTML report is saved to `report_<date>.html`.

## Usage

```bash
python3 -u agents/trip_orchestrator.py -w 2026-03-16
```

With all options:

```bash
python3 -u agents/trip_orchestrator.py \
  -s "Edison, NJ" \
  -d "New York Penn Station" \
  -w 2026-03-16 \
  -e your@email.com \
  -mt "07:00-10:00" \
  -et "16:00-20:00"
```

| Flag | Default | Description |
|------|---------|-------------|
| `-s` / `--source` | `ORIGIN_LOCATION` from `.env` | Origin city |
| `-d` / `--destination` | `DESTINATION_LOCATION` from `.env` | Destination city |
| `-w` / `--week` | *(required)* | Week start date `YYYY-MM-DD` |
| `-e` / `--email` | `DEFAULT_EMAIL` from `.env` | Recipient email |
| `-mt` / `--morning-time` | `07:00-10:00` | Morning departure window (24h) |
| `-et` / `--evening-time` | `16:00-20:00` | Evening return window (24h) |

Pipe output to a file with `-u` for unbuffered stdout:

```bash
python3 -u agents/trip_orchestrator.py -w 2026-03-16 2>&1 | tee output_$(date +%Y%m%d_%H%M%S).txt
```

## LLM Configuration

### Option A — Unified (recommended)

Set `LLM_MODEL` + `LLM_API_KEY`. Provider is auto-detected from the model name prefix:

| Model prefix | Provider | Example |
|---|---|---|
| `claude-*` | Anthropic | `claude-haiku-4-5-20251001` |
| `gpt-*`, `o1-*`, `o3-*`, `o4-*` | OpenAI | `gpt-4.1-nano` |
| `gemini-*` | Google | `gemini-2.0-flash` |
| `mistral-*`, `mixtral-*` | Mistral | `mistral-small-latest` |
| `command-*`, `c4ai-*` | Cohere | `command-r-plus` |

### Option B — Explicit provider

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-nano
```

## Project Structure

```
travelAgent/
├── agents/
│   ├── trip_orchestrator.py  # Orchestrator: runs both scouts, builds + sends report
│   ├── week_trip_scout.py    # Batch LLM: picks best 3 travel days
│   └── route_scout.py        # LangGraph agent (standalone commute optimizer)
├── config/
│   └── settings.py           # LLM factory, env loading, provider auto-detection
├── tools/
│   ├── search_tools.py       # NWS weather + Tavily search tools
│   ├── commute_tools.py      # Transit tools (NJ Transit, PATH, subway, traffic, bus)
│   ├── timetable_cache.py    # 7-day local cache for transit schedules + fares
│   └── email_tools.py        # Gmail send tool (optional)
├── prompts/
│   └── travel_prompts.py     # System prompts for Week Trip Scout and Route Scout
├── metrics/
│   └── metrics.py            # Run tracking: tokens, cost, tool calls, failure rate
├── utils/
│   ├── logging_config.py     # Logging utilities
│   └── setup_auth.py         # Gmail OAuth setup
├── cache/
│   └── timetables.json       # Auto-generated timetable cache (7-day TTL)
├── tests/
├── .env.example              # Template — copy to .env
└── requirements.txt
```

## Output

### Email / HTML Report

The report has two parts:

**Part 1 — Weekly Travel Analysis**
- Weather forecast for each day (Mon–Fri)
- Travel disturbances and transit service status
- Daily feasibility table
- Top 3 recommended days with reasoning

**Part 2 — Daily Commute Plans**
- One card per recommended day
- Best transit option (single recommendation, not a list)
- Morning departure + evening return times within specified windows
- Official fare links (no dollar amounts — NJ Transit fares are JS-rendered and unreliable to scrape)
- Day-specific disruption notes

### End-of-Run Summary

```
╔════════════════════════════════════════════════════╗
║                   RUN SUMMARY                      ║
╠════════════════════════════════════════════════════╣
║  Duration      :  52.1s                            ║
║  LLM Calls     :  2   (gpt-4.1-nano)               ║
║  Tool Calls    :  12                               ║
║  Tokens Used   :  11,840  (in: 9,200 / out: 2,640)║
║  Est. Cost     :  ~$0.0021                         ║
║  Email         :  ✅ sent                          ║
║  Best Days     :  2026-03-23, 2026-03-24, ...      ║
╚════════════════════════════════════════════════════╝
```

## LLM Cost Reference

| Provider | Model | Input / 1M tokens | Output / 1M tokens |
|----------|-------|-------------------|--------------------|
| OpenAI | `gpt-4.1-nano` | $0.10 | $0.40 |
| OpenAI | `gpt-4.1-mini` | $0.40 | $1.60 |
| Google | `gemini-2.0-flash` | $0.075 | $0.30 |
| Google | `gemini-2.0-flash-lite` | $0.075 | $0.30 |
| Anthropic | `claude-haiku-4-5-20251001` | $0.80 | $4.00 |

One full integrated run uses ~12 Tavily searches + 2 LLM calls.

## Timetable Cache

Transit schedules change infrequently. On the first run, `tools/timetable_cache.py` fetches schedule and route data via Tavily and stores it in `cache/timetables.json` with a 7-day TTL. Subsequent runs reuse the cache — saving ~9 Tavily API calls per run.

To force a refresh:

```python
from tools.timetable_cache import clear_timetable_cache
clear_timetable_cache()  # clear all
clear_timetable_cache("Edison, NJ", "New York Penn Station")  # clear one route
```

Or configure the TTL:

```env
TIMETABLE_CACHE_DAYS=3  # default: 7
```

## Sensitive Files (gitignored)

| File | Contains |
|------|----------|
| `.env` | API keys, email address |
| `token.json` | Gmail OAuth access token |
| `credentials.json` | Google OAuth client credentials |
| `metrics/runs.json` | Run statistics |
| `cache/timetables.json` | Cached schedule data |

Never commit these. Use `.env.example` as the template.

## Troubleshooting

**No Gmail / email not sent** — Reports are saved to `report_<date>.html`. Run `python3 utils/setup_auth.py` to enable Gmail.

**Rate limit (429)** — Switch to a cheaper/freer model (e.g. `gemini-2.0-flash`) or wait. The LLM will print a friendly message.

**Auth error (401)** — Check that `LLM_API_KEY` in `.env` is correct and active.

**Wrong city in commute plans** — Set `ORIGIN_LOCATION` and `DESTINATION_LOCATION` in `.env`. All tools read from `Config` — there are no hardcoded city names.

**Commute plan shows parse error** — The LLM didn't follow the `===DATE: YYYY-MM-DD===...===END===` format. Check the raw output in the error message. Retry; nano-class models occasionally deviate from strict format instructions.

**Claude API credit error** — Claude.ai Pro subscription != Anthropic API credits. Add credits at [console.anthropic.com](https://console.anthropic.com) or switch to a different provider.

## License

MIT
