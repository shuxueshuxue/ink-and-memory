# Dark Theme 暗色主题设计稿

> Source of truth: `frontend/src/styles/tokens.css` `[data-theme='dark']` 块。  
> 触发方式：`[data-theme='dark']`（用户手动切换）；系统偏好暗色时 `prefers-color-scheme: dark` 自动生效（`:root:not([data-theme='light'])`）。  
> 切换入口：`TopNavBar` 右侧 🌙/☀️ 按钮 → 调用 `utils/theme.ts` `toggleTheme()`，持久化到 `localStorage`（键名 `ink-theme`）。
> [Sync] 2026-07-09: Connector settings pages use a dashed deep-paper boundary plus flat low-contrast list rows; selected resources use a right-side checkmark, and ordinary resource rows do not use stacked dark cards or dark selected fills.
> [Sync] 2026-07-09: Decks follows the same low-contrast dark paper rule: deck colors are small accents, not full-card borders, gradients, or hover shadows.

---

## 1. 视觉语言

Ink & Memory 暗色主题的关键词是 **"暖夜纸张、烛光书桌、深棕静谧"**。

| 维度 | 规范 |
|---|---|
| 画布 | 深暖棕 `#1f1b16`，避免纯黑 `#000` 和冷蓝深色（`#0d1117` 只用于代码块）。 |
| 承载面 | 深纸面 `#2a251e`，比画布亮一档；设置详情页和 Decks 页面以单一虚线页边界、轻列表和留白保持层次。 |
| 文本 | 主文本暖白 `#f3eee6`，正文 `#eee8df`，辅助 `#c8bcae`；文字偏暖不偏冷。 |
| 字体 | 与亮色完全一致（`Excalifont` / `Xiaolai` / 系统无衬线）。 |
| 边框 | 纸面分隔线 `#5a4d3d`（深棕），控件线 `#4a4238`（深暖灰）。 |
| 圆角 | 与亮色完全一致（4–12 px / Dock 16 px）。 |
| 动效 | 与亮色完全一致（0.2–0.3 s；无强 glow）。 |

> **设计原则**：暗色不是对亮色的简单反色——背景走暖棕而非冷灰，文字走暖白而非纯白，保持与亮色"同一本笔记本"的视觉连续性。

---

## 2. 品牌基础色板（暗色）

| 色板名 | 色值 | 用途 |
|---|---:|---|
| Warm Night Canvas | `#1f1b16` | App 整体背景。 |
| Night Paper | `#2a251e` | 编辑区、消息流、弹窗主体。 |
| Dim Surface | `rgba(42,37,30,0.82)` | 设置轻分区、文件信息组、低强调列表容器。 |
| Solid Night | `#332d25` | 菜单、Tooltip、Popover。 |
| Warm White | `#f3eee6` | 主文本、主操作、焦点线。 |
| Soft White | `#eee8df` | 正文内容。 |
| Warm Gray | `#c8bcae` | 元信息、图标默认。 |
| Dim Tan | `#9f9283` | placeholder、时间戳、说明。 |
| Deep Paper Border | `#5a4d3d` | 深纸页边界、输入区、分隔线；可经 `color-mix` 派生虚线边界。 |
| Deep Neutral Border | `#4a4238` | 工具条按钮、文件卡边框。 |
| Muted Blue | `#81b7d2` | 链接、发送可用态。 |
| Muted Blue Hover | `#6aa3bf` | 链接/发送按钮 hover 态。 |
| Sage Green | `#7bcf8f` | 成功 toast、在线状态。 |
| Sage Hover | `#5abd72` | 头像按钮 hover 态。 |
| Warm Red | `#ff7a70` | 错误 toast、失败反馈。 |
| Soft Danger | `#ff8a7f` | 删除、破坏性操作。 |
| Danger Hover | `#e06060` | 删除按钮 hover 态。 |
| Amber | `#f7c96a` | 工具步骤左线、提醒标记。 |
| Code Night | `#0d1117` | 代码块背景（GitHub dark 风格）。 |
| Code Cream | `#e6edf3` | 代码块前景。 |
| Disabled Dark | `#58504a` | 禁用态背景。 |
| Scrollbar Thumb | `#4a4238` | 滚动条滑块。 |
| Scrollbar Hover | `#6a5e52` | 滚动条滑块 hover。 |

