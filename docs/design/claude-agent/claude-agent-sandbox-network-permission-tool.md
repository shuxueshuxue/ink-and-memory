# Claude Agent 沙箱网络 SandboxPermissionRequest 权限工具设计

> 状态：**已修订（2026-07-26）——现行架构为 can_use_tool 单一通道**
> - 2026-07-23 初版在 PreToolUse 层实现网络门禁（步骤 ②.5），同日补充
>   can_use_tool 运行时代理通道。
> - **2026-07-26 架构反转：PreToolUse 层网络门禁已拆除。** 原因：网络策略
>   是系统级控制，由 Claude Code 自身沙箱执行（workspace.py 写入每线程
>   `.claude/settings.json` 的 `sandbox.network`），其询问只经 `can_use_tool`
>   通道投递；PreToolUse 门禁属于错误层级的重复实现。被拆除的内容：
>   步骤 ②.5 `_apply_sandbox_network_permission` 及其调用点、
>   `_match_sandbox_network_allowed_domain` / `_extract_network_tool_host` /
>   `_is_ip_literal` 辅助函数、full-access/低敏跳过守卫、步骤 ⑦ payload
>   鉴别扩展、`AgentRunOptions.sandbox_network_allowed_domains` plumbing、
>   `networkRequest.source` 字段（单一触发源后不再需要）。历史设计保留于
>   附录 A。`sandbox_network_mode` plumbing 保留（can_use_tool payload 仍
>   上报 `policyMode`）；system_config 键与 workspace.py 的 settings.json
>   写入器不在拆除范围——它们配置 CLI 自身沙箱。
> - **2026-07-26 SDK 迁移（can_use_tool 通道的生效前提）**：
>   `claude-code-sdk 0.0.25` → `claude-agent-sdk 0.2.128`。0.0.25 虽有
>   `can_use_tool` 参数，但控制响应序列化为旧方言 `{"allow": true}`，
>   被部署的新版 CLI 按 `permissionToolOutputSchema` 拒绝 → 审批
>   fail-closed（生产 bug）；0.2.128 输出 `{behavior:'allow', updatedInput}`
>   / `{behavior:'deny', message}`，方言对齐已验证。见
>   `claude-agent-sandbox-network-sdk-gap.md` §2.3 后续注与 §5 实施记录。
> 关联文档：
> - `claude-agent-permission-policy.md`（权限等级与决策顺序）
> - `claude-agent-tool-confirmation-flow.md`（工具确认链路，§6.3）
> - `claude-agent-sandbox-network-permission-sequence.md`（交互时序图）
> - `claude-agent-sandbox-network-interaction-plan.md`（沙箱网络配置设计）
> - `../sandbox-wildcard-network-issue/interaction-design.md`（Claude Code 原生 SandboxPermissionRequest 现状分析，§5）
> 日期：2026-07-23（初版）；2026-07-26（架构反转修订）

---

## 1. 背景与目标

Claude Code 原生的 `SandboxPermissionRequest` 弹窗（restored-src `REPL.tsx:2216` → `SandboxPermissionRequest.tsx`）依赖 sandbox-runtime 的 `sandboxAskCallback`，在 headless/SDK 模式下该回调 fail-closed（`cli/structuredIO.ts:731-753`），因此 Ink & Memory 需要自己的按请求粒度网络审批交互。

**架构定位（2026-07-26 明确）**：网络策略是**系统级控制**——
`sandbox_network_mode` / `sandbox_network_allowed_domains` 由
`backend/libs/claude_agent_kit/server/workspace.py` 写入每线程
`.claude/settings.json` 的 `sandbox.network`，由 Claude Code 自身沙箱
（bwrap `--unshare-net` + 过滤代理）强制执行。当 sandboxed Bash 在代理层
命中未授权域名时，CLI 发起**系统级 control request**——不经 PreToolUse
hook，只通过 SDK 的 `can_use_tool` 回调通道送达。本设计将该通道接入
Ink & Memory 既有 `on_tool_confirmation_request` 确认链路，成为**唯一的
网络确认通道**。

| 业务配置 | 行为 |
|---|---|
| 网络禁用（`sandbox_network_mode = "disabled"`） | 双层硬拒：PreToolUse 层 `_apply_disabled_network_permission` 拒绝 `WebFetch`/`WebSearch`/常见网络 Bash 命令（2026-06-21 既有行为，未变）；运行时 `sandbox.network` 配 `deniedDomains=["*"]` |
| 白名单（`sandbox_network_mode = "allowlist"`） | CLI 沙箱代理按 `sandbox.network.allowedDomains` 放行清单内域名；清单外域名触发 `can_use_tool` 询问 → Ink & Memory 网络变体确认卡 |
| 开放网络（`sandbox_network_mode = "open"`） | 不写 `sandbox.network` = 不限制出网；**无逐次询问**（语义已回退，见 `claude-agent-sandbox-network-interaction-plan.md`） |

