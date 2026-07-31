# Chat Sidebar PRD

> 聊天侧边栏、会话导航、文件入口和设置入口的产品与视觉规范。本文引用 [Color System](<./color_system/README.md>)，并与前端实现保持同步。
> **[Sync] 2026-06-28**: 当前 ChatView 不再使用左侧 rail/展开侧栏；历史对话由右上角「更多」菜单打开右侧 HistorySidePanel，搜索由面板标题栏按钮打开居中 HistorySearchDialog。

## 1. 文档范围

Chat Sidebar 覆盖对话工作区中的历史会话面板、文件入口和移动端替代导航。当前 Chat 工作区不再使用左侧固定 rail；会话历史通过右上角「更多」菜单打开右侧 HistorySidePanel，文件通过同一菜单打开 FileSidebar。

旧稿中的“玫瑰金”“高级灰调极简主义”“侧边栏设置 HTML 原型”不作为当前项目规范。

## 2. 设计目标

- 帮助用户快速切换会话、进入文件和设置，不干扰主编辑/聊天区域。
- 在桌面端提供清晰层级，在移动端收敛为顶部或底部轻导航。
- 当前项、hover、focus、折叠、空列表、错误、加载状态都有可验收描述。
- 与 Dashboard、History、Send 共享 [Color System](<./color_system/README.md>)。

## 3. 布局结构

```
ChatSidePanels
├── MoreMenu（右上角）
│   ├── 历史对话
│   ├── 工作空间
│   └── 分享
├── HistorySidePanel（右侧展开）
│   ├── Header（历史对话 / 搜索按钮 / 关闭按钮）
│   └── SessionList
│       └── ChatSessionItem
├── HistorySearchDialog（居中弹窗）
│   ├── SearchInput
│   └── SearchResultList / GroupedDefaultHistory
└── FileSidebar（右侧展开）
```

## 4. 桌面端规范

| 区域 | 规范 |
|---|---|
| 宽度 | HistorySidePanel 约 `16rem`；FileSidebar 按文件工作区规范。 |
| 背景 | 右侧业务面板使用 `color.bg.paper`。 |
| 分隔 | 右侧业务面板左边框使用 `color.border.paper`。 |
| 历史入口 | MoreMenu 中「历史对话」打开右侧 HistorySidePanel；面板会占用横向布局宽度。 |
| 内边距 | 一级容器 16px 到 24px，列表项 8px 到 12px。 |
| 字体 | 导航用系统无衬线，品牌/标题可使用 Georgia/Excalifont 气质。 |

## 5. 组件规范

### 5.1 MoreMenu Entrypoints

- MoreMenu 位于 Chat 主界面右上角，由「更多」图标按钮触发。
- 历史对话、工作空间、分享作为同一菜单中的低频入口展示。
- 历史对话使用 `IconClock`，工作空间使用 `IconFolder`，分享使用 `IconShare`。
- 菜单项 hover 使用 `color.bg.surface`，不使用高饱和填充。

### 5.2 Panel Header

| 状态 | 视觉 |
|---|---|
| 默认 | `color.text.secondary`，透明背景。 |
| Hover | 背景轻微加深，文本变为 `color.text.primary`。 |
| Active | 炭黑文本、左线/下划线或浅底选中，不使用橙色填充。 |
| Focus | 可见边框或 ring。 |
| Disabled | 降低对比并显示原因。 |

- HistorySidePanel 头部左侧显示「历史对话」。
- 右侧显示搜索按钮和关闭按钮；搜索按钮打开 HistorySearchDialog，不在侧栏内渲染输入框。
- 关闭按钮只关闭 HistorySidePanel，不改变当前会话。

### 5.3 SessionList

- 会话标题一行截断；默认历史侧栏不展示搜索摘要。
- 当前会话使用 `color.border.focus` 或 `color.text.primary` 强化。
- 未读或进行中状态使用小徽标，不使用大面积背景色。
- 打开 HistorySidePanel 时必须主动加载默认历史；加载中显示「加载历史中...」。
- 空列表显示「暂无会话」，不在历史面板内显示新建入口。
- hover 时可显示删除按钮；删除当前会话后清空当前 Chat 工作区。

### 5.4 HistorySearchDialog

- 点击 HistorySidePanel 头部搜索按钮打开居中弹窗。
- 顶部为无边框搜索输入和关闭按钮；输入为空时显示按时间分组的默认历史列表。
- 弹窗不显示「新聊天」入口；新建会话只由 Chat 顶部「新建」按钮负责。
- 输入后搜索 thread 标题和持久化对话正文；结果显示对话图标、标题、命中摘要和日期。
- 无结果显示「未找到匹配会话」。
- 点击结果关闭弹窗并切换会话。

