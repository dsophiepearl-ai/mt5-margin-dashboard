"""
MetaTrader 5 client wrapper.

The official `MetaTrader5` Python package only works on Windows, alongside a
running MT5 terminal logged into a real or demo account. To keep this project
runnable anywhere (including this build environment, CI, or a reviewer's
laptop that doesn't have MT5 installed), this module tries to use the real
package when it's available and properly configured, and otherwise falls
back automatically to a MockMT5Client that produces realistic account and
position data.

This is a deliberate interface-abstraction pattern: the rest of the app
(margin_engine.py, dashboard.py) only ever talks to "a client that exposes
account_info() / positions_get() / symbol_info_tick()", and never needs to
know or care whether that client is real or simulated.
"""

from __future__ import annotations

import os
import random
import time
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AccountInfo:
    login: int
    balance: float
    equity: float
    margin: float
    margin_free: float
    margin_level: float
    leverage: int
    currency: str = "USD"


@dataclass
class Position:
    ticket: int
    symbol: str
    volume: float          # in lots
    price_open: float
    type: int              # 0 = buy, 1 = sell
    profit: float = 0.0


@dataclass
class Tick:
    symbol: str
    bid: float
    ask: float


CONTRACT_SIZE = 100_000  # standard lot

# Simplification note: required-margin math below treats price as if it's already
# quoted in the account's deposit currency (true for pairs like EURUSD/GBPUSD when
# the account is in USD). A production system would also convert margin currency
# for cross/JPY-quoted pairs (e.g. USDJPY) - deliberately out of scope here so the
# demo positions stay in easily sanity-checked USD terms.


class MockMT5Client:
    """
    Simulated MetaTrader 5 client.

    Used automatically whenever the real MetaTrader5 terminal/package isn't
    available or isn't configured. Generates a small, reproducible book of
    open positions and a live-ish price feed so the rest of the app can be
    built, tested, and demoed without a live broker connection.
    """

    SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD"]

    def __init__(self, seed: int = 42, starting_balance: float = 10_000.0, leverage: int = 100):
        self._rng = random.Random(seed)
        self._login = 900000 + self._rng.randint(1, 999)
        self._balance = starting_balance
        self._leverage = leverage
        self._prices = {
            "EURUSD": 1.0850,
            "GBPUSD": 1.2650,
            "USDJPY": 149.50,
            "AUDUSD": 0.6550,
        }
        self._positions: List[Position] = self._generate_positions()

    def _generate_positions(self) -> List[Position]:
        # Only USD-quoted pairs by default, to keep the margin math above valid
        # without needing a currency-conversion step (see CONTRACT_SIZE note).
        positions = []
        for i, symbol in enumerate(["EURUSD", "GBPUSD"]):
            side = self._rng.choice([0, 1])
            volume = round(self._rng.uniform(0.1, 1.0), 2)
            positions.append(
                Position(
                    ticket=1000 + i,
                    symbol=symbol,
                    volume=volume,
                    price_open=self._prices[symbol],
                    type=side,
                )
            )
        return positions

    # -- connection lifecycle (mirrors the real MetaTrader5 module's API shape) --
    def initialize(self, *args, **kwargs) -> bool:
        return True

    def login(self, *args, **kwargs) -> bool:
        return True

    def shutdown(self) -> None:
        return None

    # -- data access --
    def account_info(self) -> AccountInfo:
        equity = self._balance + sum(self._position_profit(p) for p in self._positions)
        used_margin = sum(
            (p.volume * CONTRACT_SIZE * p.price_open) / self._leverage for p in self._positions
        )
        margin_level = (equity / used_margin * 100) if used_margin > 0 else float("inf")
        return AccountInfo(
            login=self._login,
            balance=self._balance,
            equity=equity,
            margin=used_margin,
            margin_free=equity - used_margin,
            margin_level=margin_level,
            leverage=self._leverage,
        )

    def positions_get(self) -> List[Position]:
        for p in self._positions:
            p.profit = self._position_profit(p)
        return self._positions

    def symbol_info_tick(self, symbol: str) -> Optional[Tick]:
        price = self._nudge_price(symbol)
        spread = price * 0.00005
        return Tick(symbol=symbol, bid=round(price - spread, 5), ask=round(price + spread, 5))

    # -- internal helpers --
    def _nudge_price(self, symbol: str) -> float:
        drift = self._rng.uniform(-0.0006, 0.0006)
        self._prices[symbol] = round(self._prices[symbol] * (1 + drift), 5)
        return self._prices[symbol]

    def _position_profit(self, position: Position) -> float:
        current = self._prices[position.symbol]
        direction = 1 if position.type == 0 else -1
        return (current - position.price_open) * direction * position.volume * CONTRACT_SIZE


def get_client():
    """
    Return a live MetaTrader5 module if MT5_USE_MOCK=false and the real
    package/terminal/credentials are all available, otherwise fall back to
    MockMT5Client. Defaults to the mock client so the project runs out of
    the box with no configuration.
    """
    use_mock = os.getenv("MT5_USE_MOCK", "true").lower() != "false"

    if not use_mock:
        try:
            import MetaTrader5 as mt5  # type: ignore

            login = int(os.environ["MT5_LOGIN"])
            password = os.environ["MT5_PASSWORD"]
            server = os.environ["MT5_SERVER"]

            if mt5.initialize() and mt5.login(login, password=password, server=server):
                return mt5
            print("MT5 login failed - falling back to the mock client.")
        except Exception as exc:  # pragma: no cover - depends on local environment
            print(f"MetaTrader5 package/terminal unavailable ({exc}) - falling back to the mock client.")

    return MockMT5Client()


if __name__ == "__main__":
    client = get_client()
    client.initialize()
    info = client.account_info()
    print(f"Login: {info.login}  Balance: {info.balance:.2f}  Equity: {info.equity:.2f}  "
          f"Margin level: {info.margin_level:.1f}%")
    for pos in client.positions_get():
        print(f"  {pos.symbol}  {'BUY' if pos.type == 0 else 'SELL'}  "
              f"{pos.volume} lots @ {pos.price_open}  P/L: {pos.profit:.2f}")
