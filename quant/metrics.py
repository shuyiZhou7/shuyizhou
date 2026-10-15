"""绩效指标。"""
import numpy as np
import pandas as pd

TRADING_DAYS = 252


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def summarize(returns: pd.Series, trades: pd.DataFrame | None = None) -> dict:
    equity = (1 + returns).cumprod()
    years = len(returns) / TRADING_DAYS
    total_return = equity.iloc[-1] - 1
    cagr = (1 + total_return) ** (1 / years) - 1 if years > 0 else np.nan
    vol = returns.std() * np.sqrt(TRADING_DAYS)
    sharpe = returns.mean() / returns.std() * np.sqrt(TRADING_DAYS) if returns.std() > 0 else np.nan

    stats = {
        "总收益": total_return,
        "年化收益": cagr,
        "年化波动": vol,
        "夏普比率": sharpe,
        "最大回撤": max_drawdown(equity),
    }
    if trades is not None:
        stats["交易次数"] = len(trades)
        stats["胜率"] = (trades["return"] > 0).mean() if len(trades) else np.nan
    return stats


def format_stats(stats: dict) -> str:
    lines = []
    for k, v in stats.items():
        if k == "夏普比率":
            lines.append(f"{k:<6}: {v:.2f}")
        elif k == "交易次数":
            lines.append(f"{k:<6}: {v}")
        else:
            lines.append(f"{k:<6}: {v:.2%}")
    return "\n".join(lines)
