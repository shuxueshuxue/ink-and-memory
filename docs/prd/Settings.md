# Settings PRD

> Settings 页面的产品与视觉设计规范。本文引用 [Color System](<./color_system/README.md>)，并与当前产品实现保持同步。
> **[Sync] 2026-05-27**: 新增用户 API 配置区域（现 §4.3.7，`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL` 等按用户存储并注入 Claude SDK 子进程）；关联设计文档 [用户 SDK Env 注入方案设计](../design/claude-agent/user-env-injection-design.md)。
> **[Sync] 2026-06-09**: AI 模型配置新增「应如何批准 IM」操作开关；打开后保存 `system_config.im_full_access_enabled=true`，Claude-agent 对除问答表单外的已暴露工具的 `PreToolUse` 返回显式 allow，Chat 输入区隐藏「逐步确认」并显示「完全访问」；同页切换通过前端事件实时同步，无需刷新。
> **[Sync] 2026-06-13**: 「工作区模式」开启后同时启用每个 thread
> workspace 的 Claude Code Bash sandbox；后端写入
> `{AGENT_CWD}/{thread_id}/.claude/settings.json` 的 `sandbox` 配置。
> **[Sync] 2026-06-13**: 「完全访问」不跳过 AskUserQuestion 类问答确认；
> 该类工具仍显示前端确认窗口以收集用户答案。
> **[Sync] 2026-06-14**: Workspace sandbox 的 Bash 读权限包含必要运行时依赖目录；
> 项目源码目录不会因 runtime allowlist 被默认放行。
> **[Sync] 2026-06-21**: AI 模型配置新增「沙箱网络」策略，用于区分
> WebFetch 域名权限、Bash/curl 出站网络和本机工具缺失三类失败；配置写入
> `system_config.sandbox_network_mode` 与
> `system_config.sandbox_network_allowed_domains`，并同步到 thread-local
> `.claude/settings.json` 的 `sandbox.network`。
> **[Sync] 2026-07-08**: 新增资源链接设置区，Connector 入口改为进入 Settings 的资源链接管理；Chat 只保留轻量摘要面板和跳转按钮。
> **[Sync] 2026-07-08**: 修复设置页问题——Notion「管理」不再原地展开，改为导航到独立的 `ConnectorNotionDetailPage`（带面包屑导航），并移除顶部/移动端导航栏里单独的 `Connector` 入口，统一由 Settings 资源链接区和 Chat 轻量摘要面板承载入口。

## 1. 文档范围

Settings 是应用的全局配置页面，作为顶部导航栏（`TopNavBar`）和移动端底部导航栏中"设置"入口的对应视图。本次更新新增 **资源链接** 与 **AI 模型配置区域**，将原本位于 Chat 页面侧边栏的模型配置迁移至此，并新增 **用户 API 配置区域**，支持每位用户存储自己的 Anthropic API 密钥及模型端点配置。

该页面包含：
- 语言偏好设置
- 界面展示选项（如能量条开关）
- **资源链接**（Notion、飞书、本地 CLI 执行器占位）
- **AI 模型配置**（主题、模型选择、系统提示词、工作区模式、沙箱网络、IM 审批模式）
- **用户 API 配置**（Anthropic API 密钥、自定义端点、默认模型等 env 变量）
- 关于 Ink & Memory（`AboutView`）

## 2. 设计目标

- 将所有应用级全局配置集中于一处，避免配置入口散落在各页面侧边栏。
- 与 Ink & Memory 的"暖纸张、安静工具台"气质保持一致，不使用高饱和填充块或营销式排版。
- 为 Light/Dark 模式共用同一语义 token。
- 设置项清晰分区，每个区域有标题说明，便于用户快速定位。

## 3. 页面布局

