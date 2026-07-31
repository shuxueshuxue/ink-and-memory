# Color System PRD — 索引

> 面向 `docs/prd` 下聊天、文件、侧边栏、Dashboard、历史记录、发送区和暗色模式 PRD 的统一色彩系统。  
> 本文是索引入口，具体设计稿见子文档。不修改源码、不引入新业务逻辑。
> [Sync] 2026-07-09: Settings / connector detail pages may use one dashed paper boundary, while inner sections and resource rows must stay flat, whitespace-led, and non-card-like; selected resources use a right-side checkmark, not dark fills.
> [Sync] 2026-07-09: Decks uses the same paper-boundary rule: one dashed page boundary, flat deck items, small accent marks, and no gradient / shadow-heavy ordinary cards.

---

## 子文档

| 文档 | 内容 |
|---|---|
| [light-theme.md](./light-theme.md) | 亮色主题完整设计稿：视觉语言、品牌色板、全量 Token 亮色值、高亮色、衍生变量。 |
| [dark-theme.md](./dark-theme.md) | 暗色主题完整设计稿：视觉语言、品牌色板、全量 Token 暗色值、亮↔暗映射关系、暗色使用补充规则。 |

---

## 1. 文档目的

统一当前项目的视觉语言和 PRD 表达，避免新增 PRD 沿用旧稿中的 Tailwind 原型、霓虹橙主色、高级灰营销风或外部资产假设。

本文基于当前产品实际视觉系统抽象 Design Token，用于指导后续设计、前端评审和 QA 验收。  
`frontend/src/styles/tokens.css` 是运行时 source of truth；外部参考色只能作为未来独立探索，不得覆盖现有主题。

---

## 2. 设计依据与取舍

| 依据 | 结论 |
|---|---|
| `frontend/src/styles/tokens.css` | `:root` 定义亮色，`[data-theme='dark']` 定义暗色，`prefers-color-scheme: dark` 媒体查询提供系统自动回退。 |
| `frontend/src/App.css` | 产品底色为暖纸张；`.notebook-lines` 使用 `color-mix` 派生格线色；滚动条颜色已全部替换为 token。 |
| `frontend/src/App.tsx` / `TopNavBar.tsx` | 已完成从硬编码 `#fff`/`#555`/`#d44` 等到 CSS 变量的迁移。 |
| `frontend/src/utils/theme.ts` | 提供 `initTheme` / `setTheme` / `toggleTheme` / `getTheme`；`main.tsx` 在 render 前调用 `initTheme()`。 |

冲突取舍：

- 不使用本轮外部 Fictional / sticker 参考色覆盖产品主题。
- 旧 PRD 中 `#FF7A00`、`#FF6B00` 不作为全局主色；工具步骤或链接可使用"注意色"，但不得压过产品的纸张与炭黑主视觉。
- 旧 PRD 中 Tailwind、Font Awesome、远程头像和独立 HTML 原型不作为项目约束；项目当前使用 React、CSS/inline style、`react-icons` 和本地字体。
- 暗色主题已完整实现；亮色保持不变作为默认主题。

---

## 3. 共同视觉准则

Ink & Memory 的视觉关键词是 **"纸张、笔记、手写、安静工具台"**。两套主题共享以下规范：

| 维度 | 规范 |
|---|---|
| 字体 | 英文优先 `Excalifont`/Georgia，中文优先 `Xiaolai`，功能控件用系统无衬线。 |
| 圆角 | 文档、卡片、弹窗 4/6/8/12 px；聊天输入 Dock 约 16 px。 |
| 分区 | 设置详情页和 Decks 页面优先使用留白、轻纸面列表和单一虚线页边界；避免在页面内叠加多层卡片面板。 |
| 动效 | 0.2–0.3 s 的 hover、focus、展开过渡；避免大幅旋转、强 glow、持续闪烁。 |

---

## 4. 通用使用规则

- 不新增孤立十六进制颜色；新增视觉需求先映射到 token。
- 代码块统一使用 `--color-code-bg` / `--color-code-text`；行内代码用 `--color-code-inline-bg`。
- 主操作按钮前景统一用 `--color-text-on-action`（`#ffffff`）。
- 状态色只做小面积提示，不只用颜色表达状态（需配文字或图标）。
- hover 态统一使用对应 `-hover` token，不自行叠加透明度或调色。
- Settings / connector detail page 的页面级承载可用 `--color-border-paper` 经 `color-mix` 混合后的虚线边界；内部结构区块不再额外套实线卡片。
- 资源列表、已挂载来源列表使用轻纸面容器和行分隔线表达层级；资源选中态使用右侧对勾，普通资源行不使用深色背景、外框、投影或卡片式按钮底。
- Decks 页面使用同一套纸面分区：页面级虚线边界、轻纸面 deck item、弱控件边界；deck 颜色只作为小面积 icon / 左侧 accent，不作为整卡边框、渐变底或 hover 阴影。

---

## 5. 模块落地

| 模块 | 规则 |
|---|---|
| Chat Dashboard | 颜色必须继续使用现有主题 token；可收窄布局但不改颜色。 |
| History | 会话选中态使用 `color.bg.app` 或边框强化，不使用高饱和色填充。 |
| Send | 输入 Dock 与已发送卡保持同一纸面语言；发送按钮用 link blue 或主操作色。 |
| File Work | 上传、文件列表、预览都使用纸面层级，类型色只做辅助。 |
| Sidebar | 使用 `bg.app` 或 `bg.surfaceSolid`；当前项以主文本/下划线/左线表示。 |
| Settings | 设置组保持纸面层级；连接器详情页使用单一虚线页边界、轻列表和留白，状态标记来自语义 token。 |
| Decks | Deck 管理页使用单一虚线页边界；deck item 是轻纸面条目，颜色只做小面积 accent，普通条目不使用渐变图标、强边框或阴影。 |

---

## 6. 验收标准

- `tokens.css` 中 `:root` 与 `[data-theme='dark']` 覆盖全部语义 token，两套值完整对称。
- `prefers-color-scheme: dark` 媒体查询在用户未手动设置时自动生效。
- `TopNavBar` 右侧 🌙/☀️ 按钮可切换主题，偏好持久化到 `localStorage`（键名 `ink-theme`）。
- 所有组件中不存在孤立十六进制颜色（已通过代码审查确认）。
- `docs/prd` 下 PRD 文档颜色引用均可追溯到 `light-theme.md` 或 `dark-theme.md` 中的 token。
- UI 中状态反馈不只用颜色表达。
- `docs/prd/image.png` 不被覆盖；需要更新截图时另起视觉更新任务。
