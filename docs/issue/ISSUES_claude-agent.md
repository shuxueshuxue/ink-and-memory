# Claude Agent 模块 Issue 清单

## 0. 文档元信息

- Issue 清单文件：`docs/issue/ISSUES_claude-agent.md`
- 来源设计稿：
  - 主设计稿：`docs/design/claude-agent.md`
  - 关联设计稿：
    - `docs/design/claude-agent/claude-agent-service-design.md`
    - `docs/design/claude-agent/claude-agent-context-assembly.md`
    - `docs/design/claude-agent/claude-agent-session-persistence.md`
    - `docs/design/claude-agent/claude-agent-api-contracts.md`
    - `docs/design/claude-agent/claude-agent-thread-session-patterns.md`
    - `docs/design/claude-agent/sse-reconnect-and-event-bus.md`
    - `docs/design/claude-agent/claude-agent-tool-confirmation-flow.md`
    - `docs/design/claude-agent/claude-agent-permission-policy.md`
    - `docs/design/claude-agent/claude-agent-runner-design.md`
    - `docs/design/claude-agent/claude-agent-workspace-sandbox.md`
    - `docs/design/claude-agent/claude-agent-workspace-sandbox-interaction-plan.md`
    - `docs/design/claude-agent/claude-agent-docker-sandbox-egress-incident-plan.md`
    - `docs/design/claude-agent/claude-agent-sandbox-network-interaction-plan.md`
    - `docs/design/claude-agent/claude-sdk-env-design.md`
    - `docs/design/claude-agent/user-env-injection-design.md`
    - `docs/design/claude-agent/chat-history-search.md`
    - `docs/design/claude-agent/session-labels-and-retrieval.md`
    - `docs/design/claude-agent/chat-session-message-er-model.md`
    - `docs/design/claude-agent/claude-agent-prompt-optimization.md`
    - `docs/design/claude-agent/claude-agent-stop-interaction.md`
    - `docs/design/claude-agent/write-tool-terminal-preview.md`
    - `docs/design/claude-agent/claude-sdk-message-types.md`
    - `docs/design/claude-agent/workspace-filesystem.md`
  - `docs/design/claude-agent/workspace-design-comparison.md`
- 生成 Agent：`IssueDispatcher`
- 所属流水线阶段：`issue`
- 上游阶段：`design`
- 下游阶段：`task`
- 下游 Agent：
  - `FrontendTaskAgent`
  - `BackendTaskAgent`
- 共享设计稿来源：`docs/design/`
- 是否作为当前实现合同：`是`
- 备注：
  - 本文档由设计稿拆解生成，作为 task 阶段任务规划输入。
  - 若与设计稿冲突，以 `docs/design/` 中稳定设计稿为准。
  - 若与当前 API / 代码实现冲突，必须记录为阻塞或澄清项，不得静默覆盖。

## 1. 关联设计稿信息

- 主设计稿：`docs/design/claude-agent.md`
- 重点补充设计稿：
  - `docs/design/claude-agent/claude-agent-service-design.md`
  - `docs/design/claude-agent/claude-agent-context-assembly.md`
  - `docs/design/claude-agent/claude-agent-session-persistence.md`
  - `docs/design/claude-agent/claude-agent-api-contracts.md`
  - `docs/design/claude-agent/claude-agent-thread-session-patterns.md`
  - `docs/design/claude-agent/sse-reconnect-and-event-bus.md`
  - `docs/design/claude-agent/claude-agent-tool-confirmation-flow.md`
  - `docs/design/claude-agent/claude-agent-workspace-sandbox.md`
  - `docs/design/claude-agent/claude-agent-workspace-sandbox-interaction-plan.md`
  - `docs/design/claude-agent/claude-agent-docker-sandbox-egress-incident-plan.md`
  - `docs/design/claude-agent/claude-sdk-env-design.md`
  - `docs/design/claude-agent/user-env-injection-design.md`
  - `docs/design/claude-agent/chat-history-search.md`
  - `docs/design/claude-agent/session-labels-and-retrieval.md`
  - `docs/design/claude-agent/claude-agent-prompt-optimization.md`
  - `docs/design/claude-agent/claude-agent-stop-interaction.md`
  - `docs/design/claude-agent/write-tool-terminal-preview.md`
  - `docs/design/claude-agent/claude-sdk-message-types.md`
  - `docs/design/claude-agent/workspace-filesystem.md`
  - `docs/design/claude-agent/workspace-design-comparison.md`
