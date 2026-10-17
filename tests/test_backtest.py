import numpy as np
import pandas as pd
import pytest

from quant.backtest import run_backtest
from quant.metrics import max_drawdown, summarize
from quant.strategy import SmaCross


def make_prices(close):
    idx = pd.bdate_range("2020-01-01", periods=len(close))
    return pd.DataFrame({"close": close}, index=idx)


def test_sma_cross_rejects_bad_params():
    with pytest.raises(ValueError):
        SmaCross(fast=50, slow=20)


def test_positions_flat_until_slow_window_ready():
    prices = make_prices(np.linspace(100, 200, 50))
    pos = SmaCross(3, 10).generate_positions(prices)
    assert (pos.iloc[:9] == 0).all()
    assert (pos.iloc[10:] == 1).all()  # 单边上涨，短均线始终在上方


def test_no_lookahead_signal_executes_next_day():
    # 前 10 天平稳，第 11 天大涨：策略不能吃到这根大阳线
    close = [100.0] * 10 + [150.0] + [150.0] * 5
    prices = make_prices(close)
    result = run_backtest(prices, SmaCross(2, 5), cost_bps=0)
    jump_day = prices.index[10]
    assert result.positions[jump_day] == 0
    assert result.returns[jump_day] == 0


def test_costs_reduce_returns():
    prices = make_prices(100 + 10 * np.sin(np.linspace(0, 20, 300)))
    free = run_backtest(prices, SmaCross(5, 20), cost_bps=0)
    paid = run_backtest(prices, SmaCross(5, 20), cost_bps=20)
    assert paid.equity.iloc[-1] < free.equity.iloc[-1]


def test_trades_are_extracted():
    prices = make_prices(100 + 10 * np.sin(np.linspace(0, 20, 300)))
    result = run_backtest(prices, SmaCross(5, 20))
    assert len(result.trades) > 0
    assert (result.trades["exit_date"] > result.trades["entry_date"]).all()


def test_metrics():
    equity = pd.Series([100, 120, 90, 110])
    assert max_drawdown(equity) == pytest.approx(-0.25)
    stats = summarize(pd.Series([0.0, 0.1, -0.1]))
    assert stats["总收益"] == pytest.approx(1.1 * 0.9 - 1)
