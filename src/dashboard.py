"""
Streamlit dashboard with two views:

1. Live Account Snapshot - pulls account info, open positions, equity and
   margin level from mt5_client.get_client() (mock by default, real MT5 if
   configured - see README).

2. Margin Call & Stop-Out Simulator - runs the standalone margin_engine
   scenario with user-configurable drift/volatility, plots margin level
   over time, and lists every margin call / forced closure event.

Run with:  streamlit run src/dashboard.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd
import streamlit as st

from mt5_client import get_client
from margin_engine import Account, PricePathGenerator, Position, Side, run_scenario

st.set_page_config(page_title="FX Margin Dashboard", layout="wide")
st.title("FX Margin Dashboard")

tab_live, tab_sim = st.tabs(["Live Account Snapshot", "Margin Call & Stop-Out Simulator"])

with tab_live:
    st.caption("Backed by MockMT5Client unless MT5_USE_MOCK=false is set with real credentials in .env - see README.")

    client = get_client()
    client.initialize()
    info = client.account_info()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Balance", f"{info.balance:,.2f}")
    col2.metric("Equity", f"{info.equity:,.2f}")
    col3.metric("Used Margin", f"{info.margin:,.2f}")
    col4.metric("Margin Level", f"{info.margin_level:,.1f}%")

    positions = client.positions_get()
    if positions:
        df = pd.DataFrame([{
            "Ticket": p.ticket,
            "Symbol": p.symbol,
            "Side": "BUY" if p.type == 0 else "SELL",
            "Volume": p.volume,
            "Open Price": p.price_open,
            "Profit": round(p.profit, 2),
        } for p in positions])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No open positions.")

with tab_sim:
    st.caption("Synthetic scenario - lets you force an adverse price move and watch the margin call / "
               "stop-out rules engine react, on demand.")

    with st.sidebar:
        st.header("Simulator settings")
        side = st.selectbox("Position side", ["SELL", "BUY"])
        volume = st.slider("Volume (lots)", 0.5, 10.0, 5.0, 0.5)
        balance = st.slider("Starting balance", 1000, 20000, 6000, 500)
        drift_bps = st.slider("Adverse drift per tick (basis points)", 0, 30, 15)
        volatility_bps = st.slider("Volatility per tick (basis points)", 0, 20, 3)
        margin_call_level = st.slider("Margin call threshold (%)", 50, 200, 100)
        stop_out_level = st.slider("Stop-out threshold (%)", 10, 100, 50)
        ticks = st.slider("Number of price ticks", 20, 300, 100)
        run = st.button("Run scenario")

    if run:
        entry_price = 1.0850
        position = Position(ticket=1, symbol="EURUSD",
                             side=Side.SELL if side == "SELL" else Side.BUY,
                             volume=volume, entry_price=entry_price, current_price=entry_price)
        account = Account(account_id="SIM-001", balance=float(balance), leverage=100, positions=[position])

        # For a SELL, price rising is adverse -> positive drift. For a BUY, price falling is adverse -> negative drift.
        drift = (drift_bps / 10_000) if side == "SELL" else -(drift_bps / 10_000)
        generator = PricePathGenerator(start_price=entry_price, drift_per_tick=drift,
                                        volatility=volatility_bps / 10_000)

        monitor = run_scenario(account, {"EURUSD": generator}, ticks=ticks,
                                margin_call_level=margin_call_level, stop_out_level=stop_out_level)

        history = pd.DataFrame([e for e in monitor.event_log if e["event"] == "price_update"])
        if not history.empty:
            st.line_chart(history.set_index("tick")[["margin_level"]])

        events = [e for e in monitor.event_log if e["event"] != "price_update"]
        if events:
            st.subheader("Alert log")
            st.dataframe(pd.DataFrame(events), use_container_width=True)
        else:
            st.success("No margin call or stop-out triggered at these settings.")

        st.metric("Final balance", f"{account.balance:,.2f}")
        st.metric("Open positions remaining", len(account.positions))
    else:
        st.info("Set your scenario in the sidebar and click 'Run scenario'.")