```
SettingsView（position: fixed，overflow: auto）
└── ContentWrapper（maxWidth: 800，width: 100%）
    ├── GeneralSection
    │   ├── 标题：Settings / 设置
    │   └── LanguageGroup（语言选择按钮组）
    ├── DisplaySection
    │   └── EnergyBarToggle
    ├── ConnectorSettingsSection（资源链接）
    │   ├── 远程资源链接（Notion / 飞书）
    │   └── 本地资源链接（CLI 执行器占位）
    ├── ModelConfigSection（AI 模型配置）
    │   ├── 标题：AI 模型配置
    │   ├── ThemeGroup（Light / System / Dark 切换）
    │   ├── ModelSelect（模型下拉选择）
    │   ├── SystemPromptTextarea（系统提示词，含保存/重置）
    │   ├── WorkspaceModeToggle
    │   ├── SandboxNetworkPolicy（沙箱网络模式 + 域名白名单）
    │   ├── IMApprovalModeToggle（应如何批准 IM：完全访问）
    │   └── UserApiConfigGroup（用户 API 配置）
    │       ├── ANTHROPIC_AUTH_TOKEN 输入框（password 类型）
    │       ├── ANTHROPIC_BASE_URL 输入框
    │       ├── ANTHROPIC_MODEL 输入框（可选）
    │       └── 保存按钮
    └── AboutSection
        └── AboutView
```

| 区域 | 规范 |
|---|---|
| 页面容器 | `color.bg.app`，`overflow: auto`，顶部留 `viewTopOffset` |
| 内容最大宽度 | 800px，居中，桌面端横向内边距 40px，移动端 16px |
| 区域间距 | `marginBottom: 48px` |
| 分组容器 | `color.bg.surface`，`border: 1px solid color.border.paper`，`borderRadius: 8px`，`padding: 24px` |

## 4. 组件层级

### 4.1 GeneralSection（通用设置）

- 标题使用 `color.text.primary`，Georgia 字体，24px，fontWeight 600。
- 语言切换按钮组：激活项使用 `color.action.primary`（炭黑底 + 白字），未激活使用 `color.border.paper` 边框。
- 不使用高饱和背景或渐变表示选中状态。

### 4.2 DisplaySection（展示选项）

- 每项使用 flex 横向排列：左侧标题+描述，右侧切换开关。
- 开关激活时使用 `color.action.primary`（炭黑底），未激活使用 `color.border.paper`。
- 标题 14px，描述 12px `color.text.secondary`。

### 4.3 ModelConfigSection（AI 模型配置）

此区域由 `ModelConfigSection` 组件实现，包含以下子区域：

#### 4.3.1 外观主题 / Theme

- 三个按钮（Light / System / Dark），横向排列，带图标和文字标签。
- 激活项：`border: color.border.focus`，`background: color.bg.paper`，`color: color.text.primary`，fontWeight 600。
- 未激活项：`background: transparent`，`color: color.text.muted`。
- 按钮圆角 `999px`，过渡 `0.2s ease`。
- 选中后立即应用主题，同步写入 `localStorage` 和 `/api/system-config`。

#### 4.3.2 AI 模型 / Model

- 下拉选择框 `<select>`，样式使用 `color.bg.paper` 背景，`color.border.paper` 边框，`borderRadius: 12px`，`padding: 0.75rem 0.85rem`。
- 可选项：Auto、Claude Sonnet、GPT-4.1。
- 选中后立即同步到 `/api/system-config`。

#### 4.3.3 系统提示词 / System Prompt

- `<textarea>`，`rows: 5`，样式与 Model select 一致，`resize: vertical`。
- 底部操作行：左侧"恢复默认"（text button，`color.text.muted`），右侧"保存"（`color.action.link` 填充圆角按钮，白色文字）。
- "保存"按钮在 `dirty` 为 `false` 或 `saving` 时 `opacity: 0.55`，`cursor: not-allowed`。
- 保存中显示"保存中…"，完成后恢复。

#### 4.3.4 工作区模式 / Workspace Mode

- flex 横向排列：左侧标题 + 描述说明，右侧切换开关（`flexShrink: 0`）。
- 开关激活：`background: color.action.link`，未激活：`background: color.disabled.bg`。
- 过渡 `0.2s ease`。
- 立即同步到 `/api/system-config`。
- 开启后，后端在每个对话 thread workspace 的 `.claude/settings.json`
  写入 `sandbox.enabled=true`、`failIfUnavailable=true`、
  `autoAllowBashIfSandboxed=true`、`allowUnsandboxedCommands=false`，并将
  Bash filesystem 写范围约束到当前 `{AGENT_CWD}/{thread_id}`。
- Bash read policy 先 deny `/`，再 allow 当前 thread workspace 与必要只读运行时依赖目录（Python/Node/system libs/temp 等）；不默认放行项目源码根目录。
- 关闭后，后端保留 settings 文件同步但写入 `sandbox.enabled=false`；
  Bash 不再使用该工作区沙箱策略。
