"""日内策略对比：python run_intraday.py --symbols SPY QQQ"""
import argparse

import pandas as pd

from quant.intraday import (open_to_close, opening_range_breakout, split_days,
                            summarize_trades, vwap_reversion)


def load(symbol: str, interval: str) -> pd.DataFrame:
    df = pd.read_csv(f"data/{symbol}_{interval}.csv", index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    return df


def main() -> None:
    p = argparse.ArgumentParser(description="日内策略回测对比")
    p.add_argument("--symbols", nargs="+", default=["SPY", "QQQ"])
    p.add_argument("--interval", default="30m", help="对应 data/<代码>_<周期>.csv")
    p.add_argument("--bars-per-day", type=int, default=13, help="完整交易日的 K 线数量（30 分钟 = 13）")
    p.add_argument("--cost-bps", type=float, default=1.0, help="单边成本（基点）")
    args = p.parse_args()

    strategies = {
        "开盘买入收盘卖出(基准)": lambda d: [open_to_close(d)],
        "ORB 30分钟 止损区间另一侧": lambda d: [t for t in [opening_range_breakout(d, 1, "range")] if t],
        "ORB 30分钟 止损区间中点": lambda d: [t for t in [opening_range_breakout(d, 1, "mid")] if t],
        "ORB 60分钟 止损区间另一侧": lambda d: [t for t in [opening_range_breakout(d, 2, "range")] if t],
        "VWAP回归 偏离0.3% 止损0.3%": lambda d: vwap_reversion(d, 0.003, 0.003),
        "VWAP回归 偏离0.5% 止损0.5%": lambda d: vwap_reversion(d, 0.005, 0.005),
    }

    rows = []
    for sym in args.symbols:
        days = split_days(load(sym, args.interval), args.bars_per_day)
        for name, fn in strategies.items():
            trades = [t for d in days for t in fn(d)]
            s = summarize_trades(trades, args.cost_bps)
            rows.append({"标的": sym, "策略": name, **s})
        first, last = days[0].index[0].date(), days[-1].index[0].date()
        print(f"{sym}: {len(days)} 个完整交易日 ({first} ~ {last})")

    table = pd.DataFrame(rows).set_index(["策略", "标的"]).sort_index(level=0, sort_remaining=False)
    fmt = {"胜率": "{:.0%}", "平均每笔(bp)": "{:+.1f}", "累计收益": "{:+.2%}", "盈亏比": "{:.2f}",
           "利润因子": "{:.2f}", "最大回撤": "{:.2%}", "t值": "{:+.2f}"}
    for col, f in fmt.items():
        table[col] = table[col].map(lambda v: f.format(v) if pd.notna(v) else "-")
    pd.set_option("display.width", 200)
    pd.set_option("display.unicode.east_asian_width", True)
    print(f"\n单边成本 {args.cost_bps}bp，1 倍仓位，收益为单利累加\n")
    print(table.to_string())
    print("\n|t值| < 2 说明结果在统计上不显著，可能只是运气。")


if __name__ == "__main__":
    main()
