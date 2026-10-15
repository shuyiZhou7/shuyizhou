"""命令行入口：python run_backtest.py --symbol SPY --fast 20 --slow 60"""
import argparse
from pathlib import Path

import pandas as pd

from quant.backtest import run_backtest
from quant.data import load_prices
from quant.metrics import format_stats, summarize
from quant.plot import plot_result
from quant.strategy import SmaCross


def main() -> None:
    parser = argparse.ArgumentParser(description="双均线策略回测")
    parser.add_argument("--symbol", default="SPY", help="美股代码，例如 SPY、AAPL、QQQ")
    parser.add_argument("--start", default="2015-01-01")
    parser.add_argument("--end", default=None)
    parser.add_argument("--fast", type=int, default=20, help="短期均线天数")
    parser.add_argument("--slow", type=int, default=60, help="长期均线天数")
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--cost-bps", type=float, default=5.0, help="单边交易成本（基点）")
    parser.add_argument("--csv", default=None, help="使用本地 CSV 而不是在线下载（需含 date/close 列）")
    args = parser.parse_args()

    if args.csv:
        prices = pd.read_csv(args.csv, index_col=0, parse_dates=True)
        prices.columns = [c.lower() for c in prices.columns]
    else:
        prices = load_prices(args.symbol, args.start, args.end)

    strategy = SmaCross(args.fast, args.slow)
    result = run_backtest(prices, strategy, args.capital, args.cost_bps)

    start, end = prices.index[0].date(), prices.index[-1].date()
    print(f"\n{args.symbol}  {strategy.name}  {start} ~ {end}\n")
    print("【策略】")
    print(format_stats(summarize(result.returns, result.trades)))
    print("\n【买入持有】")
    print(format_stats(summarize(prices["close"].pct_change().fillna(0.0))))

    out = Path("output") / f"{args.symbol}_sma_{args.fast}_{args.slow}.png"
    plot_result(prices, result, f"{args.symbol} {strategy.name}", out, args.fast, args.slow)
    result.trades.to_csv(out.with_suffix(".trades.csv"), index=False)
    print(f"\n图表: {out}\n交易记录: {out.with_suffix('.trades.csv')}")


if __name__ == "__main__":
    main()