- 该沙箱只约束 Claude Code `Bash` 工具及其子进程；非 Bash 工具仍由
  Claude-agent 的权限策略和前端确认流控制。

#### 4.3.5 沙箱网络 / Sandbox Network

> 交互设计稿见
> [Claude-Agent Sandbox Network Interaction Plan](../design/claude-agent/claude-agent-sandbox-network-interaction-plan.md)。

此子区域用于控制 Claude Code Bash sandbox 的出站网络策略，解决
`curl` / `git` / `npm` 等子进程不能对外建连的问题归因和配置入口。

**问题分层**：

| 方式 | 失败层级 | 处理位置 |
|---|---|---|
| WebFetch | 工具域名权限 | Claude-agent 权限规则 / WebFetch domain allow/deny |
| curl / git / npm | Bash sandbox 网络层 | Settings「沙箱网络」→ `sandbox.network` |
| gh CLI | 环境层 | 后端镜像或运行时工具安装 |

**配置项**：

| 模式 | `system_config.sandbox_network_mode` | 写入 `sandbox.network` | 说明 |
|---|---|---|---|
| 禁用网络 | `disabled` | `allowedDomains: []` + `deniedDomains: ["*"]` | 请求阻断沙箱子进程访问外网，并由 PreToolUse 拒绝网络工具 |
| 白名单 | `allowlist` | `allowedDomains: [...]` | 预授权填写域名；非白名单域名仍受 Claude Code / managed policy 控制 |
| 开放网络 | `open` | 省略 `sandbox.network` | 请求允许所有域名访问；不向 sandbox runtime 写入不支持的裸 `*` allowlist，仍受部署、后端和托管策略限制 |

**UI 布局**：

- 位于 Workspace Mode 之后、IM Approval Mode 之前。
- 顶部显示标题「沙箱网络 / Sandbox Network」和一句说明：
  该设置控制 Bash、curl、git、npm 等沙箱子进程；关闭态会拒绝网络工具，
  启用态 WebFetch 仍由工具权限和域名规则控制。
- 使用截图式纵向设置布局：
  - 「代理网络访问」为关闭/启用胶囊分段控件。
  - 关闭时在控件下方显示「设置完成后将禁用网络访问。」。
  - 启用后显示左侧竖线分组，包含「域允许列表」「其他允许的域」；仅在自定义域模式显示「允许的 HTTP 方法」。
  - 「域允许列表」使用下拉选择：自定义域（`allowlist`）或所有域（`open`）。
  - 「其他允许的域」使用 `+ 添加域` 交互；点击后出现单行域名输入、保存、取消。
  - 已保存域名以 pill 形式展示，可逐个移除。
  - 「允许的 HTTP 方法」在自定义域模式按截图布局展示为禁用下拉「所有方法」；当前 Claude Code sandbox 仅支持域名级策略，不保存方法级配置；所有域模式隐藏该控件。
  - 网络启用状态始终显示「高风险 启用互联网访问会使你的环境暴露于安全风险之中」提示，包括所有域模式。
- 添加域时支持粘贴完整 URL，保存前去重、去协议和路径；支持 `*.example.com` 通配域名。
- 保存失败时保留用户输入并显示弱提示，不清空配置。

**行为规范**：

- 模式切换立即调用 `PUT /api/system-config` 保存 `sandbox_network_mode`。
- 白名单域名通过「添加域」保存或移除 pill 时调用 `PUT /api/system-config`
  保存 `sandbox_network_allowed_domains`。
- 后端清洗规则不接受裸 `*` 作为白名单域名；全开放必须通过 `open` 模式表达。
- 下一次 Claude Agent turn 或附件 workspace 初始化时，后端把 disabled /
  allowlist 配置写入 `{AGENT_CWD}/{thread_id}/.claude/settings.json` 的
  `sandbox.network`；`open` 模式删除/省略该配置块。
- 当模式为 `disabled` 时，runner 在 PreToolUse 层拒绝 `WebFetch`、
  `WebSearch` 和常见 Bash 网络命令（如 `curl`、`wget`、`git fetch`、
  `npm install`），且优先级高于 IM full-access。
- 该配置不安装缺失工具；WebFetch 在关闭态会被拒绝，启用态仍由工具权限和域名规则控制。

**沙箱文件写入（2026-07-26 新增）**：

