> **迁移来源**: Pawkeyland docs/app/design/Claude Code Runtime 服务入参与SSE响应报文整理.md
> **Ink & Memory 适配**: API 端点路径一致（`POST /api/claude-agent`）；necklace/pet/Mem0 等 Pawkeyland 专属字段已移除。
> **[Sync] 2026-05-24**: SSE 报文格式已与 Pawkeyland 完全对齐：`text-delta.delta`（原 `text`）、`text-start/end`（原 `text-done`）、分离 tool 事件、`error.errorText`（原 `message`）、`finish.finishReason`（原 `reason`）。  
> **[Sync] 2026-05-25**: 新增 §4.5.4 说明 SSE 事件收集机制：`collected_parts` 按发出顺序收集原始事件 dict，`_sse_events_to_ui_parts()` 在持久化时做线性转换。
> **[Sync] 2026-05-24**: backend `_make_tool_event_cb` 改为 `event.type` 分发（原 `payload.state`）；修复 `result` 事件导致 `toolCallId=null` 的错误 SSE 帧；新增 `registered_tool_call_ids` / `emitted_tool_input_ids` 去重集合到 `_TurnContext`；`_make_tool_confirm_cb` 增加 `turn_ctx` 参数与 `CancelledError` 处理。
> **[Sync] 2026-05-24**: frontend `claude-agent-transport.ts` 完全重写：移除旧 `text-delta.text` / `text-done` / `tool-event.state` / `finish.reason` / `error.message`；新增 `text-start` / `text-delta(delta)` / `text-end` / `tool-input-start` / `tool-input-available` / `tool-output-available` 独立事件处理；当时 `tool-approval-request` 不重复 emit chunks（backend 已单独发 tool-input-start/available）。
> **[Sync] 2026-05-24**: 启用 thinking 模式 — 迁移 Pawkeyland `thinking_delta` / `thinking` / `content_block_stop` 分支到 `_make_tool_event_cb`；`_TurnContext` 新增 `current_reasoning_id` / `has_thinking_delta` / `completed_streamed_reasoning_texts`；SSE 新增 `reasoning-start/delta/end` 三类事件；前端 transport 新增对应处理；`DISABLE_INTERLEAVED_THINKING` 未设置时 thinking 默认启用。
> **[Sync] 2026-05-27**: `tool_choice` 字段新增 `"manual"` 合法值；当时 `tool-approval-request` 触发条件扩展为"manual 模式全部工具 **或** auto 模式下工具名属于 `_ALWAYS_CONFIRM_TOOL_NAMES`（`AskUserQuestion`、`mcp__user__ask_user`）"；新增 §4.6.4 auto+AskUserQuestion SSE 顺序；`PreToolUse` hook `hookSpecificOutput` 格式迁移至 CLI ≥2.1 规范（`hookEventName` + `permissionDecision` + `updatedInput`）；前端 `ChatMessageList` 新增 `toolChoice` prop 在 manual 模式下为非 AskUserQuestion 工具显示 Approve/Cancel UI。
> **[Sync] 2026-06-07**: `tool-approval-request` 触发条件更新：auto 模式对当前 workspace `files/` 下的内置文件工具和低敏查询工具显式 allow；当时状态切换工具也进入前端确认侧路。该分类已被 2026-06-09 的 `switch_editor` 低敏策略取代。
> **[Sync] 2026-06-09**: 权限策略抽取为 [`claude-agent-permission-policy.md`](./claude-agent-permission-policy.md)；`Skill` 与 `mcp__editor__switch_editor` 归入 auto 低敏显式 allow。
> **[Sync] 2026-06-13**: Settings 完全访问模式仍会为 `AskUserQuestion` / `mcp__user__ask_user` 发送 `tool-approval-request`，以便前端显示问答表单并回传 answers。
> **[Sync] 2026-06-13**: 新增 `tool-input-delta` SSE 事件，用于把 SDK `input_json_delta.partial_json` 转发给前端；前端对内置 `Write` 工具使用终端式写入预览，设计见 [`write-tool-terminal-preview.md`](./write-tool-terminal-preview.md)。
> **[Sync] 2026-06-25**: 新增 `POST /api/claude-agent/threads/{thread_id}/stop`，作为前端主动停止当前运行 turn 的显式控制 API；普通 SSE 断线仍保持后台 turn 可重连。
> **[Sync] 2026-07-20**: 登记 claude-plan 两个新 SSE 事件 `plan-mode-changed` / `plan-updated`（§4.5.2 事件表 + §4.5.4 收集表 + §4.7.8 报文示例），均为生命周期帧、不入 `collected_parts`、不映射 UIMessageChunk；配套 `GET /api/claude-agent/threads/{thread_id}/plan` REST 端点契约见 [`claude-plan.md`](./claude-plan.md) §5.5。
> **[Sync] 2026-07-20**: 登记 claude-todo 新 SSE 事件 `todo-updated`（§4.5.2 事件表 + §4.5.4 收集表 + §4.7.9 报文示例），生命周期帧、不入 `collected_parts`、不映射 UIMessageChunk；配套 `GET /api/claude-agent/threads/{thread_id}/todos` REST 端点契约见 [`claude-todo.md`](./claude-todo.md) §5.5。
> **[Sync] 2026-07-23**: SandboxPermissionRequest——`tool-approval-request` 新增可选字段 `confirmationKind:"sandbox_network"` 与 `networkRequest:{host, policyMode, matchedAllowedDomain}`（§4.5.2 事件表）；字段缺失时前端回退通用确认卡，向后兼容。设计见 `claude-agent-sandbox-network-permission-tool.md`。
> **[Sync] 2026-07-26**: 触发条件④修订——PreToolUse 网络门禁拆除后，沙箱网络确认仅来自 SDK `can_use_tool` 通道的 `SandboxNetworkAccess` 运行时沙箱代理询问（§4.5.2 事件表）；曾短暂存在的 `networkRequest.source` 字段取消。

