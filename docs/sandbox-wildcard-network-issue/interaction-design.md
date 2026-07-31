# 沙箱网络配置 `allowedDomains: ["*"]` 问题 — 交互方案设计稿

> 关联源码：
> - Claude Code 还原源码：`/Users/dmeck/project/claude-code-sourcemap/restored-src`
> - sandbox-runtime 本地仓库：`/Users/dmeck/project/sandbox-runtime`（`anthropic-experimental/sandbox-runtime`）
>
> 日期：2026-07-23

---

## 1. 问题背景

用户在 Docker 容器内运行 Claude Code 并启用沙箱（`sandbox.enabled: true`），经历两个阶段：

1. **阶段一**：沙箱完全无法启用（Docker 内缺 `bwrap`/`socat` 或 userns 受限）。
2. **阶段二**：沙箱可启用后，希望通过配置自定义域名放行网络（目标域名 `raw.githubusercontent.com`），于是配置：

```json
{
  "sandbox": {
    "enabled": true,
    "network": {
      "allowedDomains": ["*"]
    }
  }
}
```

**观测现象**：`*` 配置看似"没生效"——请求仍被网络策略拦截（"配置 * 匹配被网络策略拦了"）。

---

## 2. 根因分析（源码证据）

### 2.1 配置链路全貌

```
settings.json  sandbox.network.allowedDomains: ["*"]
  └─ SandboxSettingsSchema 校验（entrypoints/sandboxTypes.ts:91-144）
       └─ allowedDomains 仅 z.array(z.string()) —— 不校验域名格式，"*" 原样通过
  └─ convertToSandboxRuntimeConfig()（utils/sandbox/sandbox-adapter.ts:172-381）
       └─ 域名原样透传，无任何转换/合并默认域名
  └─ BaseSandboxManager.initialize(runtimeConfig, askCallback)（sandbox-adapter.ts:769-773）
       └─ sandbox-runtime 启动本地 HTTP/SOCKS 过滤代理
  └─ Bash 命令经 bwrap --unshare-net + --setenv HTTP_PROXY=... 执行
  └─ 代理侧 filterNetworkRequest() 判定放行/拦截
```

### 2.2 核心发现：两个版本的 `*` 语义不一致

| 位置 | `*` 的处理 | 结果 |
|---|---|---|
| **restored-src 内 bundled dist**（`node_modules/@anthropic-ai/sandbox-runtime/dist/sandbox/sandbox-manager.js:41-51`） | `matchesDomainPattern` 只支持 `*.suffix` 后缀通配和精确匹配；`"*"` 走精确比较 `host === "*"`，**永不匹配** | `["*"]` 完全无效，所有未命中的域名落入 ask-callback / 拒绝路径 → **用户看到的"被拦"** |
| **本地 sandbox-runtime 仓库（较新 TS 源码）**（`src/sandbox/domain-pattern.ts:30`） | `if (pattern === '*') return true` —— `*` 是**放行全部** | 若走未校验的编程式 API 传入，`["*"]` 变成 allow-all → 对应"所有网络可访问"的说法 |
| **schema 层（两版一致）**（`src/sandbox/sandbox-config.ts:43-53`） | `domainPatternSchema` 明确拒绝 `allowedDomains` 中的 `*`："Overly broad patterns like "\*.com" or "\*" are not allowed for security reasons"；`*` 仅允许出现在 `deniedDomains`（deny-all） | 设计意图：**`allowedDomains` 不支持 allow-all 通配符** |

**关键结论**：`*` 从来不是 `allowedDomains` 的合法值。用户当前运行版本（restored-src 对应构建）中它是"静默无效串"；新版源码中它是"逃逸校验的 allow-all"。两种现象都源于同一个事实——**配置层（settings schema）不校验，运行时匹配语义随版本漂移**。

### 2.3 Docker 环境次生问题

- 沙箱网络隔离在 Linux 上依赖 `bwrap --unshare-net` + socat 桥接到宿主机过滤代理（`linux-sandbox-utils.ts:1291-1356`）。
- Docker 非特权容器需：
  - 安装 `bubblewrap` 和 `socat`（缺失则报 error，初始化失败）；
  - 容器启动加 `--security-opt seccomp=unconfined --security-opt apparmor=unconfined`（参考 `test/docker-weak-sandbox.test.ts:8-13`）；
  - 配置 `sandbox.enableWeakerNestedSandbox: true`（跳过 `--proc /proc`，`linux-sandbox-utils.ts:1380-1393`）。