- 位于「沙箱网络」之后、IM Approval Mode 之前，仅在 Workspace Mode 开启时显示。
- 配置项 `system_config.sandbox_fs_allowed_write_paths`：除线程工作区外额外允许沙箱内 Bash 写入的绝对路径列表，以 pill 形式展示、`+ 添加可写路径` 单行输入保存（复用域允许列表的交互样式）。
- 后端清洗规则仅接受绝对路径（去尾随斜杠、去重、上限 32 条 / 512 字符）。
- Claude Code 自身沙箱临时目录（`$CLAUDE_TMPDIR` 或 `/tmp/claude-$UID`）始终默认放行——其 shell hook 会向该目录写入 `cwd-*` 文件，之前因工作区独占的 `allowWrite` 被拒绝并产生 `zsh: operation not permitted` 噪音；UI 提示文案需说明该默认值。
- 工作区内部配置（`.claude/settings*`、`.editor` 等）仍在 `denyWrite` 中，按 sandbox-runtime 语义 deny 始终优先于 allow，用户路径不可覆盖。
- 下一次 workspace 初始化时写入 `{AGENT_CWD}/{thread_id}/.claude/settings.json` 的 `sandbox.filesystem.allowWrite`（顺序：工作区 → Claude 临时目录 → 用户路径）。

**非目标 / 避免过度设计**：

- 不做多角色权限系统。
- 不新增审计后台或企业 managed settings 管理界面。
- 不在前端承诺一定能联网；真实可用性仍取决于 Claude Code sandbox、
  Docker/主机网络和上层托管策略。
- 不把 `raw.githubusercontent.com` / `github.com` 写成默认业务策略；
  用户按需加入白名单。

#### 4.3.6 应如何批准 IM / IM Approval Mode

- flex 横向排列：左侧标题「应如何批准 IM」+ 描述说明，右侧操作切换按钮。
- 开关文案固定显示「完全访问」。
- 开启态：按钮使用 `color.text.primary` 背景、`color.bg.paper` 文案，表示除问答表单外的已暴露工具调用由 IM 自动批准。
- 关闭态：按钮使用 `color.disabled.bg` 背景、`color.text.secondary` 文案。
- 立即同步到 `/api/system-config`，字段为 `im_full_access_enabled`。
- 切换时必须立即广播同页配置变更，已打开的 Chat 输入区无需刷新即可更新显示。
- 开启后，后端 Claude-agent runner 在 `PreToolUse` 中对除问答表单外的已暴露工具返回（纯字典字面量）：

```python
{
    "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
    }
}
```

- `tool_choice="none"` 仍不暴露工具；该开关只影响已经进入 `PreToolUse` 的工具调用审批。
- `AskUserQuestion` / `mcp__user__ask_user` 仍需要显示前端确认窗口；
  这些工具不是单纯权限审批，还需要用户填写/确认答案，并由后端把
  `answers` 合并进 `updatedInput` 后再 allow。
- Chat 页面输入区的工具调用模式不再显示「逐步确认」按钮，改为静态显示「完全访问」；关闭后恢复自动/逐步确认分段控件。

#### 4.3.7 用户 API 配置 / User API Config

> 关联设计文档：[用户 SDK Env 注入方案设计](../design/claude-agent/user-env-injection-design.md)

此子区域允许每位用户配置自己的 Anthropic API 密钥和模型端点，存储到 `system_config.env_vars` 中，并在用户发起 Claude Agent 会话时优先注入到 Claude SDK 子进程环境。

**UI 布局**：

- 区域标题：`API 配置 / API Config`，与上方 Workspace Mode 用分割线隔开，`marginTop: 24px`，`paddingTop: 24px`，`borderTop: 1px solid color.border.paper`。
- 每个配置项独占一行，左侧 label + 说明，右侧输入框。

**配置项列表**：

| 字段标签 | env key | 输入类型 | 说明 |
|---------|---------|---------|------|
| API 密钥 | `ANTHROPIC_AUTH_TOKEN` | `<input type="password">` | Anthropic API 密钥，留空则使用服务器默认 |
| API 端点 | `ANTHROPIC_BASE_URL` | `<input type="text">` | 自定义 API 端点（代理/自建），留空则使用 Anthropic 默认 |
| 默认模型 | `ANTHROPIC_MODEL` | `<input type="text">` | 模型名称，留空则由服务器 `.env` 或 Claude Code 默认值决定 |

