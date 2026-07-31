# Reflection Blog Page — 颜色与主题规范

> 本文记录 `ReflectionBlogPage` 和 `BlogResultCard` 组件的颜色体系。  
> Source of truth: `frontend/src/styles/tokens.css`  
> 组件路径: `frontend/src/components/AnalysisView.tsx`  
> 上次更新: 2026-06-09

---

## 设计语义

Reflection Blog Page 是一个全页「博客阅读」视图，用于展示单条 Past Reflection 的详细内容。  
视觉参考：杂志/音乐详情页风格——封面艺术块（左）、标题与元数据（右）、博客正文（下方内容区）。  
**主视觉语言与整体 Ink & Memory 一致：温暖纸张、手写日记、静物台。**

---

## Token 使用映射

### 页面背景层

| 区域 | Token | 说明 |
|---|---|---|
| 页面底色 | `--color-bg-app` | 浅暖米 / 暗棕，整页基础色 |
| Hero / Masthead 背景 | `linear-gradient(var(--color-bg-surface-solid) → var(--color-bg-app))` | 封面区渐变，顶部亮、底部融入页面 |
| Sticky Nav 背景 | `color-mix(var(--color-bg-surface-solid) 90%, transparent)` + `backdrop-filter: blur(16px)` | 毛玻璃顶栏 |
| Table of Contents 条 | `var(--color-bg-surface)` | 目录导航浅背景 |
| BlogResultCard 背景 | `linear-gradient(var(--color-bg-surface-solid) → var(--color-bg-surface))` | 卡片微渐变，纸感 |

### 分隔线 / 边框

| 区域 | Token |
|---|---|
| Hero 下边框 | `--color-border-paper` |
| Section 标题下划线 | `color-mix(var(--color-border-paper) 60%, transparent)` |
| Card 边框（静止） | `color-mix(var(--color-border-paper) 55%, transparent)` |
| Card 边框（hover） | `--color-border-paper` |
| Nav / ToC 分隔线 | `--color-border-paper` |

### 文字层

| 区域 | Token | 字体 |
|---|---|---|
| 封面日期数字 | `--color-text-primary` | Georgia, serif |
| 页面大标题 | `--color-text-primary` | Georgia, serif, italic |
| 卡片标题 | `--color-text-primary` | Georgia, serif, italic |
| 卡片正文 | `--color-text-body` | 系统无衬线 |
| 元数据、标签 | `--color-text-secondary` | 系统无衬线 |
| Muted (月份、年份、标签) | `--color-text-muted` | 系统无衬线 |
| 序号水印 | `color-mix(var(--color-border-paper) 70%, transparent)` | Georgia, serif |

### 交互状态

| 元素 | 静止 | Hover |
|---|---|---|
| Back 按钮 | `--color-border-paper` 边框，无背景 | `--color-bg-hover` 背景，`--color-text-muted` 边框 |
| ToC 链接 | `--color-text-secondary`，无下边框 | `--color-text-body`，`--color-text-muted` 下边框 |
| BlogResultCard | 无阴影 | `0 6px 24px var(--color-shadow-soft)` + `--color-border-paper` 边框 |

### 阴影

| 用途 | Token |
|---|---|
| 封面艺术块 | `--color-shadow-medium` (主) + `--color-shadow-soft` (层) |
| Card Hover | `--color-shadow-soft` |

---

## 布局规格

### 响应式断点

- `isMobile = true`：单列，padding `1rem`，封面块 88×88px，标题 22px
- `isMobile = false`：双列 Hero（封面160×160 + 标题），正文最大宽 `1100px`，padding `3rem`

### Hero / Masthead 构成

