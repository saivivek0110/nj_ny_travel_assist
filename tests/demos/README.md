# Demo Scripts

Smoke tests that run a live agent call. Require API keys set in `.env`.

Run from project root (`travelAgent/`):

```bash
source venv/bin/activate
```

---

## demo.py — Week Trip Scout (fixed week)

```bash
python tests/demos/demo.py
```

Expected output:
```
🎬 WEEK TRIP SCOUT DEMO
======================================================================

🌍 WEEK TRIP SCOUT - Weekly Analysis
================================================================================
📍 From: New York
📍 To: San Francisco
📅 Range: 2026-03-16 to 2026-03-20
...
✅ ANALYSIS COMPLETE
================================================================================

📊 TRAVEL ANALYSIS REPORT:
...
  Top 3 Recommended Days for Travel:
  1. Wednesday, 2026-03-18
  2. Tuesday, 2026-03-17
  3. Thursday, 2026-03-19
...
✅ Demo completed successfully!
```

---

## travel_demo.py — Week Trip Scout (dynamic next-Monday)

```bash
python tests/demos/travel_demo.py
```

Same structure as `demo.py` but automatically picks the next Monday.

---

## commute_demo.py — Route Scout (today's commute)

```bash
python tests/demos/commute_demo.py
```

Expected output:
```
🎬 ROUTE SCOUT DEMO
================================================================================

🚇 ROUTE SCOUT - North Brunswick, NJ → New York Penn Station
================================================================================
📍 Route: North Brunswick, NJ → New York Penn Station
📅 Analysis Date: 2026-03-04
...
✅ ANALYSIS COMPLETE
================================================================================
[Ranked commute options: NJ Transit, PATH, Subway, Bus, Car]
...
✅ Demo completed successfully!
```
