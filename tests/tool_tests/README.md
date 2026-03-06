# Tool Tests

Unit tests for individual tools in `tools/`.

Each tool can be tested in isolation without running a full agent loop, making these faster and cheaper than demos.

## Structure (to be added)

```
tests/tool_tests/
├── test_search_tools.py     # search_weather, tavily_search, search_travel_disturbances
├── test_commute_tools.py    # NJ Transit, PATH, subway, traffic, bus, cost, schedule
└── test_email_tools.py      # send_email (mock), is_email_configured
```

## Running (once tests are added)

```bash
# From project root
source venv/bin/activate
python -m pytest tests/tool_tests/ -v
```

## Writing a new tool test

```python
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.commute_tools import check_nj_transit_status

def test_nj_transit_returns_string():
    result = check_nj_transit_status.invoke({})
    assert isinstance(result, str)
    assert len(result) > 0
```