- 关联实现路径：
  - `backend/server.py`
  - `backend/routers/claude_agent.py`
  - `backend/database.py`
  - `backend/claude_agent/service.py`
  - `backend/claude_agent/context_builder.py`
  - `backend/claude_agent/thread_factory.py`
  - `backend/claude_agent/thread_pool.py`
  - `backend/claude_agent/thread_retrieval.py`
  - `backend/claude_agent/event_bus.py`
  - `backend/claude_agent/event_bus_redis.py`
  - `backend/claude_agent/tool_confirmation_store.py`
  - `backend/claude_agent/workspace_context.py`
  - `backend/libs/claude_agent_kit/server/workspace.py`
  - `backend/libs/claude_agent_kit/server/sdk_env.py`
  - `backend/libs/claude_agent_kit/server/agent_runner.py`
  - `frontend/src/components/chat/ChatView.tsx`
  - `frontend/src/components/chat/ChatPanel.tsx`
  - `frontend/src/components/chat/AIInputDock.tsx`
  - `frontend/src/components/chat/ChatMessageList.tsx`
  - `frontend/src/components/chat/AskUserQuestionUI.tsx`
  - `frontend/src/components/chat/EditorWriteApprovalUI.tsx`
  - `frontend/src/lib/claude-agent-transport.ts`

- 本清单覆盖范围：
  - Claude Agent 运行合同的 request / response / SSE 归一
  - 会话持久化、resume 回写、labels 协作检索和历史检索
  - Thread Session 生命周期、EventBus 重连与 stop 语义
  - 工具确认、问答回传、Write 预览和审批 UI
  - Workspace Mode、沙箱策略、SDK env 注入与前端联动
  - Chat 历史搜索、labels 协作检索与前端消息回放
  - Agent 跨 session 笔记检索（`labels` + `mcp__user__get_sessions_range`）

- 明确排除范围：
  - `docs/design/deck-claude-agent.md` 的 Deck / voice 绑定流
  - `docs/design/edit-session/` 的编辑器会话引擎
  - `docs/design/memory/` 的 Reflections / 长期记忆工作流
  - `docs/design/notion-session/` 的 Notion 资源连接器
  - `docs/design/remote-ssh-interaction-plan.md` 的远端 SSH 部署流
  - 本批不直接拆 `task` / `stage` / `exec` 产物

- 关键约束：
  - `POST /api/claude-agent` 必须由服务端统一组装系统 prompt，不接受客户端自定义 system prompt 作为权威输入
  - `workspace_enabled=false` 时，聊天路径不得初始化 thread workspace，也不得注入 workspace context
  - `workspace_enabled=true` 时，Bash sandbox 的读边界必须收敛到当前 thread workspace 与必要 runtime 依赖，不能退化为宽松的父目录访问
  - `tool_choice="manual"` / 高敏 `auto` 工具必须走确认侧路，`AskUserQuestion` 需要 answers 回传
  - SSE 断线默认只取消消费者，不应等同于停止后台 turn
  - 历史检索默认字符模糊匹配，`labels` 仅作为过滤与排序辅助，`vector` 仅保留接口边界

- 补充说明：
  - `claude-agent.md` 是本批主线合同，子设计稿用于细化具体子系统。
  - 本次拆解以 Claude Agent 模块为边界，不把 Deck、Edit Session、Memory 或 Notion 设计稿并入同一批 Issue。
  - 由于本批同时覆盖运行时、协议、UI 和 workspace 基座，Issue 之间的依赖关系必须显式写出，不允许靠隐式默认假设推进。

## 2. Issue 总览表

