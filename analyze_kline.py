"""K 线走势分析：python analyze_kline.py --symbol AAPL  或  --csv data/SPY_daily.csv"""
import argparse
from pathlib import Path

import pandas as pd

from quant.analysis import add_indicators, analyze, format_report
from quant.data import load_prices
from quant.kline_plot import plot_kline


def main() -> None:
    parser = argparse.ArgumentParser(description="K 线走势分析")
    parser.add_argument("--symbol", default="SPY")
    parser.add_argument("--start", default="2023-01-01", help="数据起始日期（至少要比分析区间早约 130 个交易日）")
    parser.add_argument("--csv", default=None, help="本地 CSV（需含 date/open/high/low/close/volume 列）")
    parser.add_argument("--bars", type=int, default=120, help="图表显示最近多少根 K 线")
    args = parser.parse_args()

    if args.csv:
        df = pd.read_csv(args.csv, index_col=0, parse_dates=True)
        df.columns = [c.lower() for c in df.columns]
    else:
        df = load_prices(args.symbol, args.start)

    report = analyze(df)
    print(format_report(args.symbol, report))

    out = Path("output") / f"{args.symbol}_kline.png"
    plot_kline(add_indicators(df), report, args.symbol, out, args.bars)
    print(f"\n图表: {out}")


if __name__ == "__main__":
    main()
