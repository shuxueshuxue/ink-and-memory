# Chat History PRD

> 对话历史消息流、工具步骤、Terminal 输出和会话统计的视觉与交互规范。本文引用 [Color System](<./color_system/README.md>)，仅更新 PRD，不修改产品代码。

## 1. 文档范围

Chat History 负责展示一个会话内从用户输入到助手回复、工具调用、终端输出、文件附件和错误反馈的完整时间线。文件级附件详见 [Chat File](<./Chat File.md>)，发送区详见 [Chat Send](<./Chat Send.md>)。

## 2. 设计目标

- 消息流优先服务阅读和追溯，而不是卡片堆叠。
- 工具步骤、终端输出和普通文本有清晰层级。
- 与 `docs/prd/image.png` 中的聊天参考图保持同一视觉方向：暖纸面、轻消息气泡、深色 Terminal、细线工具步骤。
- 所有状态都能被 QA 通过截图和交互路径验证。

## 3. 消息类型与布局

| 消息类型 | 对齐 | 容器 | 视觉规则 |
|---|---|---|---|
| 用户消息 | 右侧或同轴靠右 | 柔和纸面气泡 | 使用 `color.bg.surfaceSolid`，可带小尾巴；不使用大面积橙色。 |
| 助手文本 | 左侧或主轴自然流 | 默认无重卡片 | Markdown 正文使用 `color.text.body`。 |
| 工具步骤 | 左侧 | 可折叠区块 | 2px `color.state.warning` 左线，标题为次级文本。 |
| Terminal 输出 | 左侧全宽 | 深色代码块 | 标题栏、复制按钮、命令、输出、Exit code 分层。 |
| 文件附件 | 随消息 | 文件卡/缩略图 | 遵循 [Chat File](<./Chat File.md>)。 |
| 会话统计 | 居中或底部 | 轻量元信息 | Token、耗时、状态不得压过正文。 |
| 系统错误 | 左侧 | 错误提示块 | `color.state.error` + 明确文本 + 重试入口。 |

## 4. 结构规范

```
ChatHistory
├── ChatHeader
│   └── New Chat / 会话状态
├── MessageList
│   ├── UserMessage
│   ├── AssistantMarkdown
│   ├── ToolStepGroup
│   ├── TerminalBlock
│   ├── FileMessagePart
│   └── ErrorNotice
└── HistoryFooter
    ├── StreamingStatus
    └── SessionStats
```

### 4.1 用户消息

- 最大宽度与输入 Dock 对齐，移动端全宽减去安全边距。
- 文本使用 `color.text.body` 或在深底时使用反色文本。
- 附件位于文本上方或下方，但同一消息内保持 8px 间距。
- 已发送状态可用小型状态文本，不使用持续动画。

### 4.2 助手文本

- 默认无背景，保持纸面阅读感。
- Markdown 标题不使用超大字号，避免破坏消息节奏。
- 链接使用 `color.action.link`，工具或源码相关链接可增加下划线。

### 4.3 工具步骤

- 默认折叠，展示动词短语和摘要。
- 展开后显示参数、执行摘要、输出路径或错误原因。
- 左线使用 `color.state.warning`，不是全局主色。
- Hover 仅改变标题文本或背景透明度，不整体上浮。

### 4.4 TerminalBlock

| 元素 | 规范 |
|---|---|
| 背景 | 深色块，Light/Dark 下都保持代码区高对比。 |
| 标题栏 | `Terminal`、复制按钮、执行状态。 |
| 命令提示 | `$` 可使用 `color.action.link`。 |
| 输出文本 | 浅灰等宽字体。 |
| Exit code | `0` 使用 success，非 0 使用 error。 |

## 5. 状态设计

| 状态 | 设计要求 |
|---|---|
| 空历史 | 显示输入引导和最近入口，不显示假消息。 |
| Streaming | 助手消息位置显示低调光标或省略号，不大面积闪烁。 |
| Tool Running | 工具步骤标题显示进行中状态，左线可低频 pulse。 |
| Tool Success | 收起标题附加成功状态，详情保留可展开。 |
| Tool Error | 展开错误摘要，并提供重试/复制错误信息入口。 |
| Long Output | Terminal 默认限高，支持展开和复制。 |
| Selected Message | 边框或浅背景加强，并保持 focus 可见。 |
| Deleted/Unavailable | 保留时间线占位，说明内容不可用。 |

## 6. 色彩规范

| 场景 | Token |
|---|---|
| 背景 | `color.bg.app`、`color.bg.paper` |
| 消息气泡 | `color.bg.surfaceSolid`、`color.border.paper` |
| 正文 | `color.text.body` |
| 元信息 | `color.text.muted` |
| 工具步骤 | `color.state.warning` |
| Terminal 命令 | `color.action.link` |
| 成功/失败 | `color.state.success`、`color.state.error` |

## 7. 暗色模式

- 消息流整体改为暖黑纸张层级，不改为纯黑聊天室。
- 用户和助手消息仍以层级和对齐区分，不依赖高饱和色。
- Terminal 背景比页面更深，但边框和标题栏要能被看见。
- 工具步骤 warning 色在暗色模式中降低饱和度，避免霓虹效果。

## 8. `image.png` 用途

`image.png` 是本 PRD 的主要视觉参考之一，尤其用于工具步骤和 Terminal 输出的层级判断。本轮不修改图片；若后续生成新版，应补齐文件附件、错误态、暗色模式和移动端截图。

## 9. 可访问性

- 折叠工具步骤必须支持键盘展开/收起。
- Terminal 复制按钮需要 aria label。
- Streaming 状态需要文本等价说明。
- 成功/失败不能只依赖颜色。

## 10. 验收标准

- 每类消息均有对齐、容器、色彩和状态定义。
- 工具步骤和 Terminal 输出与 [Color System](<./color_system/README.md>) 保持一致。
- PRD 不包含与当前项目冲突的 Tailwind 类和独立 HTML 原型。
- `image.png` 未被覆盖，仅作为参考。

## 11. 前端实现备注

本 PRD 不要求实现。后续实现应优先抽象消息类型渲染和工具步骤折叠逻辑，避免在不同消息组件中复制终端、附件和状态展示。
