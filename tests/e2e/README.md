# End-to-End Tests

Full pipeline tests that run the Trip Orchestrator from source to final report.

## Quick run

```bash
source venv/bin/activate

python agents/trip_orchestrator.py \
  -s "North Brunswick, NJ" \
  -d "New York Penn Station" \
  -w 2026-03-16 \
  -e your@email.com \
  --verbose 2>&1 | tee run_$(date +%Y%m%d_%H%M%S).log
```

## What it tests

1. **Week Trip Scout** — fetches weather + disturbances, picks best 3 days via single LLM call
2. **Batch Commute Analysis** — fetches all 8 transit data sources once, single LLM call for all days
3. **HTML Report** — builds and either sends via Gmail or saves to `report_<date>.html`
4. **Metrics** — run summary box printed at end; JSON saved to `metrics/`

## Verifying success

Look for these lines in the output:

```
✅ Week Trip Scout identified best days: ['YYYY-MM-DD', 'YYYY-MM-DD', 'YYYY-MM-DD']
✅ INTEGRATED PLANNING COMPLETE
╔════════════════════════════════════════════════════╗
║                    RUN SUMMARY                     ║
╠════════════════════════════════════════════════════╣
  Duration      :  ...
  LLM Calls     :  2   (...)
  Tool Calls    :  12
  ...
╚════════════════════════════════════════════════════╝
```

## Individual agent E2E

```bash
# Week Trip Scout only
python agents/week_trip_scout.py \
  -s "North Brunswick, NJ" -d "New York Penn Station" \
  -w 2026-03-16 --quiet

# Route Scout only
python agents/route_scout.py --quiet
```
