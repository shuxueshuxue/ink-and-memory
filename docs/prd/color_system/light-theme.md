# Light Theme 亮色主题设计稿

> Source of truth: `frontend/src/styles/tokens.css` `:root` 块。  
> 触发方式：默认状态 / `[data-theme='light']` / `prefers-color-scheme` 无暗色偏好。
> [Sync] 2026-07-09: Connector settings pages use a dashed paper page boundary plus flat light-list rows; selected resources use a right-side checkmark, and ordinary resource rows do not use card shadows or dark fills.
> [Sync] 2026-07-09: Decks follows the same light paper rule: deck colors are small accents, not full-card borders, gradients, or hover shadows.

---

## 1. 视觉语言

Ink & Memory 亮色主题的关键词是 **"暖纸张、手写笔记本、安静工具台"**。

| 维度 | 规范 |
|---|---|
| 画布 | 暖米色 `#f8f0e6`，避免纯白全屏和冷灰渐变。 |
| 承载面 | 奶油纸面 `#fffef9`；设置详情页和 Decks 页面使用留白、轻纸面列表和单一虚线页边界，避免多层面板堆叠。 |
| 文本 | 主文本炭黑 `#2c2c2c`，正文深灰 `#333`，辅助棕灰；禁止亮橙作正文强调。 |
| 字体 | 英文优先 `Excalifont`/Georgia，中文优先 `Xiaolai`，控件用系统无衬线。 |
| 边框 | 纸面分隔线 `#d0c4b0`（暖棕），控件线 `#e0e0e0`（中性灰）。 |
| 圆角 | 卡片/弹窗 4–12 px；聊天 Dock 16 px。 |
| 动效 | hover/focus 0.2–0.3 s；无大幅旋转、强 glow、持续闪烁。 |

---

## 2. 品牌基础色板（亮色）

| 色板名 | 色值 | 用途 |
|---|---:|---|
| Warm Canvas | `#f8f0e6` | App 整体背景。 |
| Paper Surface | `#fffef9` | 编辑区、消息流、弹窗主体。 |
| Soft Surface | `rgba(255,255,255,0.5)` | 设置轻分区、文件信息组、低强调列表容器。 |
| Solid Surface | `#ffffff` | 菜单、Tooltip、Popover。 |
| Charcoal | `#2c2c2c` | 主文本、主操作、焦点线。 |
| Ink Text | `#333333` | 正文内容。 |
| Secondary Text | `#666666` | 元信息、图标默认。 |
| Muted Text | `#8a7a69` | placeholder、时间戳、说明。 |
| Paper Border | `#d0c4b0` | 纸面页边界、输入区、分隔线；可经 `color-mix` 派生虚线边界。 |
| Neutral Border | `#e0e0e0` | 工具条按钮、文件卡边框。 |
| Link Blue | `#4a90e2` | 链接、发送可用态。 |
| Link Blue Hover | `#357abd` | 链接/发送按钮 hover 态。 |
| Success Green | `#4CAF50` | 成功 toast、在线状态。 |
| Success Hover | `#45a049` | 头像按钮 hover 态。 |
| Error Red | `#f44336` | 错误 toast、失败反馈。 |
| Danger Red | `#dd4444` | 删除、破坏性操作。 |
| Danger Hover | `#bb3333` | 删除按钮 hover 态。 |
| Attention Yellow | `#f39c12` | 工具步骤左线、提醒标记。 |
| Code Surface | `#2c2c2c` | 代码块背景（与 Charcoal 同色）。 |
| Code Text | `#f3eee6` | 代码块前景（与 Warm Canvas 同色）。 |
| Disabled | `#cccccc` | 禁用态背景。 |
| Scrollbar Thumb | `#cccccc` | 滚动条滑块。 |
| Scrollbar Hover | `#999999` | 滚动条滑块 hover。 |

---

## 3. 语义 Token 完整列表（亮色值）

