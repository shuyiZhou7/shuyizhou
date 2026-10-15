"""K 线图绘制：蜡烛图 + 均线 + 布林带 + 支撑阻力，下方是成交量、MACD、RSI。"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .analysis import TrendReport

UP, DOWN = "#e03131", "#2f9e44"  # 中国习惯：红涨绿跌


def plot_kline(d: pd.DataFrame, report: TrendReport, symbol: str, out_path: Path, bars: int = 120) -> None:
    d = d.tail(bars)
    x = np.arange(len(d))
    up = d["close"] >= d["open"]
    colors = np.where(up, UP, DOWN)

    fig, axes = plt.subplots(4, 1, figsize=(13, 11), sharex=True,
                             gridspec_kw={"height_ratios": [4, 1, 1.3, 1]})
    ax = axes[0]
    ax.vlines(x, d["low"], d["high"], color=colors, linewidth=0.8)
    body_lo = d[["open", "close"]].min(axis=1)
    body_h = np.maximum((d["close"] - d["open"]).abs(), d["close"] * 1e-4)  # 十字星也画一条细线
    ax.bar(x, body_h, bottom=body_lo, color=colors, width=0.7)

    for n, c in ((5, "#868e96"), (20, "#f08c00"), (60, "#1971c2"), (120, "#9c36b5")):
        ax.plot(x, d[f"ma{n}"], color=c, linewidth=1, label=f"MA{n}")
    ax.fill_between(x, d["bb_lower"], d["bb_upper"], color="#adb5bd", alpha=0.15, label="Bollinger")

    for lv in report.resistances:
        ax.axhline(lv, color=DOWN, linestyle="--", linewidth=0.8, alpha=0.7)
        ax.text(x[-1] + 1, lv, f"R {lv:.2f}", va="center", fontsize=8, color=DOWN)
    for lv in report.supports:
        ax.axhline(lv, color=UP, linestyle="--", linewidth=0.8, alpha=0.7)
        ax.text(x[-1] + 1, lv, f"S {lv:.2f}", va="center", fontsize=8, color=UP)

    trend_en = {"上升趋势": "Uptrend", "下降趋势": "Downtrend", "震荡": "Range"}[report.trend]
    ax.set_title(f"{symbol}  {d.index[-1].date()}  close {report.close:.2f}  |  "
                 f"{trend_en}  score {report.score:+d}  ADX {report.adx:.0f}")
    ax.legend(loc="upper left", fontsize=8, ncol=6)
    ax.set_xlim(-1, len(d) + 6)

    axes[1].bar(x, d["volume"], color=colors, width=0.7)
    axes[1].set_ylabel("Volume")

    axes[2].bar(x, d["hist"], color=np.where(d["hist"] >= 0, UP, DOWN), width=0.7)
    axes[2].plot(x, d["dif"], color="#1971c2", linewidth=1, label="DIF")
    axes[2].plot(x, d["dea"], color="#f08c00", linewidth=1, label="DEA")
    axes[2].set_ylabel("MACD")
    axes[2].legend(loc="upper left", fontsize=8)

    axes[3].plot(x, d["rsi"], color="#5f3dc4", linewidth=1)
    axes[3].axhline(70, color=DOWN, linestyle=":", linewidth=0.8)
    axes[3].axhline(30, color=UP, linestyle=":", linewidth=0.8)
    axes[3].set_ylim(0, 100)
    axes[3].set_ylabel("RSI")

    ticks = x[:: max(1, len(x) // 8)]
    axes[3].set_xticks(ticks)
    axes[3].set_xticklabels([d.index[i].strftime("%Y-%m-%d") for i in ticks], fontsize=8)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