- **fail-open 风险**：`isSandboxingEnabled()`（`sandbox-adapter.ts:532-547`）在依赖缺失时返回 false，命令直接**非沙箱运行**（网络不受限）。这就是"所有网络可访问"的另一可能解释——不是 `*` 生效，而是沙箱整体静默停用。除非设置 `sandbox.failIfUnavailable: true` 才会 fail-closed 拒绝启动（`REPL.tsx:2320-2323`）。

---

## 3. 处理方案（任务一结论）

### 3.1 立即可用的正确配置

放弃 `*`，使用显式域名清单：

```json
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "enableWeakerNestedSandbox": true,
    "network": {
      "allowedDomains": [
        "raw.githubusercontent.com",
        "github.com",
        "*.github.com",
        "api.github.com",
        "codeload.github.com",
        "objects.githubusercontent.com"
      ]
    }
  }
}
```

- `raw.githubusercontent.com` 必须单独列出：`*.github.com` 只匹配 `x.github.com` 形式的严格子域（`domain-pattern.ts:31-36`），且通配符**不匹配 IP 字面量**。
- `failIfUnavailable: true` 消除"沙箱静默停用导致全网可通"的隐患。

### 3.2 交互式放行路径（不改配置文件）

会话中触发网络拦截时，REPL 弹出 `SandboxPermissionRequest` 对话框（`REPL.tsx:4609`），选 **"Yes, and don't ask again for \<host\>"** 会：

1. 写入 `.claude/settings.local.json` 的 `permissions.allow: ["WebFetch(domain:raw.githubusercontent.com)"]`（`REPL.tsx:4620-4639`）；
2. 调用 `SandboxManager.refreshConfig()` 热更新运行中的代理（`sandbox-adapter.ts:798-803`）——`WebFetch(domain:X)` 规则会被合并进 `allowedDomains`（`sandbox-adapter.ts:201-209`）。

### 3.3 Docker 侧检查清单

| 检查项 | 命令/配置 |
|---|---|
| 依赖安装 | `apt install bubblewrap socat`（缺 seccomp 工具仅降级 unix socket 限制，不影响域名过滤） |
| 容器安全选项 | `docker run --security-opt seccomp=unconfined --security-opt apparmor=unconfined ...` |
| 嵌套沙箱模式 | `sandbox.enableWeakerNestedSandbox: true` |
| 防静默降级 | `sandbox.failIfUnavailable: true` |
| 验证生效 | 沙箱内 `curl -sI https://raw.githubusercontent.com` 应通；`curl -sI https://example.com` 应返回 403 `X-Proxy-Error: blocked-by-allowlist` |

### 3.4 如需向 Anthropic 反馈的改进点

1. **settings 层补校验**：`sandboxTypes.ts:17` 的 `allowedDomains: z.array(z.string())` 应复用 sandbox-runtime 的 `domainPatternSchema`，让 `["*"]` 在配置加载时即报错，而非静默无效。
2. **运行时双路径校验对齐**：`SandboxManager.initialize()` / `updateConfig()` 编程式入口不跑 schema 校验（`sandbox-manager.ts:366-378, 1115-1128`），导致同一非法值在文件路径被拒、在 API 路径变 allow-all，应统一。
3. **明确语义或文档**：README 只写"supports wildcards like `*.example.com`"，未说明无 allow-all 语法；若确需 allow-all，应提供显式开关（如 `network.allowAllOutbound`）而非依赖未文档化的 `*`。

---

## 4. 交互方案设计（任务二）

### 4.1 目标

当用户在沙箱内触发网络拦截，或配置了无效/过宽的域名模式时，提供**可理解、可操作、可持久化**的交互路径，消除"配置了却不知道为什么没生效"的黑盒感。

### 4.2 交互流程设计

