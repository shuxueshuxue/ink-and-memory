# Dark Mode PRD

> Ink & Memory 聊天与文件 PRD 的暗色模式设计规范。本文引用 [Color System](<./color_system/README.md>)，仅更新 PRD，不修改产品代码。

## 1. 文档范围

Dark Mode 定义聊天 Dashboard、Sidebar、History、Send、File 和 File Work 在暗色模式下的视觉目标、token 映射、组件状态和验收标准。

当前产品源码尚未提供完整暗色模式实现；本文是设计目标，不声称功能已经存在。

## 2. 设计原则

- 保留纸张和笔记本气质：暗色模式应是“夜间纸张”，不是赛博控制台。
- 统一语义 token：所有模块使用 [Color System](<./color_system/README.md>) 的 Dark 值，不在模块内新增孤立色值。
- 降低装饰亮度：状态色只做小面积提示，不使用霓虹 glow。
- 阅读优先：正文对比度、Terminal 可读性、文件预览辨识度必须高于装饰。

## 3. Token 映射

| 语义 | Light | Dark 目标 | 用途 |
|---|---:|---:|---|
| `color.bg.app` | `#f8f0e6` | `#1f1b16` | 页面背景。 |
| `color.bg.paper` | `#fffef9` | `#2a251e` | 主纸面、输入 Dock。 |
| `color.bg.surface` | `rgba(255,255,255,0.5)` | `rgba(42,37,30,0.82)` | 次级面板。 |
| `color.bg.surfaceSolid` | `#ffffff` | `#332d25` | 菜单、卡片。 |
| `color.border.paper` | `#d0c4b0` | `#5a4d3d` | 暖色边框。 |
| `color.border.neutral` | `#e0e0e0` | `#4a4238` | 控件边框。 |
| `color.text.primary` | `#2c2c2c` | `#f3eee6` | 标题、active。 |
| `color.text.body` | `#333333` | `#eee8df` | 正文。 |
| `color.text.secondary` | `#666666` | `#c8bcae` | 次级文本。 |
| `color.text.muted` | `#8a7a69` | `#9f9283` | 弱提示。 |
| `color.action.link` | `#4a90e2` | `#81b7d2` | 链接、发送可用态。 |
| `color.state.warning` | `#f39c12` | `#f7c96a` | 工具步骤、提醒。 |
| `color.state.success` | `#4CAF50` | `#7bcf8f` | 成功。 |
| `color.state.error` | `#f44336` | `#ff7a70` | 错误。 |
| `color.state.danger` | `#d44` | `#ff8a7f` | 删除、破坏性。 |

## 4. 模块适配

### 4.1 Chat Dashboard

- 页面背景使用 Dark `color.bg.app`。
- 主内容和输入 Dock 使用 Dark `color.bg.paper`。
- 快捷卡片使用 Dark `color.bg.surfaceSolid`。
- `New Chat` 使用 `color.text.primary`，hover 使用低透明浅色底。

### 4.2 Chat History

- 助手正文不使用纯黑卡片，保留纸面阅读。
- 用户消息通过对齐、边框或浅层纸面区分。
- 工具步骤 warning 左线降低饱和度，不出现发光线。
- Terminal 背景可更深，但标题栏、复制按钮和输出文字必须可辨。

### 4.3 Chat Send

- 输入 Dock 使用 Dark `color.bg.paper`，边框使用 Dark `color.border.paper`。
- Placeholder 使用 Dark `color.text.muted`，但对比度必须足够。
- SendButton 可用态使用 Dark `color.action.link` 或反色主操作。
- 发送中不使用高频闪烁。

### 4.4 Chat File 与 File Work

- 文件卡使用 Dark `color.bg.surfaceSolid`。
- 文件类型色只用于图标/徽标。
- 图片缩略图保持原图，不叠加暗色滤镜。
- 上传、成功、失败状态使用 Dark 状态色，同时有文本说明。

### 4.5 Chat Sidebar

- 侧栏背景可比主画布略亮或略暗，但必须保留边界。
- Active 使用文本/边框强化，不使用橙色填充。
- 抽屉遮罩使用 Dark `color.bg.overlay`。

## 5. 组件状态

| 状态 | 暗色模式规范 |
|---|---|
| Hover | 使用低透明浅色背景或边框增强，不用 glow。 |
| Focus | 使用 `color.border.focus` 的 Dark 值，键盘可见。 |
| Selected | 文本变为 `color.text.primary`，可附加边框/左线。 |
| Disabled | 保持可读说明，背景和文本同时降级。 |
| Loading | 低频 pulse 或 spinner，亮度不刺眼。 |
| Error | `color.state.error` + 文本原因 + 重试。 |
| Success | `color.state.success` + 完成文案。 |

## 6. 可访问性

- 正文、按钮、输入文本对背景至少满足 WCAG AA。
- Terminal 输出不能使用过低对比的灰色。
- 状态必须有颜色之外的文本或图标说明。
- 系统偏好 `prefers-color-scheme` 只能作为默认值，用户选择应可覆盖。

## 7. 禁止用法

- 禁止使用旧稿中的深空黑 `#0F0F12` + 霓虹橙 `#FF6B00` 作为暗色品牌。
- 禁止斜切角、噪点、内发光、强 glow 作为核心语言。
- 禁止把所有卡片变成纯黑高对比盒子。
- 禁止图片预览统一加暗色滤镜。

## 8. 验收标准

- 所有暗色颜色均来自 [Color System](<./color_system/README.md>)。
- Dashboard、Sidebar、History、Send、File、File Work 均有暗色适配说明。
- Hover、Focus、Selected、Disabled、Loading、Error、Success 状态均可验收。
- 文档明确说明当前为设计目标，不声称源码已实现。

## 9. 前端实现备注

本 PRD 不要求本轮实现。后续实现建议先建立主题状态和语义 token，再逐步替换现有 inline style；避免在单个组件内直接写死暗色值。