| Issue ID | 标题 | 类型 | 优先级 | 标签 | 前置依赖 | 分发去向 |
|---|---|---|---|---|---|---|
| `CA-SH-01` | 建立 Workspace Mode、沙箱策略与 SDK env 注入基座 | shared | P0 | `shared,workspace,sandbox,env,settings,claude-code` | 无 | `@BackendTaskAgent` + `@FrontendTaskAgent` |
| `CA-BE-01` | 收敛 `POST /api/claude-agent` 的入参归一与 Phase 1 上下文组装 | backend | P0 | `backend,api-contract,context-assembly,session,resume,prompt` | `CA-SH-01` | `@BackendTaskAgent` |
| `CA-BE-02` | 实现会话持久化、labels 回写与历史检索接口 | backend | P0 | `backend,persistence,history,resume,sqlite,retrieval,labels,mcp` | `CA-BE-01` | `@BackendTaskAgent` |
| `CA-SH-02` | 重构 Thread Session 生命周期、EventBus 与断线重连 | shared | P0 | `shared,thread-session,eventbus,reconnect,streaming,stop` | `CA-BE-02` | `@BackendTaskAgent` + `@FrontendTaskAgent` |
| `CA-SH-03` | 落地工具确认、批准/拒绝与问答回传链路 | shared | P0 | `shared,tool-confirmation,approval,sse,manual,ask-user` | `CA-BE-01`, `CA-SH-02` | `@BackendTaskAgent` + `@FrontendTaskAgent` |
| `CA-FE-01` | 落地 Chat 历史搜索面板与结果回放 | frontend | P1 | `frontend,history-search,chat,search,retrieval` | `CA-BE-02` | `@FrontendTaskAgent` |
| `CA-FE-02` | 落地前端主动停止与运行中状态反馈 | frontend | P1 | `frontend,stop,chat,streaming,reconnect` | `CA-SH-02` | `@FrontendTaskAgent` |
| `CA-FE-03` | 落地 Write 工具终端式预览与 inline approval 渲染 | frontend | P1 | `frontend,write-preview,tool-delta,approval,chat` | `CA-SH-03` | `@FrontendTaskAgent` |

## 3. Issue 明细

### `CA-SH-01`

- 标题：建立 Workspace Mode、沙箱策略与 SDK env 注入基座
- 类型：shared
- 优先级：P0
- 标签：`shared,workspace,sandbox,env,settings,claude-code`
- 描述：
  落实 thread workspace 的生命周期开关、Claude Code Bash sandbox、`backend/.env` 与进程环境的 SDK env 合并、`setting-sources=project`、以及 Workspace Mode 关闭时对前端设置/侧边栏的隐藏逻辑。该 Issue 是后续所有 Claude Agent turn 的运行基座。

- 验收条件：
  - `workspace_enabled=true` 时，按 thread 初始化 workspace，并写入 `.claude/settings.json` 的 sandbox 配置。
  - `workspace_enabled=false` 时，不初始化 thread workspace，不注入 `cwd`，不做 attachment-driven workspace sync。
  - SDK env 合并顺序符合设计：`backend/.env` -> 当前进程白名单 env -> 显式 `options.env`。
  - `options.extra_args["setting-sources"] = "project"` 生效，避免用户目录 settings 覆盖项目配置。
  - Sandbox network 三种模式 `disabled` / `allowlist` / `open` 的行为与设计一致。
  - Settings 中与 workspace 绑定的控制在关闭 Workspace Mode 时被隐藏或禁用。

- 前置依赖：无
- 关联路径：
  - `backend/libs/claude_agent_kit/server/workspace.py`
  - `backend/libs/claude_agent_kit/server/sdk_env.py`
  - `backend/libs/claude_agent_kit/server/agent_runner.py`
  - `backend/claude_agent/workspace_context.py`
  - `backend/claude_agent/service.py`
  - `backend/routers/system_config.py`
  - `frontend/src/components/dashboard/ModelConfigSection.tsx`
  - `frontend/src/components/dashboard/Sidebar.tsx`
  - `frontend/src/contexts/WorkspaceContext.tsx`
  - `backend/tests/test_claude_agent_workspace.py`
  - `backend/tests/test_claude_agent_runner.py`

- 分发去向：`@BackendTaskAgent` + `@FrontendTaskAgent`
- 主责 Agent：
  - `BackendTaskAgent`
- 协作 Agent：
  - `FrontendTaskAgent`