```
┌─────────────────────────────────────────────────────────────┐
│ 触发点 A：命令执行时网络请求被代理拦截 (403 blocked-by-allowlist) │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
[拦截提示卡] "沙箱网络拦截：raw.githubusercontent.com:443"
  ├─ 命中规则：无（未在 allowedDomains 中）
  ├─ [本次放行]  → 仅本次 ask-callback 返回 true
  ├─ [放行并记住] → 写 permissions.allow WebFetch(domain:host)
  │                 + refreshConfig() 热生效（现有行为，保留）
  ├─ [查看当前网络配置] → 展开 /sandbox 网络面板（见 4.3）
  └─ [拒绝] → 默认

┌─────────────────────────────────────────────────────────────┐
│ 触发点 B：settings.json 加载 / /sandbox 面板打开时            │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
[配置诊断] 对 sandbox.network.allowedDomains 逐条校验：
  ├─ "*"        → ⚠️ "无效：不允许 allow-all 通配符（安全策略）。
  │               该条目将被忽略，不会匹配任何域名。"
  │               [一键替换为常用域名清单]
  ├─ "*.com"    → ⚠️ "过宽通配符，已忽略"
  ├─ "github.com" → ✅ 精确匹配 github.com（不含子域）
  │               💡 提示："如需子域，加 *.github.com"
  └─ 展示生效后的合并视图（settings 域名 + WebFetch(domain:) 规则）

┌─────────────────────────────────────────────────────────────┐
│ 触发点 C：沙箱初始化失败（Docker 缺依赖 / userns 受限）        │
└─────────────────────────────────────────────────────────────┘
        │
        ▼
[启动横幅] 现有" sandbox disabled · /sandbox "被动提示 → 升级：
  ├─ failIfUnavailable=false：⚠️ 明确警告"命令将在无网络隔离下运行"
  │   + 一键修复指引（apt install bubblewrap socat / docker 安全选项）
  └─ failIfUnavailable=true：❌ 阻断启动（现有行为，保留）
```

### 4.3 `/sandbox` 网络配置面板增强（SandboxConfigTab）

新增三块内容：

1. **域名规则有效性标注**：逐条渲染 allowedDomains，无效条目（`*`、`*.com`、含非法字符）标红并附原因，避免"配置了但静默无效"。
2. **合并来源视图**：区分"来自 sandbox.network.allowedDomains"与"来自 permissions WebFetch(domain:) 规则"两组，hover 显示来源文件路径。
3. **连通性自测按钮**：对每个域名发起一次经代理的 HEAD 请求，展示 放行/拦截 实测结果，把"配置是否生效"从猜测变成可观测事实。

### 4.4 文案规范

| 场景 | 文案（中） | 原则 |
|---|---|---|
| `*` 被诊断拦截 | "`*` 不是合法的 allowedDomains 取值。出于安全设计，放行需逐域名列出；如需全放行请关闭沙箱而非使用通配符。" | 说明"为什么"而不只是"不行" |
| 拦截弹窗 | "该域名不在沙箱放行清单中。放行后可选择记住，规则写入 `.claude/settings.local.json` 并立即生效。" | 告知持久化位置与热生效 |
| Docker 降级警告 | "沙箱依赖不可用（缺 bubblewrap/socat 或容器限制），当前命令无网络隔离运行。设置 `failIfUnavailable: true` 可改为阻断。" | 暴露 fail-open 事实，给出开关 |

### 4.5 验收标准

- 配置 `allowedDomains: ["*"]` 时，`/sandbox` 面板在 3 秒内给出明确无效标注与替代建议；
- 拦截弹窗"放行并记住"后，同域名后续请求无需再次询问，且规则可在 settings.local.json 中查验；
- Docker 缺依赖启动时，用户能在首屏看到明确的 fail-open 警告而非仅被动提示；
- 所有诊断信息可通过 `file:line` 级来源（schema 错误信息、代理 403 头）回溯。

---

## 5. 网络 Hook 现状分析（源码实证）

> 调研问题：Claude Code 源码中是否存在网络 Hook，能在请求初次发生时提示用户如何配置 `allowedDomains` / `deniedDomains`？
>
> **结论：Hook 存在且链路完整，但弹窗只做"放行/拒绝"决策，全程不向用户提及 `sandbox.network.allowedDomains` / `deniedDomains` 配置项。**

### 5.1 Hook 三层触发链路

**第 1 层：运行时钩子（sandbox-runtime 侧）**

`filterNetworkRequest`（`sandbox-manager.ts:154-176`）：域名不命中 allow/deny 清单时，调用宿主注入的 `sandboxAskCallback({host, port})` —— 这就是"请求初次发生时"的拦截点。无回调或设置了 `strictAllowlist` 时直接 fail-closed 拒绝。

**第 2 层：REPL 回调（Claude Code 侧）**

`REPL.tsx:2216` 的 `sandboxAskCallback` 按运行模式分三条分支：

