"""
Standalone margin call and stop-out simulator.

This module is intentionally independent of mt5_client.py: it works on a
synthetic account and a synthetic price path so that a margin call / forced
liquidation scenario can be triggered on demand and demonstrated reliably,
rather than waiting for a real account to drift into one.

Core concepts:
    equity        = balance + unrealized profit/loss across all open positions
    used_margin   = collateral locked to keep positions open (position size / leverage)
    margin_level  = equity / used_margin * 100  (percentage)
    free_margin   = equity - used_margin

Two configurable thresholds (real values vary by broker and regulator):
    margin_call_level  - below this, a warning is issued (e.g. 100%)
    stop_out_level     - below this, positions are force-closed (e.g. 50%)
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum
from typing import List

CONTRACT_SIZE = 100_000


class Side(Enum):
    BUY = 1
    SELL = -1


@dataclass
class Position:
    ticket: int
    symbol: str
    side: Side
    volume: float          # lots
    entry_price: float
    current_price: float

    def unrealized_pnl(self) -> float:
        direction = 1 if self.side == Side.BUY else -1
        return (self.current_price - self.entry_price) * direction * self.volume * CONTRACT_SIZE

    def required_margin(self, leverage: int) -> float:
        return (self.volume * CONTRACT_SIZE * self.entry_price) / leverage


@dataclass
class Account:
    account_id: str
    balance: float
    leverage: int = 100
    positions: List[Position] = field(default_factory=list)

    @property
    def equity(self) -> float:
        return self.balance + sum(p.unrealized_pnl() for p in self.positions)

    @property
    def used_margin(self) -> float:
        return sum(p.required_margin(self.leverage) for p in self.positions)

    @property
    def margin_level(self) -> float:
        used = self.used_margin
        return (self.equity / used * 100) if used > 0 else float("inf")

    @property
    def free_margin(self) -> float:
        return self.equity - self.used_margin


class PricePathGenerator:
    """
    Produces a sequence of prices for a symbol using a random walk with a
    configurable drift, so an adverse move against the client's position can
    be forced on demand (positive drift for a losing SELL, negative drift
    for a losing BUY - see run_scenario()).
    """

    def __init__(self, start_price: float, drift_per_tick: float = 0.0, volatility: float = 0.0004, seed: int = 7):
        self.price = start_price
        self.drift = drift_per_tick
        self.volatility = volatility
        self._rng = random.Random(seed)

    def next(self) -> float:
        shock = self._rng.gauss(0, self.volatility)
        self.price = round(self.price * (1 + self.drift + shock), 5)
        return self.price


class MarginMonitor:
    """
    Watches an Account across a sequence of price ticks and applies the
    margin call / stop-out rules engine described in the project README.
    """

    def __init__(self, account: Account, margin_call_level: float = 100.0, stop_out_level: float = 50.0):
        self.account = account
        self.margin_call_level = margin_call_level
        self.stop_out_level = stop_out_level
        self._margin_call_active = False
        self.event_log: List[dict] = []

    def apply_tick(self, tick_index: int, prices: dict) -> None:
        for position in self.account.positions:
            if position.symbol in prices:
                position.current_price = prices[position.symbol]

        margin_level = self.account.margin_level
        self.event_log.append({
            "tick": tick_index,
            "event": "price_update",
            "margin_level": round(margin_level, 2),
            "equity": round(self.account.equity, 2),
            "used_margin": round(self.account.used_margin, 2),
        })

        if margin_level <= self.stop_out_level and self.account.positions:
            self._trigger_stop_out(tick_index)
        elif margin_level <= self.margin_call_level:
            self._trigger_margin_call(tick_index, margin_level)
        else:
            self._margin_call_active = False

    def _trigger_margin_call(self, tick_index: int, margin_level: float) -> None:
        if not self._margin_call_active:
            self.event_log.append({
                "tick": tick_index,
                "event": "MARGIN_CALL",
                "margin_level": round(margin_level, 2),
                "message": f"Account {self.account.account_id}: margin level {margin_level:.1f}% "
                           f"is below the {self.margin_call_level:.0f}% margin call threshold.",
            })
            self._margin_call_active = True

    def _trigger_stop_out(self, tick_index: int) -> None:
        while self.account.positions and self.account.margin_level <= self.stop_out_level:
            loser = min(self.account.positions, key=lambda p: p.unrealized_pnl())
            realized = loser.unrealized_pnl()
            self.account.balance += realized
            self.account.positions.remove(loser)
            self.event_log.append({
                "tick": tick_index,
                "event": "STOP_OUT_CLOSE",
                "ticket": loser.ticket,
                "symbol": loser.symbol,
                "realized_pnl": round(realized, 2),
                "margin_level_after": round(self.account.margin_level, 2),
                "message": f"Forced closure: ticket {loser.ticket} ({loser.symbol}) closed at a loss of "
                           f"{realized:.2f} to bring margin level back above the stop-out threshold.",
            })


def run_scenario(account: Account, generators: dict, ticks: int = 200,
                  margin_call_level: float = 100.0, stop_out_level: float = 50.0):
    """
    Runs `ticks` price updates through a MarginMonitor and returns the
    monitor (with its full event_log) plus the final account state.
    """
    monitor = MarginMonitor(account, margin_call_level=margin_call_level, stop_out_level=stop_out_level)
    for i in range(1, ticks + 1):
        prices = {symbol: gen.next() for symbol, gen in generators.items()}
        monitor.apply_tick(i, prices)
        if not account.positions:
            break
    return monitor


if __name__ == "__main__":
    # Demo: one SELL position on EURUSD, with price drifting upward against it
    # until it triggers a margin call and then a stop-out.
    position = Position(ticket=1, symbol="EURUSD", side=Side.SELL, volume=5.0,
                         entry_price=1.0850, current_price=1.0850)
    account = Account(account_id="DEMO-001", balance=6000.0, leverage=100, positions=[position])
    generator = PricePathGenerator(start_price=1.0850, drift_per_tick=0.0015, volatility=0.0003)

    monitor = run_scenario(account, {"EURUSD": generator}, ticks=100)
    for event in monitor.event_log:
        if event["event"] != "price_update":
            print(event["event"], "-", event.get("message", event))
    print(f"\nFinal balance: {account.balance:.2f}  Open positions remaining: {len(account.positions)}")
