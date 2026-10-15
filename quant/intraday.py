"""日内策略回测（基于分钟级 K 线，所有持仓当天收盘前平掉）。

K 线内部的价格先后顺序未知：如果同一根 K 线同时触及入场价和止损价，一律按亏损处理（保守假设）。
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class Trade:
    date: object
    side: int          # 1 = 做多，-1 = 做空
    entry: float
    exit: float
    reason: str        # stop / target / close

    @property
    def ret(self) -> float:
        return self.side * (self.exit / self.entry - 1)


def split_days(df: pd.DataFrame, bars_per_day: int | None = None) -> list[pd.DataFrame]:
    """按交易日切分；指定 bars_per_day 时丢弃不完整的交易日（如数据首尾、提前收盘日）。"""
    days = [g for _, g in df.groupby(df.index.date)]
    if bars_per_day:
        days = [g for g in days if len(g) == bars_per_day]
    return days


def opening_range_breakout(day: pd.DataFrame, or_bars: int = 1, stop: str = "range") -> Trade | None:
    """
    开盘区间突破（ORB）：前 or_bars 根 K 线的最高/最低价构成开盘区间。
    之后价格先突破上沿就做多、先跌破下沿就做空（每天只做第一次突破），收盘平仓。
    stop="range"：止损放在区间另一侧；stop="mid"：止损放在区间中点。
    """
    rng = day.iloc[:or_bars]
    hi, lo = rng["high"].max(), rng["low"].min()
    mid = (hi + lo) / 2
    rest = day.iloc[or_bars:]
    for i, (_, bar) in enumerate(rest.iterrows()):
        up, down = bar["high"] > hi, bar["low"] < lo
        if not (up or down):
            continue
        if up and down:  # 同一根 K 线上下都破，无法判断先后，跳过当天
            return None
        side = 1 if up else -1
        entry = max(hi, bar["open"]) if side == 1 else min(lo, bar["open"])  # 跳空时按开盘价成交
        stop_px = (lo if side == 1 else hi) if stop == "range" else mid
        if (side == 1 and bar["low"] <= stop_px) or (side == -1 and bar["high"] >= stop_px):
            return Trade(day.index[0].date(), side, entry, stop_px, "stop")
        for _, b in rest.iloc[i + 1:].iterrows():
            if (side == 1 and b["low"] <= stop_px) or (side == -1 and b["high"] >= stop_px):
                exit_px = min(stop_px, b["open"]) if side == 1 else max(stop_px, b["open"])
                return Trade(day.index[0].date(), side, entry, exit_px, "stop")
        return Trade(day.index[0].date(), side, entry, day["close"].iloc[-1], "close")
    return None


def vwap(day: pd.DataFrame) -> pd.Series:
    typical = (day["high"] + day["low"] + day["close"]) / 3
    return (typical * day["volume"]).cumsum() / day["volume"].cumsum()


def vwap_reversion(day: pd.DataFrame, threshold: float = 0.003, stop: float = 0.003,
                   skip_bars: int = 1) -> list[Trade]:
    """
    VWAP 均值回归：K 线收盘价偏离 VWAP 超过 threshold 时，下一根 K 线开盘反向入场，
    目标是回到 VWAP，止损为入场价再朝不利方向走 stop，收盘前强制平仓。同一时间只持有一笔。
    """
    vw = vwap(day)
    trades: list[Trade] = []
    pos = None  # (side, entry, stop_px)
    rows = list(day.itertuples())
    for i in range(skip_bars, len(rows)):
        bar = rows[i]
        if pos is not None:
            side, entry, stop_px = pos
            target = vw.iloc[i - 1]
            hit_stop = bar.low <= stop_px if side == 1 else bar.high >= stop_px
            hit_tgt = bar.high >= target if side == 1 else bar.low <= target
            if hit_stop:  # 同时触及时按止损处理
                px = min(stop_px, bar.open) if side == 1 else max(stop_px, bar.open)
                trades.append(Trade(day.index[0].date(), side, entry, px, "stop"))
                pos = None
            elif hit_tgt:
                px = max(target, bar.open) if side == 1 else min(target, bar.open)
                trades.append(Trade(day.index[0].date(), side, entry, px, "target"))
                pos = None
            continue
        if i == len(rows) - 1:
            break
        dev = rows[i].close / vw.iloc[i] - 1
        if abs(dev) >= threshold:
            side = -1 if dev > 0 else 1
            entry = rows[i + 1].open
            pos = (side, entry, entry * (1 - side * stop))
            # 入场 K 线在下一轮循环里检查止损/目标
    if pos is not None:
        side, entry, _ = pos
        trades.append(Trade(day.index[0].date(), side, entry, day["close"].iloc[-1], "close"))
    return trades


def open_to_close(day: pd.DataFrame) -> Trade:
    """基准：开盘买入、收盘卖出。"""
    return Trade(day.index[0].date(), 1, day["open"].iloc[0], day["close"].iloc[-1], "close")


def summarize_trades(trades: list[Trade], cost_bps: float = 1.0, n_days: int | None = None) -> dict:
    """cost_bps：单边成本（基点），每笔交易扣两次。收益按 1 倍仓位、单利累加。"""
    if not trades:
        return {"交易次数": 0}
    r = pd.Series([t.ret for t in trades]) - 2 * cost_bps / 10_000
    equity = r.cumsum()
    wins, losses = r[r > 0], r[r <= 0]
    t_stat = r.mean() / r.std() * np.sqrt(len(r)) if len(r) > 1 and r.std() > 0 else np.nan
    return {
        "交易次数": len(r),
        "胜率": (r > 0).mean(),
        "平均每笔(bp)": r.mean() * 1e4,
        "累计收益": r.sum(),
        "盈亏比": wins.mean() / -losses.mean() if len(losses) and losses.mean() < 0 else np.nan,
        "利润因子": wins.sum() / -losses.sum() if losses.sum() < 0 else np.nan,
        "最大回撤": (equity - equity.cummax().clip(lower=0)).min(),
        "t值": t_stat,
    }