### 5.5 StatusArea

- Ready 使用 `color.state.success` 小图标或文字。
- Syncing 使用 `color.action.link` 或中性色 spinner。
- Error 使用 `color.state.error` 和修复入口。
- 存储、文件保留、权限等策略文案不得硬编码阈值，需引用产品策略。

### 5.6 UserOrUtilityArea

- 设置、账户、退出等低频操作放在底部或折叠菜单。
- 破坏性操作使用 `color.state.danger`，需要确认或撤销路径。

## 6. 历史面板与搜索交互设计

### 6.1 HistorySidePanel

| 模式 | 规范 |
|---|---|
| 打开 | 点击 MoreMenu 中「历史对话」后右侧展开，打开即加载默认历史。 |
| 关闭 | 点击头部关闭按钮；不清空当前会话。 |
| 默认列表 | 展示所有 thread，按 `updated_at DESC`；标题一行截断。 |
| 当前会话 | 右侧显示 `color.action.link` 小圆点。 |
| 删除 | hover 显示删除按钮；删除动作不进入搜索弹窗。 |
| 加载/空态 | 加载中显示「加载历史中...」；无数据后显示「暂无会话」。 |

### 6.2 HistorySearchDialog

| 区域 | 规范 |
|---|---|
| 触发 | HistorySidePanel 标题栏搜索按钮。 |
| 头部 | 搜索输入 + 关闭按钮；打开时输入框清空并聚焦。 |
| 默认内容 | 输入为空时展示按时间分组的默认历史，不展示新建入口。 |
| 搜索内容 | 输入后显示匹配 thread；摘要来自标题或对话正文命中片段。 |
| 关闭 | 点击关闭、Esc 或遮罩关闭。 |

面板和弹窗开关不改变当前会话，不清空消息列表滚动位置。

## 7. 移动端适配

- 不固定 280px 侧栏。
- HistorySidePanel 在移动端优先变为右侧抽屉或全屏面板。
- HistorySearchDialog 在移动端接近全屏，保留搜索输入和关闭按钮。
- 优先使用顶部轻导航、底部 tab 或抽屉。
- 抽屉打开时使用 `color.bg.overlay` 遮罩。
- 输入 Dock 始终优先于侧栏入口，不被遮挡。

## 8. 色彩规范

| 场景 | Token |
|---|---|
| 侧栏背景 | `color.bg.app`、`color.bg.surfaceSolid` |
| 分隔线 | `color.border.paper` |
| 导航默认 | `color.text.secondary` |
| 导航 active | `color.text.primary`、`color.border.focus` |
| 状态 ready | `color.state.success` |
| 状态 error | `color.state.error` |
| 文件提示 | `color.text.muted`、必要时 `color.state.warning` |

## 9. 暗色模式

- 背景切换为暖黑纸面，不使用冷黑侧栏。
- Active 状态使用反色炭黑 token 或边框，而不是霓虹橙。
- Tooltip、菜单和抽屉必须与主内容保持层级区分。

## 10. 可访问性

- 所有导航项可键盘访问。
- MoreMenu、搜索、关闭、删除等图标按钮必须提供 Tooltip 或 aria-label。
- 当前项需要同时通过语义状态和视觉表达。
- 会话列表的时间、未读、错误不能只靠颜色。

## 11. 验收标准

- HistorySidePanel 的打开、关闭、隐藏、移动端抽屉均有设计要求。
- 历史侧栏初次打开必须显示真实历史或加载态，不得空白。
- HistorySearchDialog 不显示「新聊天」入口。
- 默认、hover、active、focus、disabled、loading、error、empty 状态均可验收。
- 所有颜色引用 [Color System](<./color_system/README.md>)。
- 不包含玫瑰金、Tailwind 原型或外部图标依赖作为必要实现。

## 12. 前端实现备注（2026-05-29 本轮）

**`VerticalNav` 组件已从 `ChatView.tsx` 移除。** 侧边栏功能已重新分配：

- 历史对话入口 → `ChatView.tsx` 右上角「更多」下拉菜单 → 右侧 `HistorySidePanel`
- 历史搜索入口 → `HistorySidePanel` 标题栏搜索按钮 → 居中 `HistorySearchDialog`
- 文件/工作空间入口 → 「更多」菜单 → 右侧 `FileSidebar`
- 新建对话 → 右上角常驻「新建」按钮

`VerticalNav.tsx` 文件保留在代码库中但不再被 `ChatView.tsx` 引用，可在后续需要时复用其展开/折叠 + 内联线程列表的实现模式。

当前 Chat 工作区已无左侧固定导航栏；HistorySidePanel 和 FileSidebar 作为右侧临时工作面板出现。
