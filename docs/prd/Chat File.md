# Chat File PRD

> 聊天输入区和消息流中的文件/附件体验规范。本文引用 [Color System](<./color_system/README.md>)，仅更新 PRD，不修改产品代码。

## 1. 文档范围

Chat File 覆盖对话中的附件选择、拖拽上传、文件预览、消息内文件展示、上传反馈和错误处理。更完整的文件工作区见 [FIle work](<./FIle work.md>)。

旧稿中“数字资产管理系统”“奢华功能主义”“Tailwind + Font Awesome”的方案不作为当前项目规范。

## 2. 设计目标

- 文件体验服务于对话，不抢占聊天主流程。
- 文件卡片与输入 Dock、消息气泡保持同一纸张视觉语言。
- 上传、失败、删除、禁用等状态可被产品、设计、前端和 QA 明确验证。
- 文件类型色只作为辅助标记，不制造新的品牌色。

## 3. 信息架构

```
ChatFileExperience
├── AddEntry
│   ├── Upload files
│   ├── Recent files
│   └── Workspace files
├── AttachmentTray
│   ├── ImagePreviewCard
│   ├── DocumentFileCard
│   └── UploadProgressCard
├── MessageFilePart
│   ├── InlineThumbnail
│   ├── FileMetadata
│   └── Open/Download/Remove actions
└── PreviewOverlay
    ├── Image preview
    ├── Text/code preview
    └── Error fallback
```

## 4. 组件规范

### 4.1 AddEntry

- 位于输入 Dock 左下方或附件菜单中。
- 默认使用 `color.text.secondary`，hover 使用 `color.text.primary`。
- 图标使用项目已有图标库风格，避免引入外部图标依赖。

### 4.2 AttachmentTray

- 条件显示：当用户已选择或拖入文件时出现。
- 位置：输入框上方，保持与输入 Dock 同宽。
- 背景：`color.bg.surface`，边框：`color.border.paper`。
- 文件卡之间保持 8px 到 12px 间距，长文件名需要中间截断。

### 4.3 ImagePreviewCard

| 属性 | 规范 |
|---|---|
| 缩略图 | 方形或 4:3，保持原图比例，不裁掉关键信息。 |
| 边框 | `color.border.neutral`。 |
| Hover | 显示查看和移除操作。 |
| 加载中 | 半透明遮罩 + 低频 spinner 或进度条。 |

### 4.4 DocumentFileCard

- 文件图标使用类型色小面积标记。
- 文件名、扩展名、大小、上传状态分层展示。
- 失败时保留文件名，并显示失败原因和重试/移除操作。

### 4.5 MessageFilePart

- 消息中附件不应撑破消息宽度。
- 图片可显示缩略图，点击进入预览。
- 非图片文件以纸面卡片展示，主信息优先：文件名、类型、大小、状态。
- 多附件按网格或横向列表展示，移动端改为单列。

## 5. 文件类型色规则

| 类型 | 推荐 token | 使用范围 |
|---|---|---|
| 图片 | `color.voice.blue` | 缩略图角标、图标。 |
| 文档 | `color.voice.green` | 文件类型图标。 |
| 表格/数据 | `color.voice.yellow` | 文件类型图标或小徽标。 |
| 代码/终端 | `color.text.primary` | 深色代码块或等宽文本。 |
| 未知类型 | `color.text.secondary` | 中性图标。 |
| 危险/失败 | `color.state.error` 或 `color.state.danger` | 错误、删除。 |

类型色不得作为大面积卡片背景。

## 6. 交互状态

| 状态 | 视觉与行为 |
|---|---|
| 空状态 | Add 入口可见，附件托盘不占位。 |
| Drag Over | 输入 Dock 或文件区域出现虚线边框，使用 `color.action.link` 或 `color.state.warning` 小面积提示。 |
| Uploading | 文件卡显示进度和禁用移除以外的主要发送动作。 |
| Uploaded | 显示成功状态，发送按钮恢复可用。 |
| Error | 文件卡显示错误文本、重试和移除；使用 `color.state.error`。 |
| Disabled | 上传中、网络不可用或权限不足时，入口降级并显示原因。 |
| Hover | 显示查看、移除等次级操作，不改变卡片尺寸。 |
| Selected | 预览中的文件使用边框加强和可见 focus。 |

## 7. 明暗模式

- Light：文件卡使用 `color.bg.surfaceSolid`，附件托盘使用 `color.bg.surface`。
- Dark：文件卡使用 Dark `color.bg.surfaceSolid`，缩略图边框使用 Dark `color.border.neutral`。
- 上传进度、错误、成功都使用语义状态色的 Dark 映射。
- 文件缩略图不加深色滤镜；仅外围容器切换。

## 8. 错误与边界

- 超出大小、格式不支持、上传失败、预览失败都需要独立文案。
- 文件名过长时保留扩展名。
- 删除附件需要即时反馈；若已发送消息中的文件不可删除，应显示只读状态。
- 不要在 PRD 中硬编码文件大小阈值；阈值应来自配置或产品策略。

## 9. 可访问性

- 文件卡、移除按钮、预览按钮必须有可读 label。
- 上传进度需要文本或 aria 状态。
- 错误不能只用红色表达。
- 拖拽上传必须有点击选择文件的替代路径。

## 10. 验收标准

- 附件入口、预览、上传、错误、删除、禁用、hover、selected 状态均有明确设计规则。
- 文件色彩全部映射到 [Color System](<./color_system/README.md>)。
- 不包含 Tailwind 原型、Font Awesome 或外部资源依赖。
- 未对 `docs/prd/image.png` 做任何覆盖。

## 11. 前端实现备注

本 PRD 不要求实现。后续实现应优先复用聊天输入 Dock、消息列表和现有上传/文件 API 抽象；文件大小、格式和保留策略不得写死在组件中。