- 设计决策引用：
  - `claude-agent-workspace-sandbox.md §1-5`
  - `claude-agent-workspace-sandbox-interaction-plan.md §1-5`
  - `claude-agent-docker-sandbox-egress-incident-plan.md §1-6`
  - `claude-agent-sandbox-network-interaction-plan.md §1-6`
  - `claude-sdk-env-design.md §1-6`
  - `user-env-injection-design.md §1-5`
  - `claude-agent/workspace-filesystem.md §1-5`
  - `claude-agent/workspace-design-comparison.md §1-3`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - 这里的重点不是新增 workspace 功能，而是把现有 workspace / sandbox / env 的运行边界收敛成可复用基座。

### `CA-BE-01`

- 标题：收敛 `POST /api/claude-agent` 的入参归一与 Phase 1 上下文组装
- 类型：backend
- 优先级：P0
- 标签：`backend,api-contract,context-assembly,session,resume,prompt`
- 描述：
  按 `claude-agent-api-contracts.md` 与 `claude-agent-context-assembly.md`，实现请求规范化、系统 prompt 组装、resume 判定、runtime 上下文注入、近期 session block（含 `labels`）和 older-session retrieval workflow、附件 / workspace-file 规则、以及 `_TurnExecution` 载体构建。该 Issue 负责把客户端输入收敛为稳定的服务端 turn 合同。

- 验收条件：
  - `id` / `thread_id` 别名、`message`、`resume`、`tool_choice`、`model`、`max_turns`、`cwd` 的服务端归一规则与设计一致。
  - 客户端不得以 `system_prompt` 或历史数组覆盖服务端权威上下文。
  - Settings `system_prompt` 作为低优先级块进入 system prompt，且与 `_SYSTEM_PROMPT_TEMPLATE` 冲突时以模板为准。
  - 系统提示中的最近 session block 按 `### {date} — sessionId:{sessionId}, {labels}: {title}` 格式输出，`labels` 缺失时保持空展示但不破坏格式。
  - 系统提示包含 `Session Retrieval Workflow`，明确 older-session 场景下使用 `mcp__user__get_sessions_range`，并保持 `query` 优先于 labels-only 搜索。
  - `INK_AGENT_USER_ID` 被注入到用户 MCP 环境中，older-session 检索只作用于当前用户历史。
  - resume 仅在 `chat_thread.claude_session_id`、契约版本和本地 transcript probe 同时满足时启用。
  - workspace disabled 时，不初始化 workspace，也不注入 `<workspace_context>` / `<memory_context>`。
  - 生成的 `AgentRunOptions` 与 `_TurnExecution` 中字段可直接被 Phase 3 消费。

- 前置依赖：`CA-SH-01`
- 关联路径：
  - `backend/server.py`
  - `backend/routers/claude_agent.py`
  - `backend/claude_agent/service.py`
  - `backend/claude_agent/context_builder.py`
  - `backend/database.py`
  - `backend/libs/claude_agent_kit/server/workspace.py`
  - `backend/tests/test_claude_agent_context_builder.py`
  - `backend/tests/test_server_claude_agent.py`

- 分发去向：`@BackendTaskAgent`
- 主责 Agent：
  - `BackendTaskAgent`
- 协作 Agent：
  - 无
- 设计决策引用：
  - `claude-agent-api-contracts.md §4.1-4.9`
  - `claude-agent-context-assembly.md §1-8`
  - `claude-agent-prompt-optimization.md §1-4`
  - `claude-agent.md §7.3-7.5`
  - `claude-agent-service-design.md §3-4`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - 本 Issue 只处理服务端权威合同，不把前端请求构造细节写进实现边界。

### `CA-BE-02`

- 标题：实现会话持久化、labels 回写与历史检索接口
- 类型：backend
- 优先级：P0
- 标签：`backend,persistence,history,resume,sqlite,retrieval,labels,mcp`
- 描述：
  按 `claude-agent-session-persistence.md`、`chat-session-message-er-model.md`、`chat-history-search.md` 与设计稿第 7 节的 labels / get_sessions_range 约束，把 turn 结束后的 user / assistant 消息、metadata、thread title、Claude session id、labels，以及历史检索候选加载全部落到数据库与后端检索层；同时补齐 `mcp__user__get_sessions_range` 的日期范围检索、labels 过滤、fuzzy 默认口径和 vector 占位边界。这个 Issue 是前端历史回放、会话恢复和跨 session 协作检索能力的共同后端基座。

