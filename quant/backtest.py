"""向量化回测引擎。"""
from dataclasses import dataclass

import pandas as pd

from .strategy import Strategy


@dataclass
class BacktestResult:
    equity: pd.Series        # 策略净值
    benchmark: pd.Series     # 买入持有净值
    positions: pd.Series     # 实际持仓（已延后一天执行）
    returns: pd.Series       # 策略日收益（已扣成本）
    trades: pd.DataFrame     # 每笔完整交易的进出场记录


def run_backtest(
    prices: pd.DataFrame,
    strategy: Strategy,
    initial_capital: float = 100_000,
    cost_bps: float = 5.0,
) -> BacktestResult:
    """
    cost_bps: 单边交易成本（手续费 + 滑点），单位为基点，5 表示 0.05%。

    信号用当天收盘价计算，第二天才执行（shift(1)），避免未来函数。
    """
    close = prices["close"]
    asset_returns = close.pct_change().fillna(0.0)

    target = strategy.generate_positions(prices)
    positions = target.shift(1).fillna(0.0)

    turnover = positions.diff().abs().fillna(positions.abs())
    costs = turnover * cost_bps / 10_000
    returns = positions * asset_returns - costs

    equity = initial_capital * (1 + returns).cumprod()
    benchmark = initial_capital * (1 + asset_returns).cumprod()

    return BacktestResult(
        equity=equity,
        benchmark=benchmark,
        positions=positions,
        returns=returns,
        trades=_extract_trades(close, positions),
    )


def _extract_trades(close: pd.Series, positions: pd.Series) -> pd.DataFrame:
    """把持仓序列拆成一笔笔交易。以执行当天的前一日收盘价近似成交价。"""
    entry_price = close.shift(1)
    records = []
    entry_date = None
    prev = 0.0
    for date, pos in positions.items():
        if prev == 0 and pos > 0:
            entry_date = date
        elif prev > 0 and pos == 0 and entry_date is not None:
            records.append((entry_date, date, entry_price[entry_date], entry_price[date]))
            entry_date = None
        prev = pos
    if entry_date is not None:  # 回测结束时仍持仓，按最后收盘价计算
        records.append((entry_date, close.index[-1], entry_price[entry_date], close.iloc[-1]))

    trades = pd.DataFrame(records, columns=["entry_date", "exit_date", "entry_price", "exit_price"])
    trades["return"] = trades["exit_price"] / trades["entry_price"] - 1
    return trades