# Ink & Memory Claude Agent 服务入参与SSE响应报文整理

> 目标服务：`POST /api/claude-agent`
> 配套接口：`POST /api/claude-agent/tool-confirm`
> 代码依据：`backend/server.py`、`backend/claude_agent/service.py`、`backend/claude_agent/thread_factory.py`、`backend/claude_agent/context_builder.py`
> 前端消费：`frontend/src/lib/claude-agent-transport.ts`
> 关联设计稿：
> - `docs/design/claude-agent/claude-agent-service-design.md`
> - `docs/design/claude-agent/claude-agent-thread-session-patterns.md`

## 1. 背景与目标

Ink & Memory Claude Agent 业务主入口为 `POST /api/claude-agent`，SSE 协议与 Pawkeyland 保持一致。

本文目标是把服务的两类协议整理为可直接消费的设计真相源：

1. HTTP 入参协议：调用方可以传什么，哪些字段会被服务层归一或覆盖。
2. SSE 响应协议：服务会按什么顺序推送什么事件，每个事件包含哪些字段。

## 2. 范围界定

### 2.1 本文覆盖

- `POST /api/claude-agent` 的请求体契约、默认值、校验与服务层归一规则。
- `POST /api/claude-agent/tool-confirm` 的请求/响应契约。
- Claude Agent SSE 通道的传输约定、事件全集、事件顺序和字段语义。
- `pet_info`、`runtime`、硬件状态、`long_term_profile` 在服务层中的实际消费方式。

### 2.2 本文不覆盖

- 已下线旧聊天入口的协议细节。
- 前端如何渲染各类 SSE 事件。
- Claude SDK 内部消息原文格式。
- `onFinish` 后续 DB 落库扩展；当前服务尚未实现该部分。

## 3. 方案摘要

- pet-agent 业务主入口定义为 `POST /api/claude-agent`，输出 `text/event-stream`，每个 SSE frame 只写 `data: {json}\n\n`，事件类型由 JSON 内的 `type` 字段标识，不额外写 `event:` 行。
- 请求模型是“强约束外层字段 + 弱约束上下文字典”的混合模式：外层字段由 `ClaudeAgentRequest` 明确约束，`pet_info` 与 `runtime` 保持开放字典，但服务层只消费其中少数字段。
- 请求中不再传入 `conversation_id`；服务层以 `(user_id, persona_id)` 为键查询 DB 展开会话续接。首轮 情况 Runner 自动生成新 `session_id`，`onFinish` 后绑定到 `chat_session`。
- SSE 事件分为 4 类：元数据类（`message-metadata`）、文本/思考类（`text-*` / `reasoning-*`）、工具类（`tool-*`）、结束/错误类（`finish` / `error`）。
- Runner 注册 `PreToolUse` hook。`tool_choice=auto` 时，目标位于当前 workspace `files/` 下的内置文件工具、低敏查询工具、`Skill` 与 `switch_editor` 会被显式 allow；高敏执行/写入/交互工具进入 `on_tool_confirmation_request` 侧路等待前端确认。`tool_choice=manual` 时所有工具均进入确认侧路，前端显示 Approve/Cancel UI。完整矩阵见 [`claude-agent-permission-policy.md`](./claude-agent-permission-policy.md)。

