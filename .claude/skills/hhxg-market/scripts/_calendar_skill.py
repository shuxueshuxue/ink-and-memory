#!/usr/bin/env python3
"""A 股日历 — 交易日、解禁、业绩预告、期货交割日。

Usage:
    python3 calendar.py                    # 本周全部事件
    python3 calendar.py trading 2026-03-05 # 某天是否交易日
    python3 calendar.py unlock 2026-03     # 某月解禁
    python3 calendar.py earnings 2026-02   # 某月业绩预告
    python3 calendar.py delivery           # 全年交割日
    python3 calendar.py week               # 本周事件汇总
    python3 calendar.py --json             # JSON 原始输出

数据来源: https://hhxg.top
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch_json, print_cache_hint, run_main

YEAR = datetime.now().strftime("%Y")


def _this_week():
    today = datetime.now().date()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def _fetch_trading_days():
    data, cached = fetch_json(
        "calendar/trading_days_%s.json" % YEAR, "trading_days.json"
    )
    return data, cached


def _fetch_events(kind, month):
    """kind: delivery/earnings/unlock, month: 2026-03 或空。"""
    if kind == "delivery":
        path = "calendar/delivery_%s.json" % YEAR
    else:
        path = "calendar/%s_%s.json" % (kind, month.replace("-", ""))
    return fetch_json(path, "%s_%s.json" % (kind, month or YEAR))


# ── Formatters ──────────────────────────────────────────────


def fmt_trading(data, args):
    """查询某天是否为交易日。"""
    if not args:
        today = datetime.now().strftime("%Y-%m-%d")
        target = today
    else:
        target = args[0]
    days = data if isinstance(data, list) else data.get("days", data)
    is_trading = target in days
    if is_trading:
        return "%s 是交易日" % target
    # 找下一个交易日
    nxt = ""
    for d in sorted(days):
        if d > target:
            nxt = d
            break
    hint = "，下一个交易日是 %s" % nxt if nxt else ""
    return "%s 不是交易日（休市）%s" % (target, hint)


def fmt_events(events, title):
    if not events:
        return "暂无%s数据" % title
    lines = ["# %s" % title, ""]
    # 同日期多个事件合并为一行（如 ETF期权交割 + 富时A50交割同天）
    prev_date = ""
    for e in events:
        date = e.get("date", "")
        label = e.get("label", "")
        desc = e.get("description", "")
        if date == prev_date:
            lines.append("- ↳ %s — %s" % (label, desc))
        else:
            lines.append("- **%s** %s — %s" % (date, label, desc))
        prev_date = date
        # 解禁/业绩的 top_companies
        tops = e.get("top_companies", [])
        if tops:
            names = ", ".join(
                "%s(%s)" % (c.get("name", ""), c.get("value", "")) for c in tops[:5]
            )
            lines.append("  %s" % names)
    return "\n".join(lines)


def fmt_week(trading_days, all_events):
    """本周事件汇总。"""
    mon, sun = _this_week()
    today = datetime.now().strftime("%Y-%m-%d")

    # 本周交易日
    week_td = [d for d in trading_days if mon <= d <= sun]
    is_today_trading = today in trading_days
    lines = [
        "# 本周 A 股日历（%s ~ %s）" % (mon, sun),
        "",
        "今天 %s %s交易日" % (today, "是" if is_today_trading else "不是"),
        "本周交易日: %s" % ", ".join(week_td) if week_td else "本周无交易日",
        "",
    ]

    # 本周事件
    week_events = [e for e in all_events if mon <= e.get("date", "") <= sun]
    if week_events:
        lines.append("## 本周重要事件")
        for e in sorted(week_events, key=lambda x: x.get("date", "")):
            lines.append(
                "- **%s** [%s] %s" % (e.get("date", ""), e.get("type", ""), e.get("label", ""))
            )
            desc = e.get("description", "")
            if desc:
                lines.append("  %s" % desc)
    else:
        lines.append("本周无重大日历事件")

    lines.append("")
    lines.append("---")
    lines.append("📅 完整年度日历 / 解禁预告 / 业绩预期 → https://hhxg.top")

    return "\n".join(lines)


# ── Sections ────────────────────────────────────────────────

SECTIONS = {
    "week": "week",
    "trading": "trading",
    "unlock": "unlock",
    "earnings": "earnings",
    "delivery": "delivery",
}


def main():
    section, extra_args, use_json = run_main(SECTIONS, default="week")

    if section == "trading":
        data, cached = _fetch_trading_days()
        print_cache_hint(cached, YEAR)
        if use_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(fmt_trading(data, extra_args))

    elif section in ("unlock", "earnings"):
        month = extra_args[0] if extra_args else datetime.now().strftime("%Y-%m")
        data, cached = _fetch_events(section, month)
        print_cache_hint(cached, month)
        if use_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            events = data.get("events", []) if isinstance(data, dict) else data
            title = "限售解禁 — %s" % month if section == "unlock" else "业绩预告 — %s" % month
            print(fmt_events(events, title))

    elif section == "delivery":
        data, cached = _fetch_events("delivery", "")
        print_cache_hint(cached, YEAR)
        if use_json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            events = data.get("events", []) if isinstance(data, dict) else data
            print(fmt_events(events, "期货/期权交割日 — %s" % YEAR))

    elif section == "week":
        td_data, cached1 = _fetch_trading_days()
        trading_days = td_data if isinstance(td_data, list) else []
        # 收集本周涉及月份的事件（处理跨月边界）
        mon, sun = _this_week()
        months = {mon[:7], sun[:7]}  # 可能跨两个月
        all_events = []
        for month in sorted(months):
            for kind in ("unlock", "earnings"):
                try:
                    edata, _ = _fetch_events(kind, month)
                    evts = edata.get("events", []) if isinstance(edata, dict) else []
                    all_events.extend(evts)
                except RuntimeError:
                    pass
        # delivery 按年拉取，只拉一次避免重复
        try:
            edata, _ = _fetch_events("delivery", "")
            evts = edata.get("events", []) if isinstance(edata, dict) else []
            all_events.extend(evts)
        except RuntimeError:
            pass
        print_cache_hint(cached1, mon[:7])
        if use_json:
            print(json.dumps({"trading_days": trading_days, "events": all_events}, ensure_ascii=False, indent=2))
        else:
            print(fmt_week(trading_days, all_events))


if __name__ == "__main__":
    main()
