"""常用技术指标。输入均为 pandas Series / DataFrame（列名小写 open/high/low/close/volume）。"""
import numpy as np
import pandas as pd


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    dif = ema(close, fast) - ema(close, slow)
    dea = ema(dif, signal)
    return pd.DataFrame({"dif": dif, "dea": dea, "hist": dif - dea})


def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> pd.DataFrame:
    mid = sma(close, n)
    std = close.rolling(n).std()
    return pd.DataFrame({"mid": mid, "upper": mid + k * std, "lower": mid - k * std})


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def adx(df: pd.DataFrame, n: int = 14) -> pd.Series:
    """平均趋向指数：>25 通常表示趋势明显，<20 表示震荡。"""
    up = df["high"].diff()
    down = -df["low"].diff()
    plus_dm = pd.Series(np.where((up > down) & (up > 0), up, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down > up) & (down > 0), down, 0.0), index=df.index)
    tr_n = atr(df, n)
    plus_di = 100 * plus_dm.ewm(alpha=1 / n, adjust=False).mean() / tr_n
    minus_di = 100 * minus_dm.ewm(alpha=1 / n, adjust=False).mean() / tr_n
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()
