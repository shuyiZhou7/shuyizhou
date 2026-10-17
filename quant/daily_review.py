"""每日交易复盘：读取 IBKR 成交记录（get_account_trades 的 JSON），按「QQQ 短线期权快打」规则逐条检查。

用法：
    python -m quant.daily_review --trades trades.json --start-nav 5000            # 最近一个交易日
    python -m quant.daily_review --trades trades.json --date 2026-09-04
    python -m quant.daily_review --trades trades.json --all                       # 每天一行的汇总表
    python -m quant.daily_review --trades trades.json --out output/review.md      # 同时写入 Markdown

IBKR 成交记录里没有期权的行权价和到期日，买卖配对按「同一股票代码先进先出」估算，
同一天交易同一标的的多个合约时，持仓时间和收益率是近似值；每笔的已实现盈亏用的是 IBKR 给的准确数字。
"""
import argparse
import json
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path

import pandas as pd

TZ = "America/New_York"


@dataclass
class StrategyRules:
    symbols: tuple[str, ...] = ("QQQ", "SPY")
    min_premium: float = 1.0                    # 期权单价下限（每股）
    max_premium: float = 3.0                    # 期权单价上限（每股）
    windows: tuple[tuple[time, time], ...] = ((time(9, 45), time(11, 30)), (time(13, 0), time(15, 0)))
    max_position_pct: float = 0.05              # 每笔权利金占开盘净值上限
    max_hold_minutes: float = 20                # 时间止损
    hold_grace_minutes: float = 5               # 时间止损的宽限
    stop_loss_pct: float = 0.15                 # 止损线
    stop_grace_pct: float = 0.05                # 止损的滑点宽限：亏损超过 20% 才算违规
    max_entries_per_day: int = 5
    max_consecutive_losses: int = 2
    daily_loss_pct: float = 0.03
    no_friday_after: time = time(12, 0)


@dataclass
class RoundTrip:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    contracts: float
    entry_price: float
    exit_price: float
    cost: float
    pnl: float
    expired: bool

    @property
    def hold_minutes(self) -> float:
        return (self.exit_time - self.entry_time).total_seconds() / 60

    @property
    def ret(self) -> float:
        return self.pnl / self.cost if self.cost else 0.0


@dataclass
class Violation:
    rule: str
    when: pd.Timestamp
    detail: str


