# Claude Agent 沙箱网络审批 — SDK 通道缺口分析

> 状态：**方案 A 已实施（2026-07-26，含 SDK 迁移）**——§5 方案 A 已随
> `claude-code-sdk 0.0.25 → claude-agent-sdk 0.2.128` 迁移一并落地：
> `agent_runner.py` 接线 `can_use_tool=_can_use_tool`，`SandboxNetworkAccess`
> 控制请求桥接至 `on_tool_confirmation_request` 确认链，前端网络变体确认卡
> 上线。SDK 迁移是实施前提：0.0.25 的控制响应序列化为旧方言
> `{"allow": true}` / `{"allow": false, "reason"}`，被部署的新版 CLI 按
> `permissionToolOutputSchema`（`{behavior:'allow', updatedInput}` /
> `{behavior:'deny', message}`）拒绝，导致审批 fail-closed（生产表现为
> curl 403 blocked-by-allowlist）；0.2.128 序列化对齐已验证（见 §2.3 注）。
> 关联文档：
> - `claude-agent-sandbox-network-permission-tool.md`（SandboxPermissionRequest 现行设计）
> - `claude-agent-sandbox-network-permission-sequence.md`（模块交互图）
> - `../sandbox-wildcard-network-issue/interaction-design.md`（Claude Code 原生 Hook 现状分析，§5）
> 日期：2026-07-23；2026-07-26 实施方案 A（含 SDK 迁移）

---

## 1. 问题

Ink & Memory 通过 `claude_agent_sdk`（Python SDK，`ClaudeSDKClient`，见 `backend/libs/claude_agent_kit/server/simple_cas_client.py`；2026-07-26 前为 `claude_code_sdk`）在本地以 headless 方式驱动 Claude Code。问题：**能否直接触达 Claude Code 原生的沙箱网络审批弹窗（SandboxPermissionRequest）？**

**结论：触达不到，且是三层原因叠加。**

## 2. 三层事实（源码/依赖实证）

### 2.1 Ink 弹窗物理上不存在于 SDK 链路

`SandboxPermissionRequest` 是交互式 REPL 的 Ink UI 组件（restored-src `REPL.tsx:4609` 渲染，组件 `components/permissions/SandboxPermissionRequest.tsx`）。SDK/headless 模式没有 Ink 渲染树，该弹窗不可能出现。

### 2.2 SDK 模式的等价通道：can_use_tool 控制请求（后端未接）

CLI 在 headless 模式的降级路径是 `createSandboxAskCallback`（restored-src `cli/structuredIO.ts:731-753`）：把沙箱网络询问包装为 `can_use_tool` 控制请求发给 SDK 消费方：

```
tool_name: SANDBOX_NETWORK_ACCESS_TOOL_NAME   # 常量值为 "SandboxNetworkAccess"（structuredIO.ts:62）
input:     { host }
```

回调出错或无应答时 fail-closed 返回 false（`structuredIO.ts:750`）。
**实证：Ink & Memory backend 全库搜索 `can_use_tool` / `canUseTool` / `SANDBOX_NETWORK_ACCESS` —— 零命中，无任何处理。**

**关键分层认知（2026-07-26 修正，据官方文档 <https://code.claude.com/docs/en/agent-sdk/user-input>）**：PreToolUse 与 can_use_tool 是**两条独立的控制通道**。PreToolUse 是"发布到执行器之前"的工具权限 hook，只见得到工具调用评估；而沙箱网络询问是 CLI 内部系统级控制（sandbox-runtime 代理拦截 → `sandboxAskCallback`），不走工具权限评估，**PreToolUse 永远收不到它**——它只经 can_use_tool 控制请求投递。这解释了为什么已实现的 PreToolUse 层 SandboxPermissionRequest 模式（`claude-agent-sandbox-network-permission-tool.md`）覆盖不了 §4 的残留缺口：两者治理的是不同层面（执行前工具门控 vs 运行时代理拦截）。

