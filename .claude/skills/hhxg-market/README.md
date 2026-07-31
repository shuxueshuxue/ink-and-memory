# hhxg-market — A 股量化数据助手

> Claude Code / OpenClaw 技能：零配置获取 A 股日报、日历、融资融券、实时快讯

[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Data by hhxg.top](https://img.shields.io/badge/data-hhxg.top-blue.svg)](https://hhxg.top)

如果对你有用，欢迎点个 ⭐ Star — 帮助更多人发现这个工具。

---

## 什么是 hhxg-market？

一个 [Claude Code](https://claude.ai/code) / [OpenClaw](https://github.com/nicepkg/openclaw) 技能（Skill），安装后直接对 AI 说「今天 A 股怎么样」、「融资融券数据」、「明天是交易日吗」就能获取对应数据。

**无需注册、无需 Token、无需安装任何 Python 包**，仅需 Python 3 标准库。

数据由 [恢恢量化](https://hhxg.top) 持续更新，覆盖 5000+ 只 A 股。

---

## 效果预览

![日报快照](screenshots/snapshot.svg)

![连板天梯 & 融资融券](screenshots/ladder-margin.svg)

---

## 安装

**Claude Code：**
```bash
git clone --depth 1 https://github.com/Niceck/hhxg-top-hhxg-python.git /tmp/hhxg-market && \
  rm -rf ~/.claude/skills/hhxg-market && \
  mv /tmp/hhxg-market ~/.claude/skills/hhxg-market
```

**OpenClaw：**
```bash
git clone --depth 1 https://github.com/Niceck/hhxg-top-hhxg-python.git /tmp/hhxg-market && \
  rm -rf ~/.openclaw/skills/hhxg-market && \
  mv /tmp/hhxg-market ~/.openclaw/skills/hhxg-market
```

### 更新

```bash
cd ~/.claude/skills/hhxg-market && git pull
# OpenClaw:
cd ~/.openclaw/skills/hhxg-market && git pull
```

### 卸载

```bash
rm -rf ~/.claude/skills/hhxg-market
```

---

## 功能模块

| 模块 | 脚本 | 数据内容 |
|------|------|----------|
| 日报快照 | `fetch_snapshot.py` | 赚钱效应、热门题材、连板天梯、游资龙虎榜、行业资金、焦点新闻 |
| A 股日历 | `calendar.py` | 交易日查询、限售解禁、业绩预告、期货交割日 |
| 融资融券 | `margin.py` | 近 7 日余额变化、融资净买入/净卖出 TOP |
| 实时快讯 | `news.py` | 财经快讯流（按时间倒序） |

---

## 使用方式

### 在 Claude Code 中对话

```
你：今天 A 股怎么样？
你：热门题材 / 连板天梯 / 龙虎榜
你：明天是交易日吗？
你：融资融券数据
你：最新财经快讯
```

### 触发词

| 类别 | 触发词示例 |
|------|--------|
| 行情 | A股、股市、大盘、今天涨跌、大盘怎么样、盘后复盘、赚钱效应 |
| 题材 | 热门题材、连板天梯、连板情况、龙虎榜、涨停、行业资金流向 |
| 日历 | 今天是交易日吗、明天开盘吗、下周解禁、交割日、财报季 |
| 两融 | 融资融券、两融、两融数据、融资净买入、融资余额 |
| 快讯 | 最新快讯、财经新闻、焦点新闻、实时新闻 |

### 终端独立使用

```bash
# 定位脚本目录（兼容 Claude Code / OpenClaw）
SKILL_DIR=$(find ~/.claude/skills ~/.openclaw/skills \
  -name _common.py -path '*/hhxg-market/*' 2>/dev/null \
  | head -1 | xargs dirname)

python3 "$SKILL_DIR/fetch_snapshot.py"           # 完整日报
python3 "$SKILL_DIR/fetch_snapshot.py" market    # 赚钱效应
python3 "$SKILL_DIR/fetch_snapshot.py" themes    # 热门题材
python3 "$SKILL_DIR/calendar.py"                 # 本周日历
python3 "$SKILL_DIR/margin.py"                   # 融资融券
python3 "$SKILL_DIR/news.py" 30                  # 最新30条快讯

# 所有脚本支持 --json 输出原始数据
python3 "$SKILL_DIR/margin.py" --json
```

---

## 文件结构

```
├── README.md
├── LICENSE
├── SKILL.md                  # Skill 定义文件（Claude Code / OpenClaw 读取）
├── scripts/
│   ├── _common.py            # 共用工具（HTTP、本地缓存、schema 检查）
│   ├── fetch_snapshot.py     # 日报快照
│   ├── calendar.py           # A 股日历
│   ├── margin.py             # 融资融券
│   └── news.py               # 实时快讯
└── references/
    └── data-schema.md        # JSON 字段结构说明
```

---

## 数据来源

数据由 [恢恢量化](https://hhxg.top) 持续更新，覆盖 5000+ 只 A 股。

> 数据仅供研究参考，不构成投资建议。

如需可视化图表、AI 选股、历史回溯等高级功能，请访问 [hhxg.top](https://hhxg.top)。

---

## License

[MIT](LICENSE) &copy; [恢恢量化](https://hhxg.top)
