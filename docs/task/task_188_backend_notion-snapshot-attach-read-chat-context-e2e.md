# SUO-188 后端任务文档：Notion 快照 attach、.notion/ 读取与聊天上下文 E2E

Status: Draft  
Updated: 2026-07-05  
Scope: 后端任务规划 - Notion canonical snapshot attach / `.notion/` 读取 / 聊天上下文 E2E

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`,
>      `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`,
>      `docs/design/claude-agent/edit-point/workspace-context.md`,
>      `backend/claude_agent/service.py`,
>      `backend/claude_agent/workspace_context.py`,
>      `backend/claude_agent/context_builder.py`,
>      `backend/notion/factory.py`,
>      `backend/notion/store.py`,
>      `backend/notion/sync.py`,
>      `backend/routers/notion.py`,
>      `backend/libs/claude_agent_kit/server/notion_snapshot.py`,
>      `backend/tests/test_claude_agent_service.py`,
>      `backend/tests/test_claude_agent_context_builder.py`,
>      `backend/tests/test_notion_store.py`,
>      `backend/tests/test_notion_snapshot_contract.py`
> [Output] 可执行的后端任务文档，供后续实现阶段直接拆分与验证
> [Pos] `task_188_backend_notion-snapshot-attach-read-chat-context-e2e` in `docs/task`
> [Sync] 2026-07-05: generated from the filled requirement template for SUO-188.

## 1. 任务标题

`SUO-188 Notion 快照 attach、.notion/ 读取与聊天上下文 E2E`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-188` |
| Title | `贯通 Notion 快照 attach、.notion/ 读取与聊天上下文 E2E` |
| Type | `backend` |
| Priority | `medium` |
| Status | `done` |
| Work mode | `standard` |
| Pending comments | `0` |
| Labels | `backend, notion, snapshot, workspace, chat, e2e, regression` (按标题与设计范围推断) |
| Related contract | `SUO-176`, `SUO-177` |
| Blocked by | `none` |

## 3. 任务目标

- 将 `ClaudeAgentService.assemble_context()` 的 workspace attach 与 `build_user_message()` 串成一条稳定链路，确保每轮用户消息在进入 prompt 之前已经拿到当前 canonical snapshot。
- 让 `.notion/snapshot.json`、`.notion/connector.json`、`.notion/index.json`、`.notion/databases.json` 和 `.notion/pages/*.json` 共享同一 snapshot identity，不出现一边更新、一边仍读旧快照的分叉。
- 让 `<workspace_context>` 只暴露已 attach 的 Notion connector 和 snapshot 信息，指导 Agent 先读 `.notion/snapshot.json`，再读需要的 `.notion/*` 文件。
- 保持 `.notion/` 读取为 snapshot-scoped read，不在读取时回源 Notion 远程 API，也不把本地 derived context 当成权威状态。
- 保持纯 chat fallback 稳定：当没有 connector、没有 snapshot 或 workspace 关闭时，仍然能够正常进入对话，不泄露旧的 `.notion` 状态。
- 用定向回归测试锁住 attach -> read -> prompt 的 E2E 路径，避免后续改动把 snapshot identity、workspace context 和 chat assembly 再次拆开。

## 4. 实现步骤

1. 收紧 workspace attach 的调用顺序。
   - 在 `backend/claude_agent/service.py` 中，确保 `get_or_create_workspace()` 之后、`build_user_message()` 之前就完成 Notion snapshot materialize。
   - 通过 `build_notion_facade(user_id).materialize_workspace()` 读取当前 connector 的 persisted snapshot，而不是让 prompt 层自己拼装 Notion 状态。
   - 若当前用户没有可用 connector，清理或重置 `.notion/` 占位文件，避免纯 chat 轮次带着过期快照继续运行。