**视觉规范**：

- 输入框样式与 §4.3.2 Model select 一致：`color.bg.paper` 背景，`color.border.paper` 边框，`borderRadius: 12px`，`padding: 0.75rem 0.85rem`，`width: 100%`。
- `ANTHROPIC_AUTH_TOKEN` 输入框右侧提供"显示/隐藏"切换图标按钮（`color.text.muted`），不改变 type 以外的样式。
- 已保存的 `ANTHROPIC_AUTH_TOKEN` 值在页面加载时显示为掩码（如 `sk-ant-***`），不还原明文。其余字段显示实际值。
- 底部操作行与 §4.3.3 一致：左侧"恢复默认"（清空三个字段），右侧"保存"圆角按钮（`color.action.link`）。
- "保存"按钮仅在 `dirty=true` 且非 `saving` 状态时可用，否则 `opacity: 0.55`，`cursor: not-allowed`。

**行为规范**：

- 用户点击"保存"后，将三个字段的当前值作为 `env_vars` 字典提交到 `PUT /api/system-config`。非空字段写入对应 key；**留空字段从 `env_vars` 中删除该 key**（而非写入空字符串），以便回退到服务器默认配置。
- 用户点击"恢复默认"后，清空三个输入框并立即保存（`env_vars` 中移除这三个 key）。
- 保存成功后 `dirty` 置 `false`，按钮恢复禁用态。

### 4.4 ConnectorSettingsSection（资源链接）与 ConnectorNotionDetailPage（Notion 具体配置页面）

> 关联实现：[`frontend/src/components/dashboard/ConnectorSettingsSection.tsx`](../../frontend/src/components/dashboard/ConnectorSettingsSection.tsx)、[`frontend/src/components/dashboard/ConnectorNotionDetailPage.tsx`](../../frontend/src/components/dashboard/ConnectorNotionDetailPage.tsx)

- `ConnectorSettingsSection` 是 Settings 里的独立资源链接索引卡片；Chat 侧 `ConnectorLandingPanel` 的跳转按钮会打开 Settings 并自动滚动、聚焦到这里。
- 首页分成两个区域：`远程资源链接` 和 `本地资源链接`。
- `远程资源链接` 下展示 Notion / 飞书：
  - Notion 使用真实 connector 状态做摘要，显示绿色健康态、最近交互时间和「管理」按钮。
  - 飞书只保留禁用占位，不调用不存在的 API。
- `本地资源链接` 只保留 CLI 执行器占位，当前版本不设计完整交互。
- **点击 Notion「管理」是页面级导航，不是原地展开**：App 级 `showNotionConnectorDetail` 状态置 `true`，Settings 视图整体切换为 `ConnectorNotionDetailPage`，替换掉 Energy Bar / AI 模型配置等其它设置分区（而不是在资源链接卡片内叠加显示）。
  - `ConnectorNotionDetailPage` 顶部渲染「← 资源连接器 > Notion Connector」轻量导航（对应《链接器概念的交互设计稿》「具体配置页面 / 最上方导航」骨架屏），返回按钮回到 Settings 资源链接索引卡片。
  - 同一平台只允许认证一个账号；Notion 详情页不得出现「新建连接器」「刷新列表」「连接器列表」等集合级入口。
  - 页面主体按单账号资源配置固定为 `ConnectorHeader`、`StrategyDesignPlaceholder`、`ResourceScopeSection`、`MountedSourcesSection`。
  - `ConnectorHeader` 是紧凑无边框信息栏：展示 Notion 图标、标题、说明、状态 badge、「连接 / 重新连接 Notion」「关闭连接」两个真实操作位，并把授权状态、同步状态、已链接资源数量、最近同步时间和受限提示集中在这里。
  - `StrategyDesignPlaceholder` 只保留“策略设计暂不实现”的轻量位置，不展示表单、开关或策略配置。
  - `ResourceScopeSection` 直接调用现有 connector API 完成认证后的 database / standalone page 选择和保存，不嵌入集合型 `ResourceConnectorPage`；资源选择合并为一个列表，顶部提供搜索框，默认每页 10 条并支持翻页。
  - `MountedSourcesSection` 只展示当前 Notion 账号已挂载来源，不展示连接器列表或多实例切换。
  - 返回时重新聚焦资源链接索引卡片，与从 Chat 跳转过来的聚焦行为保持一致。