- 验收条件：
  - `_persist_turn` 将 user / assistant 消息按 UIMessage-compatible parts 持久化到 `chat_message`。
  - `user_sessions.labels` 以 JSON 数组语义写入、读取与回写，并可被后续检索消费者稳定消费。
  - assistant metadata、thread title、`claude_session_id`、`agent_contract_version` 在成功 turn 后回写。
  - `GET /api/claude-agent/threads/{thread_id}/messages` 返回已反序列化的 message parts。
  - `GET /api/claude-agent/threads` 的 `query/search_scope/retrieval_mode` 检索参数按设计工作。
  - `list_chat_threads_for_search` / retriever registry 的默认 fuzzy 行为可用，`vector` 仅返回接口占位。
  - `mcp__user__get_sessions_range` 支持 `start_date` / `end_date` 范围、`query`、`labels`、`label_match`、`retrieval_mode`，并返回可用于定位结果的 `match` 元信息。
  - `mcp__user__get_sessions_range` 以当前用户上下文为边界运行，`query` 优先于 labels-only 搜索，`retrieval_mode="vector"` 仅返回接口占位。
  - resume 失败时能通过 session write-back 自愈到新 session，而不会阻塞 turn。

- 前置依赖：`CA-BE-01`
- 关联路径：
  - `backend/database.py`
  - `backend/claude_agent/service.py`
  - `backend/claude_agent/thread_retrieval.py`
  - `backend/routers/claude_agent.py`
  - `backend/libs/claude_agent_kit/server/session_files.py`
  - `backend/libs/claude_agent_kit/server/sessions_tool.py`
  - `backend/libs/claude_agent_kit/server/mcp_server.py`
  - `backend/tests/test_chat_thread_retrieval.py`
  - `backend/tests/test_sessions_tool.py`
  - `backend/tests/test_claude_agent_service.py`
  - `backend/tests/test_database.py`

- 分发去向：`@BackendTaskAgent`
- 主责 Agent：
  - `BackendTaskAgent`
- 协作 Agent：
  - 无
- 设计决策引用：
  - `claude-agent-session-persistence.md §2-5`
  - `claude-agent.md §7.3-7.5`
  - `claude-agent-context-assembly.md §8`
  - `chat-session-message-er-model.md §1-5`
  - `session-labels-and-retrieval.md §1-9`
  - `chat-history-search.md §3-4`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - 搜索接口的目标不是引入向量检索，而是先把当前 fuzzy / labels-filter / interface-only 边界稳定下来。

### `CA-SH-02`

- 标题：重构 Thread Session 生命周期、EventBus 与断线重连
- 类型：shared
- 优先级：P0
- 标签：`shared,thread-session,eventbus,reconnect,streaming,stop`
- 描述：
  按 `claude-agent-thread-session-patterns.md` 与 `sse-reconnect-and-event-bus.md`，把 Factory / Pool / Observer / EventBus / reconnect 流程收敛为可维护的会话生命周期。SSE 断线只应取消当前消费者，不应把后台 turn 一并终止；同时要保留历史帧回放、keepalive、TTL 清扫和 stop 语义。

- 验收条件：
  - 同一 `session_id` 在同一时刻只允许一个活跃 turn，后续请求按锁串行。
  - SSE 断线只会 unsubscribe 当前消费者，后台 `bg_task` 保持运行直到自然结束或 stop。
  - 重连时可从当前 turn 的历史帧起回放，不丢失已产出的 SSE 事件。
  - `INK_AGENT_EVENT_BUS_BACKEND` 可切换 memory / redis 实现，默认 memory 可跑。
  - `/threads/{id}/status` 与 reconnect 触发逻辑能让前端在 running 时重新接入流。
  - `POST /api/claude-agent/threads/{thread_id}/stop` 可终止当前 in-memory turn，并把 lifecycle 收敛到 idle。

- 前置依赖：`CA-BE-02`
- 关联路径：
  - `backend/claude_agent/thread_factory.py`
  - `backend/claude_agent/thread_pool.py`
  - `backend/claude_agent/event_bus.py`
  - `backend/claude_agent/event_bus_redis.py`
  - `backend/claude_agent/observer.py`
  - `backend/routers/claude_agent.py`
  - `frontend/src/components/chat/ChatView.tsx`
  - `frontend/src/components/chat/ChatPanel.tsx`
  - `backend/tests/test_event_bus.py`
  - `backend/tests/test_claude_agent_thread_factory.py`

