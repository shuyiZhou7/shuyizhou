import numpy as np
import pandas as pd
import pytest

from quant import indicators as ind
from quant.analysis import analyze, swing_levels
from quant.patterns import bearish_engulfing, bullish_engulfing, doji, hammer


def make_ohlc(close, spread=1.0):
    close = np.asarray(close, dtype=float)
    idx = pd.bdate_range("2020-01-01", periods=len(close))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({
        "open": open_, "close": close,
        "high": np.maximum(open_, close) + spread,
        "low": np.minimum(open_, close) - spread,
        "volume": 1_000_000,
    }, index=idx)


def test_rsi_bounds_and_extremes():
    up = ind.rsi(pd.Series(np.arange(1, 50, dtype=float)))
    assert up.iloc[-1] == pytest.approx(100)
    down = ind.rsi(pd.Series(np.arange(50, 1, -1, dtype=float)))
    assert down.iloc[-1] == pytest.approx(0)


def test_uptrend_detected():
    df = make_ohlc(100 * 1.003 ** np.arange(200))
    r = analyze(df)
    assert r.trend == "上升趋势"
    assert r.score >= 4


def test_downtrend_detected():
    df = make_ohlc(100 * 0.997 ** np.arange(200))
    r = analyze(df)
    assert r.trend == "下降趋势"
    assert r.score <= -4


def test_requires_enough_bars():
    with pytest.raises(ValueError):
        analyze(make_ohlc(np.ones(50) * 100))


def test_swing_levels_split_by_price():
    close = 100 + 10 * np.sin(np.linspace(0, 12, 200))
    df = make_ohlc(close)
    supports, resistances = swing_levels(df)
    price = df["close"].iloc[-1]
    assert all(s < price for s in supports)
    assert all(r > price for r in resistances)


def test_candlestick_patterns():
    df = pd.DataFrame({
        "open":  [10.0, 9.0, 10.0, 10.0],
        "close": [9.0, 10.5, 10.02, 10.1],
        "high":  [10.2, 10.6, 10.5, 10.15],
        "low":   [8.9, 8.8, 9.5, 9.0],
    })
    assert bullish_engulfing(df).iloc[1]
    assert not bearish_engulfing(df).iloc[1]
    assert doji(df).iloc[2]
    assert hammer(df).iloc[3]