### 2.3 SDK 能力：0.0.25 已具备 can_use_tool（此前结论有误，已修正；2026-07-26 起依赖已迁移至 claude-agent-sdk 0.2.128）

后端当时依赖 `claude_code_sdk 0.0.25`（`backend/.venv/lib/python3.12/site-packages/claude_code_sdk`）。**修正后实证**：`types.py:308` 即 `ClaudeCodeOptions.can_use_tool: CanUseTool | None`，配套类型齐全——`PermissionResultAllow(updated_input, updated_permissions)`（types.py:66）、`PermissionResultDeny(message, interrupt)`（types.py:75）、`ToolPermissionContext(signal, suggestions)`（types.py:55）、`CanUseTool = Callable[[str, dict, ToolPermissionContext], Awaitable[PermissionResult]]`（types.py:85-87）。

> 此前"包内搜索零命中、SDK 不具备该能力"的结论**有误**：当时 Grep 未开 `include_ignored`，`.venv` 被 `.gitignore` 静默跳过所致。真实根因不是"SDK 不支持"，而是**后端从未把 `can_use_tool` 参数接进 `ClaudeCodeOptions`**（构造点 `agent_runner.py:2164`），CLI 发出的 `SandboxNetworkAccess` 控制请求无人应答，按 `structuredIO.ts:750` fail-closed 静默 deny。
>
> 官方文档同时确认：can_use_tool 回调**不会为已被前置流程放行的工具触发**（"The callback never fires for auto-approved tools"），因此接线后不会与 PreToolUse 层已显式 allow/deny 的工具产生双重询问；沙箱网络询问不是工具调用，不受此前置去重影响。
>
> **后续注（2026-07-26，实际生产 bug）**：0.0.25 虽有 `can_use_tool` 参数，但其控制协议响应序列化是**旧方言**——`{"allow": true}` / `{"allow": false, "reason"}`；部署的新版 CLI 按 `permissionToolOutputSchema` 校验（期望 `{behavior:'allow', updatedInput}` / `{behavior:'deny', message}`），校验失败 → 审批 fail-closed（生产表现为 curl 403 blocked-by-allowlist）。因此"无需升级 SDK"的判断作废，**必须迁移到改名后的 `claude-agent-sdk`**（已落地 0.2.128：`_internal/query.py` 的 can_use_tool 分支输出 `{"behavior": "allow", "updatedInput": …}` / `{"behavior": "deny", "message": …}`，方言对齐已验证）。

## 3. 为什么日常未暴露

流量到不了 CLI 内部 ask 层，因为 Ink & Memory 的治理点在更上游：

1. **PreToolUse 层**（`claude-agent-sandbox-network-permission-tool.md` 已实现）：执行前拦截 WebFetch / WebSearch / 网络类 Bash，弹 Ink & Memory 自己的确认卡；
2. **每线程 settings 写入**（`backend/libs/claude_agent_kit/server/workspace.py:297-317`）：`allowedDomains` 写入 `.claude/settings.json`，沙箱代理对清单内域名直接放行，CLI 内部 `sandboxAskCallback` 不触发。

## 4. 残留缺口

唯一会掉入缺口的场景：**沙箱内 Bash 命令访问 `allowedDomains` 之外的域名**（如对未配置主机执行 `curl`）。链路：

```
sandboxed Bash → sandbox-runtime 代理拦截（403 blocked-by-allowlist）
  → CLI 内部 sandboxAskCallback 触发
  → can_use_tool 控制请求（无人应答）
  → fail-closed deny
```

用户无任何弹窗，只能在工具输出中看到 403，排障体验为黑盒。

> **修复路径（2026-07-26 已实施）**：该缺口的正确治理点不是 PreToolUse（系统级控制请求不经过它），而是在 `ClaudeAgentOptions` 接线 `can_use_tool` 回调，把 `SandboxNetworkAccess` 控制请求桥接到 `on_tool_confirmation_request` 确认链——见 §5 方案 A。

