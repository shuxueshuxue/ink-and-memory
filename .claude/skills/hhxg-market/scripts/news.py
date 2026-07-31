#!/usr/bin/env python3
"""实时财经快讯 — 最新新闻、按分类筛选。

Usage:
    python3 news.py            # 最新 20 条
    python3 news.py 50         # 最新 50 条
    python3 news.py --json     # JSON 原始输出

数据来源: https://hhxg.top
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import fetch_json, print_cache_hint


def _fetch():
    return fetch_json("news/n0.json", "news_latest.json")


def fmt_news(items, limit=20):
    if not items:
        return "暂无快讯数据"
    lines = ["# 财经快讯（最新 %d 条）" % min(limit, len(items)), ""]

    current_date = ""
    for n in items[:limit]:
        t = n.get("t", "")
        cat = n.get("cat", "")
        title = n.get("title", "")

        # 按日期分组
        date_part = t.split("T")[0] if "T" in t else ""
        if date_part != current_date:
            current_date = date_part
            lines.append("")
            lines.append("## %s" % date_part)

        time_part = t.split("T")[1][:5] if "T" in t else t
        tag = "[%s]" % cat if cat else ""
        lines.append("- `%s` %s %s" % (time_part, tag, title))

    lines.append("")
    lines.append("---")
    lines.append("更多快讯 → https://hhxg.top/news.html")
    lines.append("量化选股 / 游资席位 / 策略回溯 → https://hhxg.top/xuangu.html")
    return "\n".join(lines)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    flags = {a for a in sys.argv[1:] if a.startswith("-")}
    use_json = "--json" in flags

    limit = 20
    if args:
        try:
            limit = int(args[0])
        except ValueError:
            pass

    try:
        data, cached = _fetch()
    except RuntimeError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    items = data if isinstance(data, list) else data.get("items", [])
    print_cache_hint(cached, "")

    if use_json:
        print(json.dumps(items[:limit], ensure_ascii=False, indent=2))
    else:
        print(fmt_news(items, limit))


if __name__ == "__main__":
    main()