- 分发去向：`@BackendTaskAgent` + `@FrontendTaskAgent`
- 主责 Agent：
  - `BackendTaskAgent`
- 协作 Agent：
  - `FrontendTaskAgent`
- 设计决策引用：
  - `claude-agent-thread-session-patterns.md §1-4`
  - `sse-reconnect-and-event-bus.md §1-7, §9-11`
  - `claude-agent-service-design.md §4, §10`
  - `claude-agent-api-contracts.md §4.6.5`
  - `claude-agent-runner-design.md §4, §7, §11`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - 这里的 stop 语义只覆盖当前运行中的 turn，不扩展成会话删除或全局任务取消。

### `CA-SH-03`

- 标题：落地工具确认、批准/拒绝与问答回传链路
- 类型：shared
- 优先级：P0
- 标签：`shared,tool-confirmation,approval,sse,manual,ask-user`
- 描述：
  按 `claude-agent-tool-confirmation-flow.md` 与 `claude-agent-api-contracts.md`，把 tool-input / approval-request / output-available 的确认链路完整贯通，并让 `AskUserQuestion`、普通 manual approval、以及 auto 模式下的高敏工具都通过同一确认合同收敛。前端必须能显示审批卡片和问答表单，后端必须能可靠阻塞 / 释放 pending confirmation。

- 验收条件：
  - `tool-input-start` / `tool-input-available` / `tool-approval-request` / `tool-output-available` 按合同顺序发出。
  - `POST /api/claude-agent/tool-confirm` 能批准、拒绝并携带 answers。
  - `toolCallId` 的前后端字段别名兼容符合设计，不再因为字段名不一致导致确认失败。
  - pending confirmation 在取消、超时或 turn 结束时会被清理，不残留挂起 Future。
  - 前端能对 `AskUserQuestion` 显示表单，对普通工具显示 Approve / Cancel，对 backend-driven approval 也可展示审批状态。
  - `tool-input-delta` 可被前端消费为写入预览，但不破坏确认主链路。

- 前置依赖：`CA-BE-01`, `CA-SH-02`
- 关联路径：
  - `backend/claude_agent/tool_confirmation_store.py`
  - `backend/claude_agent/service.py`
  - `backend/routers/claude_agent.py`
  - `backend/claude_agent/thread_factory.py`
  - `backend/libs/claude_agent_kit/server/agent_runner.py`
  - `frontend/src/components/chat/ChatMessageList.tsx`
  - `frontend/src/components/chat/AskUserQuestionUI.tsx`
  - `frontend/src/components/chat/EditorWriteApprovalUI.tsx`
  - `frontend/src/lib/claude-agent-transport.ts`
  - `backend/tests/test_claude_agent_service.py`
  - `backend/tests/test_claude_agent_runner.py`

- 分发去向：`@BackendTaskAgent` + `@FrontendTaskAgent`
- 主责 Agent：
  - `BackendTaskAgent`
- 协作 Agent：
  - `FrontendTaskAgent`
- 设计决策引用：
  - `claude-agent-tool-confirmation-flow.md §1-7`
  - `claude-agent-api-contracts.md §4.5-4.8`
  - `claude-agent-service-design.md §5`
  - `claude-agent-permission-policy.md §1-8`
  - `claude-agent-runner-design.md §5-7`
  - `claude-sdk-message-types.md §事件类型树形总览`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - 这个 Issue 必须覆盖问答型工具，不要只实现普通 approve / reject。

### `CA-FE-01`

- 标题：落地 Chat 历史搜索面板与结果回放
- 类型：frontend
- 优先级：P1
- 标签：`frontend,history-search,chat,search,retrieval`
- 描述：
  按 `chat-history-search.md` 与 `ChatView.tsx` 当前交互，完成历史面板搜索按钮、居中搜索弹窗、空查询默认历史、查询回放、选中结果重新加载 thread 等前端体验。后端检索接口由 `CA-BE-02` 提供。

