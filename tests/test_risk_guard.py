from datetime import date

from quant.risk_guard import Rules, check


def opt(desc, sym, cost, mv, upnl=None, expiry="20261016", qty=1):
    p = {"description": desc, "symbol": sym, "sec_type": "OPT", "quantity": qty,
         "cost_basis": cost, "market_value": mv, "expiry": expiry}
    if upnl is not None:
        p["unrealized_pnl"] = upnl
    return p


def rules_hit(report):
    return {v.rule for v in report.violations}


def test_clean_account_passes():
    r = check({"net_liquidation": 10_000}, [opt("QQQ C", "QQQ", 300, 280)], [], start_nav=10_000)
    assert r.ok


def test_oversized_position_and_concentration():
    r = check({"net_liquidation": 16_000}, [opt("SNDK C", "SNDK", 6_870, 6_500)], [], start_nav=16_000)
    assert {"单笔仓位过大", "单一标的集中"} <= rules_hit(r)


def test_option_stop_loss():
    r = check({"net_liquidation": 10_000}, [opt("MU C", "MU", 400, 150, upnl=-250)], [])
    assert "期权触发止损" in rules_hit(r)


def test_expiring_today():
    r = check({"net_liquidation": 10_000}, [opt("QQQ P", "QQQ", 200, 180, expiry="20261015")], [],
              today=date(2026, 10, 15))
    assert "期权今天到期" in rules_hit(r)


def test_overtrading_ignores_expirations():
    trades = [{"order_id": i, "order_type": "LIMIT"} for i in range(6)]
    assert "交易过于频繁" in rules_hit(check({"net_liquidation": 1}, [], trades))
    trades = [{"order_id": i, "order_type": "LIMIT"} for i in range(5)] + [{"order_id": 99, "order_type": "OTHER"}]
    assert "交易过于频繁" not in rules_hit(check({"net_liquidation": 1}, [], trades))


def test_daily_loss_limit():
    r = check({"net_liquidation": 9_600}, [], [], start_nav=10_000)
    assert "当日亏损超限" in rules_hit(r)


def test_custom_rules():
    r = check({"net_liquidation": 10_000}, [opt("QQQ C", "QQQ", 800, 800)], [], rules=Rules(max_position_pct=0.1))
    assert "单笔仓位过大" not in rules_hit(r)
