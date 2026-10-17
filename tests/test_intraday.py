import pandas as pd
import pytest

from quant.intraday import (open_to_close, opening_range_breakout, split_days,
                            summarize_trades, vwap_reversion)


def make_day(bars, date="2026-01-05"):
    """bars: [(open, high, low, close), ...]，每根 30 分钟。"""
    idx = pd.date_range(f"{date} 09:30", periods=len(bars), freq="30min")
    df = pd.DataFrame(bars, columns=["open", "high", "low", "close"], index=idx)
    df["volume"] = 1000
    return df


def test_orb_long_breakout_held_to_close():
    day = make_day([(100, 101, 99, 100.5), (100.5, 102, 100.2, 101.8), (101.8, 103, 101.5, 102.5)])
    t = opening_range_breakout(day)
    assert t.side == 1 and t.entry == 101 and t.exit == 102.5 and t.reason == "close"


def test_orb_short_stopped_out():
    day = make_day([(100, 101, 99, 100), (100, 100.2, 98.5, 98.8), (98.8, 101.5, 98.7, 101.2)])
    t = opening_range_breakout(day)
    assert t.side == -1 and t.entry == 99 and t.exit == 101 and t.reason == "stop"
    assert t.ret == pytest.approx(-(101 / 99 - 1))


def test_orb_no_breakout():
    day = make_day([(100, 101, 99, 100), (100, 100.8, 99.2, 100.1)])
    assert opening_range_breakout(day) is None


def test_vwap_reversion_long_hits_target():
    day = make_day([(100, 100.1, 99.9, 100), (100, 100, 99.0, 99.2),
                    (99.2, 99.4, 99.1, 99.3), (99.3, 100.5, 99.3, 100.2)])
    trades = vwap_reversion(day, threshold=0.003, stop=0.01)
    assert len(trades) == 1
    assert trades[0].side == 1 and trades[0].entry == 99.2 and trades[0].reason == "target"
    assert trades[0].ret > 0


def test_split_days_drops_partial():
    full = make_day([(1, 1, 1, 1)] * 13, "2026-01-05")
    partial = make_day([(1, 1, 1, 1)] * 5, "2026-01-06")
    assert len(split_days(pd.concat([full, partial]), 13)) == 1


def test_summary_costs():
    day = make_day([(100, 100, 100, 100), (100, 100, 100, 101)])
    s = summarize_trades([open_to_close(day)], cost_bps=5)
    assert s["累计收益"] == pytest.approx(0.01 - 0.001)
