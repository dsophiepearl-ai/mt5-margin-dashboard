# FX Margin Dashboard

Streamlit tool for monitoring account risk and simulating margin calls / stop-outs on an MT5-style trading account.

## Features

- Live account snapshot: balance, equity, used margin, margin level, open positions
- Margin call & stop-out simulator: configurable price drift, margin call threshold, and stop-out threshold; force-closes the largest losing position first and logs every event
- Works with a real MT5 demo account or a built-in mock client (no broker account required to run)

## Skills demonstrated

| Skill | Where |
|---|---|
| Python (OOP, dataclasses, type hints) | `src/margin_engine.py`, `src/mt5_client.py` |
| MT4/MT5 platform integration | `src/mt5_client.py` |
| Margin / equity / leverage calculations | `Account`, `Position` classes in `src/margin_engine.py` |
| Real-time risk monitoring & rules-based alerting | `MarginMonitor` class |
| Dashboarding / data visualization | `src/dashboard.py` (Streamlit) |
| Unit testing | `tests/test_margin_engine.py` — 6 tests |
| Config management (env vars, no hardcoded secrets) | `.env.example` |
| Version control | git repo, ready to push |

## Tech stack

Python 3, Streamlit, pandas

## Project structure

```
mt5-margin-dashboard/
  src/
    mt5_client.py      # MT5 client: real package or mock, same interface
    margin_engine.py   # Account/Position models + margin call & stop-out engine
    dashboard.py        # Streamlit UI, two tabs
  tests/
    test_margin_engine.py
  requirements.txt
  .env.example
```

## Key concepts

| Term | Definition |
|---|---|
| Equity | balance + unrealized P/L across all open positions |
| Used margin | collateral locked to keep positions open (position size ÷ leverage) |
| Margin level | equity ÷ used margin × 100% |
| Margin call | warning issued once margin level drops below a threshold (default 100%) |
| Stop-out | forced closure once margin level drops below a lower threshold (default 50%), largest loser closed first |

Thresholds are configurable — real values vary by broker and regulator.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # optional, only needed for a real MT5 connection
```

## Run

```bash
streamlit run src/dashboard.py
```

## Test

```bash
pytest
```

## Connecting to a real MT5 demo account (optional)

1. Install the `MetaTrader5` package on a Windows machine with the MT5 terminal installed and logged into a demo account (uncomment it in `requirements.txt`)
2. In `.env`, set `MT5_USE_MOCK=false` and fill in `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
3. Run the dashboard as normal — the "Live Account Snapshot" tab now shows the real account

## Design notes

- `mt5_client.py` abstracts the MetaTrader5 connection behind a single interface (`account_info()`, `positions_get()`, `symbol_info_tick()`) so the rest of the app doesn't care whether it's talking to a real terminal or the mock client. The real `MetaTrader5` package is Windows-only and requires a logged-in terminal, so the mock keeps the project runnable and testable anywhere.
- `margin_engine.py` is independent of the MT5 client and uses its own synthetic price generator. A real account can take a long time to drift into a margin call; the simulator lets that scenario be triggered on demand.
