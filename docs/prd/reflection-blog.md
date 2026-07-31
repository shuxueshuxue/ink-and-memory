# Reflection Blog Page — 固定布局播放器交互优化 PRD

> 文档类型：产品功能规格  
> 组件路径：`frontend/src/components/AnalysisView.tsx` → `ReflectionBlogPage`  
> 最后更新：2026-06-26（v5.1 — preserve layout, polish interaction）
> 颜色规范：`docs/prd/color_system/reflection-blog.md`

---

## 1. 产品定位

Reflection Blog Page 是 Past Reflections 的沉浸式阅读视图，用于展示单条历史分析中的 Echoes / Traits / Patterns。页面必须保留既有固定高度阅读结构：左侧日期封面、右侧分区标题列表、下方详情区，以及选中条目后出现的底部播放器控件。

本次目标不是重做信息架构，而是在原有布局上增强“数字杂志 + 可播放阅读队列”的质感，让用户既能像读杂志一样浏览，也能像使用播放器一样在洞察之间前后切换。

---

## 2. 必须保留的整体布局

```text
ReflectionBlogPage（height: 100%; flex column; overflow hidden）
├── Sticky Nav
│   └── ← Past Reflections
├── Main Content（flex: 1; overflow hidden）
│   ├── Split Area（flex: 1; 左右/移动端上下）
│   │   ├── Left Hero：日期封面、完整日期、days / entries / words
│   │   └── Right Panel
│   │       ├── Section Tabs：echoes / traits / patterns
│   │       └── Title List：当前分区 title-only 列表，可独立滚动
│   └── Detail Area（仅选中条目时显示，固定高度）
│       ├── Detail Header：分区、当前位置、关闭按钮
│       ├── Left Detail：标题、描述/evidence、confidence
│       └── Right Related Notes：未来相关笔记占位
└── Bottom Player Bar（仅选中条目时显示）
    ├── 当前条目信息
    ├── 上一条 / 圆点队列 / 下一条
    └── X / N 计数
```

---

## 3. 交互要求

| 场景 | 行为 |
|---|---|
| 点击 Past Reflections 卡片 | 进入 ReflectionBlogPage |
| analyzeEchoes / analyzeTraits / analyzePatterns 完成 | 将单分区结果包装成 ReflectionBlogPage report，直接进入同一阅读页，不再打开旧 PaperStack 弹窗 |
| 一键 Generate New Analysis 完成 | 将三分区结果包装成 ReflectionBlogPage report，直接进入同一阅读页 |
| 点击 Dashboard 的 View Reflections | 使用当前内存中的 echoes / traits / patterns 包装成 ReflectionBlogPage report |
| 点击 Section Tab | 切换当前分区，并清空已选条目，关闭详情区和播放器 |
| 点击标题列表条目 | 展开下方详情区，同时显示底部播放器 |
| 再次点击已选标题 | 收起详情区和播放器 |
| 点击详情关闭按钮 | 收起详情区和播放器 |
| 点击播放器上一条/下一条 | 在当前分区内切换条目，边界按钮 disabled |
| 点击播放器圆点 | 跳转到当前分区对应条目 |

---

## 4. 视觉优化方向

- **保留结构**：不得把固定左右分栏改成整页滚动杂志，不得删除底部播放器。
- **日期封面**：左侧 cover art 使用更强的深色封面、纸张内描边、Issue 日期感和细腻阴影。
- **列表反馈**：选中标题使用渐变底色、序号强化和箭头旋转，让“正在播放的条目”更明确。
- **详情区**：保留双栏详情 + Related Notes，占位态允许存在，但视觉要更轻，不抢主内容。
- **播放器**：底部播放器是核心交互控件，需保持固定在底部，增强玻璃感、阴影和当前 track 识别。
- **动效边界**：只使用轻微 hover、选中态、圆点宽度变化等低成本反馈，不引入复杂动画。

---

## 5. 非目标

- 不实现 Related Notes 后端匹配。
- 不改造为全屏单列杂志长页。
- 不删除底部 Player Bar。
- 不新增分析完成后的自动弹窗或遮罩层；唯一允许的弹窗是当天重复点击 `Generate New Analysis` 时的重新分析确认与日记选择弹窗。分析完成后的自动呈现必须使用 ReflectionBlogPage wrapper。
- 不引入额外 UI 依赖或外部 CDN。

---

## 6. Generate New Analysis 当日重分析保护（2026-06-26 v5.2）

### 6.1 问题整理

当前问题有两类：

1. `Generate New Analysis` 点击后，用户感知上没有进入后端分析过程，而是像直接打开了已有结果。正确行为应是先启动 Reflections-agent 异步任务，并在按钮下方展示 SSE/EventBus 进度，直到任务完成后才进入 `ReflectionBlogPage`。
2. 如果用户当天已经点击过 `Generate New Analysis`，再次点击时不应静默覆盖或直接复用旧结果，应先确认是否重新分析，并让用户选择本次要纳入分析的可分析日记。

### 6.2 触发规则

- 当天首次点击：直接创建 Reflections-agent task，并进入页面内进度态。
- 当天重复点击：弹出重新分析确认弹窗。
- “今天点击过”以本地日期记录为准；即使上一次分析失败，重复点击也需要确认，避免用户误触发昂贵任务。
- 如果当天已有 Past Reflections 报告，也视为需要确认。

### 6.3 弹窗内容

弹窗需要展示：

1. 今天已经生成/启动过分析的提示。
2. 重新分析会创建新报告的说明。
3. 可分析日记列表：仅展示有正文内容的 sessions。
4. 全选/清空、单条勾选、取消、确认重新分析。

确认前至少需要选择一条日记。确认后，前端将选中的 `sessionIds` 传给 Reflections-agent task，后端只基于这些日记组装 workspace 与分析上下文。

### 6.4 正确业务时序

```text
click Generate New Analysis
  → if clicked today or report exists today: open reanalysis confirm modal
  → user selects diary entries and confirms
  → create task(auto_start=false, session_ids=selectedIds)
  → establish SSE subscription or fallback grace timer
  → start task
  → stream progress in page
  → fetch completed results
  → save report
  → open ReflectionBlogPage wrapper
```

不得在 task 完成前直接打开 `ReflectionBlogPage`；如果 SSE 首帧迟迟未到，前端应通过短暂 grace timer 启动任务，避免“等待 stream connected 导致任务未启动”。