## 4. 详细设计

### 4.1 服务边界与入口

pet-agent 业务服务在当前仓库中由以下两个 HTTP 入口组成：

| 接口 | 作用 | 响应类型 |
|---|---|---|
| `POST /api/claude-agent` | 启动 Claude Agent 一轮会话，并持续输出 SSE 事件 | `text/event-stream` |
| `POST /api/claude-agent/tool-confirm` | 对交互工具（动画事件、问答等）的待确认调用做批准/拒绝 | `application/json` |
| `POST /api/claude-agent/threads/{thread_id}/stop` | 用户主动停止当前运行中的 Agent turn，不删除 thread | `application/json` |

其中：

- `server.py` 负责把 HTTP 请求映射为 `ClaudeAgentRunRequest`，并把 SSE 出流委托给 `ClaudeAgentThreadFactory.run_streaming`。
- `backend/claude_agent/thread_factory.py` 是 SSE 入口（Factory 模式），驱动 Phase 1（`service.assemble_context`）+ Phase 2（`create_agent_runner`）+ Phase 3（`service.execute_session`）+ Phase 4（`_fire_session_ended`），并维护每会话 `asyncio.Lock`、`AgentRunStatePool` 享元、10 分钟 TTL 清扫器。
- `backend/claude_agent/service.py` 在 Phase 1 / Phase 3 内完成上下文构建、pet-agent 调用和 SSE 事件出流；`run_streaming` 入口已删，对外只暴露 `assemble_context` + `execute_session` + `confirm_tool`。
- `backend/claude_agent/context_builder.py` 负责把宠物信息、运行时和显式诊断 `long_term_profile` 覆盖拼进 prompt；正式长期记忆由 Mem0 memory MCP 按需召回。

### 4.2 `POST /api/claude-agent` 入参契约

#### 4.2.1 顶层字段（Ink & Memory）

| 字段 | 类型 | 默认值 | 必填 | 说明 |
|---|---|---:|---|---|
| `id` | string | — | 是（或 thread_id） | 对话线程 ID，由 `POST /api/claude-agent/threads` 预先创建。Vercel AI SDK 发送为 `id`。 |
| `thread_id` | string | — | 是（或 id） | 同上，兼容别名。 |
| `message` | string / UIMessage | `""` | 是 | 用户本轮输入；可为纯字符串或含 `parts` 数组的 UIMessage 对象。 |
| `resume` | bool | `false` | 否 | 是否复用已有 Claude session。 |
| `tool_choice` | string | `"auto"` | 否 | 工具模式：`auto` / `manual` / `none`。`manual` = 所有工具都需前端 Approve/Cancel 确认；`auto` = workspace `files/` 内置文件工具、低敏查询、`Skill` 与 `switch_editor` 自动 allow，高敏工具需前端确认；`none` = 禁用工具。Settings 完全访问模式由后端配置控制，不改变请求字段；其仍保留 `AskUserQuestion` / `mcp__user__ask_user` 问答确认。前端通过 AIInputDock「逐步确认」开关发送 `manual`。|
| `model` | string/null | `null` | 否 | 模型覆盖。 |
| `max_turns` | integer | `100` | 否 | 本轮 agent 最大 turn 数（可由 `INK_AGENT_MAX_TURNS` 环境变量覆盖）。 |
| `cwd` | string/null | `null` | 否 | agent 子进程工作目录；不传则由 thread_id 派生 workspace 目录。 |
| `chatModel` | object/null | `null` | 否 | 前端 ChatModel 对象（前端内部使用，后端忽略）。 |

> `thread_id` 必须在请求前通过 `POST /api/claude-agent/threads` 创建，并属于认证用户。

#### 4.2.2 顶层校验与派生规则

- `thread_id`（或 `id`）不能为空；缺失时返回 `400`。
- `thread_id` 必须属于认证用户；否则返回 `404`。
- `message` 文本提取后不能为空；缺失时返回 `400`。
- `system_prompt` 由服务端 `ClaudeAgentContextBuilder` 组装，调用方不可传入。

### 4.3 服务层归一规则

`POST /api/claude-agent` 在进入 Claude runtime 之前，会依次经过以下归一流程：

1. 路由校验 `thread_id` 存在且属于认证用户，否则 `404`。
2. 从 `message` 提取文本（支持纯字符串和 UIMessage `parts` 格式）。
3. 构建 `ClaudeAgentRunRequest`（`user_id`、`thread_id`、`message_text`、`tool_choice`、`model`、`max_turns`、`cwd`）。
4. `ClaudeAgentService.assemble_context`（Phase 1）：
   - 首轮：调用 `ClaudeAgentContextBuilder.build_system_prompt(user_id)` 构建 system prompt，写入 `AgentRunState`。
   - 后续轮：复用享元缓存的 `state.system_prompt`，不再重新构建。
   - 构建 `user_message`、`AgentRunOptions`，发射初始 `message-metadata` SSE 帧。
