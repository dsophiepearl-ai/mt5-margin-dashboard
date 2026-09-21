import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from margin_engine import Account, MarginMonitor, Position, Side


def make_account(entry_price=1.0850, volume=5.0, balance=6000.0, side=Side.SELL):
    position = Position(ticket=1, symbol="EURUSD", side=side, volume=volume,
                         entry_price=entry_price, current_price=entry_price)
    return Account(account_id="TEST-001", balance=balance, leverage=100, positions=[position])


def test_margin_level_at_entry_price_has_no_unrealized_pnl():
    account = make_account()
    assert account.equity == account.balance
    assert round(account.margin_level, 2) == round(account.equity / account.used_margin * 100, 2)


def test_sell_position_loses_money_when_price_rises():
    account = make_account(side=Side.SELL)
    account.positions[0].current_price = 1.0950  # price up 100 pips against a SELL
    assert account.equity < account.balance


def test_buy_position_loses_money_when_price_falls():
    account = make_account(side=Side.BUY)
    account.positions[0].current_price = 1.0750  # price down 100 pips against a BUY
    assert account.equity < account.balance


def test_margin_call_triggers_before_stop_out():
    account = make_account()
    monitor = MarginMonitor(account, margin_call_level=100.0, stop_out_level=50.0)

    # Manually push the price against the account until margin level crosses 100% but stays above 50%
    account.positions[0].current_price = 1.0900
    monitor.apply_tick(1, {"EURUSD": 1.0900})

    call_events = [e for e in monitor.event_log if e["event"] == "MARGIN_CALL"]
    stop_out_events = [e for e in monitor.event_log if e["event"] == "STOP_OUT_CLOSE"]

    if account.margin_level <= 100.0:
        assert len(call_events) == 1
    assert len(stop_out_events) == 0


def test_stop_out_force_closes_and_realizes_the_loss():
    account = make_account(volume=5.0, balance=6000.0)
    monitor = MarginMonitor(account, margin_call_level=100.0, stop_out_level=50.0)

    balance_before = account.balance
    # Push the price far enough to guarantee a stop-out
    account.positions[0].current_price = 1.1100
    monitor.apply_tick(1, {"EURUSD": 1.1100})

    assert len(account.positions) == 0
    assert account.balance != balance_before
    stop_out_events = [e for e in monitor.event_log if e["event"] == "STOP_OUT_CLOSE"]
    assert len(stop_out_events) == 1


def test_stop_out_closes_the_largest_loser_first_with_multiple_positions():
    small_loser = Position(ticket=1, symbol="EURUSD", side=Side.SELL, volume=1.0,
                            entry_price=1.0850, current_price=1.0900)
    big_loser = Position(ticket=2, symbol="EURUSD", side=Side.SELL, volume=5.0,
                          entry_price=1.0850, current_price=1.1100)
    account = Account(account_id="TEST-002", balance=6000.0, leverage=100,
                       positions=[small_loser, big_loser])
    monitor = MarginMonitor(account, margin_call_level=100.0, stop_out_level=50.0)

    monitor.apply_tick(1, {"EURUSD": 1.1100})

    close_events = [e for e in monitor.event_log if e["event"] == "STOP_OUT_CLOSE"]
    assert close_events, "expected at least one forced closure"
    assert close_events[0]["ticket"] == 2  # the bigger loser should be closed first
