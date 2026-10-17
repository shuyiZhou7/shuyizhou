"""价格行为学（Al Brooks 风格）的量化实现。

- 波段高低点与市场结构（HH/HL/LH/LL）
- H1/H2（上升趋势回调）与 L1/L2（下降趋势反弹）入场信号
- 以 R（单笔风险）为单位的逐根 K 线回测

做空逻辑通过把价格取负数复用做多逻辑：-low 变成新的 high，下降趋势变成上升趋势。
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


# ---------- 市场结构 ----------

def find_swings(df: pd.DataFrame, n: int = 3) -> pd.DataFrame:
    """左右各 n 根 K 线内的最高/最低点为波段点。波段点要在 n 根 K 线后才能确认（confirm_idx）。"""
    hi, lo = df["high"].to_numpy(), df["low"].to_numpy()
    rows = []
    for i in range(n, len(df) - n):
        # 左侧严格大于/小于，右侧允许相等：相邻等高的 K 线只算一个波段点
        if hi[i] > hi[i - n:i].max() and hi[i] >= hi[i + 1:i + n + 1].max():
            rows.append((i, i + n, "high", hi[i]))
        if lo[i] < lo[i - n:i].min() and lo[i] <= lo[i + 1:i + n + 1].min():
            rows.append((i, i + n, "low", lo[i]))
    sw = pd.DataFrame(rows, columns=["idx", "confirm_idx", "kind", "price"])
    sw["label"] = ""
    for kind in ("high", "low"):
        m = sw["kind"] == kind
        price, prev = sw.loc[m, "price"], sw.loc[m, "price"].shift(1)
        if kind == "high":   # 等高视为双顶，记为 LH
            label = np.where(price > prev, "HH", "LH")
        else:                # 等低视为双底，记为 HL
            label = np.where(price >= prev, "HL", "LL")
        sw.loc[m, "label"] = np.where(prev.isna(), "", label)
    return sw


def structure_state(df: pd.DataFrame, swings: pd.DataFrame) -> pd.Series:
    """每根 K 线当时已确认的市场结构：1 = 上升（HH+HL），-1 = 下降（LH+LL），0 = 区间。不含未来信息。"""
    state = np.zeros(len(df), dtype=int)
    last = {"high": "", "low": ""}
    events = swings.sort_values("confirm_idx")
    j, ev = 0, events.to_dict("records")
    cur = 0
    for i in range(len(df)):
        while j < len(ev) and ev[j]["confirm_idx"] <= i:
            last[ev[j]["kind"]] = ev[j]["label"]
            j += 1
            if last["high"] == "HH" and last["low"] == "HL":
                cur = 1
            elif last["high"] == "LH" and last["low"] == "LL":
                cur = -1
            else:
                cur = 0
        state[i] = cur
    return pd.Series(state, index=df.index)


# ---------- H1/H2 信号与回测 ----------

@dataclass
class PATrade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    side: int
    entry: float
    stop: float
    exit: float
    reason: str
    r: float          # 扣除成本后的 R 倍数
    ret: float        # 扣除成本后的收益率（1 倍仓位）


SIGNAL_FILTERS = {
    "any": "不过滤",
    "bull": "阳线（收盘 > 开盘）",
    "strong": "阳线且收在 K 线上方 1/3",
    "strong_small": "阳线、收在上方 1/3，且振幅不超过近 20 根平均振幅的 1.5 倍",
}


def signal_bar_ok(df: pd.DataFrame, signal: str = "any") -> np.ndarray:
    """做多信号 K 线的质量（做空时价格已取负，同一套规则即为"阴线收在低位"）。"""
    if signal not in SIGNAL_FILTERS:
        raise ValueError(f"未知的 signal: {signal}")
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    rng = h - l
    ok = np.ones(len(df), dtype=bool)
    if signal in ("bull", "strong", "strong_small"):
        ok &= c > o
    if signal in ("strong", "strong_small"):
        ok &= (c - l) >= rng * 2 / 3
    if signal == "strong_small":
        avg = pd.Series(rng).rolling(20, min_periods=5).mean().to_numpy()
        ok &= ~(rng > 1.5 * avg)
    return ok


def _invert(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({"open": -df["open"], "high": -df["low"], "low": -df["high"],
                         "close": -df["close"]}, index=df.index)


def _run_long(df: pd.DataFrame, count: int, target_r: float, ema_n: int, swing_n: int,
              max_hold: int, cost_bps: float, session_end: np.ndarray | None,
              require_structure: bool, signal: str = "any") -> list[tuple]:
    o, h, l, c = (df[k].to_numpy() for k in ("open", "high", "low", "close"))
    ema = df["close"].ewm(span=ema_n, adjust=False).mean().to_numpy()
    sig_ok = signal_bar_ok(df, signal)
    struct = structure_state(df, find_swings(df, swing_n)).to_numpy() if require_structure else None
    n = len(df)
    trades = []
    trend_high = h[0]
    in_pb, cnt, pb_low = False, 0, np.inf
    i = 1
    while i < n:
        # ---- 是否在第 i 根 K 线触发入场（挂单在前一根 K 线高点上方）----
        ctx_ok = i - 1 >= ema_n and ema[i - 1] > ema[i - 1 - 5]
        if require_structure:
            ctx_ok = ctx_ok and struct[i - 1] == 1
        ctx_ok = ctx_ok and sig_ok[i - 1]
        can_enter = session_end is None or not session_end[i]
        triggered = False
        if in_pb and cnt == count - 1 and ctx_ok and can_enter and h[i] > h[i - 1]:
            entry = max(o[i], h[i - 1])
            stop = min(pb_low, l[i - 1])
            risk = entry - stop
            if risk > 0:
                triggered = True
                target = entry + target_r * risk
                j, reason, exit_px = i, None, None
                while True:
                    if l[j] <= stop:
                        exit_px, reason = (min(stop, o[j]) if j > i else stop), "stop"
                    elif h[j] >= target:
                        exit_px, reason = (max(target, o[j]) if j > i else target), "target"
                    elif (session_end is not None and session_end[j]) or j - i + 1 >= max_hold or j == n - 1:
                        exit_px, reason = c[j], "time"
                    if reason:
                        break
                    j += 1
                cost = 2 * cost_bps / 1e4 * abs(entry)
                trades.append((i, j, entry, stop, exit_px, reason,
                               (exit_px - entry - cost) / risk, (exit_px - entry - cost) / abs(entry)))
                in_pb, cnt, trend_high = False, 0, max(h[i:j + 1])
                i = j + 1
                continue
        # ---- 更新回调计数 ----
        if h[i] > trend_high:
            trend_high, in_pb, cnt = h[i], False, 0
        elif not in_pb and h[i] < h[i - 1]:
            in_pb, cnt, pb_low = True, 0, l[i]
        elif in_pb and h[i] > h[i - 1]:
            cnt += 1
        if in_pb:
            pb_low = min(pb_low, l[i])
        if session_end is not None and session_end[i]:
            in_pb, cnt, trend_high = False, 0, h[i]   # 日内模式：每天重新开始数
        if not triggered:
            i += 1
    return trades


def backtest_hl(df: pd.DataFrame, count: int = 2, sides=(1, -1), target_r: float = 2.0,
                ema_n: int = 20, swing_n: int = 3, max_hold: int = 20, cost_bps: float = 1.0,
                intraday: bool = False, require_structure: bool = True,
                signal: str = "any") -> list[PATrade]:
    """
    count=2 即 H2/L2，count=1 即 H1/L1。
    入场条件：EMA20 在上升（做空时下降）且市场结构为上升趋势（HH+HL），回调中第 count 次
    有 K 线向上突破前一根 K 线高点时入场。止损放在回调最低点，目标 target_r 倍风险。
    同一根 K 线同时触及止损和目标按止损处理。intraday=True 时每天收盘强制平仓。
    signal：信号 K 线（入场前一根）的质量要求，见 signal_bar_ok。
    """
    session_end = None
    if intraday:
        d = pd.Series(df.index.date, index=df.index)
        session_end = (d != d.shift(-1)).to_numpy()
    out = []
    for side in sides:
        data = df if side == 1 else _invert(df)
        for i, j, e, s, x, reason, r, ret in _run_long(data, count, target_r, ema_n, swing_n, max_hold,
                                                         cost_bps, session_end, require_structure, signal):
            out.append(PATrade(df.index[i], df.index[j], side, side * e, side * s, side * x, reason, r, ret))
    return sorted(out, key=lambda t: t.entry_time)


def summarize_r(trades: list[PATrade]) -> dict:
    if not trades:
        return {"交易次数": 0}
    r = pd.Series([t.r for t in trades])
    eq = r.cumsum()
    return {
        "交易次数": len(r),
        "胜率": (r > 0).mean(),
        "平均R": r.mean(),
        "累计R": r.sum(),
        "最大回撤R": (eq - eq.cummax().clip(lower=0)).min(),
        "t值": r.mean() / r.std() * np.sqrt(len(r)) if len(r) > 1 and r.std() > 0 else np.nan,
    }
