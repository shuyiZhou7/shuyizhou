"""行情数据获取：通过 yfinance 下载日线数据，并缓存到本地 CSV。"""
from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent.parent / "data_cache"


def load_prices(symbol: str, start: str, end: str | None = None, use_cache: bool = True) -> pd.DataFrame:
    """返回包含 open/high/low/close/volume 列的日线数据（已复权），索引为日期。"""
    CACHE_DIR.mkdir(exist_ok=True)
    cache_file = CACHE_DIR / f"{symbol}_{start}_{end or 'latest'}.csv"
    if use_cache and cache_file.exists():
        return pd.read_csv(cache_file, index_col=0, parse_dates=True)

    import yfinance as yf

    df = yf.download(symbol, start=start, end=end, auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"没有下载到 {symbol} 的数据，请检查代码或网络")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df = df[["open", "high", "low", "close", "volume"]].dropna()
    df.index.name = "date"
    df.to_csv(cache_file)
    return df