## 2. 现行机制：can_use_tool 确认通道

- 入参：`tool_name == "SandboxNetworkAccess"`，`input == {"host": <hostname>}`；
- SDK 支持：`claude_agent_sdk 0.2.128` 的 `ClaudeAgentOptions.can_use_tool: CanUseTool | None`（2026-07-26 迁移；此前 `claude_code_sdk 0.0.25` 的序列化方言过旧被新版 CLI 拒绝，见状态头），结果类型 `PermissionResultAllow(updated_input, updated_permissions)` / `PermissionResultDeny(message, interrupt)`；
- CLI 配对（2026-07-26）：`cli_path` 经 `sdk_env.apply_cli_path_to_options()` 锁定系统/npm CLI（2.1.220，与内置线对齐；内置优先会遮蔽 Docker 的 apply-seccomp 补丁 CLI）；apply-seccomp passthrough 经 `sandbox.seccomp.applyPath` settings 覆盖实现（2.1.220 单一二进制，无 vendor 文件可补丁）；
- 官方契约保证：`can_use_tool` 不会对权限流中已被解析的工具再次触发——本系统的 PreToolUse hook 对所有工具返回显式 allow/deny，因此接线后**不会重复弹窗**（含 AskUserQuestion，其由 hook 路径带 answers 解决）。

实现（`agent_runner.py`）：与 `_pre_tool_use_hook` 同闭包定义
`_can_use_tool(tool_name, input_data, context)` 并传入
`ClaudeAgentOptions(can_use_tool=...)`：

| 触发 | 行为 |
|---|---|
| `SandboxNetworkAccess` | 提取 `host`；走与 PreToolUse 步骤 ⑦ **相同**的 `on_tool_confirmation_request` 确认链路，payload 携带 `confirmationKind: "sandbox_network"` + `networkRequest: {host, policyMode, matchedAllowedDomain: null}`；批准 → `PermissionResultAllow(updated_input=input_data)`；拒绝/失败/超时 → `PermissionResultDeny(message=…)`，message 指明目标 host 并提示"可在设置中将该域名加入沙箱网络 allowedDomains" |
| 其他 tool_name | 走同一通用确认链路（不带 discriminator），映射方式镜像步骤 ⑦（含 AskUserQuestion 的 answers 合并进 updated_input）；按官方契约此分支极少触发 |
| 回调内任意异常 / 无确认回调 | 记录 warning 并 fail-closed → `PermissionResultDeny` |

## 3. 确认弹窗协议

复用现有链路，零新通道：

```
CLI 沙箱代理拦截 → SDK can_use_tool
  → runner._can_use_tool → callbacks.on_tool_confirmation_request(payload)
  → service._make_tool_confirm_cb（service.py，~1580-1650 行）
  → SSE tool-approval-request {toolCallId, toolName, input, confirmationKind, networkRequest}
  → 前端 ToolConfirmationDock（网络变体卡片）
  → POST /api/claude-agent/tool-confirm {thread_id, tool_call_id, approved, reason?}
  → ToolConfirmationStore.resolve → runner PermissionResultAllow/Deny
```

**payload 契约**：

```json
{
  "toolCallId": "...",
  "toolName": "SandboxNetworkAccess",
  "input": { "host": "cdn.example.com" },
  "confirmationKind": "sandbox_network",
  "networkRequest": {
    "host": "cdn.example.com",
    "policyMode": "allowlist",
    "matchedAllowedDomain": null
  }
}
```

前端 `toolConfirmation.ts` 的 `'sandbox-network'` `PendingConfirmationKind`
（由 `confirmationKind` 鉴别）驱动 `ToolConfirmationDock.tsx` 渲染网络变体
卡片：host、策略模式、二元 放行/拒绝。`claude-agent-transport.ts` 与
`claude-agent-sse-utils.ts` 透传 `confirmationKind` / `networkRequest`；
字段缺失时回退通用确认卡（向后兼容）。

> "放行并记住"（写入 `sandbox_network_allowed_domains` → `PUT /api/system-config`）列为后续迭代；本期 Dock 维持二元 批准/拒绝（`tool-confirmation-flow.md` §8.3 的两态约束）。

## 4. 行为矩阵（2026-07-26 现状）

