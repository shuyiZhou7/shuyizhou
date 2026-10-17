"""交易风控检查：读取 IBKR 账户数据（JSON），检查是否违反风控规则。

用法：
    python -m quant.risk_guard --summary summary.json --positions positions.json \
        --trades trades.json [--start-nav 5000]

输入文件就是 IBKR 接口 get_account_summary / get_account_positions /
get_account_trades(TODAY) 的原始 JSON。有违规时退出码为 1。
"""
import argparse
import json
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Rules:
    max_position_pct: float = 0.05      # 单个仓位成本不超过账户净值 5%
    max_symbol_pct: float = 0.10        # 同一标的（含期权）合计不超过 10%
    option_stop_pct: float = 0.50       # 期权浮亏达到成本 50% 必须止损
    max_orders_per_day: int = 5         # 每天最多 5 个订单
    daily_loss_pct: float = 0.03        # 当天亏损超过 3% 停止交易


@dataclass
class Violation:
    rule: str
    detail: str
    action: str


@dataclass
class Report:
    nav: float
    violations: list[Violation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations


def _num(d: dict, *keys, default=None):
    for k in keys:
        if k in d and d[k] is not None:
            try:
                return float(d[k])
            except (TypeError, ValueError):
                pass
    return default


def _str(d: dict, *keys, default=""):
    for k in keys:
        if d.get(k):
            return str(d[k])
    return default


def _underlying(p: dict) -> str:
    sym = _str(p, "underlying_symbol", "underlying", "symbol", "ticker", default="?")
    return sym.split()[0]


def _parse_date(s: str) -> date | None:
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:10] if "-" in s else s[:8], fmt).date()
        except ValueError:
            continue
    return None


def check(summary: dict, positions: list[dict], trades: list[dict],
          start_nav: float | None = None, rules: Rules = Rules(), today: date | None = None) -> Report:
    today = today or date.today()
    nav = _num(summary, "net_liquidation", "netliquidation", "nav", default=0.0)
    report = Report(nav=nav)
    if nav <= 0:
        report.notes.append("账户净值为 0，跳过仓位比例检查")

    by_symbol: dict[str, float] = {}
    for p in positions:
        qty = _num(p, "quantity", "position", "size", default=0.0)
        if not qty:
            continue
        name = _str(p, "description", "contract_desc", "name", "symbol", default="?")
        sec = _str(p, "sec_type", "asset_class", "security_type").upper()
        mv = abs(_num(p, "market_value", "mkt_value", "marketvalue", default=0.0))
        cost = abs(_num(p, "cost_basis", "cost", "avg_cost_total", default=mv))
        exposure = max(mv, cost)
        by_symbol[_underlying(p)] = by_symbol.get(_underlying(p), 0.0) + exposure

        if nav > 0 and exposure / nav > rules.max_position_pct:
            report.violations.append(Violation(
                "单笔仓位过大", f"{name}: ${exposure:,.0f}，占净值 {exposure / nav:.0%}",
                f"减仓到 ${nav * rules.max_position_pct:,.0f} 以下"))

        if sec in ("OPT", "FOP") and cost > 0:
            upnl = _num(p, "unrealized_pnl", "unrealizedpnl", "upnl", default=mv - cost)
            if upnl / cost <= -rules.option_stop_pct:
                report.violations.append(Violation(
                    "期权触发止损", f"{name}: 浮亏 {upnl / cost:.0%}（${upnl:,.0f}）",
                    "立即平仓，不要拿到到期"))
            expiry = _parse_date(_str(p, "expiry", "expiration", "last_trade_date", "maturity"))
            if expiry == today:
                report.violations.append(Violation(
                    "期权今天到期", f"{name} 今天到期", "收盘前平仓，避免归零或被行权"))

    if nav > 0:
        for sym, exp in by_symbol.items():
            if exp / nav > rules.max_symbol_pct:
                report.violations.append(Violation(
                    "单一标的集中", f"{sym} 相关仓位合计 ${exp:,.0f}，占净值 {exp / nav:.0%}",
                    "分散或减仓"))

    orders = {t.get("order_id") or t.get("trade_id") for t in trades
              if str(t.get("order_type", "")).upper() != "OTHER"}  # OTHER = 到期/行权，不算主动下单
    if len(orders) > rules.max_orders_per_day:
        report.violations.append(Violation(
            "交易过于频繁", f"今天已下 {len(orders)} 个订单（上限 {rules.max_orders_per_day}）",
            "今天停止开新仓"))

    if start_nav and start_nav > 0:
        change = nav / start_nav - 1
        if change <= -rules.daily_loss_pct:
            report.violations.append(Violation(
                "当日亏损超限", f"今天净值 {change:+.1%}（${nav - start_nav:,.0f}）",
                "今天停止交易，明天再说"))
    else:
        report.notes.append("未提供开盘净值，跳过当日亏损检查")

    return report


def format_report(r: Report) -> str:
    head = f"账户净值 ${r.nav:,.2f}"
    if r.ok:
        lines = [f"✅ 风控检查通过（{head}）"]
    else:
        lines = [f"⚠️ 风控警报：{len(r.violations)} 项违规（{head}）"]
        for v in r.violations:
            lines.append(f"· [{v.rule}] {v.detail} → {v.action}")
    lines += [f"（{n}）" for n in r.notes]
    return "\n".join(lines)


def _load(path: str, key: str):
    data = json.load(open(path))
    return data.get(key, data) if isinstance(data, dict) else data


def main() -> None:
    p = argparse.ArgumentParser(description="IBKR 账户风控检查")
    p.add_argument("--summary", required=True)
    p.add_argument("--positions", required=True)
    p.add_argument("--trades", required=True)
    p.add_argument("--start-nav", type=float, default=None, help="今天开盘时的净值")
    a = p.parse_args()
    summary = json.load(open(a.summary))
    report = check(summary, _load(a.positions, "positions"), _load(a.trades, "trades"), a.start_nav)
    print(format_report(report))
    raise SystemExit(0 if report.ok else 1)


if __name__ == "__main__":
    main()