5. Phase 2：创建（或复用）`ClaudeAgentRunner`。
6. `ClaudeAgentService.execute_session`（Phase 3）：驱动 runner、emit SSE 事件、持久化消息。
7. `onFinish`：保存 `user` + `assistant` 消息到 `chat_messages` 表，自动填充线程标题。

### 4.4 请求报文示例

```json
{
  "id": "thread-abc123",
  "message": "帮我整理一下今天的笔记",
  "resume": false,
  "tool_choice": "auto",
  "max_turns": 100
}
```

### 4.5 SSE 传输协议

#### 4.5.1 传输层约定

- HTTP 响应头：
  - `Content-Type: text/event-stream`
  - `Cache-Control: no-cache`
  - `X-Accel-Buffering: no`
- 每个事件都序列化为一行 `data: {json}\n\n`。
- 当前实现不写 `event:` 字段，因此客户端必须读取 `data` 内 JSON 的 `type` 字段来分发事件。
- 流开始时一定先发一条 `message-metadata`。
- 流正常结束时一定发 `finish`；异常结束时发 `error` 后关闭流，通常不会再补 `finish`。

#### 4.5.2 事件全集（Ink & Memory 当前实现）

| `type` | 触发时机 | 关键字段 | 备注 |
|---|---|---|---|
| `message-metadata` | 流开始（Phase 1） | `sessionId`, `turnIndex` | 第一条事件；由 `assemble_context` 发射。 |
| `text-start` | 首个文本 delta 前 | `id` | `id` 固定为服务端分配的块 ID。 |
| `text-delta` | 文本增量 | `id`, `delta` | 与最近一次 `text-start` 对应；字段名 `delta`（非 `text`）。 |
| `text-end` | 文本块结束 | `id` | 与最近一次 `text-start` 对应；由 `on_text_done` 发射。 |
| `reasoning-start` | thinking 块开始（thinking 模式） | `id` | 由 `thinking_delta` 或 `thinking` 事件触发。 |
| `reasoning-delta` | thinking 内容增量 | `id`, `delta` | 与最近一次 `reasoning-start` 对应。 |
| `reasoning-end` | thinking 块结束 | `id` | 由 `content_block_stop`（流式）或 `thinking`（完整块）触发。 |
| `tool-input-start` | 工具调用开始 | `toolCallId`, `toolName` | auto/manual 都会出现。 |
| `tool-input-delta` | 工具输入 JSON 增量 | `toolCallId`, `toolName`, `delta` | SDK `input_json_delta.partial_json` 的透传。用于 live preview，不参与持久化；完整 input 仍以 `tool-input-available` 为准。 |
| `tool-input-available` | 工具输入完整 | `toolCallId`, `toolName`, `input` | 紧跟 `tool-input-start`。 |
| `tool-approval-request` | 工具等待确认 | `toolCallId`, `toolName`, `input`, `confirmationKind?`, `networkRequest?` | 四种情况出现：① `tool_choice="manual"` 时所有工具；② `tool_choice="auto"` 时高敏工具（执行/写入/交互等）；③ Settings 完全访问模式下的 `AskUserQuestion` / `mcp__user__ask_user` 问答表单；④ SandboxPermissionRequest——CLI 运行时沙箱代理拦截清单外域名时经 SDK `can_use_tool` 通道发起的 `SandboxNetworkAccess` 系统级询问（`input` 为 `{"host": ...}`，不经 PreToolUse）**[2026-07-26]**。workspace `files/` 内置文件工具、低敏查询、`Skill` 与 `switch_editor` 不会触发该事件。前端 transport 将其转成同一 tool part 的 `toolMetadata.approvalRequested=true` 并显示 Approve/Cancel 或问答表单 UI；用户操作后调用 `/api/claude-agent/tool-confirm`。**[2026-07-23]** 沙箱网络确认额外携带 `confirmationKind:"sandbox_network"` 与 `networkRequest:{host, policyMode, matchedAllowedDomain}`（`matchedAllowedDomain` 本期恒为 `null`，预留给「放行并记住」迭代）；前端据此渲染网络变体确认卡，字段缺失时回退通用确认卡（向后兼容）。**[2026-06-13]** |
| `tool-output-available` | 工具结果返回 | `toolCallId`, `output`, `isError` | `isError=true` 时表示工具执行出错。 |
| `plan-mode-changed` | Plan Mode 状态迁移 | `planMode`, `toolCallId` | 观察到 `tool-input-available` 且 `toolName` 为 `EnterPlanMode` / `ExitPlanMode` 时发射；`planMode` 取 `"planning"` / `"exited"`。生命周期帧，不入 `collected_parts`，不映射 UIMessageChunk；前端转发到 plan store（[`claude-plan.md`](./claude-plan.md) §5.4）。**[2026-07-20]** |
| `plan-updated` | 计划内容快照 | `slug`, `fileName`, `content`, `contentBytes`, `truncated`, `updatedAt` | 计划文件写入（PostToolUse 观察 `Write`/`Edit`/`MultiEdit` 落入 plans 目录，防抖 `INK_AGENT_PLAN_EMIT_DEBOUNCE_MS` 默认 500ms）或 `ExitPlanMode` 终读时发射；内容超过 `INK_AGENT_PLAN_MAX_CONTENT_BYTES`（默认 262144）时截断并置 `truncated:true`，前端可经 `GET /api/claude-agent/threads/{thread_id}/plan` 拉全量。不收集、不映射 UIMessageChunk；读取失败仅记日志不发射。**[2026-07-20]** |
| `todo-updated` | 待办清单快照 | `source`, `todos`, `truncated`, `updatedAt` | 观察到 `tool-input-available` 且 `toolName` 为 `TodoWrite`（v1 流内捕获，`source:"todo_write"`），或 PostToolUse 观察 `TaskCreate`/`TaskUpdate` 后重读 tasks 目录（v2 文件任务，`source:"task_v2"`，防抖 `INK_AGENT_TODO_EMIT_DEBOUNCE_MS` 默认 500ms）时发射；`todos` 为统一 TodoItem 全量快照（`id`/`content`/`status`/`active_form`/`owner`/`blocked_by`），超过 `INK_AGENT_TODO_MAX_ITEMS`（默认 200）截断并置 `truncated:true`。生命周期帧，不入 `collected_parts`，不映射 UIMessageChunk；前端转发到 todos store（[`claude-todo.md`](./claude-todo.md) §5.4）。schema 不符或读取失败仅记日志不发射。**[2026-07-20]** |
| `message-final` | 流成功结束前 | `text`, `usage`, `sessionId` | 包含完整 assistant 文本和 token 用量。 |
| `finish` | 流结束 | `finishReason` | 成功时为 `"stop"`，失败时为 `"error"`。 |
| `error` | 任意异常 | `errorText` | 字段名 `errorText`（非 `message`）。 |

