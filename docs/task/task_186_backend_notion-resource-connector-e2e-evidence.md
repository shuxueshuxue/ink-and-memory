# SUO-186 后端任务文档：Notion 资源连接器后端链路 E2E 证据验证

Status: Draft  
Updated: 2026-07-05  
Scope: 后端任务规划 - Notion 资源连接器后端链路 E2E 证据验证与 snapshot attach 归一

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/resource-connector-er.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`,
>      `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`,
>      `backend/routers/notion.py`,
>      `backend/notion/auth.py`,
>      `backend/notion/factory.py`,
>      `backend/notion/store.py`,
>      `backend/notion/sync.py`,
>      `backend/notion/errors.py`,
>      `backend/claude_agent/service.py`,
>      `backend/claude_agent/workspace_context.py`,
>      `backend/libs/claude_agent_kit/server/notion_snapshot.py`,
>      `backend/tests/test_notion_connector_router_flow.py`,
>      `backend/tests/test_notion_store.py`,
>      `backend/tests/test_notion_snapshot_contract.py`,
>      `backend/tests/test_claude_agent_service.py`,
>      `backend/tests/test_server_claude_agent.py`
> [Output] 可执行的后端任务文档，供后续验证阶段直接复用与引用
> [Pos] `task_186_backend_notion-resource-connector-e2e-evidence` in `docs/task`
> [Sync] 2026-07-05: generated from the filled requirement template for SUO-186 and aligned to the route-flow + workspace-attach evidence chain.

## 1. 任务标题

`SUO-186 Notion 资源连接器后端链路 E2E 证据验证`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-186` |
| Title | `验证 Notion 资源连接器后端链路 E2E 证据` |
| Type | `backend` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Pending comments | `0` |
| Parent | `未提供` |
| Parent title | `未提供` |
| Parent status | `未提供` |
| Blocks | `none` |
| Blocked by | `none` |
| Labels | `backend, notion, connector, e2e, evidence, snapshot, workspace-attach` (按标题与设计范围推断) |
| Backend contract baseline | `SUO-177` |

## 3. 任务目标

- 证明 Notion 资源连接器后端链路可以稳定跑通 create -> auth -> discovery -> selection -> sync -> snapshot attach。
- 证明同一个 `connector_id` 和同一个 `snapshot_identity` 会贯穿路由层、持久化层、canonical snapshot、workspace-local `.notion/` 文件和 `workspace_context` 输出。
- 把证据收敛为一个可复现、可引用的 mock-backed 后端 smoke，而不是依赖人工猜测或零散日志。
- 保持当前 backend contract 不扩张；如果证据暴露了响应形状或快照 identity 不一致，只补最小的回归断言。
- 不把这次任务扩成前端 UI、写回、Deck 或多平台抽象实现。

## 4. 实现步骤

1. 复用现有 route-flow 证明链。
   - 基于 `backend/tests/test_notion_connector_router_flow.py` 的 temp SQLite + mocked Notion CLI / discovery fixture，确认 create、auth/login、auth/poll、databases、pages、resources/select、sync 和 final get 都返回同一个 `connector_id`。
   - 保留 route 返回中的 `snapshotIdentity`、`databaseCount`、`pageCount` 和 final connector snapshot 字段，作为证据主线。

2. 把 attach 证明接到同一条链上。
   - 新增一个薄的 E2E smoke，优先命名为 `backend/tests/test_notion_connector_e2e_evidence.py`。
   - 在同一个 temp DB / workspace 上，调用 `ClaudeAgentService.assemble_context()` 或等价的 workspace attach 路径，让 `build_notion_facade(...).materialize_workspace()` 真实写出 `.notion/`。
   - 断言 `.notion/snapshot.json`、`.notion/connector.json`、`.notion/index.json`、`.notion/databases.json` 和 `build_workspace_context_block()` 中的 snapshot 版本、source revision 与 last synced 信息一致。

3. 复用已有 contract 作为证据护栏。
   - 使用 `backend/tests/test_notion_snapshot_contract.py` 验证 `.notion/` 虚拟路径解析和 snapshot identity contract。
   - 使用 `backend/tests/test_claude_agent_service.py` 验证 attach/materialize 路径不会退回到 fake context。
   - 使用 `backend/tests/test_server_claude_agent.py` 保证 route 注册和 auth gating 没有回退。

4. 只在证据缺口处做最小修正。
   - 如果 route 返回、store 保存、snapshot materialization 或 workspace attach 之间存在 shape mismatch，只修正对应的 contract，不重写 connector 架构。
   - 如果现有测试已经覆盖链路，就不要额外扩成更大的集成套件。

5. 留下可引用的证据记录。
   - 记录验证命令、退出码、connector id、snapshot version、source revision 和 workspace path。
   - 让这些值可以直接复制到 issue 评论或后续回归记录中。

## 5. 涉及文件路径

### 证据主线