- `ConnectorSettingsSection` 本身只负责入口、摘要和触发页面导航，不承载创建、认证、资源选择或同步逻辑。

### 4.5 AboutSection

- 复用 `AboutView` 组件，不做额外样式包裹。

## 5. 色彩与视觉规范

| 元素 | Token | 说明 |
|---|---|---|
| 页面背景 | `color.bg.app` | 暖纸张背景。 |
| 分组容器 | `color.bg.surface` | 半透明白，轻量分组。 |
| 边框 | `color.border.paper` | 棕灰纸张感。 |
| 标题 | `color.text.primary` | 区域标题、配置项标题。 |
| 说明文字 | `color.text.secondary` | 配置项描述、辅助说明。 |
| 弱提示 | `color.text.muted` | placeholder、"恢复默认"按钮文字。 |
| 激活操作 | `color.action.primary` | 语言/主题选中状态。 |
| 链接/保存 | `color.action.link` | 保存按钮、Workspace Mode 开关激活色。 |
| 开关禁用 | `color.disabled.bg` | Workspace Mode 未激活背景。 |
| 焦点边框 | `color.border.focus` | Theme 选中按钮边框。 |

## 6. 状态设计

| 状态 | 设计要求 |
|---|---|
| 加载态 | 配置加载中显示"Loading config…"弱文本，不显示骨架屏 |
| 保存中 | 保存按钮文案变为"保存中…"，opacity 降低，cursor 为 not-allowed |
| 已保存 | dirty 置 false，按钮恢复为禁用态（内容未变时无需再次保存） |
| 悬停态 | 主题/语言按钮轻微改变颜色，0.2s ease |
| 焦点态 | 输入框 focus 使用 `color.border.focus` 或系统默认 outline |

## 7. 暗色模式适配

- 使用同一套语义 token，背景切换为 `color.bg.app` Dark 值（`#1f1b16`）。
- 分组容器使用 `color.bg.surface` Dark 值（`rgba(42,37,30,0.82)`）。
- 输入框、下拉框使用 `color.bg.paper` Dark 值（`#2a251e`）。
- 文字使用对应 Dark token，保持可读性。
- 不使用霓虹橙或纯黑背景。

## 8. API 交互

- 页面挂载时调用 `GET /api/system-config` 加载当前配置。
- Theme、Model、Workspace Mode 变更后立即调用 `PUT /api/system-config` 保存。
- Workspace Mode 变更保存字段为 `workspace_enabled`；后端在下一次
  Claude Agent turn 或附件 workspace 初始化时同步 thread-local
  `.claude/settings.json` sandbox 配置。
- Sandbox Network 变更后调用 `PUT /api/system-config` 保存
  `sandbox_network_mode` 与 `sandbox_network_allowed_domains`；后端在下一次
  Agent turn、附件同步或文件侧栏 workspace 刷新时同步到 thread-local
  `.claude/settings.json` `sandbox.network`。
- IM Approval Mode 变更后立即调用 `PUT /api/system-config` 保存 `im_full_access_enabled`。
- System Prompt 在用户点击"保存"后调用 `PUT /api/system-config`。
- **用户 API 配置**在用户点击"保存"后调用 `PUT /api/system-config`，将三个 env key 作为 `env_vars` 字典传入。留空的字段通过传入空字符串或在前端过滤后不包含该 key 来实现删除（与服务端 `_sanitize_env_vars` 保持一致：空字符串 key 会被过滤；value 为空字符串则保留 key，建议前端在保存前将空值字段从 `env_vars` 中省略）。
- 请求失败时保留 UI 状态，不清除用户输入，可选添加错误提示。

## 9. 导航入口

Settings 页面通过以下入口访问：

- 桌面端顶部导航栏（`TopNavBar`）的 Settings 选项。
- 移动端底部导航栏的 Settings 图标。
- Chat 侧 `ConnectorLandingPanel` 的跳转按钮会打开 Settings 并自动滚动、聚焦到资源链接区（顶部导航栏与移动端底部导航栏不再单独展示 `Connector` 入口）。

## 10. 可访问性

- 所有表单控件需有可见 label 或 aria-label。
- 开关按钮使用 `aria-pressed` 表示状态。
- 主题选择按钮使用 `title` 属性说明作用。
- 禁用按钮保持文字可读，不能只靠颜色表达状态。

## 11. 验收标准

