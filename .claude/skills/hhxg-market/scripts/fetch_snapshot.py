#!/usr/bin/env python3
"""A 股日报快照获取脚本 — 零依赖，仅需 Python 3 标准库。

Usage:
    python3 fetch_snapshot.py              # 完整快照
    python3 fetch_snapshot.py summary      # AI 一句话总结
    python3 fetch_snapshot.py market       # 市场赚钱效应
    python3 fetch_snapshot.py themes       # 热门题材
    python3 fetch_snapshot.py ladder       # 连板天梯
    python3 fetch_snapshot.py hotmoney     # 游资龙虎榜
    python3 fetch_snapshot.py sectors      # 行业资金
    python3 fetch_snapshot.py news         # 焦点新闻
    python3 fetch_snapshot.py themes --json # JSON 原始输出

数据来源: https://hhxg.top
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch_json, check_schema, print_cache_hint


def fetch():
    """获取日报快照数据。"""
    return fetch_json("assistant/skill_snapshot.json", "last.json")


# ── Formatters ──────────────────────────────────────────────


def fmt_market(data):
    m = data.get("market")
    if not m:
        return "暂无市场数据"

    comp = data.get("comparison", {})
    yd = comp.get("yesterday", {})

    # 赚钱效应指数 + 昨日对比
    today_si = m.get("sentiment_index", "?")
    yd_si = yd.get("sentiment_index")
    si_diff = ""
    if yd_si is not None and isinstance(today_si, (int, float)):
        diff = round(today_si - yd_si, 1)
        sign = "+" if diff > 0 else ""
        si_diff = "，昨 %s%%，%s%s%%" % (yd_si, sign, diff)

    # 涨停 + 昨日对比
    today_lu = m.get("limit_up", "?")
    yd_lu = yd.get("limit_up")
    lu_diff = ""
    if yd_lu is not None and isinstance(today_lu, int):
        diff = today_lu - yd_lu
        sign = "+" if diff > 0 else ""
        lu_diff = "（昨%s，%s%s）" % (yd_lu, sign, diff)

    # 炸板 + 昨日对比
    today_fr = m.get("fried", "?")
    yd_fr = yd.get("fried")
    fr_diff = ""
    if yd_fr is not None and isinstance(today_fr, int):
        diff = today_fr - yd_fr
        sign = "+" if diff > 0 else ""
        fr_diff = "（昨%s，%s%s）" % (yd_fr, sign, diff)

    lines = [
        "# 市场赚钱效应 — %s" % data.get("date", ""),
        "",
        "赚钱效应指数: **%s%%** (%s)%s" % (today_si, m.get("sentiment_label", "?"), si_diff),
        "涨停 %s%s | 炸板 %s%s | 跌停 %s" % (
            today_lu, lu_diff, today_fr, fr_diff, m.get("limit_down", "?")
        ),
        "结构差值: %s  |  晋级率: %s" % (m.get("struct_diff", "?"), m.get("promotion_rate", "?")),
    ]

    trend_label = comp.get("trend_label", "")
    trend_url = comp.get("trend_url", "")
    if trend_label:
        lines.append("情绪趋势: **%s**" % trend_label)
    if trend_url:
        lines.append("近期走势 → %s" % trend_url)

    lines += [
        "",
        "### 涨跌分布",
        "| 区间 | 今日 | 昨日 | 变化 |",
        "|------|------|------|------|",
    ]
    _dir_map = {"up": "↑", "down": "↓"}
    for b in m.get("buckets", []):
        prev = b.get("prev")
        dir_sym = _dir_map.get(b.get("dir", ""), "-")
        lines.append("| %s | %s | %s | %s |" % (
            b.get("name", "?"),
            b.get("count", "?"),
            prev if prev is not None else "-",
            dir_sym,
        ))
    return "\n".join(lines)


def fmt_themes(data):
    themes = data.get("hot_themes", [])
    if not themes:
        return "暂无热门题材数据"
    lines = [
        "# 热门题材 — %s" % data.get("date", ""),
        "",
        "| # | 题材 | 涨停数 | 游资净流入(亿) | 龙头股 |",
        "|---|------|--------|--------------|--------|",
    ]
    for i, t in enumerate(themes, 1):
        leaders = " / ".join(
            "%s(%s亿)" % (s.get("name", ""), s["net_yi"]) if s.get("net_yi") is not None
            else s.get("name", "")
            for s in t.get("top_stocks", [])[:3]
        )
        net = t.get("net_yi", "-")
        lines.append("| %d | %s | %s | %s | %s |" % (i, t.get("name", ""), t.get("limitup_count", ""), net, leaders))
    return "\n".join(lines)


def fmt_ladder(data):
    ld = data.get("ladder_detail")
    if not ld:
        return "暂无连板数据"
    ladder = data.get("ladder", {})
    ts = ladder.get("top_streak", {})
    rates = ld.get("lb_rates_map", {})

    lines = [
        "# 连板天梯 — %s" % data.get("date", ""),
        "",
        "最高连板: **%s板** — %s (%s)" % (
            ladder.get("max_streak", "?"),
            ts.get("name", "?"),
            ts.get("industry", ""),
        ),
        "涨停总数: %s" % ladder.get("total_limit_up", "?"),
        "",
    ]

    for level in ld.get("levels", []):
        boards = level.get("boards", "?")
        stocks = level.get("stocks", [])
        count = level.get("count", len(stocks))

        # 本级晋级率：key=boards 表示「boards板→boards+1板」的成功率
        rate = rates.get(str(boards), "")
        rate_str = "  · 晋级率 %s →%s板" % (rate, int(boards) + 1) if rate else ""

        names = " / ".join(
            ("%s(%s)" % (s.get("name", ""), ind) if (ind := s.get("industry", "")) else s.get("name", ""))
            for s in stocks
        )
        lines.append("### %s板（%s 只）%s" % (boards, count, rate_str))
        lines.append(names if names else "—")
        lines.append("")

    areas = ld.get("area_counts", {})
    if areas:
        lines.append("### 地域分布 TOP 5")
        for name, count in list(areas.items())[:5]:
            lines.append("- %s: %s 只" % (name, count))

    concepts = ld.get("concept_counts", {})
    if concepts:
        lines.append("")
        lines.append("### 概念分布 TOP 5")
        for name, count in list(concepts.items())[:5]:
            lines.append("- %s: %s 只" % (name, count))

    return "\n".join(lines)


def fmt_hotmoney(data):
    hm = data.get("hotmoney")
    if not hm:
        return "暂无游资数据"
    lines = [
        "# 游资龙虎榜 — %s" % data.get("date", ""),
        "",
        "龙虎榜总净买入: **%s 亿**" % hm.get("total_net_yi", "?"),
        "",
        "### 净买入 TOP",
        "| 股票 | 净买入(亿) | 占比 |",
        "|------|-----------|------|",
    ]
    for b in hm.get("top_net_buy", []):
        lines.append("| %s | %s | %s%% |" % (
            b.get("name", "-"), b.get("net_yi", "-"), b.get("ratio_pct", "-"),
        ))

    seats = hm.get("seats", [])
    if seats:
        lines.append("")
        lines.append("### 知名游资席位动向")
        for seat in seats:
            seat_stocks = seat.get("stocks", [])
            buy = [s for s in seat_stocks if s.get("net_yi", 0) >= 0]
            sell = [s for s in seat_stocks if s.get("net_yi", 0) < 0]
            # 机构席位股票多，截取前8/后4
            if len(seat_stocks) > 12:
                buy = buy[:8]
                sell = sell[:4]
            buy_str = "、".join(
                "%s(+%.2f亿)" % (s["name"], s["net_yi"]) for s in buy
            )
            sell_str = "、".join(
                "%s(%.2f亿)" % (s["name"], s["net_yi"]) for s in sell
            )
            parts = []
            if buy_str:
                parts.append("买 " + buy_str)
            if sell_str:
                parts.append("卖 " + sell_str)
            lines.append("- **%s**: %s" % (seat.get("name", ""), " | ".join(parts)))

    return "\n".join(lines)


def fmt_sectors(data):
    sectors = data.get("sectors", [])
    if not sectors:
        return "暂无行业资金数据"
    lines = ["# 行业资金流向 — %s" % data.get("date", "")]
    for group in sectors:
        label = group.get("label", "")
        lines.append("\n## %s" % label)
        for section_key in ("strong", "weak"):
            section = group.get(section_key, [])
            if not section:
                continue
            tag = "强势" if section_key == "strong" else "弱势"
            lines.append("\n### %s" % tag)
            lines.append("| 板块 | 净流入(亿) | 龙头股 | 偏离度 |")
            lines.append("|------|-----------|--------|--------|")
            for item in section:
                lines.append("| %s | %s | %s | %s%% |" % (
                    item.get("name", "-"),
                    item.get("net_yi", "-"),
                    item.get("leader", "-"),
                    item.get("bias_pct", "-"),
                ))
    return "\n".join(lines)


def fmt_news(data):
    macro = data.get("macro_news", [])
    if not macro:
        return "暂无新闻数据"
    lines = ["# 宏观新闻 — %s" % data.get("date", ""), ""]
    for n in macro[:6]:
        t = n.get("t", "")
        if "T" in t:
            t = t.split("T")[1][:5]
        cat = n.get("cat", "")
        tag = "[%s] " % cat if cat else ""
        lines.append("- `%s` %s%s" % (t, tag, n.get("title", "")))
    return "\n".join(lines)


def fmt_ai_summary(data):
    """AI 一句话总结"""
    ai = data.get("ai_summary")
    if not ai:
        return ""
    if isinstance(ai, str):
        return "> %s" % ai
    if not isinstance(ai, dict):
        return ""
    # 构建摘要块：一句话总览 + 关键要点
    lines = []
    headline = ai.get("market_state", "")
    if headline:
        lines.append("> **%s**" % headline)
    bullets = [
        ("theme_focus", "题材"),
        ("focus_direction", "资金"),
        ("hotmoney_state", "游资"),
        ("news_highlight", "焦点"),
    ]
    for key, label in bullets:
        val = ai.get(key, "")
        if val:
            # 新闻摘要截断避免过长
            if len(val) > 60:
                val = val[:57] + "..."
            lines.append("> - **%s**: %s" % (label, val))
    return "\n".join(lines)


def fmt_comparison(data):
    """较昨日变化 + 趋势钩子"""
    comp = data.get("comparison")
    if not comp:
        return ""
    yd = comp.get("yesterday", {})
    m = data.get("market", {})
    lines = ["## 较昨日变化", ""]

    today_lu = m.get("limit_up")
    yd_lu = yd.get("limit_up")
    if today_lu is not None and yd_lu is not None:
        diff_lu = today_lu - yd_lu
        sign_lu = "+" if diff_lu > 0 else ""
        lines.append("涨停 %s（昨 %s，%s%s）" % (today_lu, yd_lu, sign_lu, diff_lu))

    today_si = m.get("sentiment_index")
    yd_si = yd.get("sentiment_index")
    if today_si is not None and yd_si is not None:
        diff_si = round(today_si - yd_si, 1)
        sign_si = "+" if diff_si > 0 else ""
        lines.append("情绪 %s%%（昨 %s%%，%s%s%%）" % (today_si, yd_si, sign_si, diff_si))

    today_fr = m.get("fried")
    yd_fr = yd.get("fried")
    if today_fr is not None and yd_fr is not None:
        diff_fr = today_fr - yd_fr
        sign_fr = "+" if diff_fr > 0 else ""
        lines.append("炸板 %s（昨 %s，%s%s）" % (today_fr, yd_fr, sign_fr, diff_fr))

    trend_label = comp.get("trend_label", "")
    if trend_label:
        lines.append("")
        lines.append("趋势判断: **%s**" % trend_label)

    trend_url = comp.get("trend_url", "")
    if trend_url:
        lines.append("近10日趋势图 → %s" % trend_url)

    return "\n".join(lines)


def fmt_signals(data):
    """量化工具钩子（选股信号 + 策略回溯 + 异动/ETF）"""
    sig = data.get("signals_count")
    if not sig:
        return ""
    lines = ["## 量化工具", ""]

    # 钩子② 选股信号
    counts = []
    for key, label in [
        ("jiuzhuan", "九转买入信号"),
        ("multi_factor", "多因子评分>80"),
        ("emotion_sync", "情绪共振信号"),
    ]:
        val = sig.get(key)
        if val is not None:
            counts.append("· %s: %s只" % (label, val))
    if counts:
        total = sum(
            sig.get(k, 0) for k in ("jiuzhuan", "multi_factor", "emotion_sync")
        )
        is_free_today = datetime.now().weekday() == 0  # 周一
        free_hint = "今天免费查看名单" if is_free_today else "%s免费查看名单" % sig.get("free_day", "每周一")
        lines.append("选股信号 %s个（%s）" % (total, free_hint))
        lines.extend(counts)
        xuangu_url = sig.get("xuangu_url", "https://hhxg.top/xuangu.html")
        lines.append("→ %s" % xuangu_url)
        lines.append("")

    # 钩子③ 策略回溯
    backtest_url = sig.get("backtest_url", "https://hhxg.top/xuangu.html#backtest")
    lines.append("策略回溯（自定义信号组合 + 历史胜率）")
    lines.append("→ %s" % backtest_url)
    lines.append("")

    # 钩子④ 异动预警
    vol_count = sig.get("volatility_alert")
    if vol_count is not None:
        lines.append("异动预警 %s只 → https://hhxg.top/yidong.html" % vol_count)

    lines.append("ETF工具 → https://hhxg.top/etf.html")

    return "\n".join(lines)


def fmt_footer(data):
    """结尾引流 — 使用 links 字段"""
    links = data.get("links", {})
    lines = ["---", ""]
    full = links.get("full_report", {})
    url = full.get("url", "https://hhxg.top")
    lines.append("详细数据请查看 %s" % url)
    lines.append("")
    for key in ("stock_picker", "hotmoney", "margin", "etf", "volatility"):
        lk = links.get(key, {})
        if lk.get("title") and lk.get("url"):
            lines.append("· %s → %s" % (lk["title"], lk["url"]))
    if not any(links.get(k) for k in ("stock_picker", "hotmoney", "margin", "etf", "volatility")):
        lines.append("· 更多工具 → https://hhxg.top")
    return "\n".join(lines)


def fmt_snapshot(data):
    """完整快照 — 标准输出模板"""
    parts = [
        "# 恢恢量化 · %s" % data.get("date", ""),
        "",
    ]
    summary = fmt_ai_summary(data)
    if summary:
        parts.append(summary)
        parts.append("")

    sep = "\n\n---\n\n"

    # ━━ 今日完整数据 ━━
    parts.append(fmt_market(data))      # 含今日 vs 昨日对比
    parts.append(sep)
    parts.append(fmt_themes(data))
    parts.append(sep)
    parts.append(fmt_ladder(data))
    parts.append(sep)
    parts.append(fmt_hotmoney(data))
    parts.append(sep)
    parts.append(fmt_sectors(data))
    parts.append(sep)
    parts.append(fmt_news(data))

    # ━━ 量化工具钩子 ━━
    sig_text = fmt_signals(data)
    if sig_text:
        parts.append(sep)
        parts.append(sig_text)

    # ━━ 引流 footer ━━
    parts.append("\n\n")
    parts.append(fmt_footer(data))
    return "\n".join(parts)


# ── Main ────────────────────────────────────────────────────

SECTIONS = {
    "all": fmt_snapshot,
    "summary": fmt_ai_summary,
    "market": fmt_market,
    "themes": fmt_themes,
    "ladder": fmt_ladder,
    "hotmoney": fmt_hotmoney,
    "sectors": fmt_sectors,
    "news": fmt_news,
    "comparison": fmt_comparison,
    "signals": fmt_signals,
}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    use_json = "--json" in flags

    section = args[0] if args else "all"
    if section not in SECTIONS:
        print("未知板块: %s" % section)
        print("可选: %s" % ", ".join(SECTIONS))
        sys.exit(1)

    try:
        data, from_cache = fetch()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    check_schema(data)
    print_cache_hint(from_cache, data.get("date", ""))

    # 数据日期 ≠ 今天时，提示数据截止日期及更新时间
    data_date = data.get("date", "")
    today = datetime.now().strftime("%Y-%m-%d")
    if data_date and data_date != today:
        print(
            "NOTE: 以下为 %s 的数据（最近交易日）。"
            "每个交易日盘后约 20:00 更新，今日数据尚未发布。\n" % data_date,
            file=sys.stderr,
        )

    if use_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(SECTIONS[section](data))


if __name__ == "__main__":
    main()