#### 4.5.3 字段对比：与 Pawkeyland 的关键差异

| 事件 | Pawkeyland 字段 | Ink & Memory 字段 | 说明 |
|---|---|---|---|
| `text-delta` | `id` + `delta` | `id` + `delta` | 已对齐 ✅ |
| `text-start` / `text-end` | 有 | 有 | 已对齐 ✅ |
| `error` | `errorText` | `errorText` | 已对齐 ✅ |
| `finish` | `finishReason: "stop"` | `finishReason: "stop"/"error"` | 已对齐 ✅ |
| `tool` 事件 | 三条分离事件 | 三条分离事件 | 已对齐 ✅ |
| `reasoning-start/delta/end` | 有（thinking 模式） | 有 ✅ | 2026-05-24 启用 |
| `message-metadata` | `toolChoice/toolCount/sessionId` | `sessionId/turnIndex` | 结构略有简化 |

#### 4.5.4 持久化侧的 SSE 事件收集

每个 SSE 回调在发出事件到前端的同时，将**原始事件 dict** 追加到 `_TurnContext.collected_parts`：

| 收集 | 不收集 |
|------|--------|
| `text-start/delta/end` | `tool-input-start`（无数据载荷） |
| `reasoning-start/delta/end` | `tool-approval-request`（lifecycle） |
| `tool-input-available` | `message-metadata`、`message-final` |
| `tool-output-available` | `tool-input-delta`（live preview）、`finish`、`error` |
| | `plan-mode-changed` / `plan-updated`（lifecycle，claude-plan） **[2026-07-20]** |
| | `todo-updated`（lifecycle，claude-todo） **[2026-07-20]** |

`_persist_turn` 调用 `_sse_events_to_ui_parts(collected_parts)` 做一次线性转换，输出 UIMessage-compatible parts 列表写入 `chat_message.parts`。见 [claude-agent-session-persistence.md §4](./claude-agent-session-persistence.md)。

### 4.6 SSE 顺序规则