- Settings 页面包含 AI 模型配置区域（主题、模型、系统提示词、工作区模式、沙箱网络、IM 审批模式）。
- Settings 页面包含资源链接区域（Notion / 飞书 / 本地 CLI 执行器占位）；点击 Notion「管理」会导航到独立的 `ConnectorNotionDetailPage`（带「← 资源连接器 > Notion Connector」面包屑），而不是在资源链接卡片内原地展开。
- Settings 页面包含用户 API 配置区域（API 密钥、API 端点、默认模型三个输入项）。
- Chat 页面不再渲染模型配置侧边栏，也不再承载完整 connector workbench；顶部导航栏与移动端底部导航栏不再展示 `Connector` 入口，Connector 管理只能通过 Settings 资源链接区或 Chat 轻量摘要面板的跳转按钮进入。
- 所有颜色引用 [Color System](<./color_system/README.md>) token，无孤立十六进制值。
- Light/Dark 模式均可正常显示。
- 配置变更后正确同步到 `/api/system-config`。
- 语言、展示选项、AI 模型配置、用户 API 配置、关于内容分区清晰，各自有标题说明。
- `ANTHROPIC_AUTH_TOKEN` 输入框已保存的值以掩码形式展示，不反向暴露明文。
- 用户 API 配置保存后，该用户的后续 Agent 会话使用用户配置的 API 密钥和端点（而非全局 `backend/.env`）。
- 「应如何批准 IM」开启后，该用户后续 Agent 普通工具调用自动获得完全访问；Chat 输入区隐藏「逐步确认」并显示「完全访问」；AskUserQuestion 类工具仍显示问答确认窗口。
- 「沙箱网络」保存后，该用户后续 Agent workspace 写入对应
  `sandbox.network`，并能在 Settings 中回显模式和白名单域名。
- 清空字段并保存后，该 key 从 `env_vars` 中移除，回退到服务器默认配置。

## 12. 前端实现备注

本轮已完成以下前端实现：
- 新建 `ModelConfigSection.tsx`，封装主题、模型、系统提示词、工作区模式的配置 UI 与 API 交互逻辑。
- 新建 `ConnectorSettingsSection.tsx`，封装 Settings 里的资源链接索引卡片以及远程/本地资源占位。
- 新建 `ConnectorNotionDetailPage.tsx`，作为 Notion「具体配置页面」的独立导航页面；该页直接承载单账号认证、资源选择、来源列表、同步和关闭流程，不再复用集合型 `ResourceConnectorPage` page mode。
- 新建 `ConnectorLandingPanel.tsx`，作为 Chat 中的轻量 connector 摘要和 Settings 跳转 CTA。
- 在 `App.tsx` Settings 视图中注入 `<ModelConfigSection />`，作为独立区域显示。
- 在 `App.tsx` 新增 `showNotionConnectorDetail` 状态；点击 Notion「管理」时把 Settings 视图整体切换为 `<ConnectorNotionDetailPage />`，不再与其它设置分区混排。
- `TopNavBar.tsx` 与移动端底部导航栏不再渲染独立的 `Connector` 按钮；`VerticalNav.tsx` 不再渲染 Settings 图标；Settings 保留顶部导航栏和移动端底部导航栏入口。
- `ChatView.tsx` 只在 Chat 视图内渲染轻量 connector landing panel，不再挂载黑底 connector workbench。

**用户 API 配置（待实现）**：
- 在 `ModelConfigSection.tsx`（或提取后的 `UserApiConfigGroup.tsx`）中新增 §4.3.7 描述的三个输入框区域。
- 页面挂载时从 `GET /api/system-config` 的 `env_vars` 字段读取初始值；`ANTHROPIC_AUTH_TOKEN` 有值时显示掩码，其余字段显示实际值。
- 保存时将非空字段组成 `env_vars` dict 通过 `PUT /api/system-config` 提交；空字段对应 key 从 dict 中省略（服务端会保留旧值），如需清除则显式发送空字符串（服务端 `_sanitize_env_vars` 会写入空字符串，效果等同清除）。
- 建议后续在 `GET /api/system-config` 路由层对 `ANTHROPIC_AUTH_TOKEN` 返回掩码，避免前端 JS 中出现明文密钥。

后续如需扩展 Settings 页面，建议将整个 Settings 视图提取为独立 `SettingsView.tsx` 组件，与 `App.tsx` 解耦。