---

## 3. 语义 Token 完整列表（暗色值）

| CSS 变量 | 暗色值 | 语义用途 |
|---|---:|---|
| `--color-bg-app` | `#1f1b16` | App 背景 |
| `--color-bg-paper` | `#2a251e` | 主阅读/编辑面 |
| `--color-bg-surface` | `rgba(42,37,30,0.82)` | 次级半透明承载面 / 轻分区 |
| `--color-bg-surface-solid` | `#332d25` | 不透明浮层 |
| `--color-bg-overlay` | `rgba(0,0,0,0.72)` | Modal 遮罩（比亮色更重）|
| `--color-bg-hover` | `rgba(255,255,255,0.08)` | 控件 hover 叠层 |
| `--color-border-paper` | `#5a4d3d` | 暖纸边框 |
| `--color-border-neutral` | `#4a4238` | 中性控件边框 |
| `--color-border-focus` | `#f3eee6` | 键盘焦点线（暖白反转）|
| `--color-text-primary` | `#f3eee6` | 标题、主操作文案 |
| `--color-text-body` | `#eee8df` | 正文内容 |
| `--color-text-secondary` | `#c8bcae` | 元信息、图标默认 |
| `--color-text-muted` | `#9f9283` | placeholder、时间戳 |
| `--color-text-on-action` | `#ffffff` | 深色按钮上的前景（不变）|
| `--color-action-primary` | `#f3eee6` | 主按钮背景/当前导航 |
| `--color-action-link` | `#81b7d2` | 链接、发送可用 |
| `--color-action-link-hover` | `#6aa3bf` | 链接/发送 hover |
| `--color-state-success` | `#7bcf8f` | 成功态 |
| `--color-state-success-hover` | `#5abd72` | 成功态 hover |
| `--color-state-warning` | `#f7c96a` | 提醒/工具步骤 |
| `--color-state-error` | `#ff7a70` | 错误态 |
| `--color-state-danger` | `#ff8a7f` | 破坏性操作 |
| `--color-state-danger-hover` | `#e06060` | 破坏性操作 hover |
| `--color-disabled-bg` | `#58504a` | 禁用态背景 |
| `--color-shadow-soft` | `rgba(0,0,0,0.32)` | 少量卡片 / 浮层轻阴影；普通列表行不用 |
| `--color-shadow-medium` | `rgba(0,0,0,0.45)` | Popover/菜单阴影 |
| `--color-scrollbar-thumb` | `#4a4238` | 滚动条滑块 |
| `--color-scrollbar-thumb-hover` | `#6a5e52` | 滚动条滑块 hover |
| `--color-voice-blue` | `#81b7d2` | 蓝色声部 |
| `--color-voice-purple` | `#c99be1` | 紫色声部 |
| `--color-voice-pink` | `#ff8fbd` | 粉色声部 |
| `--color-voice-green` | `#7bdba0` | 绿色声部 |
| `--color-voice-yellow` | `#f7c96a` | 黄色声部 |
| `--color-code-bg` | `#0d1117` | 代码块背景 |
| `--color-code-text` | `#e6edf3` | 代码块前景 |
| `--color-code-inline-bg` | `rgba(0,0,0,0.18)` | 行内代码背景 |

---

## 4. 高亮色（暗色）

暗色下水彩笔刷降低不透明度，避免在深背景上过曝：

| Token | 暗色值 | 用途 |
|---|---:|---|
| `color.highlight.blue` | `rgba(129,183,210,0.38)` | 蓝色文本高亮背景 |
| `color.highlight.pink` | `rgba(255,143,189,0.34)` | 粉色文本高亮背景 |
| `color.highlight.green` | `rgba(123,219,160,0.30)` | 绿色文本高亮背景 |
| `color.highlight.yellow` | `rgba(247,201,106,0.36)` | 黄色文本高亮背景 |
| `color.highlight.purple` | `rgba(201,155,225,0.34)` | 紫色文本高亮背景 |

---

## 5. 组件级衍生变量（暗色效果）

作用域限于对应组件类，不写入全局 `:root`；颜色自动跟随 token 切换：

