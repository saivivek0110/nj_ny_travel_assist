# Running Tests

All commands below are run from the project root (`travelAgent/`) with the virtualenv active:

```bash
source venv/bin/activate
```

---

## Demos (smoke tests — require live API keys)

Quick end-to-end checks that agents load, call tools, and return output.

```bash
python tests/demos/demo.py
python tests/demos/travel_demo.py
python tests/demos/commute_demo.py
```

See [`tests/demos/README.md`](demos/README.md) for expected output.

---

## Tool Tests (`tests/tool_tests/`)

Unit tests for individual tools (weather, transit, email, etc.).

```bash
# stub — add per-tool unit tests here
```

See [`tests/tool_tests/README.md`](tool_tests/README.md).

---

## E2E Tests (`tests/e2e/`)

Full integrated run through the Trip Orchestrator:

```bash
python agents/trip_orchestrator.py \
  -s "North Brunswick, NJ" \
  -d "New York Penn Station" \
  -w 2026-03-16 \
  -e your@email.com
```

Expected output (truncated):

```
🤖 TRIP ORCHESTRATOR (Parent Agent)
================================================================================
🎯 Goal: Plan best days for North Brunswick, NJ -> New York Penn Station
📅 Week: 2026-03-16
...
STEP 1: Analyzing Week to find Best Travel Days
  📡 Fetching travel data (weather + disturbances)...
  🤖 Single LLM call to pick best 3 days...
✅ Week Trip Scout identified best days: ['2026-03-17', '2026-03-18', '2026-03-19']
...
STEP 2: Batch Commute Analysis (all days in one shot)
  ⚡ Batching 3 days → 8 Tavily + 1 LLM
...
✅ INTEGRATED PLANNING COMPLETE
```

See [`tests/e2e/README.md`](e2e/README.md) for more detail.
