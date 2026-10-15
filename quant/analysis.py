"""K 线走势综合分析：趋势判断、支撑阻力、指标状态、近期形态。"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import indicators as ind
from .patterns import PATTERNS, detect_all


@dataclass
class TrendReport:
    date: pd.Timestamp
    close: float
    trend: str                  # 上升趋势 / 下降趋势 / 震荡
    score: int                  # -6 ~ +6，越大越偏多
    adx: float
    signals: list[str] = field(default_factory=list)
    supports: list[float] = field(default_factory=list)
    resistances: list[float] = field(default_factory=list)
    patterns: list[str] = field(default_factory=list)
    rsi: float = np.nan
    atr: float = np.nan


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for n in (5, 20, 60, 120):
        out[f"ma{n}"] = ind.sma(out["close"], n)
    out = out.join(ind.macd(out["close"]))
    out = out.join(ind.bollinger(out["close"]).add_prefix("bb_"))
    out["rsi"] = ind.rsi(out["close"])
    out["atr"] = ind.atr(out)
    out["adx"] = ind.adx(out)
    return out


def swing_levels(df: pd.DataFrame, window: int = 5, lookback: int = 120) -> tuple[list[float], list[float]]:
    """用局部高低点（左右各 window 根 K 线内的极值）找出支撑位和阻力位。"""
    recent = df.tail(lookback)
    span = 2 * window + 1
    highs = recent["high"][recent["high"] == recent["high"].rolling(span, center=True).max()]
    lows = recent["low"][recent["low"] == recent["low"].rolling(span, center=True).min()]
    price = df["close"].iloc[-1]
    resistances = sorted(_merge_levels(highs[highs > price].tolist(), price))[:3]
    supports = sorted(_merge_levels(lows[lows < price].tolist(), price), reverse=True)[:3]
    return supports, resistances


def _merge_levels(levels: list[float], price: float, tol: float = 0.01) -> list[float]:
    """把相距不到 1% 的价位合并成一个。"""
    merged: list[float] = []
    for lv in sorted(levels):
        if merged and abs(lv - merged[-1]) / price < tol:
            merged[-1] = (merged[-1] + lv) / 2
        else:
            merged.append(lv)
    return merged


def analyze(df: pd.DataFrame, pattern_days: int = 5) -> TrendReport:
    if len(df) < 130:
        raise ValueError("数据太少，至少需要 130 根 K 线")
    d = add_indicators(df)
    last, prev = d.iloc[-1], d.iloc[-2]
    signals: list[str] = []
    score = 0

    # 1) 价格相对均线
    for n in (20, 60, 120):
        if last["close"] > last[f"ma{n}"]:
            score += 1
            signals.append(f"收盘价在 MA{n} 上方")
        else:
            score -= 1
            signals.append(f"收盘价在 MA{n} 下方")

    # 2) 均线排列
    if last["ma5"] > last["ma20"] > last["ma60"]:
        score += 1
        signals.append("均线多头排列（MA5 > MA20 > MA60）")
    elif last["ma5"] < last["ma20"] < last["ma60"]:
        score -= 1
        signals.append("均线空头排列（MA5 < MA20 < MA60）")

    # 3) MA20 斜率（近 10 日）
    slope = last["ma20"] / d["ma20"].iloc[-11] - 1
    if slope > 0.005:
        score += 1
        signals.append(f"MA20 向上（10 日 {slope:+.2%}）")
    elif slope < -0.005:
        score -= 1
        signals.append(f"MA20 向下（10 日 {slope:+.2%}）")

    # 4) MACD
    if last["dif"] > last["dea"]:
        score += 1
        signals.append("MACD 在信号线上方")
    else:
        score -= 1
        signals.append("MACD 在信号线下方")
    if prev["dif"] <= prev["dea"] and last["dif"] > last["dea"]:
        signals.append("MACD 刚刚金叉")
    elif prev["dif"] >= prev["dea"] and last["dif"] < last["dea"]:
        signals.append("MACD 刚刚死叉")

    # 趋势结论：ADX 判断强弱，得分判断方向
    if last["adx"] < 20 or abs(score) <= 1:
        trend = "震荡"
    elif score > 0:
        trend = "上升趋势"
    else:
        trend = "下降趋势"

    # RSI / 布林带提示
    if last["rsi"] >= 70:
        signals.append(f"RSI {last['rsi']:.0f}，超买区，注意回调")
    elif last["rsi"] <= 30:
        signals.append(f"RSI {last['rsi']:.0f}，超卖区，可能反弹")
    if last["close"] > last["bb_upper"]:
        signals.append("收盘价突破布林上轨")
    elif last["close"] < last["bb_lower"]:
        signals.append("收盘价跌破布林下轨")

    supports, resistances = swing_levels(d)

    pats = detect_all(d).tail(pattern_days)
    found = []
    for date, row in pats.iterrows():
        for name in row.index[row.values]:
            found.append(f"{date.date()} {name}（{PATTERNS[name][1]}）")

    return TrendReport(
        date=d.index[-1], close=float(last["close"]), trend=trend, score=score,
        adx=float(last["adx"]), signals=signals, supports=supports,
        resistances=resistances, patterns=found, rsi=float(last["rsi"]), atr=float(last["atr"]),
    )


def format_report(symbol: str, r: TrendReport) -> str:
    strength = "强" if r.adx >= 25 else ("弱" if r.adx < 20 else "中等")
    lines = [
        f"===== {symbol} K线走势分析  {r.date.date()} =====",
        f"收盘价: {r.close:.2f}    ATR(14): {r.atr:.2f}（日均波幅 {r.atr / r.close:.2%}）",
        f"趋势判断: {r.trend}    多空得分: {r.score:+d} / 6    趋势强度 ADX: {r.adx:.1f}（{strength}）",
        "",
        "【信号】",
        *[f"  · {s}" for s in r.signals],
        "",
        "【阻力位】 " + (", ".join(f"{x:.2f}（{x / r.close - 1:+.1%}）" for x in r.resistances) or "近期无明显阻力（处于新高附近）"),
        "【支撑位】 " + (", ".join(f"{x:.2f}（{x / r.close - 1:+.1%}）" for x in r.supports) or "近期无明显支撑（处于新低附近）"),
        "",
        "【近 5 日 K 线形态】",
        *([f"  · {p}" for p in r.patterns] or ["  · 无明显形态"]),
        "",
        "注：技术分析只反映历史价格行为，不构成投资建议。",
    ]
    return "\n".join(lines)