@dataclass
class DayReview:
    day: object
    start_nav: float | None
    entries: int
    round_trips: list[RoundTrip]
    realized: float
    commission: float
    violations: list[Violation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def wins(self) -> list[RoundTrip]:
        return [r for r in self.round_trips if r.pnl > 0]

    @property
    def losses(self) -> list[RoundTrip]:
        return [r for r in self.round_trips if r.pnl <= 0]

    @property
    def clean_entries(self) -> int:
        """没有触犯任何入场规则的开仓次数。"""
        bad = {v.when for v in self.violations if v.rule in ENTRY_RULES}
        return max(0, self.entries - len(bad))


ENTRY_RULES = {"非策略标的", "期权单价不合规", "不在交易时段", "仓位过大", "超过每日笔数",
               "连亏后继续交易", "日亏超限后继续交易", "周五下午交易"}


def load_trades(path: str | Path) -> pd.DataFrame:
    data = json.load(open(path))
    rows = data.get("trades", data) if isinstance(data, dict) else data
    t = pd.DataFrame(rows)
    if t.empty:
        return t
    t["time"] = pd.to_datetime(t["trade_time"], utc=True).dt.tz_convert(TZ)
    t["date"] = t["time"].dt.date
    for col in ("price", "size", "realized_pnl", "commission"):
        t[col] = pd.to_numeric(t.get(col, 0), errors="coerce").fillna(0.0)
    for col in ("order_type", "sec_type", "side", "symbol"):
        t[col] = t.get(col, "").fillna("").astype(str) if col in t else ""
    if "order_id" not in t:
        t["order_id"] = t.get("trade_id", t.index)
    return t.sort_values("time").reset_index(drop=True)


def match_round_trips(trades: pd.DataFrame) -> list[RoundTrip]:
    """期权买入后卖出（含到期）按股票代码先进先出配对。"""
    opts = trades[trades["sec_type"] == "OPT"]
    queues: dict[str, deque] = defaultdict(deque)
    trips = []
    for _, r in opts.iterrows():
        if r["side"] == "BUY":
            queues[r["symbol"]].append([r["time"], float(r["size"]), float(r["price"])])
            continue
        remaining, legs = float(r["size"]), []
        q = queues[r["symbol"]]
        while remaining > 0 and q:
            lot = q[0]
            used = min(remaining, lot[1])
            legs.append((lot[0], used, lot[2]))
            lot[1] -= used
            remaining -= used
            if lot[1] <= 0:
                q.popleft()
        if not legs:
            continue  # 卖出找不到对应买入（比如在数据范围之前买的），跳过
        contracts = sum(u for _, u, _ in legs)
        cost = sum(u * p * 100 for _, u, p in legs)
        trips.append(RoundTrip(
            symbol=r["symbol"], entry_time=legs[0][0], exit_time=r["time"], contracts=contracts,
            entry_price=cost / contracts / 100, exit_price=float(r["price"]), cost=cost,
            pnl=float(r["realized_pnl"]), expired=str(r.get("order_type", "")).upper() == "OTHER",
        ))
    return trips


def _in_windows(t: time, windows) -> bool:
    return any(a <= t <= b for a, b in windows)


def review_day(trades: pd.DataFrame, start_nav: float | None = None,
               rules: StrategyRules = StrategyRules(), history: pd.DataFrame | None = None) -> DayReview:
    """trades 为某一天的成交；history 为更早的成交（用于配对隔夜持仓），可省略。"""
    all_trades = pd.concat([history, trades]) if history is not None else trades
    day = trades["date"].iloc[0]
    trips = [rt for rt in match_round_trips(all_trades) if rt.exit_time.date() == day]
    active = trades[trades["order_type"].str.upper() != "OTHER"]
    buys = active[(active["sec_type"] == "OPT") & (active["side"] == "BUY")]
    stock_orders = active[active["sec_type"] == "STK"]
    entry_orders = buys.groupby("order_id", sort=False).agg(
        time=("time", "first"), symbol=("symbol", "first"), price=("price", "mean"), size=("size", "sum"))
    entry_orders["cost"] = entry_orders["price"] * entry_orders["size"] * 100
    entry_orders = entry_orders.sort_values("time")

    rv = DayReview(day=day, start_nav=start_nav, entries=len(entry_orders), round_trips=trips,
                   realized=float(trades["realized_pnl"].sum()), commission=float(trades["commission"].sum()))
    add = lambda rule, when, detail: rv.violations.append(Violation(rule, when, detail))

    if len(stock_orders):
        rv.notes.append(f"另有 {stock_orders['order_id'].nunique()} 个股票订单，不在本策略范围内")

    # ---- 入场规则 ----
    closes = sorted(trips, key=lambda r: r.exit_time)
    for n, (_, e) in enumerate(entry_orders.iterrows(), start=1):
        when, hhmm = e["time"], e["time"].strftime("%H:%M")
        if e["symbol"] not in rules.symbols:
            add("非策略标的", when, f"{hhmm} 买入 {e['symbol']} 期权（只做 {'/'.join(rules.symbols)}）")
        if not rules.min_premium <= e["price"] <= rules.max_premium:
            add("期权单价不合规", when, f"{hhmm} {e['symbol']} 单价 ${e['price']:.2f}（要求 ${rules.min_premium:g}–{rules.max_premium:g}）")
        if not _in_windows(when.time(), rules.windows):
            add("不在交易时段", when, f"{hhmm} 开仓 {e['symbol']}")
        if start_nav and e["cost"] > start_nav * rules.max_position_pct:
            add("仓位过大", when, f"{hhmm} {e['symbol']} 权利金 ${e['cost']:,.0f}，占净值 {e['cost'] / start_nav:.0%}"
                                  f"（上限 {rules.max_position_pct:.0%}）")
        if n > rules.max_entries_per_day:
            add("超过每日笔数", when, f"{hhmm} 第 {n} 笔开仓（上限 {rules.max_entries_per_day}）")
        if when.weekday() == 4 and when.time() >= rules.no_friday_after:
            add("周五下午交易", when, f"{hhmm} 开仓 {e['symbol']}")

        before = [r for r in closes if r.exit_time < when]
        streak = 0
        for r in reversed(before):
            if r.pnl > 0:
                break
            streak += 1
        if streak >= rules.max_consecutive_losses:
            add("连亏后继续交易", when, f"{hhmm} 已连亏 {streak} 笔仍开仓")
        if start_nav:
            pnl_so_far = sum(r.pnl for r in before)
            if pnl_so_far <= -rules.daily_loss_pct * start_nav:
                add("日亏超限后继续交易", when, f"{hhmm} 当日已亏 ${-pnl_so_far:,.0f}（{pnl_so_far / start_nav:.1%}）仍开仓")
        if before and before[-1].pnl < 0 and (when - before[-1].exit_time).total_seconds() < 300:
            rv.notes.append(f"{hhmm} 亏损后 {(when - before[-1].exit_time).total_seconds() / 60:.0f} 分钟就再次开仓")

    # ---- 出场规则 ----
    for r in trips:
        hhmm = r.exit_time.strftime("%H:%M")
        if r.expired:
            add("拿到到期", r.exit_time, f"{r.symbol} 期权到期作废，亏 ${-r.pnl:,.0f}")
        elif r.entry_time.date() != r.exit_time.date():
            add("隔夜持仓", r.exit_time, f"{r.symbol} {r.entry_time:%m-%d %H:%M} 买入，{r.exit_time:%m-%d %H:%M} 卖出")
        if not r.expired and r.hold_minutes > rules.max_hold_minutes + rules.hold_grace_minutes:
            add("超过时间止损", r.exit_time, f"{r.symbol} 持有 {r.hold_minutes:.0f} 分钟（上限 {rules.max_hold_minutes:g}）")
        if r.ret <= -(rules.stop_loss_pct + rules.stop_grace_pct):
            add("没有按时止损", r.exit_time, f"{hhmm} {r.symbol} 亏 {r.ret:.0%}（{money(r.pnl)}），止损线 -{rules.stop_loss_pct:.0%}")
    return rv


def review_all(trades: pd.DataFrame, navs: dict | None = None,
               rules: StrategyRules = StrategyRules()) -> list[DayReview]:
    out = []
    for day in sorted(trades["date"].unique()):
        history = trades[trades["date"] < day]
        nav = (navs or {}).get(str(day))
        out.append(review_day(trades[trades["date"] == day], nav, rules, history if len(history) else None))
    return out


def money(v: float, sign: bool = False) -> str:
    s = f"${abs(v):,.0f}"
    if v < 0:
        return "-" + s
    return ("+" + s) if sign else s


def format_day(rv: DayReview) -> str:
    wins, losses = rv.wins, rv.losses
    n = len(rv.round_trips)
    lines = [f"## {rv.day} 交易复盘", ""]
    lines.append(f"- 开仓 {rv.entries} 次，平仓 {n} 笔，已实现盈亏 **{money(rv.realized, True)}**，手续费 {money(rv.commission)}")
    if rv.start_nav:
        lines.append(f"- 开盘净值 ${rv.start_nav:,.0f}，当日已实现盈亏占 {rv.realized / rv.start_nav:+.1%}")
    if n:
        avg_w = sum(r.pnl for r in wins) / len(wins) if wins else 0
        avg_l = sum(r.pnl for r in losses) / len(losses) if losses else 0
        med_hold = sorted(r.hold_minutes for r in rv.round_trips if not r.expired) or [0]
        lines.append(f"- 胜率 {len(wins) / n:.0%}，平均盈利 {money(avg_w)}，平均亏损 {money(avg_l)}，"
                     f"持仓时间中位数 {med_hold[len(med_hold) // 2]:.0f} 分钟")
    lines.append(f"- 守规则的开仓：{rv.clean_entries} / {rv.entries}")
    lines.append("")
    if rv.violations:
        lines.append(f"### 违反规则 {len(rv.violations)} 次")
        counts = pd.Series([v.rule for v in rv.violations]).value_counts()
        lines.append("、".join(f"{k} ×{v}" for k, v in counts.items()))
        lines.append("")
        for v in sorted(rv.violations, key=lambda v: v.when)[:30]:
            lines.append(f"- [{v.rule}] {v.detail}")
        if len(rv.violations) > 30:
            lines.append(f"- ……另有 {len(rv.violations) - 30} 条")
    else:
        lines.append("### 全部规则都遵守了")
    if rv.notes:
        lines += ["", "### 备注"] + [f"- {x}" for x in rv.notes[:10]]
    return "\n".join(lines)


def format_summary(reviews: list[DayReview]) -> str:
    rows = []
    for rv in reviews:
        n = len(rv.round_trips)
        rows.append({
            "日期": str(rv.day), "开仓": rv.entries, "平仓": n,
            "胜率": f"{len(rv.wins) / n:.0%}" if n else "-",
            "已实现": money(rv.realized, True), "违规": len(rv.violations),
            "守规开仓": f"{rv.clean_entries}/{rv.entries}",
        })
    df = pd.DataFrame(rows)
    pd.set_option("display.unicode.east_asian_width", True)
    return df.to_string(index=False)


def main() -> None:
    p = argparse.ArgumentParser(description="每日交易复盘")
    p.add_argument("--trades", required=True, help="get_account_trades 的 JSON")
    p.add_argument("--start-nav", type=float, default=None, help="当天开盘净值（单日复盘时用）")
    p.add_argument("--navs", default=None, help='每天开盘净值的 JSON，如 {"2026-09-04": 16333}')
    p.add_argument("--date", default=None, help="复盘哪一天，默认最近一个交易日")
    p.add_argument("--all", action="store_true", help="输出每天一行的汇总表")
    p.add_argument("--out", default=None, help="同时写入 Markdown 文件")
    a = p.parse_args()

    trades = load_trades(a.trades)
    if trades.empty:
        print("没有成交记录，今天没有交易。")
        return
    navs = json.load(open(a.navs)) if a.navs else {}
    reviews = review_all(trades, navs)
    if a.all:
        text = format_summary(reviews)
    else:
        target = a.date or str(reviews[-1].day)
        rv = next((r for r in reviews if str(r.day) == target), None)
        if rv is None:
            raise SystemExit(f"{target} 没有成交记录")
        if a.start_nav:
            rv = review_day(trades[trades["date"] == rv.day], a.start_nav,
                            history=trades[trades["date"] < rv.day] if (trades["date"] < rv.day).any() else None)
        text = format_day(rv)
    print(text)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