#### 4.6.1 普通文本流

```text
message-metadata(initial)
text-start
text-delta*
text-end
message-metadata(final)
finish
```

#### 4.6.2 auto 模式 — workspace `files/` 内置文件工具和低敏查询自动执行

```text
message-metadata(initial)
text-*
tool-input-start
tool-input-available
tool-output-available
text-*
message-metadata(final)
finish
```

#### 4.6.3 manual 模式 — 所有工具需 Approve/Cancel

```text
message-metadata(initial)
tool-input-start
tool-input-available
tool-approval-request          ← 前端显示 Approve / Cancel 按钮
POST /api/claude-agent/tool-confirm {approved:true|false}
tool-output-available          ← 仅 approved=true 后出现
text-*
message-final
finish
```

auto 模式下的高敏工具（例如复杂/写入型 `Bash`、`Write` outside `files/`、MCP 写入工具等）也使用同一确认顺序。低敏工具（例如 `Read` outside `files/`、`Glob`、`Grep`、`LS`、`WebSearch`、会话查询、memory/necklace 查询、`Skill`、`switch_editor`）不会触发 `tool-approval-request`。

#### 4.6.4 auto 模式 — AskUserQuestion 工具需填答案 **[2026-05-27]**

当 Settings「应如何批准 IM」为完全访问时，本节顺序仍适用。
完全访问只跳过普通权限审批，不能跳过问答表单，因为 answers 必须经
`POST /api/claude-agent/tool-confirm` 回传并合并到 PreToolUse
`updatedInput`。

```text
message-metadata(initial)
text-*
tool-input-start
tool-input-available           ← 前端显示 AskUserQuestion 表单
tool-approval-request
POST /api/claude-agent/tool-confirm {approved:true, answers:{...}}
tool-output-available          ← 包含 answers 的工具结果
text-*
message-final
finish
```

#### 4.6.5 用户主动停止当前 turn **[2026-06-25]**

前端停止按钮调用：

```http
POST /api/claude-agent/threads/{thread_id}/stop
```

该接口只取消当前运行中的 in-memory turn，不删除 `chat_thread`，也不销毁历史消息。
服务端校验 thread 所有权后调用 ThreadFactory 取消 `state.bg_task`。
取消路径复用 `_persist_partial_assistant()` 保存已收集 parts，并向 EventBus 发布
`finish` 后关闭 sentinel：

```text
message-metadata(initial)
text-* / reasoning-* / tool-*        ← 已经产生的事件可被收集
POST /api/claude-agent/threads/{id}/stop
finish { "finishReason": "stop" }
```

如果 thread 当前未运行，接口仍返回 200，并以 `stop_requested=false`
表示没有可取消的 turn。普通 SSE 断线、切换 thread 或刷新页面不会触发该语义；
它们仍只 unsubscribe，后台 turn 继续运行并支持 reconnect。

### 4.7 典型 SSE 报文示例

#### 4.7.1 流开始

```text
data: {"type":"message-metadata","sessionId":"thread-abc123","turnIndex":0}

```

#### 4.7.2 文本流

```text
data: {"type":"text-start","id":"text-0"}

data: {"type":"text-delta","id":"text-0","delta":"你好"}

data: {"type":"text-delta","id":"text-0","delta":"，今天有什么可以帮你的？"}

data: {"type":"text-end","id":"text-0"}

```

#### 4.7.3 普通工具确认（auto 或 manual 模式）

```text
data: {"type":"tool-input-start","toolCallId":"toolu_01","toolName":"Bash"}

data: {"type":"tool-input-delta","toolCallId":"toolu_01","toolName":"Bash","delta":"{\"command\""}

data: {"type":"tool-input-delta","toolCallId":"toolu_01","toolName":"Bash","delta":":\"ls\"}"}

data: {"type":"tool-input-available","toolCallId":"toolu_01","toolName":"Bash","input":{"command":"ls"}}

data: {"type":"tool-approval-request","toolCallId":"toolu_01","toolName":"Bash","input":{"command":"ls"}}

data: {"type":"tool-output-available","toolCallId":"toolu_01","output":"file1.txt","isError":false}

```

#### 4.7.4 AskUserQuestion 确认（auto、manual 或完全访问模式均适用）**[2026-06-13]**

```text
data: {"type":"tool-input-start","toolCallId":"call_abc","toolName":"AskUserQuestion"}

data: {"type":"tool-input-available","toolCallId":"call_abc","toolName":"AskUserQuestion","input":{"questions":[{"question":"你想选哪些水果？","header":"水果选择","options":[{"label":"苹果","description":"清甜爽脆"},{"label":"香蕉","description":"软糯香甜"}],"multiSelect":true}]}}

data: {"type":"tool-approval-request","toolCallId":"call_abc","toolName":"AskUserQuestion","input":{...同上...}}

```

