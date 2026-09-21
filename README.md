# FX Margin Dashboard

Streamlit tool for monitoring account risk and simulating margin calls / stop-outs on an MT5-style trading account.

## Try it now — no installation needed

**[Open the live dashboard →](https://mt5-margin-dashboard-pygbfhx6xq3nkbxgch5shx.streamlit.app/)**

Click the link, it opens in your browser. Nothing to install, no terminal, no downloading this repo. This is the fastest way to see it working — the rest of this README is only needed if you want to run the code yourself.

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
| Version control & deployment | git repo, deployed on Streamlit Community Cloud |

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

## Run it yourself (optional)

Only needed if you want to inspect, modify, or test the code rather than just view it through the live link above. Works the same whether you use Anaconda Prompt or Git Bash — the commands are identical either way, just open whichever terminal you normally use.

1. Pick a folder to work in and clone the repo there:
   ```bash
   cd Desktop
   git clone https://github.com/dsophiepearl-ai/mt5-margin-dashboard.git
   cd mt5-margin-dashboard
   ```
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Launch it:
   ```bash
   streamlit run src/dashboard.py
   ```
4. Streamlit opens the dashboard automatically at `http://localhost:8501`. If it doesn't open on its own, copy that address into your browser.
5. To stop it, go back to the terminal and press `Ctrl+C`.

## Test

```bash
pytest
```

6/6 tests pass, covering margin level calculations, margin call triggering, and stop-out logic (including that the largest loser is closed first when multiple positions are open).

## Connecting to a real MT5 demo account (optional)

1. Install the `MetaTrader5` package on a Windows machine with the MT5 terminal installed and logged into a demo account (uncomment it in `requirements.txt`)
2. Copy `.env.example` to `.env` (`cp .env.example .env`), set `MT5_USE_MOCK=false`, and fill in `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
3. Run the dashboard as normal — the "Live Account Snapshot" tab now shows the real account

## Design notes

- `mt5_client.py` abstracts the MetaTrader5 connection behind a single interface (`account_info()`, `positions_get()`, `symbol_info_tick()`) so the rest of the app doesn't care whether it's talking to a real terminal or the mock client. The real `MetaTrader5` package is Windows-only and requires a logged-in terminal, so the mock keeps the project runnable and testable anywhere — including on Streamlit Community Cloud, where the live demo above is hosted.
- `margin_engine.py` is independent of the MT5 client and uses its own synthetic price generator. A real account can take a long time to drift into a margin call; the simulator lets that scenario be triggered on demand.
