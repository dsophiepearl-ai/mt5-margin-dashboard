# FX Margin Dashboard

A small trading-risk tool built for two responsibilities named directly in
forex Risk Analyst / Trading Operations job postings:

- "Familiarity with trading platforms (e.g., MT4/MT5)"
- "Execute hedge trades and facilitate margin calls or account liquidations as needed"

It has two parts:

1. **Live Account Snapshot** - connects to MetaTrader 5 (or a realistic mock,
   see below) and shows balance, equity, used margin, margin level, and open
   positions.
2. **Margin Call & Stop-Out Simulator** - a standalone rules engine that
   simulates a price moving against an open position and reacts the way a
   real risk desk would: issue a margin call warning, then force-close the
   position (stop-out / liquidation) if the margin level keeps falling.

## Why it's built this way

The official `MetaTrader5` Python package is Windows-only and requires a
running MT5 terminal logged into an account, which makes it awkward to
demo, test, or run in CI. So the project uses a client abstraction
(`src/mt5_client.py`): the rest of the app only ever calls
`account_info()` / `positions_get()` / `symbol_info_tick()`, and doesn't
know or care whether the answer came from a real terminal or from
`MockMT5Client`, which generates realistic account and position data.
This means the whole project runs out of the box with no broker account,
and can be pointed at a real MT5 demo account later just by setting
environment variables.

The margin call / stop-out logic (`src/margin_engine.py`) is deliberately
kept separate from the MT5 client. A real account can take a long time to
drift into a margin call naturally, which makes it hard to demo reliably -
so the simulator uses its own synthetic price generator with a
configurable drift, letting you force the scenario on demand and watch the
exact sequence a risk desk follows: **monitor -> warn -> escalate -> force-close**.

## Project structure

```
mt5-margin-dashboard/
  README.md
  requirements.txt
  .env.example
  .gitignore
  src/
    mt5_client.py      # real/mock MetaTrader 5 client abstraction
    margin_engine.py   # margin call / stop-out simulator (standalone, synthetic)
    dashboard.py        # Streamlit UI, two tabs
  tests/
    test_margin_engine.py
```

## Key concepts

- **Equity** = balance + unrealized profit/loss across all open positions
- **Used margin** = collateral locked to keep positions open (position size ÷ leverage)
- **Margin level** = equity ÷ used margin × 100%
- **Margin call** = a warning issued once margin level falls below a threshold (default 100%)
- **Stop-out / liquidation** = automatic forced closure once margin level falls below a lower
  threshold (default 50%), closing the most lossy position first and repeating until the
  level recovers or no positions remain

Both thresholds are configurable in the simulator sidebar, because real values vary by
broker and regulator - there's no universal number.

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

1. Install the `MetaTrader5` package on a Windows machine with the MT5 terminal installed and
   logged into a demo account (uncomment it in `requirements.txt`)
2. In `.env`, set `MT5_USE_MOCK=false` and fill in `MT5_LOGIN`, `MT5_PASSWORD`, `MT5_SERVER`
3. Run the dashboard as normal - the "Live Account Snapshot" tab will now show the real account

## What this demonstrates for the role

- Understanding of margin, equity, and leverage mechanics well enough to model them in code
- The actual sequence a risk desk follows when an account moves against a client
- Practical engineering judgment: designing around a platform dependency (MT4/MT5) that can't
  run everywhere, rather than assuming it can
