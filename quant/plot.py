"""绘图：净值曲线、回撤与价格均线图。"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from .backtest import BacktestResult


def plot_result(prices: pd.DataFrame, result: BacktestResult, title: str, out_path: Path,
                fast: int | None = None, slow: int | None = None) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True,
                             gridspec_kw={"height_ratios": [3, 2, 1]})

    ax = axes[0]
    ax.plot(prices.index, prices["close"], label="Close", color="black", linewidth=1)
    if fast and slow:
        ax.plot(prices.index, prices["close"].rolling(fast).mean(), label=f"SMA {fast}")
        ax.plot(prices.index, prices["close"].rolling(slow).mean(), label=f"SMA {slow}")
    entries = result.positions.diff() > 0
    exits = result.positions.diff() < 0
    ax.scatter(prices.index[entries], prices["close"][entries], marker="^", color="green", label="Buy", zorder=3)
    ax.scatter(prices.index[exits], prices["close"][exits], marker="v", color="red", label="Sell", zorder=3)
    ax.set_title(title)
    ax.legend(loc="upper left")

    ax = axes[1]
    ax.plot(result.equity.index, result.equity, label="Strategy")
    ax.plot(result.benchmark.index, result.benchmark, label="Buy & Hold", alpha=0.7)
    ax.set_ylabel("Equity")
    ax.legend(loc="upper left")

    ax = axes[2]
    dd = result.equity / result.equity.cummax() - 1
    ax.fill_between(dd.index, dd, 0, color="red", alpha=0.4)
    ax.set_ylabel("Drawdown")

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
