"""价格行为标注图：K 线 + EMA20 + 波段点（HH/HL/LH/LL）+ 结构背景色 + H2/L2 入场点。"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .price_action import PATrade, find_swings, structure_state

UP, DOWN = "#e03131", "#2f9e44"  # 红涨绿跌


def plot_price_action(df: pd.DataFrame, trades: list[PATrade], title: str, out_path: Path,
                      bars: int = 150, swing_n: int = 3) -> None:
    swings = find_swings(df, swing_n)
    state = structure_state(df, swings)
    start = max(0, len(df) - bars)
    d = df.iloc[start:]
    x = np.arange(len(d))
    colors = np.where(d["close"] >= d["open"], UP, DOWN)

    fig, ax = plt.subplots(figsize=(14, 7))
    st = state.iloc[start:].to_numpy()
    for i, s in enumerate(st):
        if s:
            ax.axvspan(i - 0.5, i + 0.5, color=UP if s == 1 else DOWN, alpha=0.06, linewidth=0)
    ax.vlines(x, d["low"], d["high"], color=colors, linewidth=0.8)
    body = np.maximum((d["close"] - d["open"]).abs(), d["close"] * 1e-4)
    ax.bar(x, body, bottom=d[["open", "close"]].min(axis=1), color=colors, width=0.7)
    ax.plot(x, df["close"].ewm(span=20, adjust=False).mean().iloc[start:], color="#1971c2", lw=1, label="EMA20")

    pad = (d["high"].max() - d["low"].min()) * 0.015
    for _, s in swings[swings["idx"] >= start].iterrows():
        xi = s["idx"] - start
        if s["kind"] == "high":
            ax.annotate(s["label"], (xi, s["price"] + pad), ha="center", fontsize=7, color="#495057")
        else:
            ax.annotate(s["label"], (xi, s["price"] - pad), ha="center", va="top", fontsize=7, color="#495057")

    pos = {t: i for i, t in enumerate(d.index)}
    for t in trades:
        if t.entry_time not in pos:
            continue
        xi = pos[t.entry_time]
        color = UP if t.r > 0 else DOWN
        ax.scatter(xi, t.entry, marker="^" if t.side == 1 else "v", s=70, color=color,
                   edgecolor="black", linewidth=0.5, zorder=4)
        xe = pos.get(t.exit_time, len(d) - 1)
        ax.plot([xi, xe], [t.stop, t.stop], color="black", lw=0.6, ls=":")

    ax.set_title(title + "   (shade: red = HH+HL uptrend, green = LH+LL downtrend; "
                 "marker: H2 ▲ / L2 ▼, red = win)", fontsize=10)
    ticks = x[:: max(1, len(x) // 10)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([d.index[i].strftime("%Y-%m-%d") for i in ticks], fontsize=8)
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=110)
    plt.close(fig)
