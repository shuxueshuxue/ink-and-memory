#!/usr/bin/env python3
"""生成 macOS 终端风格 SVG 截图。运行一次即可，产物提交到 screenshots/"""
from __future__ import annotations
import html
import os
import re
import subprocess
import sys
import textwrap

# ── 配色（One Dark Pro） ────────────────────────────────────────
BG         = "#282C34"
TITLE_BAR  = "#21252B"
TEXT       = "#ABB2BF"
BOLD       = "#E5C07B"
HEADING    = "#61AFEF"
COMMENT    = "#5C6370"
GREEN      = "#98C379"
RED        = "#E06C75"
CYAN       = "#56B6C2"
DOT_RED    = "#FF5F56"
DOT_YEL    = "#FFBD2E"
DOT_GRN    = "#27C93F"

FONT = "monospace"
FONT_SIZE  = 13
LINE_H     = 19
PAD_X      = 20
PAD_Y_TOP  = 52   # 标题栏高度
PAD_Y_BOT  = 20
MAX_COLS   = 80   # 行宽截断


def _esc(s: str) -> str:
    return html.escape(s)


def _color_line(raw: str) -> str:
    """将一行 markdown 文本转为带颜色的 SVG tspan 片段。"""
    line = raw[:MAX_COLS]  # 截断过长行

    # 标题 #
    if re.match(r'^#{1,3} ', line):
        text = re.sub(r'^#{1,3} ', '', line)
        return '<tspan fill="%s" font-weight="bold">%s</tspan>' % (HEADING, _esc(line))

    # blockquote >
    if line.startswith('> '):
        inner = line[2:]
        # 处理 **...**
        inner = re.sub(r'\*\*(.+?)\*\*', '<tspan fill="%s" font-weight="bold">\\1</tspan>' % BOLD, inner)
        return '<tspan fill="%s">&gt; %s</tspan>' % (GREEN, inner)

    # 分隔线
    if re.match(r'^-{3,}$', line.strip()):
        return '<tspan fill="%s">%s</tspan>' % (COMMENT, _esc(line))

    # 表格行
    if line.startswith('|'):
        # 表头/分隔行用不同色
        if re.match(r'^\|[-| ]+\|$', line):
            return '<tspan fill="%s">%s</tspan>' % (COMMENT, _esc(line))
        parts = line.split('|')
        result = ''
        for i, p in enumerate(parts):
            p_e = _esc(p)
            if i == 0 or i == len(parts) - 1:
                result += '<tspan fill="%s">|</tspan>' % COMMENT
            else:
                # 数字高亮
                p_colored = re.sub(
                    r'(\d[\d.,亿%+\-只板]*)',
                    '<tspan fill="%s">\\1</tspan>' % CYAN,
                    p_e
                )
                # ↑ ↓
                p_colored = p_colored.replace('↑', '<tspan fill="%s">↑</tspan>' % GREEN)
                p_colored = p_colored.replace('↓', '<tspan fill="%s">↓</tspan>' % RED)
                result += '<tspan fill="%s"> %s </tspan><tspan fill="%s">|</tspan>' % (TEXT, p_colored, COMMENT)
        return result

    # 无序列表 - / •
    if re.match(r'^[-•] ', line) or re.match(r'^  [-•] ', line):
        prefix = '• '
        body = re.sub(r'^  ?[-•] ', '', line)
        body_e = _esc(body)
        # 先数字、再粗体，避免粗体颜色码 #E5C07B 里的数字被误匹配
        body_e = re.sub(r'(\d[\d.,亿%+\-只板]*)', '<tspan fill="%s">\\1</tspan>' % CYAN, body_e)
        body_e = re.sub(r'\*\*(.+?)\*\*', '<tspan font-weight="bold" fill="%s">\\1</tspan>' % BOLD, body_e)
        return '<tspan fill="%s">%s</tspan><tspan fill="%s">%s</tspan>' % (COMMENT, prefix, TEXT, body_e)

    # ### 子标题
    if re.match(r'^### ', line):
        text = line[4:]
        return '<tspan fill="%s" font-weight="bold">### %s</tspan>' % (CYAN, _esc(text))

    # 普通行（处理 ** **）
    line_e = _esc(line)
    # 先数字、再粗体，避免粗体颜色码 #E5C07B 里的数字被误匹配
    line_e = re.sub(r'(\d[\d.,亿%+\-只板]*)', '<tspan fill="%s">\\1</tspan>' % CYAN, line_e)
    line_e = re.sub(r'\*\*(.+?)\*\*', '<tspan font-weight="bold" fill="%s">\\1</tspan>' % BOLD, line_e)
    # → 链接引导
    if '→' in line_e or 'https://' in line_e:
        line_e = line_e.replace('→', '<tspan fill="%s">→</tspan>' % GREEN)
        line_e = re.sub(r'(https?://\S+)', '<tspan fill="%s">\\1</tspan>' % GREEN, line_e)

    return '<tspan fill="%s">%s</tspan>' % (TEXT, line_e)