- `backend/tests/test_notion_connector_router_flow.py`
- `backend/tests/test_notion_connector_e2e_evidence.py`（proposed）
- `backend/tests/test_notion_store.py`
- `backend/tests/test_notion_snapshot_contract.py`
- `backend/tests/test_claude_agent_service.py`
- `backend/tests/test_server_claude_agent.py`

### 后端 contract 面

- `backend/routers/notion.py`
- `backend/notion/auth.py`
- `backend/notion/factory.py`
- `backend/notion/store.py`
- `backend/notion/sync.py`
- `backend/notion/errors.py`
- `backend/claude_agent/service.py`
- `backend/claude_agent/workspace_context.py`
- `backend/libs/claude_agent_kit/server/notion_snapshot.py`

### 兼容性参考

- `frontend/src/api/resourceConnectorApi.ts`

## 6. 输入 / 输出说明

### 输入

- 临时 SQLite connector store。
- mocked Notion CLI / discovery / snapshot builder 结果。
- 已选择的 Notion databases / pages。
- workspace 路径与当前 connector 的 snapshot identity。

### 输出

- 路由链路的稳定响应：`connector_id`、`auth_status`、`selected resources`、`snapshotIdentity`、`databaseCount`、`pageCount`。
- canonical snapshot 和 workspace-local `.notion/` 文件。
- `build_workspace_context_block()` 中的 Notion device summary。
- 可引用的验证命令与关键 identity 值。

## 7. 依赖项

- `docs/design/notion-session/overview.md`
- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/resource-connector-er.md`
- `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
- `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
- `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
- `SUO-177`，backend contract baseline
- `SUO-182`，create-response / 404 regression guard
- `backend/tests/test_notion_connector_router_flow.py`
- `backend/tests/test_notion_snapshot_contract.py`
- `backend/tests/test_claude_agent_service.py`

## 8. 测试策略

- 运行定向验证，而不是全量后端构建。
- 当前仓库的证据链主要是 mock-backed integration / contract tests，不应误标为已连通外部 Notion 的真实线上 E2E。
- 推荐命令：

```bash
python -m pytest \
  backend/tests/test_notion_connector_router_flow.py \
  backend/tests/test_notion_snapshot_contract.py \
  backend/tests/test_claude_agent_service.py \
  backend/tests/test_server_claude_agent.py \
  -q
```

- 如果新增 `backend/tests/test_notion_connector_e2e_evidence.py`，把它加入同一条定向命令。
- 断言同一个 `connector_id` 与 `snapshot_identity` 在 route response、store snapshot、`.notion/` 文件和 workspace context 中一致。
- 只在证据链断裂时增加最小回归断言，不扩大到额外的平台能力。

## 9. 证据映射

| Test / Surface | Evidence role | Backing |
|---|---|---|
| `backend/tests/test_notion_auth.py` | 认证流程与 `ntn` 输出解析证据 | mock-backed（`_run_ntn_command` patch） |
| `backend/tests/test_notion_store.py` | connector persistence / snapshot pointer 证据 | local SQLite / in-memory style fixture |
| `backend/tests/test_notion_snapshot_contract.py` | `.notion/` 路径解析与 snapshot contract 证据 | pure contract / no external Notion dependency |
| `backend/tests/test_notion_connector_router_flow.py` | create -> auth -> discovery -> select -> sync route 证据 | mock-backed route integration |
| `backend/tests/test_claude_agent_service.py` | workspace attach / `.notion/` materialization 证据 | fake facade + local workspace files |
| `backend/tests/test_server_claude_agent.py` | route registration / auth gating smoke | app-level smoke only |

### Mock boundary note

- 以上测试可以一起构成“后端链路 E2E 证据链”，但它们仍然依赖 mock / fake / contract fixtures。
- 若后续需要外部 Notion CLI + 网络联通的真实 smoke，应单独补测并给出 owner；当前文档不把这些 mock-backed 用例误记为真实线上 E2E。

## 10. 完成标志

- 一条可重复的定向测试命令能够证明 Notion connector 后端链路跑通。
- 同一个 `connector_id` 和 `snapshot_identity` 可以从 create 一路跟到 auth、select、sync、attach 和 workspace_context。
- `.notion/snapshot.json`、`.notion/connector.json`、`.notion/index.json`、`.notion/databases.json` 与 `build_workspace_context_block()` 的内容一致。
- 证据已经记录到可引用的位置，后续回归可以直接复用。
- 没有把任务扩张成写回、前端 UI 或新 connector 架构。

## 11. 风险提示

- 如果 mocked boundary 过多，可能把真实 contract drift 掩盖掉，因此 route/store/snapshot/attach 层要尽量保留真实实现。
- 如果 attach 使用了不同的 workspace_id 或旧 snapshot，证据会“看起来正确”但实际上是假的，必须显式断言 identity。
- 如果 response wrapper 仍和当前 consumer contract 不一致，应记录为 evidence risk，而不是扩大 task 范围。
- 不要把这个 issue 变成通用的集成测试框架或新的 connector 子系统。