前端随即显示 `AskUserQuestionUI` 表单，用户选择后发起：

```json
POST /api/claude-agent/tool-confirm
{
  "thread_id": "thread-abc123",
  "tool_call_id": "call_abc",
  "approved": true,
  "answers": { "你想选哪些水果？": "苹果,香蕉" }
}
```

批准后后端 hook 将 `answers` 合并进 `updatedInput`，CLI 以完整 input 执行工具，返回：

```text
data: {"type":"tool-output-available","toolCallId":"call_abc","output":{"questions":[...],"answers":{"你想选哪些水果？":"苹果,香蕉"}},"isError":false}
```

#### 4.7.5 manual 模式 — 普通工具（Read / Bash 等）

```text
data: {"type":"tool-input-start","toolCallId":"call_xyz","toolName":"Read"}

data: {"type":"tool-input-available","toolCallId":"call_xyz","toolName":"Read","input":{"file_path":"/workspace/notes.md"}}

data: {"type":"tool-approval-request","toolCallId":"call_xyz","toolName":"Read","input":{...}}

```

前端显示工具卡片 + Approve/Cancel 按钮。用户点击 Approve 后：

```json
POST /api/claude-agent/tool-confirm
{ "thread_id": "thread-abc123", "tool_call_id": "call_xyz", "approved": true }
```

#### 4.7.6 正常结束

```text
data: {"type":"message-final","text":"整理完成。","usage":{"input_tokens":120,"output_tokens":45},"sessionId":"thread-abc123"}

data: {"type":"finish","finishReason":"stop"}

```

#### 4.7.7 错误结束

```text
data: {"type":"error","errorText":"Command failed with exit code 1"}

data: {"type":"finish","finishReason":"error"}

```

#### 4.7.8 Plan Mode 计划帧（claude-plan）**[2026-07-20]**

`EnterPlanMode` 的 `tool-input-available` 到达后发射状态迁移帧；计划文件每次写入（防抖合并）发射内容快照；`ExitPlanMode` 时发射 `exited` 迁移帧与最终版快照：

```text
data: {"type":"tool-input-available","toolCallId":"call_plan1","toolName":"EnterPlanMode","input":{}}

data: {"type":"plan-mode-changed","planMode":"planning","toolCallId":"call_plan1"}

data: {"type":"plan-updated","slug":"amber-churn-otter","fileName":"amber-churn-otter.md","content":"# 计划\n...","contentBytes":1832,"truncated":false,"updatedAt":"2026-07-20T01:23:45.678Z"}

data: {"type":"tool-input-available","toolCallId":"call_plan2","toolName":"ExitPlanMode","input":{}}

data: {"type":"plan-mode-changed","planMode":"exited","toolCallId":"call_plan2"}

data: {"type":"plan-updated","slug":"amber-churn-otter","fileName":"amber-churn-otter.md","content":"# 计划\n...最终版","contentBytes":1905,"truncated":false,"updatedAt":"2026-07-20T01:24:10.120Z"}

```

两类帧均为生命周期帧：不入 `collected_parts`，前端 transport 不映射为 UIMessageChunk，转发到按 threadId 键控的 plan store；初始加载/重连经 `GET /api/claude-agent/threads/{thread_id}/plan` 水合（契约见 [`claude-plan.md`](./claude-plan.md) §5.5）。

#### 4.7.9 待办清单帧（claude-todo）**[2026-07-20]**

v1：`TodoWrite` 的 `tool-input-available` 携带全量 `input.todos`，后端映射为统一 TodoItem 后发射快照；v2（`INK_AGENT_TASK_V2_ENABLED` 开启）：`TaskCreate`/`TaskUpdate` 的 PostToolUse 防抖重读 tasks 目录后发射快照：

```text
data: {"type":"tool-input-available","toolCallId":"call_todo1","toolName":"TodoWrite","input":{"todos":[{"content":"设计文档","status":"completed","activeForm":"正在编写设计文档"},{"content":"实现捕获逻辑","status":"in_progress"}]}}

data: {"type":"todo-updated","source":"todo_write","todos":[{"id":"1","content":"设计文档","status":"completed","active_form":"正在编写设计文档","owner":null,"blocked_by":[]},{"id":"2","content":"实现捕获逻辑","status":"in_progress","active_form":null,"owner":null,"blocked_by":[]}],"truncated":false,"updatedAt":"2026-07-20T06:30:00.000Z"}

data: {"type":"todo-updated","source":"task_v2","todos":[{"id":"1","content":"设计文档","status":"completed","active_form":null,"owner":"claude","blocked_by":[]},{"id":"2","content":"实现捕获逻辑","status":"pending","active_form":null,"owner":null,"blocked_by":[]}],"truncated":false,"updatedAt":"2026-07-20T06:31:05.120Z"}

```

