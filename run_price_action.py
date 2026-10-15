"""价格行为学 H1/H2 回测对比：python run_price_action.py"""
from pathlib import Path

import pandas as pd

from quant.pa_plot import plot_price_action
from quant.price_action import backtest_hl, summarize_r

DATASETS = [  # (名称, 文件, 是否日内, 最长持有 K 线数)
    ("SPY 日线 2021-2026", "data/SPY_daily.csv", False, 20),
    ("SPY 30分钟 3个月", "data/SPY_30m.csv", True, 13),
    ("QQQ 30分钟 3个月", "data/QQQ_30m.csv", True, 13),
]


def load(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, index_col=0, parse_dates=True)
    df.columns = [c.lower() for c in df.columns]
    return df


def main() -> None:
    rows = []
    for name, path, intraday, hold in DATASETS:
        df = load(path)
        for count in (1, 2):
            for target in (1.0, 2.0):
                for sides, side_name in (((1,), "只做多"), ((-1,), "只做空"), ((1, -1), "多空")):
                    trades = backtest_hl(df, count=count, sides=sides, target_r=target,
                                         max_hold=hold, intraday=intraday)
                    rows.append({"数据": name, "信号": f"{'H' if sides == (1,) else 'L' if sides == (-1,) else 'H/L'}{count}",
                                 "目标": f"{target:g}R", "方向": side_name, **summarize_r(trades)})

    t = pd.DataFrame(rows)
    fmt = {"胜率": "{:.0%}", "平均R": "{:+.2f}", "累计R": "{:+.1f}", "最大回撤R": "{:.1f}", "t值": "{:+.2f}"}
    for col, f in fmt.items():
        t[col] = t[col].map(lambda v: f.format(v) if pd.notna(v) else "-")
    pd.set_option("display.width", 200)
    pd.set_option("display.unicode.east_asian_width", True)
    for name, g in t.groupby("数据", sort=False):
        print(f"\n=== {name} ===")
        print(g.drop(columns="数据").to_string(index=False))
    print("\nR = 单笔风险（入场价到止损价）。按每笔风险账户 1% 计算，累计 +10R ≈ 账户 +10%。")
    print("|t值| < 2 说明结果在统计上不显著。已扣单边 1bp 成本。")

    df = load("data/SPY_daily.csv")
    out = Path("output/SPY_price_action.png")
    plot_price_action(df, backtest_hl(df, count=2), "SPY daily  H2/L2  2R", out, bars=250)
    print(f"\n标注图: {out}")


if __name__ == "__main__":
    main()