| 变量名 | 暗色计算效果 | 视觉效果 |
|---|---|---|
| `--notebook-margin-line` | `color-mix(in srgb, #ff7a70 24%, transparent)` | 极淡暖红页边线 |
| `--notebook-rule-line` | `color-mix(in srgb, #5a4d3d 58%, transparent)` | 极淡深棕横格线 |

---

## 6. 亮色 → 暗色映射关系

| 亮色语义 | 亮色值 | 暗色值 | 映射逻辑 |
|---|---:|---:|---|
| 暖纸背景 | `#f8f0e6` | `#1f1b16` | 同色相翻转明度 |
| 纸面 | `#fffef9` | `#2a251e` | 同色相翻转明度 |
| 弹层 | `#ffffff` | `#332d25` | 纯白 → 深暖棕 |
| 主文本 | `#2c2c2c` | `#f3eee6` | 炭黑 ↔ 暖白 |
| 正文 | `#333333` | `#eee8df` | 深灰 ↔ 浅暖灰 |
| 链接蓝 | `#4a90e2` | `#81b7d2` | 饱和蓝 → 低饱和蓝（护眼）|
| 成功绿 | `#4CAF50` | `#7bcf8f` | 饱和绿 → 低饱和浅绿 |
| 错误红 | `#f44336` | `#ff7a70` | 纯红 → 带橙调暖红 |
| 危险红 | `#dd4444` | `#ff8a7f` | 深红 → 浅粉红 |
| 代码背景 | `#2c2c2c` | `#0d1117` | 炭灰 → GitHub 超深蓝黑 |

---

## 7. 使用规则（暗色补充）

- 暗色背景层级：`bg-app` (`#1f1b16`) < `bg-paper` (`#2a251e`) < `bg-surface-solid` (`#332d25`)，层次分明。
- 阴影在暗色下只用于浮层、菜单和真正卡片；设置资源行依靠深纸面透明混合、细分隔线和右侧对勾表达选中态，不用深色填充或投影堆层级。
- `text-on-action` 在暗色下保持 `#ffffff`，确保主操作按钮文字可读（按钮背景为暖白，前景白色可能对比度不足 → 实际主按钮在暗色下背景为暖白 `#f3eee6`，前景应用 `--color-bg-app` 或使用深色字，此处按实际渲染验收）。
- 水彩高亮全部使用 `rgba()` 半透明，不用不透明纯色，避免遮蔽背景层次。
- 不新增孤立十六进制；新需求先映射到现有 token。
- Settings 连接器详情页只保留一个 `--color-border-paper` 派生的虚线页边界；内部资源列表和已挂载来源列表保持无外框、无卡片底、无阴影。
- Decks 页面只保留页面级虚线深纸边界；deck item 使用低对比轻分区、细边界和小面积 accent，避免彩色整卡边框、渐变图标和普通 item 阴影在暗色下堆叠。

---

## 8. 浮层 / Popover / Dropdown 暗色配色

所有悬浮弹层（下拉菜单、Tooltip、Popover、@Agent Dropdown 等）在暗色主题下的规范：

| 属性 | Token | 暗色值 | 说明 |
|---|---|---:|---|
| 背景 | `--color-bg-surface-solid` | `#332d25` | 深暖棕不透明弹层，比 bg-paper 亮一档。 |
| 边框 | `--color-border-neutral` | `#4a4238` | 深暖灰细线，与背景形成区分。 |
| 阴影 | `--color-shadow-medium` | `rgba(0,0,0,0.45)` | 暗色下阴影加重以保持浮层感。 |
| 项目 hover 背景 | `--color-bg-hover` | `rgba(255,255,255,0.08)` | 白色叠层，在深背景上清晰可见。 |
| 项目选中/激活背景 | `--color-bg-active` | `rgba(129,183,210,0.18)` | 蓝色调选中态，与暗底适配。 |
| 文字主 | `--color-text-body` | `#eee8df` | 条目名称，暖白正文色。 |
| 文字次 | `--color-text-secondary` | `#c8bcae` | 描述/元信息，暖灰次级色。 |

> `AgentDropdown`、`TopNavBar` 用户菜单、`CalendarPopup` 条目卡、`LeftToolbar` Tooltip 均遵循此规范。