def render_svg(title: str, lines: list[str], width: int = 760) -> str:
    # 过滤空尾行
    while lines and not lines[-1].strip():
        lines.pop()

    n = len(lines)
    height = PAD_Y_TOP + n * LINE_H + PAD_Y_BOT

    rows = []
    for i, raw in enumerate(lines):
        y = PAD_Y_TOP + (i + 1) * LINE_H
        colored = _color_line(raw)
        rows.append(
            '<text x="%d" y="%d" font-family="%s" font-size="%d">%s</text>'
            % (PAD_X, y, FONT, FONT_SIZE, colored)
        )

    svg = textwrap.dedent("""\
        <svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">
          <rect width="{w}" height="{h}" rx="8" fill="{bg}"/>
          <!-- 标题栏 -->
          <rect width="{w}" height="36" rx="8" fill="{tb}"/>
          <rect y="20" width="{w}" height="16" fill="{tb}"/>
          <!-- 控制点 -->
          <circle cx="16" cy="18" r="6" fill="{dr}"/>
          <circle cx="36" cy="18" r="6" fill="{dy}"/>
          <circle cx="56" cy="18" r="6" fill="{dg}"/>
          <!-- 标题 -->
          <text x="{w2}" y="23" text-anchor="middle"
            font-family="{font}" font-size="12" fill="{co}">{title}</text>
          <!-- 内容 -->
          {rows}
        </svg>
    """).format(
        w=width, h=height, bg=BG, tb=TITLE_BAR,
        dr=DOT_RED, dy=DOT_YEL, dg=DOT_GRN,
        w2=width // 2, font=FONT, co=COMMENT,
        title=_esc(title),
        rows="\n  ".join(rows),
    )
    return svg


def run_script(script: str, *args) -> list[str]:
    """运行 scripts/ 下的脚本，返回输出行列表。"""
    here = os.path.dirname(os.path.abspath(__file__))
    scripts_dir = os.path.join(here, "..", "scripts")
    cmd = [sys.executable, os.path.join(scripts_dir, script)] + list(args)
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=20)
    return result.stdout.splitlines()


def main():
    out_dir = os.path.dirname(os.path.abspath(__file__))

    # ── 截图 1：日报快照（summary + market + themes + ladder 节选）──
    print("生成 snapshot.svg ...")
    lines = []
    lines += run_script("fetch_snapshot.py", "summary")
    lines += [""]
    lines += run_script("fetch_snapshot.py", "market")
    lines += [""]
    # 只取 themes 前 10 行
    lines += run_script("fetch_snapshot.py", "themes")[:10]
    lines += ["  ..."]

    svg1 = render_svg("恢恢量化 · A股日报快照 — hhxg.top", lines, width=780)
    with open(os.path.join(out_dir, "snapshot.svg"), "w", encoding="utf-8") as f:
        f.write(svg1)

    # ── 截图 2：连板天梯 + 融资融券总览 ──
    print("生成 ladder-margin.svg ...")
    lines2 = []
    ladder = run_script("fetch_snapshot.py", "ladder")
    # 截取连板天梯前 28 行
    lines2 += ladder[:28]
    lines2 += [""]
    lines2 += ["─" * 60]
    lines2 += [""]
    lines2 += run_script("margin.py", "overview")[:18]

    svg2 = render_svg("恢恢量化 · 连板天梯 & 融资融券 — hhxg.top", lines2, width=780)
    with open(os.path.join(out_dir, "ladder-margin.svg"), "w", encoding="utf-8") as f:
        f.write(svg2)

    print("✓ screenshots/snapshot.svg")
    print("✓ screenshots/ladder-margin.svg")


if __name__ == "__main__":
    main()
