> [Input] Chat 页面报错堆栈（`[<pre /> in Markdown (at react-markdown) in AssistMessagePart ...]`）、`frontend/src/components/chat/AssistMessagePart.tsx`、`frontend/src/components/chat/UserMessagePart.tsx`、`frontend/src/components/chat/PlanPanel.tsx`
> [Output] 定义 Chat 会话 Markdown 中 Mermaid 代码块的 SVG 渲染方案，并消除 `<pre>` 内嵌块级元素导致的 React DOM 嵌套报错。
> [Pos] interaction-design-doc in `docs/design/claude-agent`
> [Sync] 2026-07-20: 初版 — Mermaid 按需加载渲染、共享 `ChatMarkdown` 渲染链、流式降级与 `<pre>` 嵌套修正。
> [Sync] 2026-07-20: 新增 §2.6 图表工具栏 — 预览/源码模式切换、复制源码、导出 PNG 图片。

# Chat Markdown Mermaid 渲染设计

## 1. 问题判断

Claude Agent 的回答经常包含 ```` ```mermaid ```` 围栏代码块（流程图、时序图等）。当前 Chat 会话的 Markdown 渲染链只有 `react-markdown + remark-gfm`，Mermaid 块按普通代码原样展示，用户无法看到图形。

同时，当自定义 `code` 渲染器返回块级元素（如 `<div>`）时，react-markdown 默认的 `pre` 渲染器仍会把它包进 `<pre>`，产生非法 DOM 嵌套（`<pre>` 的内容模型是 phrasing content），React 在 `AssistMessagePart` 的 `Markdown` 渲染路径上抛出 `[<pre /> in Markdown ...]` 报错堆栈。Mermaid 支持必须连同 `pre` 渲染器一起处理，不能只改 `code`。

## 2. 渲染方案

### 2.1 依赖与加载

- 引入 `mermaid`（v11+）。该包体积大（gzip 后约 500 KB），**禁止**打进首屏 bundle：
  - 通过动态 `import('mermaid')` 在首个 Mermaid 块出现时按需加载。
  - 模块级单例 Promise 缓存加载结果，`mermaid.initialize()` 只执行一次。
- 初始化参数：
  - `startOnLoad: false` —— 渲染完全由组件驱动。
  - `securityLevel: 'strict'` —— 会话内容来自模型输出，不允许注入 HTML/脚本。

### 2.2 组件结构（复用优先）

现有三处 `ReactMarkdown` 调用点：`AssistMessagePart.tsx`、`UserMessagePart.tsx`、`PlanPanel.tsx`，插件配置各自重复。按 reuse-first 原则收敛为一条共享渲染链：

| 组件 | 位置 | 职责 |
|---|---|---|
| `ChatMarkdown` | `frontend/src/components/chat/ChatMarkdown.tsx` | 共享 `ReactMarkdown` 封装：统一 `remarkGfm` 插件与 `code`/`pre` 组件覆盖；`language-mermaid` 代码块路由到 `MermaidBlock`，其余代码块保持默认渲染 |
| `MermaidBlock` | `frontend/src/components/chat/MermaidBlock.tsx` | 单个 Mermaid 图表的加载、渲染、错误降级 |

三个调用点改为渲染 `<ChatMarkdown>`，不再直接引用 `react-markdown` / `remark-gfm`。

### 2.3 `code` / `pre` 渲染器覆盖

- `code`：`className === 'language-mermaid'` 时渲染 `<MermaidBlock chart={...} />`，其余走默认 `<code>`。
- `pre`：检查子元素是否为 Mermaid 代码块（子 `code` 的 `className` 为 `language-mermaid`），是则去掉 `<pre>` 包裹直接渲染子元素，避免 `<div>` 嵌套进 `<pre>`；否则保持默认 `<pre>`。

### 2.4 流式渲染与降级

会话文本是流式增长的，Mermaid 源码在流式期间通常是语法不完整的片段：

- `MermaidBlock` 内部对 `chart` 变化做约 300 ms 防抖后再调用 `mermaid.render()`，避免每个 token 触发一次解析。
- 解析/渲染失败（包括流式中间态）不抛错：回退展示原始代码块，并在角落标记「渲染中/无法渲染」。最后一次渲染成功的 SVG 在重渲染期间保留，避免闪烁。
- 渲染使用 `crypto.randomUUID()` 生成唯一图表 id，多个图表互不冲突。

### 2.5 主题

应用颜色体系基于语义化 CSS 变量（`--color-text-primary`、`--color-bg-paper` 等）。`mermaid.initialize()` 使用 `theme: 'base'`，`themeVariables` 在初始化时从 `getComputedStyle(document.documentElement)` 读取上述变量并映射（主色、文字色、边框色、背景色），读取失败时使用内置回退值。图表容器样式沿用既有 `prose prose-chat` 代码块视觉（圆角、纸面背景、横向滚动）。

### 2.6 图表工具栏

`MermaidBlock` 容器顶部提供工具栏，右侧为操作区：

| 功能 | 交互 | 说明 |
|---|---|---|
| 预览 / 源码切换 | 分段按钮（segmented），与 `AIInputDock` 的「自动 / 逐步确认」切换同风格 | 默认预览；预览模式显示 SVG，源码模式显示原始 Mermaid 文本；渲染失败且无可用 SVG 时强制停留源码视图 |
| 复制源码 | 图标按钮，复用 `useCopy` hook | 任意模式下复制**完整 Markdown 围栏文本**（` ```mermaid ```` 开头、` ``` ` 收尾，含图表源码），成功后图标变为对勾（2s 复位） |
| 导出图片 | 图标按钮，仅预览可用时启用 | 将当前 SVG 栅格化为 PNG 下载，文件名 `mermaid-diagram-{timestamp}.png` |

PNG 导出实现要点：

- 从 SVG 的 `viewBox` 解析逻辑尺寸（缺失时回退 800×600），序列化时写入显式 `width`/`height`。
- 按 2 倍 scale 绘制到 `<canvas>`，先以 `--color-bg-paper` 填充背景（SVG 本身是透明的），再 `drawImage`。
- `canvas.toBlob('image/png')` → 临时 `<a download>` 触发下载；全程不离开当前页面，失败时仅控制台告警并复位按钮状态。

## 3. 错误处理

| 场景 | 行为 |
|---|---|
| mermaid 包加载失败（网络/构建问题） | 展示原始代码块 + 加载失败提示，不影响其余 Markdown |
| 语法不完整（流式中） | 展示原始代码块；防抖后重试 |
| 语法错误（最终态） | 展示原始代码块 + 错误角标，控制台保留 mermaid 原始错误 |
| 多个图表并发渲染 | 单例初始化 + 串行化 `render()` 调用，避免 mermaid 内部状态竞争 |
| PNG 导出失败（canvas/编码异常） | 按钮复位、控制台告警，图表本身不受影响 |

## 4. 影响面与验证

- 改动文件：新增 `ChatMarkdown.tsx` / `MermaidBlock.tsx`；修改 `AssistMessagePart.tsx` / `UserMessagePart.tsx` / `PlanPanel.tsx`；`frontend/package.json` 新增 `mermaid` 依赖。
- 不影响后端与 SSE 事件契约。
- 验证：`npm run build`（tsc + vite）与 `npm run lint` 通过；手工确认含 ```` ```mermaid ```` 的回答渲染为 SVG，普通代码块不受影响，控制台不再出现 `<pre>` 嵌套报错。