- 验收条件：
  - 历史面板头部搜索按钮能打开居中搜索弹窗。
  - 空 query 时显示按时间分组的历史，不显示新聊天入口。
  - 输入 query 时通过 `query/search_scope/retrieval_mode` 调用后端检索。
  - 选中搜索结果后能加载对应 thread 的 persisted messages 并关闭弹窗。
  - 空结果态、加载态、摘要态的文案与布局可用。

- 前置依赖：`CA-BE-02`
- 关联路径：
  - `frontend/src/components/chat/ChatView.tsx`
  - `frontend/src/components/chat/ChatPanel.tsx`
  - `backend/routers/claude_agent.py`
  - `backend/claude_agent/thread_retrieval.py`
  - `backend/tests/test_chat_thread_retrieval.py`

- 分发去向：`@FrontendTaskAgent`
- 主责 Agent：
  - `FrontendTaskAgent`
- 协作 Agent：
  - 无
- 设计决策引用：
  - `chat-history-search.md §1-6`
  - `claude-agent-api-contracts.md §4.1-4.3`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - 这里不引入向量库，只消费后端既定的 fuzzy / interface-only 口径。

### `CA-FE-02`

- 标题：落地前端主动停止与运行中状态反馈
- 类型：frontend
- 优先级：P1
- 标签：`frontend,stop,chat,streaming,reconnect`
- 描述：
  按 `claude-agent-stop-interaction.md`，补齐 ChatPanel / AIInputDock / ChatView 的 stop 状态、按钮禁用、running / reconnect 中的视觉反馈，以及对后端 stop API 的调用与局部刷新。后台取消语义由 `CA-SH-02` 负责。

- 验收条件：
  - 停止按钮在 running / reconnect 时出现，停止中时禁用并显示加载态。
  - 点击 stop 会同时中断本地流并请求后端 stop API。
  - 停止后页面能 reload persisted partial assistant 结果，不把停止当作错误。
  - 普通 tab 切换 / 刷新仍按 reconnect 逻辑恢复，不误触 stop 语义。

- 前置依赖：`CA-SH-02`
- 关联路径：
  - `frontend/src/components/chat/ChatPanel.tsx`
  - `frontend/src/components/chat/AIInputDock.tsx`
  - `frontend/src/components/chat/ChatView.tsx`
  - `backend/routers/claude_agent.py`
  - `backend/tests/test_claude_agent_thread_factory.py`

- 分发去向：`@FrontendTaskAgent`
- 主责 Agent：
  - `FrontendTaskAgent`
- 协作 Agent：
  - 无
- 设计决策引用：
  - `claude-agent-stop-interaction.md §1-5`
  - `claude-agent-api-contracts.md §4.6.5`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - 这个 Issue 只处理 UI 和调用编排，不把后台取消策略再写一遍。

### `CA-FE-03`

- 标题：落地 Write 工具终端式预览与 inline approval 渲染
- 类型：frontend
- 优先级：P1
- 标签：`frontend,write-preview,tool-delta,approval,chat`
- 描述：
  按 `write-tool-terminal-preview.md` 和现有 `ChatMessageList` / `EditorWriteApprovalUI` 交互，把 `tool-input-delta` 映射成终端式写入预览，并确保 write / approval 卡片在 live stream 和 history replay 两条路径都能正确渲染。

- 验收条件：
  - `tool-input-delta` 在前端展示为连续写入预览，而不是只等 `tool-input-available`。
  - Write 工具的 pending / completed / error 卡片在历史回放时与 live stream 一致。
  - 审批 UI 不依赖单一工具名字段，历史 replay 时仍能识别写入类工具。
  - 长内容具备折叠 / 展开，不把消息区撑爆。

- 前置依赖：`CA-SH-03`
- 关联路径：
  - `frontend/src/lib/claude-agent-transport.ts`
  - `frontend/src/components/chat/ChatMessageList.tsx`
  - `frontend/src/components/chat/EditorWriteApprovalUI.tsx`
  - `frontend/src/components/chat/ToolMessagePart.tsx`
  - `backend/tests/test_claude_agent_service.py`

- 分发去向：`@FrontendTaskAgent`
- 主责 Agent：
  - `FrontendTaskAgent`
- 协作 Agent：
  - 无
