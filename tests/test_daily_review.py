import json

import pandas as pd

from quant.daily_review import StrategyRules, load_trades, match_round_trips, review_day


def trade(t, symbol, side, size, price, pnl=0.0, order_id=None, order_type="LIMIT", sec="OPT"):
    return {"trade_time": t, "symbol": symbol, "side": side, "size": size, "price": price,
            "realized_pnl": pnl, "commission": 1.0, "order_type": order_type, "sec_type": sec,
            "order_id": order_id or f"{t}-{side}"}


def load(tmp_path, rows):
    p = tmp_path / "t.json"
    p.write_text(json.dumps({"trades": rows}))
    return load_trades(p)


def rules_hit(rv):
    return {v.rule for v in rv.violations}


# 2026-10-14 是周三；美东 10:00 = 14:00Z
def test_clean_day_passes(tmp_path):
    t = load(tmp_path, [
        trade("2026-10-14T14:00:00Z", "QQQ", "BUY", 1, 2.0),
        trade("2026-10-14T14:10:00Z", "QQQ", "SELL", 1, 2.5, pnl=49),
    ])
    rv = review_day(t, start_nav=10_000)
    assert rv.violations == []
    assert rv.entries == 1 and rv.clean_entries == 1
    assert len(rv.round_trips) == 1 and rv.round_trips[0].hold_minutes == 10


def test_entry_rule_violations(tmp_path):
    t = load(tmp_path, [
        trade("2026-10-14T13:35:00Z", "MU", "BUY", 1, 20.0),          # 09:35，标的、单价、时段、仓位都违规
        trade("2026-10-14T13:40:00Z", "MU", "SELL", 1, 19.0, pnl=-101),
    ])
    hit = rules_hit(review_day(t, start_nav=10_000))
    assert {"非策略标的", "期权单价不合规", "不在交易时段", "仓位过大"} <= hit


def test_exit_rules_stop_and_time(tmp_path):
    t = load(tmp_path, [
        trade("2026-10-14T14:00:00Z", "QQQ", "BUY", 1, 2.0),
        trade("2026-10-14T15:00:00Z", "QQQ", "SELL", 1, 1.4, pnl=-61),  # 持有 60 分钟，亏 30%
    ])
    hit = rules_hit(review_day(t, start_nav=10_000))
    assert {"超过时间止损", "没有按时止损"} <= hit


def test_expired_and_consecutive_losses(tmp_path):
    rows = []
    for i, minute in enumerate((0, 10, 20)):
        rows.append(trade(f"2026-10-14T14:{minute:02d}:00Z", "QQQ", "BUY", 1, 2.0, order_id=f"b{i}"))
        rows.append(trade(f"2026-10-14T14:{minute + 5:02d}:00Z", "QQQ", "SELL", 1, 1.8, pnl=-21, order_id=f"s{i}"))
    rows.append(trade("2026-10-14T20:20:00Z", "QQQ", "SELL", 1, 0.0, pnl=-200, order_type="OTHER"))
    rows.insert(0, trade("2026-10-14T13:50:00Z", "QQQ", "BUY", 1, 2.0, order_id="b-early"))
    t = load(tmp_path, rows)
    rv = review_day(t, start_nav=10_000)
    hit = rules_hit(rv)
    assert "连亏后继续交易" in hit
    assert "拿到到期" in hit


def test_daily_loss_and_overtrading(tmp_path):
    rows = [trade("2026-10-14T14:00:00Z", "QQQ", "BUY", 2, 2.0, order_id="b0"),
            trade("2026-10-14T14:05:00Z", "QQQ", "SELL", 2, 1.0, pnl=-400, order_id="s0")]
    for i in range(1, 6):
        rows.append(trade(f"2026-10-14T14:{10 + i:02d}:00Z", "SPY", "BUY", 1, 2.0, order_id=f"b{i}"))
    rv = review_day(load(tmp_path, rows), start_nav=10_000)
    hit = rules_hit(rv)
    assert "日亏超限后继续交易" in hit
    assert "超过每日笔数" in hit


def test_overnight_matched_from_history(tmp_path):
    t = load(tmp_path, [
        trade("2026-10-13T19:00:00Z", "QQQ", "BUY", 1, 2.0),
        trade("2026-10-14T14:00:00Z", "QQQ", "SELL", 1, 2.2, pnl=19),
    ])
    today = t[t["date"] == pd.Timestamp("2026-10-14").date()]
    hist = t[t["date"] < pd.Timestamp("2026-10-14").date()]
    rv = review_day(today, start_nav=10_000, history=hist)
    assert "隔夜持仓" in rules_hit(rv)


def test_fifo_partial_fills(tmp_path):
    t = load(tmp_path, [
        trade("2026-10-14T14:00:00Z", "QQQ", "BUY", 2, 2.0, order_id="a"),
        trade("2026-10-14T14:01:00Z", "QQQ", "BUY", 1, 3.0, order_id="b"),
        trade("2026-10-14T14:05:00Z", "QQQ", "SELL", 3, 2.5, pnl=50),
    ])
    rt = match_round_trips(t)[0]
    assert rt.contracts == 3 and rt.cost == 700


def test_custom_rules(tmp_path):
    t = load(tmp_path, [
        trade("2026-10-14T14:00:00Z", "NVDA", "BUY", 1, 2.0),
        trade("2026-10-14T14:10:00Z", "NVDA", "SELL", 1, 2.2, pnl=19),
    ])
    rv = review_day(t, start_nav=10_000, rules=StrategyRules(symbols=("QQQ", "NVDA")))
    assert "非策略标的" not in rules_hit(rv)