2. 对齐 snapshot identity 的持久化与落盘合同。
   - 让 `backend/notion/store.py` 的 `save_snapshot()`、`get_current_snapshot()`、`list_snapshots()` 始终围绕同一 `snapshot_version / source_revision / sync_cursor` 读取和更新。
   - 让 `backend/notion/sync.py` 物化的 `.notion/snapshot.json`、`.notion/connector.json`、`.notion/index.json`、`.notion/databases.json`、`.notion/pages/*.json` 来自同一个 snapshot object。
   - 保持 `backend/notion/factory.py` 的 facade 只做 orchestration，不另起一条与 store/sync 不一致的 attach 路径。

3. 固化 chat prompt 的 Notion 上下文注入。
   - 在 `backend/claude_agent/workspace_context.py` 中继续从 workspace-local `.notion/` 文件读取 connector / snapshot 状态，并把 snapshot version、source revision、last synced 信息渲染到 `<workspace_context>`。
   - 在 `backend/claude_agent/context_builder.py` 中保持顺序稳定：`<runtime_context>` -> `<workspace_context>` -> 用户正文。
   - 确保 `workspace_context` 只描述当前 attach 的 snapshot，不把 Notion 远程结果或者临时缓存写成新的权威来源。

4. 保持 snapshot 读取契约单点化。
   - 让 `backend/libs/claude_agent_kit/server/notion_snapshot.py` 继续作为 `.notion/` 路径解析、snapshot identity 和缺页语义的唯一合同层。
   - 确保 `.notion/pages/<page_id>.json` 缺页返回 snapshot-scoped miss，而不是触发远程 lazy load。
   - 保持 `.notion/snapshot.json` 的 identity 字段足够支持后续 turn 复用与调试。

5. 补齐 E2E 回归测试。
   - 扩展 `backend/tests/test_claude_agent_service.py`，覆盖 workspace attach 后 `.notion/` 文件已 materialize 且 `build_workspace_context_block()` 读到同一 snapshot identity。
   - 扩展 `backend/tests/test_claude_agent_context_builder.py`，验证 `<workspace_context>` 的渲染顺序、Notion 块存在性和纯 chat 轮次的回退路径。
   - 复用 `backend/tests/test_notion_store.py` 与 `backend/tests/test_notion_snapshot_contract.py` 作为 identity / path-resolution / missing-page 的基础合同测试。
   - 如现有测试覆盖不足，新增 `backend/tests/test_notion_workspace_attach_e2e.py` 作为 proposed 的端到端回归入口。

## 5. 涉及文件路径

| Path | Role |
|---|---|
| `backend/claude_agent/service.py` | workspace attach、snapshot materialize、chat turn 组装的主入口。 |
| `backend/claude_agent/workspace_context.py` | 从 `.notion/` 读取并渲染 Notion connector / snapshot 上下文块。 |
| `backend/claude_agent/context_builder.py` | 保证 `<runtime_context>`、`<workspace_context>`、用户正文的装配顺序。 |
| `backend/notion/factory.py` | connector facade orchestration，串起 store/sync/materialize。 |
| `backend/notion/store.py` | current snapshot 指针、snapshot 历史、connector 归属和 thread 挂载。 |
| `backend/notion/sync.py` | canonical snapshot 物化与 workspace-local `.notion/` 落盘。 |
| `backend/routers/notion.py` | 当前 connector / sync 路由入口，作为 attach 前的 snapshot 更新面。 |
| `backend/libs/claude_agent_kit/server/notion_snapshot.py` | `.notion/` virtual path 解析、snapshot identity、缺页语义。 |
| `backend/tests/test_claude_agent_service.py` | workspace attach materialize 的现有回归点。 |
| `backend/tests/test_claude_agent_context_builder.py` | prompt 组装顺序与 `<workspace_context>` 回归点。 |
| `backend/tests/test_notion_store.py` | snapshot 保存与 current pointer 语义回归点。 |
| `backend/tests/test_notion_snapshot_contract.py` | `.notion/` 路径解析与 snapshot-scoped miss 合同。 |
| `backend/tests/test_notion_workspace_attach_e2e.py`（proposed） | 端到端 attach -> read -> prompt 回归入口。 |

