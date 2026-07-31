# File Work PRD

> 工作区文件管理、上传、保留提示、文件列表和文件操作的产品与视觉规范。本文引用 [Color System](<./color_system/README.md>)，仅更新 PRD，不修改产品代码。

## 1. 文档范围

File Work 覆盖聊天外的文件工作区体验，包括上传入口、文件列表、预览、搜索/筛选、文件状态、保留/权限提示和批量操作。聊天消息中的附件规范见 [Chat File](<./Chat File.md>)。

当前文件名保留为 `FIle work.md`，本轮不重命名，以避免破坏用户指定路径。

## 2. 设计目标

- 让文件管理像当前产品的纸张工作台，而不是独立资产管理系统。
- 上传和文件状态清晰，错误可恢复。
- 文件保留、权限和限制文案不硬编码阈值；具体策略由产品配置或后端策略提供。
- 文件工作区与 Chat Dashboard、Sidebar、Send 使用同一色彩和层级系统。

## 3. 信息架构

```
FileWork
├── FileHeader
│   ├── Title
│   ├── Retention/Permission notice
│   └── Upload action
├── UploadZone
│   ├── Empty drop area
│   ├── Drag over state
│   └── Upload progress
├── FileToolbar
│   ├── Search
│   ├── Type filters
│   └── Sort
├── FileList
│   ├── FileRow / FileCard
│   └── Empty / Loading / Error
└── FilePreview
    ├── Image/Text preview
    ├── Metadata
    └── Actions
```

## 4. 页面布局

| 区域 | 桌面端 | 移动端 |
|---|---|---|
| Header | 标题、策略提示、上传按钮横向排列 | 标题在上，操作折叠为菜单 |
| UploadZone | 主区域上方或右侧面板，虚线纸面 | 全宽，紧凑高度 |
| FileToolbar | 搜索、筛选、排序同一行 | 搜索优先，筛选进入底部抽屉 |
| FileList | 表格或卡片列表 | 单列卡片 |
| Preview | 右侧或弹窗 | 全屏弹层 |

## 5. 组件规范

### 5.1 FileHeader

- 标题使用 `color.text.primary`。
- 策略提示使用 `color.text.secondary`；重要提醒可用 `color.state.warning` 小图标。
- 上传主操作使用 `color.action.primary` 或 `color.action.link`，不使用亮橙填充。

### 5.2 UploadZone

| 状态 | 规范 |
|---|---|
| Empty | `color.bg.surface` 背景，`color.border.paper` 虚线边框。 |
| Hover | 边框加深，背景轻微增强。 |
| Drag Over | 使用 `color.action.link` 或 `color.state.warning` 边框提示。 |
| Uploading | 显示文件数、进度、可取消入口。 |
| Success | 短暂 success 提示后进入文件列表。 |
| Error | 保留失败文件项和错误原因。 |

### 5.3 FileToolbar

- 搜索框使用纸面输入样式，placeholder 使用 `color.text.muted`。
- 筛选 chip 默认中性，选中态使用 `color.text.primary` 和边框加强。
- 排序菜单使用 `color.bg.surfaceSolid`，hover 不改变高度。

### 5.4 FileList

| 元素 | 规范 |
|---|---|
| 文件名 | 主文本，单行截断但保留扩展名。 |
| 元信息 | 大小、类型、更新时间、来源使用 `color.text.muted`。 |
| 类型图标 | 使用 `color.voice.*` 小面积标记。 |
| 状态 | 上传中、处理中、可用、失败、已过期都需文本。 |
| 操作 | 预览、插入聊天、下载、删除；低频操作收进菜单。 |

### 5.5 FilePreview

- 图片保持原始比例，背景使用纸面或中性格纹，不使用暗滤镜。
- 文本/代码预览使用等宽字体和可复制操作。
- 不可预览时显示文件图标、元信息和下载/插入入口。

## 6. 色彩规范

| 场景 | Token |
|---|---|
| 页面背景 | `color.bg.app` |
| 上传区/列表纸面 | `color.bg.surface`、`color.bg.surfaceSolid` |
| 边框 | `color.border.paper`、`color.border.neutral` |
| 主文案 | `color.text.primary` |
| 元信息 | `color.text.muted` |
| 主操作 | `color.action.primary`、`color.action.link` |
| 上传成功 | `color.state.success` |
| 上传失败 | `color.state.error` |
| 删除 | `color.state.danger` |
| 策略提醒 | `color.state.warning` |

## 7. 文件状态

| 状态 | 设计要求 |
|---|---|
| Empty | 显示上传入口、支持格式入口和策略提示，不展示虚构文件。 |
| Loading | 列表 skeleton 或 spinner，保留 Header 和 Toolbar。 |
| Uploading | 进度可见，可取消；发送/插入依赖上传完成。 |
| Processing | 使用中性进行中状态，不承诺完成时间。 |
| Ready | 显示可预览和可插入操作。 |
| Failed | 错误原因、重试、删除入口。 |
| Expired/Unavailable | 灰化但保留历史元信息和原因。 |
| Selected | 边框/背景加强，同时支持键盘选择。 |

## 8. 明暗模式

- 暗色模式保持暖黑纸张背景。
- 上传区、文件列表、预览层使用 Dark `color.bg.surface`/`surfaceSolid`。
- 文件类型色降低饱和，仅用于图标和徽标。
- 删除和错误状态保留文本说明。

## 9. 策略与文案约束

- 不在 PRD 中写死文件留存天数、大小上限、格式白名单或付费策略值。
- 文案应引用“产品策略/配置返回值”或“系统策略文案”。
- 若策略未知，PRD 只描述展示位置和信息层级。

## 10. 可访问性

- 上传区必须支持点击选择文件，不能只依赖拖拽。
- 文件行支持键盘选择和操作菜单。
- 预览弹窗可用 Escape 关闭，焦点回到触发项。
- 状态文本需要读屏可读，不能只用颜色或图标。

## 11. 验收标准

- 上传区、Toolbar、文件列表、预览、策略提示和操作菜单均有视觉规则。
- Empty、Loading、Uploading、Processing、Ready、Failed、Expired、Selected 状态均可验收。
- 所有颜色来自 [Color System](<./color_system/README.md>)。
- 文档不再包含与本项目无关的 Python 架构分析内容。

## 12. 前端实现备注

本 PRD 不要求实现。后续实现应复用 Chat File 的附件卡和预览模式；文件策略、权限、大小、类型限制必须来自配置或服务端返回，不得写死在 UI。