`todo-updated` 为生命周期帧：不入 `collected_parts`，前端 transport 不映射为 UIMessageChunk，转发到按 threadId 键控的 todos store；初始加载/重连经 `GET /api/claude-agent/threads/{thread_id}/todos` 水合（契约见 [`claude-todo.md`](./claude-todo.md) §5.5）。

### 4.8 `POST /api/claude-agent/tool-confirm` 契约

#### 4.8.1 请求体

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `thread_id` | string | 是 | 对话线程 ID，与 SSE 流关联。 |
| `tool_call_id` | string | 是 | 待确认工具调用 ID，对应 SSE 中的 `toolCallId`。 |
| `approved` | bool | 是 | 是否批准执行。 |
| `reason` | string/null | 否 | 拒绝或补充说明。 |
| `answers` | object/null | 否 | 工具结果回传（问答工具等）。 |

#### 4.8.2 成功响应

```json
{
  "ok": true,
  "approved": true
}
```

#### 4.8.3 错误语义

- 若 `tool_call_id` 不存在或已超时，返回 `404`，错误信息为 `No pending confirmation for tool_call_id=...`。
- `approved=false` 时，SSE 主流不会立刻报 HTTP 错；是否继续输出后续文本由 Claude runtime 基于 deny 结果决定。

### 4.9 当前实现中的兼容性与边界

- `tool-output-available` 的 `isError=true` 表示工具执行出错。
- `finishReason` 成功时为 `"stop"`，失败时为 `"error"`。
- `text-end` 与最近一次 `text-start` 对应；`id` 字段保证客户端能关联文本块。
- 前端 `frontend/src/lib/claude-agent-transport.ts` 消费上述格式，将 SSE 事件转换为 `@ai-sdk/react` 的 `UIMessageChunk`；`tool-approval-request` 会更新对应 tool part 的 `toolMetadata.approvalRequested=true`。

## 5. 验收标准

- `docs/app/design/` 中存在单一设计稿，完整描述 pet-agent 服务的请求契约、归一规则和 SSE 报文。
- 文档明确区分“调用方可传字段”和“服务层实际消费字段”。
- 文档明确给出 `on_tool_confirmation_request` 交互工具确认徧路协议，而不是只描述主 SSE 流。
- 下游读取本文后，无需反查源码即可实现：
  - `POST /api/claude-agent` 请求组装
  - SSE 事件分发
  - `POST /api/claude-agent/tool-confirm` 回调提交

## 6. 风险与依赖

- 依赖 `server.py（路由定义内）`、`server.py`、`backend/claude_agent/service.py`、`backend/claude_agent/thread_factory.py` 的当前实现；若这些文件后续改动，本文必须同步更新。
- `conversation_id` 已从请求入参中删除。会话续接通过 `(user_id, persona_id)` 查 DB 获取 `claude_session_id` 实现，不再依赖调用方传入的外部会话标识。
- `pet_id` 命中数据库记录时会覆盖请求体 `pet_info`，如果调用方误以为请求体优先，容易在联调时产生“字段传了但没生效”的错觉。
- `runtime` 是开放字典，下游若依赖未列出的隐式键，会造成文档与实现再次漂移。
- 硬件状态查询有超时和 fallback 行为，因此同一请求在不同环境下可能注入不同丰富度的上下文，但不影响 SSE 协议本身。

## 7. 关键决策记录

| 日期 | 决策 | 原因 | 影响 |
|---|---|---|---|
| 2026-05-06 | 将 pet-agent 业务服务口径统一收敛到 `POST /api/claude-agent` + `POST /api/claude-agent/tool-confirm` | 这两条接口共同构成可执行的 Claude Agent 业务协议 | 下游不再需要同时查找模块设计稿与任务文档 |
| 2026-05-06 | 以“代码当前行为”而非旧设计草案作为本文最终口径 | 相关设计稿存在演进，只有代码能代表真实协议 | 文档中显式写入 `pet_info` 覆盖、tool 事件条件字段等实现细节 |
| 2026-05-06 | 将 `pet_info` / `runtime` 定义为“开放字典 + 已消费字段清单” | 顶层模型未对其做强 schema 限制 | 保留扩展性，同时给下游稳定依赖面 |