## 6. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | 当前用户的 `user_id`、已持久化的 Notion connector、current snapshot pointer、workspace 开关状态、以及本轮 chat 请求。 |
| 输入 | workspace-local `.notion/` 占位目录、`workspace_id` / `cwd`、和 snapshot 物化所需的 connector 元数据。 |
| 输出 | workspace-local `.notion/snapshot.json`、`.notion/connector.json`、`.notion/index.json`、`.notion/databases.json`、`.notion/pages/*.json`。 |
| 输出 | `<workspace_context>` 中的 Notion device index、snapshot version / source revision / last synced 信息。 |
| 输出 | Agent 读取 `.notion/*` 时获得的 snapshot-scoped JSON 视图，以及在无 connector 时的安全纯 chat 回退。 |

## 7. 依赖项

- `docs/design/notion-session/overview.md`
- `docs/design/notion-session/connector-interaction.md`
- `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
- `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
- `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
- `docs/design/claude-agent/edit-point/workspace-context.md`
- `SUO-176`（shared snapshot/chat contract reference）
- `SUO-177`（backend contract / data layer baseline）
- `backend/claude_agent/service.py`
- `backend/claude_agent/workspace_context.py`
- `backend/claude_agent/context_builder.py`
- `backend/notion/store.py`
- `backend/notion/sync.py`
- `backend/notion/factory.py`
- `backend/libs/claude_agent_kit/server/notion_snapshot.py`

## 8. 测试策略

- Service attach 测试：构造一个 fake connector / snapshot，验证 `assemble_context()` 会在 `build_user_message()` 之前 materialize `.notion/`，并把 workspace path 传给上下文构建器。
- Prompt 顺序测试：验证 `<runtime_context>` 仍在前、`<workspace_context>` 紧随其后、用户正文最后进入 prompt。
- Snapshot 合同测试：验证 `snapshot_identity()`、`get_notion_snapshot_resource_data()` 和 missing-page miss 语义保持一致。
- Store 合同测试：验证 `save_snapshot()` / `get_current_snapshot()` / `list_snapshots()` 对 current snapshot pointer 的读写一致性。
- E2E 回归测试：创建 connector -> 保存 snapshot -> attach workspace -> 读取 `.notion/index.json` / `.notion/pages/<id>.json` -> 校验 prompt 中的 snapshot identity 与落盘内容一致。

## 9. 完成标志

- 每轮用户消息在进入模型前，都会先 attach 当前 canonical snapshot 并 materialize 到 workspace-local `.notion/`。
- `build_workspace_context_block()` 能稳定展示当前 Notion connector 状态和 snapshot identity。
- `.notion/` 读取只依赖 attached snapshot，不再出现远程 lazy load 或本地缓存分叉。
- 同一 `snapshot_version` 在 store、workspace 文件和 prompt 中保持一致。
- 相关定向测试全部通过，且纯 chat 场景不会因为没有 Notion connector 而失败。

## 10. 风险提示

- 如果 attach 的调用顺序晚于 `build_user_message()`，Agent 会看到上一轮或空快照，E2E contract 会退化成“文件已写但 prompt 未更新”。
- 如果 `store.py` 和 `sync.py` 的 identity 字段不一致，`.notion/` 文件和 prompt 可能同时存在但语义不同步。
- 如果 `workspace_context.py` 或 `context_builder.py` 再次引入远程读取逻辑，会破坏 snapshot-scoped read contract。
- 如果无 connector 场景没有正确清理 `.notion/` 占位文件，纯 chat 轮次可能误读到过期 Notion 上下文。
- 若后续发现 response wrapper 或 snapshot shape 与当前 consumer contract 不一致，优先记录为兼容风险，不要把本 Issue 扩成新的前端或写回设计。