| 分支 | 行为 |
|---|---|
| 普通交互 | 请求入队 `sandboxPermissionRequestQueue`，弹出本地对话框 |
| Swarm worker | 通过 mailbox 转发给 leader 审批（`sendSandboxPermissionRequestViaMailbox`） |
| Bridge 模式（远程控制 / claude.ai） | 作为 `can_use_tool` 控制请求转发给远端用户；响应会一次性解决同 host 的所有挂起请求 |

Headless / SDK 模式对应 `cli/structuredIO.ts:731-753` 的 `createSandboxAskCallback`（出错时 fail-closed 返回 false）。

**第 3 层：弹窗组件**

`REPL.tsx:4609` 渲染 `SandboxPermissionRequest`（`components/permissions/SandboxPermissionRequest.tsx:154`），标题 **"Network request outside of sandbox"**，实际 UI 内容：

```
Network request outside of sandbox

Host: raw.githubusercontent.com

Do you want to allow this connection?
  ❯ Yes
    Yes, and don't ask again for raw.githubusercontent.com
    No, and tell Claude what to do differently (esc)
```

**组件源码（15-162 行）中没有任何文案提到 `allowedDomains`、`deniedDomains` 或 settings.json** —— 没有任何配置引导。

### 5.2 持久化路径：写的是 permissions，不是 allowedDomains

选 "Yes, and don't ask again" 后的处理（`REPL.tsx:4620-4639`）：

```ts
rules: [{ toolName: WEB_FETCH_TOOL_NAME, ruleContent: `domain:${approvedHost}` }],
behavior: allow ? 'allow' : 'deny',
destination: 'localSettings'   // → .claude/settings.local.json
```

写入的是 `permissions.allow: ["WebFetch(domain:raw.githubusercontent.com)"]`，随后 `SandboxManager.refreshConfig()` 热生效。它能生效是因为 `convertToSandboxRuntimeConfig`（`sandbox-adapter.ts:201-209`）会把 `WebFetch(domain:X)` 规则**合并进** `allowedDomains` —— 殊途同归，但用户从 UI 上永远感知不到 `sandbox.network.allowedDomains` 的存在。

### 5.3 现状的三个缺口

| # | 缺口 | 证据 |
|---|---|---|
| 1 | **弹窗缺配置引导**：用户不知道存在 `sandbox.network.allowedDomains` 这个批量管理入口 | `SandboxPermissionRequest.tsx` 全文无配置相关文案 |
| 2 | **deny 不可持久化**：弹窗 "No" 只拒绝本次，没有 "No, and always deny" 选项；运行时机制完全支持（`deniedDomains` 优先检查），只是 UI 未暴露 | `SandboxPermissionRequest.tsx:68-106` 选项数组中 persist 仅绑定在 "Yes" 分支 |
| 3 | **双轨写入易困惑**：交互放行写 permissions，手工配置写 sandbox.network，两处来源只能靠读 `sandbox-adapter.ts` 合并逻辑才能理解 | `sandbox-adapter.ts:198-209` |

> 已存在的企业管控分支：`shouldAllowManagedSandboxDomainsOnly()`（组件 61 行）开启时隐藏 "don't ask again"，managed 策略下不落地本地规则 —— 后续交互改造必须保留该分支。

### 5.4 对 §4 交互方案的修订

基于以上实证，修订 §4.2"触发点 A"的弹窗设计：

```
[拦截提示卡] "Network request outside of sandbox"
  Host: raw.githubusercontent.com
  Do you want to allow this connection?

  ❯ Yes
    Yes, and don't ask again for raw.githubusercontent.com
    No, and always deny this host                    ← 新增：deny 持久化
    No, and tell Claude what to do differently (esc)

  ─────────────────────────────────────────────
  💡 已写入 permissions 规则；批量管理域名请使用
     sandbox.network.allowedDomains，详见 /sandbox   ← 新增：配置引导（dim 文案）
```

对应验收标准补充（并入 §4.5）：

- 弹窗 deny 持久化选项选中后，规则写入 `permissions.deny: ["WebFetch(domain:host)"]`，同域名后续请求直接拦截不再询问；
- 弹窗底部配置引导文案在 managed 模式（`shouldAllowManagedSandboxDomainsOnly()` 为 true）下自动隐藏；
- `/sandbox` 面板能同时展示两类来源（`sandbox.network.allowedDomains` 与 permissions `WebFetch(domain:)` 规则）的合并视图，消除双轨困惑。