## 5. 弥合方案

| 方案 | 做法 | 代价 |
|---|---|---|
| A. 接线 can_use_tool（**已实施 2026-07-26**） | 在 `agent_runner.py` 构造 `ClaudeAgentOptions` 时传 `can_use_tool` 回调：`tool_name == "SandboxNetworkAccess"` 的请求桥接到现有 `on_tool_confirmation_request` 确认链（`backend/libs/claude_agent_kit/types.py`），复用 SSE `tool-approval-request` 与前端网络确认卡（`confirmationKind: "sandbox_network"`），返回 `PermissionResultAllow/Deny`。**实施前提：SDK 迁移 `claude-code-sdk 0.0.25` → `claude-agent-sdk 0.2.128`**——0.0.25 序列化方言过旧被新版 CLI 拒绝（§2.3 后续注） | 小，纯接线；与 PreToolUse 层互补不冲突（官方保证 auto-approved 工具不重复触发） |
| B. 保持 fail-closed + 收窄缺口 | 依赖 PreToolUse 预检 + "放行并记住"扩清单；在 deny 输出追加可诊断文案（提示到设置页追加域名） | 小，纯增量 |
| C. 双层清单对齐 | 保证写入 CLI settings 的 allowlist 始终 ⊇ Ink & Memory 判定结果，消除判定漂移 | 小，配置层改动 |

> 实施记录（2026-07-26）：方案 A 已落地，前提为 SDK 迁移至 `claude-agent-sdk 0.2.128`（`requirements.txt` / `pyproject.toml` 已更新；`backend/.venv` 已安装并卸载 `claude-code-sdk`）。序列化对齐证据：`claude_agent_sdk/_internal/query.py` can_use_tool 分支输出 `{"behavior": "allow", "updatedInput": …}` / `{"behavior": "deny", "message": …}`，无旧 `{"allow": true/false}` 方言。B/C 仍为可选增量，未实施。
>
> **CLI 配对决策（2026-07-26）**：0.2.128 transport `_find_cli` 内置优先会遮蔽生产 Docker 打过 apply-seccomp 补丁的 npm CLI（故障复发实证）。决策：**`cli_path` 锁定系统/npm CLI**（`sdk_env.apply_cli_path_to_options()`：`CLAUDE_CODE_CLI_PATH` → `shutil.which("claude")` → bundled 兜底），npm CLI 同步升级到 **2.1.220** 与内置线对齐；2.1.220 单一二进制布局使 vendor 补丁不可行，apply-seccomp passthrough 改为 `sandbox.seccomp.applyPath` settings 覆盖（详见 `claude-sdk-env-design.md` §5.5A 与 `claude-agent-workspace-sandbox.md`）。

## 6. 附：关联概念澄清（三处）

### 6.1 持久化路径差异（permissions.allow 与本系统）

Claude Code 原生 REPL 的 "don't ask again" 写 `.claude/settings.local.json` 的 `permissions.allow: ["WebFetch(domain:host)"]`（restored-src `REPL.tsx:4620-4639`），靠 `convertToSandboxRuntimeConfig` 把 `WebFetch(domain:X)` 合并进 allowedDomains 生效。本系统不照搬此路径：域名清单的权威存储是 system_config 的 `sandbox_network_allowed_domains`（`PUT /api/system-config`，`backend/routers/system_config.py:100-122`），PreToolUse 判定层直接读取。故"放行并记住"在本系统的落地方式为：弹窗第三选项 → `PUT /api/system-config` 追加域名（或扩展 `tool-confirm` 协议带 `remember: true` 由后端落库）。当前实现维持二元 批准/拒绝（`claude-agent-tool-confirmation-flow.md` 两态约束），持久化为后续迭代。

### 6.2 Bridge 模式（远程控制 / claude.ai）

