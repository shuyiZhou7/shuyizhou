"""常见 K 线形态识别（单根 / 两根组合）。返回与输入同索引的布尔 Series。"""
import pandas as pd


def _parts(df: pd.DataFrame):
    body = (df["close"] - df["open"]).abs()
    rng = (df["high"] - df["low"]).replace(0, 1e-12)
    upper = df["high"] - df[["open", "close"]].max(axis=1)
    lower = df[["open", "close"]].min(axis=1) - df["low"]
    return body, rng, upper, lower


def doji(df: pd.DataFrame) -> pd.Series:
    """十字星：实体很小，多空僵持。"""
    body, rng, _, _ = _parts(df)
    return body <= 0.1 * rng


def hammer(df: pd.DataFrame) -> pd.Series:
    """锤子线：下影线长、上影线短，出现在下跌后可能见底。"""
    body, rng, upper, lower = _parts(df)
    return (lower >= 2 * body) & (upper <= 0.3 * body + 0.05 * rng) & (body > 0.05 * rng)


def shooting_star(df: pd.DataFrame) -> pd.Series:
    """射击之星：上影线长、下影线短，出现在上涨后可能见顶。"""
    body, rng, upper, lower = _parts(df)
    return (upper >= 2 * body) & (lower <= 0.3 * body + 0.05 * rng) & (body > 0.05 * rng)


def bullish_engulfing(df: pd.DataFrame) -> pd.Series:
    """看涨吞没：阳线实体完全包住前一根阴线实体。"""
    o, c = df["open"], df["close"]
    po, pc = o.shift(1), c.shift(1)
    return (pc < po) & (c > o) & (o <= pc) & (c >= po)


def bearish_engulfing(df: pd.DataFrame) -> pd.Series:
    """看跌吞没：阴线实体完全包住前一根阳线实体。"""
    o, c = df["open"], df["close"]
    po, pc = o.shift(1), c.shift(1)
    return (pc > po) & (c < o) & (o >= pc) & (c <= po)


PATTERNS = {
    "十字星": (doji, "中性"),
    "锤子线": (hammer, "看涨"),
    "射击之星": (shooting_star, "看跌"),
    "看涨吞没": (bullish_engulfing, "看涨"),
    "看跌吞没": (bearish_engulfing, "看跌"),
}


def detect_all(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({name: fn(df) for name, (fn, _) in PATTERNS.items()})