- 设计决策引用：
  - `write-tool-terminal-preview.md §1-5`
  - `claude-agent-api-contracts.md §4.5.2-4.7.6`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - `tool-input-delta` 已在协议层定义，这里只负责把它渲染成可读的 UI。

## 4. 共享任务与依赖说明

- `CA-SH-01` 是本批最底层的运行基座，workspace / sandbox / env 相关的后续 Issue 不应绕开它直接推进。
- `CA-BE-01` 依赖 `CA-SH-01`，因为 Phase 1 上下文组装需要 workspace / env / settings 的基座能力。
- `CA-BE-02` 依赖 `CA-BE-01`，因为持久化与历史检索建立在稳定的 turn 合同之上。
- `CA-SH-02` 依赖 `CA-BE-02`，因为 Thread Session / EventBus / reconnect 需要完整的 turn 与持久化边界。
- `CA-SH-03` 依赖 `CA-BE-01` 和 `CA-SH-02`，因为确认链路既依赖稳定的请求合同，也依赖可恢复的流式生命周期。
- `CA-FE-01` 依赖 `CA-BE-02`，因为搜索 UI 的后端结果集和回放都来自持久化历史。
- `CA-FE-02` 依赖 `CA-SH-02`，因为 stop 按钮和 running / reconnect 反馈必须与后台取消语义一致。
- `CA-FE-03` 依赖 `CA-SH-03`，因为 write 预览和 approval 卡片都消费工具事件协议。

- 本批 issue 的主线顺序是：
  - `CA-SH-01`
  - `CA-BE-01`
  - `CA-BE-02`
  - `CA-SH-02`
  - `CA-SH-03`
  - `CA-FE-01`
  - `CA-FE-02`
  - `CA-FE-03`

## 5. 分发去向说明

- `BackendTaskAgent`
  - 领取 `CA-SH-01`、`CA-BE-01`、`CA-BE-02`、`CA-SH-02`、`CA-SH-03` 的 backend 部分。
  - 负责 API 合同、数据库、事件总线、生命周期、确认 store、workspace/runtime 基座等任务规划。

- `FrontendTaskAgent`
  - 领取 `CA-SH-01`、`CA-SH-02`、`CA-SH-03` 中的前端联动部分，以及 `CA-FE-01`、`CA-FE-02`、`CA-FE-03`。
  - 负责 Chat 页面、历史搜索、stop 状态、工具审批、Write 预览、消息列表渲染与前端 transport 任务规划。

- `Shared Issue` 处理规则：
  - shared 类型 Issue 必须明确主责 Agent。
  - 另一个 Agent 作为协作方。
  - 不允许 shared Issue 无主责。
  - 若主责不清，必须标记 `[CLARIFICATION_NEEDED]`。

## 6. 推荐推进顺序

1. `CA-SH-01`
2. `CA-BE-01`
3. `CA-BE-02`
4. `CA-SH-02`
5. `CA-SH-03`
6. `CA-FE-01`
7. `CA-FE-02`
8. `CA-FE-03`

推荐理由：

- 先把 workspace / env 基座收紧，避免后续上下文、stream 和 UI 继续建立在漂移合同上。
- 再落地 Phase 1 / persistence / reconnect 这些后端核心能力，前端才能稳定消费 thread、history 和 status。
- 然后补工具确认链路，最后收尾前端搜索、stop 和 Write 体验，减少重复联调。

## 7. 阻塞与澄清记录

- `[BLOCKED]` 无
- `[CLARIFICATION_NEEDED]` 无
- 本批设计稿已经足够支撑 issue 拆解，没有出现需要回退 `design` 的硬缺口。
- 若后续 `deck-claude-agent.md` 或 `edit-session/` 需要并入同一执行批次，应由 `DesignArchitect` 另起设计稿，不在本 Issue 清单里静默扩展范围。

## 8. Issue-First 协作说明

* Issue 是最小调度单元。
* 同一 Issue 任一时刻只允许一个主责 Agent。
* shared Issue 必须有主责 Agent 与协作 Agent。
* 必须通过 Issue 评论区补充上下文、阻塞、回退和评审意见。
* 必须通过 `@mention` 唤醒目标 Agent。
* 不假设 Agent 之间存在隐式共享内存。
* 不允许绕过 Issue 直接下发 task。