| CSS 变量 | 亮色值 | 语义用途 |
|---|---:|---|
| `--color-bg-app` | `#f8f0e6` | App 背景 |
| `--color-bg-paper` | `#fffef9` | 主阅读/编辑面 |
| `--color-bg-surface` | `rgba(255,255,255,0.5)` | 次级半透明承载面 / 轻分区 |
| `--color-bg-surface-solid` | `#ffffff` | 不透明浮层 |
| `--color-bg-overlay` | `rgba(0,0,0,0.5)` | Modal 遮罩 |
| `--color-bg-hover` | `rgba(0,0,0,0.05)` | 控件 hover 叠层 |
| `--color-border-paper` | `#d0c4b0` | 暖纸边框 |
| `--color-border-neutral` | `#e0e0e0` | 中性控件边框 |
| `--color-border-focus` | `#2c2c2c` | 键盘焦点线 |
| `--color-text-primary` | `#2c2c2c` | 标题、主操作文案 |
| `--color-text-body` | `#333333` | 正文内容 |
| `--color-text-secondary` | `#666666` | 元信息、图标默认 |
| `--color-text-muted` | `#8a7a69` | placeholder、时间戳 |
| `--color-text-on-action` | `#ffffff` | 深色按钮上的前景 |
| `--color-action-primary` | `#2c2c2c` | 主按钮背景/当前导航 |
| `--color-action-link` | `#4a90e2` | 链接、发送可用 |
| `--color-action-link-hover` | `#357abd` | 链接/发送 hover |
| `--color-state-success` | `#4CAF50` | 成功态 |
| `--color-state-success-hover` | `#45a049` | 成功态 hover |
| `--color-state-warning` | `#f39c12` | 提醒/工具步骤 |
| `--color-state-error` | `#f44336` | 错误态 |
| `--color-state-danger` | `#dd4444` | 破坏性操作 |
| `--color-state-danger-hover` | `#bb3333` | 破坏性操作 hover |
| `--color-disabled-bg` | `#cccccc` | 禁用态背景 |
| `--color-shadow-soft` | `rgba(0,0,0,0.08)` | 少量卡片 / 浮层轻阴影；普通列表行不用 |
| `--color-shadow-medium` | `rgba(0,0,0,0.15)` | Popover/菜单阴影 |
| `--color-scrollbar-thumb` | `#cccccc` | 滚动条滑块 |
| `--color-scrollbar-thumb-hover` | `#999999` | 滚动条滑块 hover |
| `--color-voice-blue` | `#4a90e2` | 蓝色声部 |
| `--color-voice-purple` | `#9b59b6` | 紫色声部（创意/洞察）|
| `--color-voice-pink` | `#e91e63` | 粉色声部（情绪/关系）|
| `--color-voice-green` | `#27ae60` | 绿色声部（成长/正向）|
| `--color-voice-yellow` | `#f39c12` | 黄色声部（提醒/重点）|
| `--color-code-bg` | `#2c2c2c` | 代码块背景 |
| `--color-code-text` | `#f3eee6` | 代码块前景 |
| `--color-code-inline-bg` | `rgba(0,0,0,0.08)` | 行内代码背景 |

---

## 4. 高亮色（亮色）

水彩笔刷高亮，作为 SVG background-image URL 内嵌颜色，不写入全局 token：

| 类名 | 颜色值 | 用途 |
|---|---:|---|
| `.voice-highlight-yellow` | `#ffff43` | 黄色水彩高亮 |
| `.voice-highlight-blue` | `#a3d5ff` | 蓝色水彩高亮 |
| `.voice-highlight-pink` | `#ffb3d9` | 粉色水彩高亮 |
| `.voice-highlight-green` | `#b3ffb3` | 绿色水彩高亮 |
| `.voice-highlight-purple` | `#ddb3ff` | 紫色水彩高亮 |

---

## 5. 组件级衍生变量（亮色）

作用域限于对应组件类，不写入全局 `:root`：

| 变量名 | 宿主类 | 派生规则 | 亮色效果 |
|---|---|---|---|
| `--notebook-margin-line` | `.notebook-lines` | `color-mix(in srgb, var(--color-state-error) 24%, transparent)` | 淡红色页边线 |
| `--notebook-rule-line` | `.notebook-lines` | `color-mix(in srgb, var(--color-border-paper) 58%, transparent)` | 淡棕色横格线 |

---

## 6. 使用规则

- 页面背景 `--color-bg-app`；内容区 `--color-bg-paper`；轻分区 / 轻列表容器 `--color-bg-surface` 或 `--color-bg-paper` 透明混合。
- 链接/发送可用 `--color-action-link`；hover 用 `--color-action-link-hover`。
- 主操作按钮背景 `--color-action-primary`，前景 `--color-text-on-action`。
- 状态色小面积使用，不单独用颜色传达信息（需配文字或图标）。
- 不新增孤立十六进制；新需求先映射到现有 token。
- Settings 连接器详情页只保留一个 `--color-border-paper` 派生的虚线页边界；资源行使用透明或浅纸面列表容器、细分隔线和右侧对勾表达选中态，不使用深色背景、外框卡片或投影。
- Decks 页面只保留页面级虚线纸边界；deck item 使用浅纸面容器、细边界和小面积 accent，主按钮使用炭黑 / 纸面反差，不使用渐变图标、彩色整卡边框或普通 item 阴影。

---

## 7. 浮层 / Popover / Dropdown 配色

所有悬浮弹层（下拉菜单、Tooltip、Popover、@Agent Dropdown 等）遵循统一规范：

| 属性 | Token | 亮色值 | 说明 |
|---|---|---:|---|
| 背景 | `--color-bg-surface-solid` | `#ffffff` | 不透明弹层，确保内容可读。 |
| 边框 | `--color-border-neutral` | `#e0e0e0` | 中性细线，与背景区分。 |
| 阴影 | `--color-shadow-medium` | `rgba(0,0,0,0.15)` | 浮层层次感。 |
| 项目 hover 背景 | `--color-bg-hover` | `rgba(0,0,0,0.05)` | 低对比度叠层，不抢主视觉。 |
| 项目选中/激活背景 | `--color-bg-active` | `rgba(74,144,226,0.12)` | 键盘/鼠标选中项。 |
| 文字主 | `--color-text-body` | `#333333` | 条目名称。 |
| 文字次 | `--color-text-secondary` | `#666666` | 描述/元信息。 |

> `AgentDropdown`、`TopNavBar` 用户菜单、`CalendarPopup` 条目卡、`LeftToolbar` Tooltip 均遵循此规范。
