import numpy as np
import pandas as pd
import pytest

from quant.price_action import backtest_hl, find_swings, structure_state


def from_close(close, spread=0.3):
    close = np.asarray(close, dtype=float)
    idx = pd.bdate_range("2024-01-01", periods=len(close))
    open_ = np.r_[close[0], close[:-1]]
    return pd.DataFrame({"open": open_, "close": close,
                         "high": np.maximum(open_, close) + spread,
                         "low": np.minimum(open_, close) - spread}, index=idx)


def zigzag_up(cycles=12):
    # 每个周期：上涨 6 根，回调 4 根（两段式回调：跌、小反弹、再跌），整体抬高
    path, p = [], 100.0
    for _ in range(cycles):
        for _ in range(6):
            p += 1.0; path.append(p)
        for step in (-1.2, +0.5, -1.0, -0.6):
            p += step; path.append(p)
    return path


def test_swings_labels_uptrend():
    sw = find_swings(from_close(zigzag_up()), n=2)
    highs = sw[sw.kind == "high"].label.iloc[1:]
    lows = sw[sw.kind == "low"].label.iloc[1:]
    assert (highs == "HH").all() and (lows == "HL").all()


def test_structure_state_no_lookahead():
    df = from_close(zigzag_up())
    sw = find_swings(df, n=2)
    st = structure_state(df, sw)
    assert st.iloc[-1] == 1
    # 截断数据后，前面的状态不应改变（没有用到未来信息）
    cut = df.iloc[:60]
    st_cut = structure_state(cut, find_swings(cut, n=2))
    assert (st_cut.to_numpy()[:55] == st.to_numpy()[:55]).all()


def test_h2_trades_in_uptrend_and_win():
    df = from_close(zigzag_up(15))
    trades = backtest_hl(df, count=2, sides=(1,), target_r=1.0, swing_n=2, ema_n=10, cost_bps=0)
    assert len(trades) > 0
    assert all(t.side == 1 and t.stop < t.entry for t in trades)
    assert np.mean([t.r > 0 for t in trades]) > 0.5


def test_short_is_mirror_of_long():
    up = from_close(zigzag_up(15))
    down = pd.DataFrame({"open": 1000 - up["open"], "close": 1000 - up["close"],
                         "high": 1000 - up["low"], "low": 1000 - up["high"]}, index=up.index)
    longs = backtest_hl(up, count=2, sides=(1,), swing_n=2, ema_n=10, cost_bps=0)
    shorts = backtest_hl(down, count=2, sides=(-1,), swing_n=2, ema_n=10, cost_bps=0)
    assert [t.entry_time for t in longs] == [t.entry_time for t in shorts]
    assert [t.r for t in longs] == pytest.approx([t.r for t in shorts])
    assert all(t.stop > t.entry for t in shorts)


def test_signal_bar_filters():
    from quant.price_action import signal_bar_ok
    df = pd.DataFrame({"open":  [10, 10, 10, 10.0],
                       "close": [11, 9, 10.2, 10.9],
                       "high":  [11.1, 10.5, 11, 11],
                       "low":   [9.9, 8.9, 9.8, 9.9]})
    assert signal_bar_ok(df, "bull").tolist() == [True, False, True, True]
    assert signal_bar_ok(df, "strong").tolist() == [True, False, False, True]


def test_filtered_trades_have_good_signal_bars():
    from quant.price_action import signal_bar_ok
    df = from_close(zigzag_up(15))
    ok = pd.Series(signal_bar_ok(df, "strong"), index=df.index)
    trades = backtest_hl(df, count=2, sides=(1,), swing_n=2, ema_n=10, signal="strong")
    for t in trades:
        assert ok.iloc[df.index.get_loc(t.entry_time) - 1]