| 触发 | disabled | allowlist | open |
|---|---|---|---|
| `WebFetch` / `WebSearch` | PreToolUse 硬拒（既有） | **无 Ink & Memory 门禁**：遵循既有通用权限策略（auto 模式下低敏自动放行）；域名行为由 CLI 自身权限/沙箱层处理 | 同 allowlist——无逐次询问 |
| 网络类 Bash（sandboxed） | PreToolUse 硬拒（既有）+ 运行时 `deniedDomains=["*"]` | 清单内域名沙箱代理放行；**清单外域名 → can_use_tool 网络确认卡** | 不写 `sandbox.network` = 不限制出网，无询问 |
| 网络类 Bash（非沙箱，如 workspace 关闭） | PreToolUse 硬拒（既有） | 走既有通用确认策略（高敏 Bash 弹窗，无网络鉴别字段） | 同左 |
| 非网络工具 | 现有分类不变 | 现有分类不变 | 现有分类不变 |

关键权衡：PreToolUse 门禁拆除后，`open` 模式不再有任何逐次确认
（`sandbox.network` 省略 = 不限制出网）；`allowlist` 模式下 `WebFetch`
访问清单外域名不再被我们的确认卡前置拦截（它遵循 CLI 自身权限流），
只有沙箱内 Bash 的运行时代理拦截会经 `can_use_tool` 弹卡。

## 5. 配置 plumbing（现状）

| 层 | 状态 |
|---|---|
| `backend/routers/system_config.py` | 不变——`sandbox_network_mode` / `sandbox_network_allowed_domains` 键为 CLI 沙箱配置的真相源 |
| `backend/libs/claude_agent_kit/server/workspace.py` | 不变——把上述配置写入每线程 `.claude/settings.json` 的 `sandbox.network` |
| `backend/claude_agent/service.py` | 读取配置用于 workspace 初始化（保留）；透传 `confirmationKind` / `networkRequest` 到 SSE（保留）；不再向 `AgentRunOptions` 传 allowed_domains（2026-07-26 移除） |
| `backend/libs/claude_agent_kit/types.py`（`AgentRunOptions`） | 仅保留 `sandbox_network_mode`（can_use_tool payload 上报 `policyMode` 用） |

## 6. 验收标准（2026-07-26 修订）

1. sandboxed Bash 命中清单外域名 → `can_use_tool` 收到 `SandboxNetworkAccess{host}` → 弹出网络变体确认卡；批准后 `PermissionResultAllow(updated_input)` 放行，拒绝后 `PermissionResultDeny` 回传且 message 含 host 与 allowedDomains 提示；
2. 确认链路异常 / 无确认回调 → fail-closed `PermissionResultDeny` 并记 warning；
3. 其他 tool_name 走同一通用确认链路（不带 discriminator），不重复弹窗；
4. `disabled` 模式行为与现状完全一致（PreToolUse 硬拒回归测试）；
5. 事件契约：`tool-approval-request` 携带 `confirmationKind: "sandbox_network"` 时前端渲染网络卡片，缺失时回退通用确认卡（向后兼容）；
6. `open` 模式无逐次网络确认（语义回退）；`allowlist` 模式 `WebFetch` 清单外域名不再被 Ink & Memory 前置拦截。

---

## 附录 A：PreToolUse 门禁历史设计（2026-07-23 实现，2026-07-26 拆除）

> 以下为被取代的初版设计，仅作历史记录保留。**勿再按本节实现。**

初版在 `_pre_tool_use_hook` 插入步骤 ②.5 `_apply_sandbox_network_permission`
（disabled 硬拒之后、full-access 之前）：

```
mode == "allowlist":
    提取目标 host（WebFetch/WebSearch 经 urllib.parse input.url；Bash 不解析）
    host 命中 allowedDomains  → return allow（低敏感度子类 sandbox_network_allowed）
    host 未命中 / 无法提取    → return None（落入 ⑦ 确认弹窗）
mode == "open":
    任意网络请求 → 落入 ⑦ 确认弹窗（每次），且步骤 ⑥ 低敏放行跳过网络类工具
mode == "disabled":
    不进入本步骤（② 已硬拒）
```

域名匹配语义（与 sandbox-runtime `domain-pattern.ts:25-37` 对齐）：
`example.com` 精确匹配（大小写不敏感，不含子域）；`*.example.com` 严格子域
（不匹配裸域、不匹配 IP 字面量）；裸 `*` 非法 → warning + 永不命中。

正确性约束：WebFetch/WebSearch 在 `_LOW_SENSITIVITY_QUERY_TOOL_NAMES` 内，
open 模式下步骤 ⑥ 必须跳过网络类工具，否则新规则被静默绕过；待审批网络
请求同样跳过步骤 ④ full-access allow（防止被完全访问模式吞掉）。

**拆除原因**：上述门控与 CLI 沙箱的系统级控制重复——`WebFetch`/Bash 的
真实出网由 sandbox-runtime 代理强制执行，其询问只经 `can_use_tool` 投递；
PreToolUse 层既看不到运行时代理拦截，又会对已被 CLI 沙箱放行的流量重复
审批。`open` 模式"每次询问"的产品语义随之回退。
