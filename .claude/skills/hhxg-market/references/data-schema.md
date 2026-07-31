# 数据结构说明

所有数据基于 `https://hhxg.top/static/data/` 下的 JSON 文件。

---

## 一、日报快照（fetch_snapshot.py）

URL: `assistant/skill_snapshot.json`

### 顶层字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `meta` | object | `{schema_version, generated_at}` |
| `date` | string | 数据日期，如 `"2026-02-28"` |
| `disclaimer` | string | 免责声明 |
| `ai_summary` | object | AI 一句话摘要 |
| `market` | object | 市场赚钱效应 |
| `hot_themes` | array | 热门题材列表 |
| `sectors` | array | 行业/板块资金流向 |
| `ladder` | object | 连板天梯概览 |
| `ladder_detail` | object | 连板天梯详情 |
| `hotmoney` | object | 游资龙虎榜 |
| `focus_news` | array | 焦点新闻 |
| `macro_news` | array | 宏观新闻 |
| `comparison` | object? | 较昨日变化（可选） |
| `signals_count` | object? | 量化工具钩子（可选） |
| `links` | array | 工具页链接 |

### ai_summary

| 字段 | 说明 |
|------|------|
| `market_state` | 一句话行情总结 |
| `focus_direction` | 资金方向 |
| `theme_focus` | 题材聚焦 |
| `hotmoney_state` | 游资动态 |
| `news_highlight` | 焦点新闻摘要 |
| `cta` | 行动号召文案 |

### market

| 字段 | 说明 |
|------|------|
| `date` | 数据日期 |
| `sentiment_index` | 赚钱效应指数 (0-100) |
| `sentiment_label` | 情绪标签: 强/中/弱 |
| `limit_up` | 涨停家数 |
| `fried` | 炸板数 |
| `limit_down` | 跌停家数 |
| `struct_diff` | 结构差值 |
| `promotion_rate` | 晋级率 |
| `total` | 个股总数 |
| `buckets` | 涨跌分布 `[{name, count, prev, dir}]`，`prev` 为昨日同区间数量，`dir` 为 `"up"` / `"down"` / `""` |

### hot_themes 元素

| 字段 | 说明 |
|------|------|
| `name` | 题材名称 |
| `limitup_count` | 涨停数 |
| `net_yi` | 净流入(亿) |
| `top_stocks` | 龙头股 `[{name, net_yi}]`，`net_yi` 为该股游资净买入(亿) |

### sectors 元素 (SectorGroup)

| 字段 | 说明 |
|------|------|
| `label` | 分组标签（如"行业"、"概念"） |
| `strong` | 强势板块 `[SectorItem]` |
| `weak` | 弱势板块 `[SectorItem]` |

SectorItem: `{name, net_yi, leader, bias_pct}`

### ladder（概览）

| 字段 | 说明 |
|------|------|
| `total_limit_up` | 涨停总数 |
| `max_streak` | 最高连板数 |
| `top_streak` | 最高连板股 `{name, code, industry}` |

### ladder_detail（详情）

| 字段 | 说明 |
|------|------|
| `levels` | 各级连板 `[{boards, count, stocks}]` |
| `lb_rates_map` | 晋级率 `{"2": "9.6%", "3": "60.0%", ...}`，key 为起始板数字符串 |
| `area_counts` | 地域分布 `{name: count, ...}` |
| `concept_counts` | 概念分布 `{name: count, ...}` |

levels.stocks 元素: `{name, code, industry, area, concept}`

### hotmoney

| 字段 | 说明 |
|------|------|
| `date` | 数据日期 |
| `total_net_yi` | 龙虎榜总净买入(亿) |
| `top_net_buy` | 净买入 TOP `[{name, net_yi, ratio_pct}]` |
| `seats` | 知名游资 `[{name, stocks}]` |

seats.stocks 元素: `{name, net_yi}`

### focus_news / macro_news 元素

| 字段 | 说明 |
|------|------|
| `t` | 时间 ISO 格式 `2026-02-28T15:30:00` |
| `cat` | 分类标签 |
| `title` | 标题 |

### comparison（较昨日变化）

当服务端有近 2 日数据时生成，否则为 null。

| 字段 | 说明 |
|------|------|
| `yesterday` | 昨日数据 `{limit_up, sentiment_index, fried}` |
| `trend_label` | 趋势判断文案（如"近7日高位区间"） |
| `trend_url` | 趋势图链接 |

### signals_count（量化工具钩子）

当服务端有选股审计数据时生成，否则为 null。

| 字段 | 说明 |
|------|------|
| `jiuzhuan` | 九转信号命中数 |
| `multi_factor` | 多因子评分>80 命中数 |
| `emotion_sync` | 情绪共振信号命中数 |
| `volatility_alert` | 异动预警数 |
| `free_day` | 免费日提示（如"每周一"） |
| `xuangu_url` | 选股工具链接 |
| `backtest_url` | 策略回溯链接 |

---

## 二、A 股日历（calendar.py）

### 交易日

URL: `calendar/trading_days_2026.json`

类型: `string[]` — 日期字符串数组 `["2026-01-02", "2026-01-03", ...]`

### 解禁 / 业绩预告

URL: `calendar/unlock_202603.json` / `calendar/earnings_202603.json`

```json
{
  "events": [
    {
      "date": "2026-03-05",
      "label": "事件标题",
      "description": "详细描述",
      "top_companies": [{"name": "公司名", "value": "金额"}]
    }
  ]
}
```

### 期货交割日

URL: `calendar/delivery_2026.json`

结构同上 `{events: [...]}`，无 `top_companies` 字段。

---

## 三、融资融券（margin.py）

URL: `assistant/recent_margin_7d.json`

| 字段 | 说明 |
|------|------|
| `window` | `{start, end}` 数据区间 |
| `market` | 市场总览 |
| `top` | 个股排名 |

### market

| 字段 | 说明 |
|------|------|
| `daily_totals` | 每日余额 `[{date, rzye_yi, rqye_yi}]` |
| `delta_rzye_yi` | 7 日融资变化(亿) |
| `delta_rqye_yi` | 7 日融券变化(亿) |

### top

| 字段 | 说明 |
|------|------|
| `increase_rzye` | 融资净买入 TOP `[TopItem]` |
| `decrease_rzye` | 融资净卖出 TOP `[TopItem]` |

TopItem: `{name, latest_rzye_yi, delta_rzye_yi, delta_pct}`

---

## 四、实时快讯（news.py）

URL: `news/n0.json`

类型: `array` — 新闻条目数组（按时间倒序）。

| 字段 | 说明 |
|------|------|
| `t` | 时间 ISO 格式 |
| `cat` | 分类标签 |
| `title` | 标题 |