Claude Code 的远程控制能力：本地 CLI 会话经 REPL bridge 桥接到 claude.ai 网页端，用户可从浏览器/手机操控本地会话。沙箱审批触发且 bridge 已连接时（restored-src `REPL.tsx:2254-2294`），系统同时：① 本地弹 `SandboxPermissionRequest`；② 将请求作为 `can_use_tool` 控制请求推给远端。两边竞争响应，先点先生效，另一方通过 `cancelRequest` 撤销；响应一次性解决同 host 所有挂起请求。Swarm worker 的 mailbox 转发（`sendSandboxPermissionRequestViaMailbox`）是同一思路在多智能体场景的变体。对本系统的启示：`on_tool_confirmation_request` → SSE `tool-approval-request` → Web 弹窗链路与 bridge 同构，协议设计（toolCallId、竞争解决、超时兜底）可直接对标。

### 6.3 Swarm worker 路径（多智能体团队审批路由）

Claude Code Agent Swarms（Teammate）场景下，worker 进程的沙箱网络审批不经本地弹窗，而是经 **mailbox** 转发给团队 leader（restored-src `REPL.tsx:2218` 第一分支）。

**触发条件**（`permissionSync.ts:596-601`）：`isAgentSwarmsEnabled()` 且 `isSwarmWorker()` —— 进程环境注入 team name + agent ID 且非 `team-lead`。

**完整链路**：

```
Worker 进程（沙箱内网络请求被拦）
  └─ sendSandboxPermissionRequestViaMailbox(host, requestId)     permissionSync.ts:805
       └─ sandbox_permission_request 消息
          {requestId, workerId, workerName, workerColor, host}   teammateMailbox.ts:576
       └─ writeToMailbox(leaderName, ...)：in-process（同进程 teammate）
          或文件邮箱（.claude/teams/<team>/）
  └─ registerSandboxPermissionCallback({requestId, resolve})     ← promise 挂起
  └─ AppState.pendingSandboxRequest                              ← worker 侧等待指示

Leader 进程（交互式 REPL）
  └─ useInboxPoller 轮询收件箱（useInboxPoller.ts:398-420）
       └─ isTeamLead() → workerSandboxPermissions 队列 → 审批 UI
  └─ sendSandboxPermissionResponseViaMailbox(workerName, requestId, host, allow)

Worker 进程
  └─ 收到响应 → resolve(allow) → 沙箱 ask 回调返回
```

**容错**：邮箱发送失败（缺 team/leader/worker ID）时降级回本地弹窗队列（`REPL.tsx:2224-2230`）；请求 ID 为 `sandbox-<timestamp>-<random>`（`generateSandboxRequestId`）。

**对 Ink & Memory 的相关性：双重不可达**——

1. **前置条件不成立**：Swarm 要求以 teammate 方式启动 CLI 进程（注入 team name + agent ID 环境）。后端 `ClaudeSDKClient` 单进程驱动、无团队上下文，`isSwarmWorker()` 恒为 false，该分支为死代码；
2. **终点依赖交互式 leader**：即使启用 swarm，worker 的审批请求最终落在 leader 邮箱，而 leader 审批 UI 仍是 Ink 组件（`useInboxPoller` → REPL 渲染）；headless 下无人轮询点击，请求堆积在 `.claude/teams/` 文件邮箱。

**设计启示**：bridge（转发 claude.ai 远程用户）与 mailbox（转发团队 leader）是同一思想的两种投递——把审批权从"无交互能力的执行体"路由给"有交互能力的对端"。Ink & Memory 的 SSE `tool-approval-request` → Web 前端是第三种实现，且具天然优势：payload 带 `toolCallId`、每 thread 独立 SSE 通道；未来若做多 Agent（每 worker 一 thread），审批路由按 thread 天然隔离，无需 mailbox 的 requestId 注册/轮询机制——仅需在 payload 增加 `workerId` / `agentName` 展示字段，让审批人识别发起方。