```
┌──────────────────────────────────────────────────────────────┐
│ Sticky Nav: [← Past Reflections]           [日期文本]         │
├──────────────────────────────────────────────────────────────┤
│ Hero                                                         │
│  ┌────────────┐  Reflection (label)                          │
│  │   JUN      │  Weekday, Month Day, Year (h1, 38px italic)  │
│  │   9  (56px)│  ────────────────────────                    │
│  │   2026     │  N days · N entries · N words                │
│  └────────────┘  [🔄 Echoes ×N] [⭐ Traits ×N] [🌀 ×N]     │
├──────────────────────────────────────────────────────────────┤
│ Table of Contents: On this page | 🔄 Themes | ⭐ Traits | …  │
├──────────────────────────────────────────────────────────────┤
│ Blog Sections (one per type)                                 │
│  [Section Header: icon + title + subtitle + count badge]     │
│  [BlogResultCard × N]                                        │
└──────────────────────────────────────────────────────────────┘
```

### BlogResultCard 构成

- 左上: `h3` 标题 (Georgia italic, 19px)
- 右上: 两位序号水印 (01/02/03...)
- 正文: 描述/证据文本 (14px, lineHeight 1.85)
- Traits 专属: 5格置信度条 + 证据文本
- Echoes/Patterns: 置信度 Pill (Confidence · high/medium/low)

---

## 字体规则

| 用途 | 字体栈 |
|---|---|
| 展示/标题 | `'Excalifont', 'Xiaolai', Georgia, serif` |
| 功能/正文 | `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif` |
| 数字 / 大标题 | `Georgia, serif` |

---

## 详情模式 (Detail Mode) 补充规范

### 左右分栏

| 区域 | Token |
|---|---|
| 左栏背景 | `var(--color-bg-app)`（继承页面底色） |
| 右栏背景 | `var(--color-bg-surface)`（轻微区分） |
| 左右分隔线（桌面） | `var(--color-border-paper)` |
| 上下分隔线（移动） | `var(--color-border-paper)` |

### 右栏占位卡

| 元素 | Token |
|---|---|
| 卡片背景 | `var(--color-bg-surface-solid)`，opacity 0.5 |
| 卡片边框 | `color-mix(var(--color-border-paper) 50%, transparent)` |
| 骨架条（长行） | `color-mix(var(--color-border-paper) 60%, transparent)` |
| 骨架条（短行） | `color-mix(var(--color-border-paper) 40%, transparent)` |

### Player Bar

| 元素 | Token |
|---|---|
| 背景 | `var(--color-bg-surface-solid)` |
| 上边框 | `var(--color-border-paper)` |
| 阴影 | `0 -4px 16px var(--color-shadow-soft)` |
| 封面小图标块 | 渐变 `var(--color-bg-surface-solid)` → `color-mix(var(--color-border-paper) 40%, var(--color-bg-surface-solid))` |
| 条目标题 | `var(--color-text-body)`，Georgia italic |
| Section 副标题 | `var(--color-text-muted)` |
| 控制按钮（激活） | `var(--color-border-paper)` 边框，`var(--color-text-body)` 前景 |
| 控制按钮（禁用） | `var(--color-border-paper)` 前景（灰化） |
| 当前位置圆点（激活） | `var(--color-text-muted)` |
| 其他位置圆点 | `color-mix(var(--color-text-muted) 35%, transparent)` |
| 计数文字 | `var(--color-text-muted)` |
| × 关闭按钮 | `var(--color-text-muted)` 前景，`var(--color-border-paper)` 边框 |

### Section Tab（Sticky Nav 右侧）

| 状态 | Token |
|---|---|
| 激活背景 | `var(--color-bg-surface-solid)` |
| 激活边框 | `var(--color-border-paper)` |
| 激活阴影 | `0 1px 4px var(--color-shadow-soft)` |
| 激活文字 | `var(--color-text-body)` |
| 非激活文字 | `var(--color-text-muted)` |
| 计数徽章背景（激活） | `color-mix(var(--color-border-paper) 50%, transparent)` |
| 计数徽章背景（非激活） | `color-mix(var(--color-border-paper) 30%, transparent)` |

---

## 与父组件 token 的一致性

`ReflectionBlogPage` **不引入任何孤立十六进制颜色**；  
所有颜色均通过 `var(--color-*)` 引用，完整继承 light/dark 主题切换。  
`tokens.css` 在 `[data-theme='dark']` 及 `prefers-color-scheme: dark` 下的覆盖值自动生效。
