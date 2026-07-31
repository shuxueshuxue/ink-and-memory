# SUO-177 后端任务文档：Notion 资源连接器后端合同、持久化与数据层接线

Status: Draft  
Updated: 2026-07-04  
Scope: 后端任务规划 - Notion 资源连接器的路由合同、认证/发现、资源选择/同步、选定资源持久化、canonical snapshot 与 workspace attach 接线；`SUO-176` 已完成，仅保留历史追踪

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/resource-connector-er.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`,
>      `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`,
>      `backend/notion/__init__.py`,
>      `backend/notion/auth.py`,
>      `backend/notion/operations.py`,
>      `backend/notion/store.py`,
>      `backend/notion/sync.py`,
>      `backend/notion/factory.py`,
>      `backend/notion/errors.py`,
>      `backend/routers/notion.py`,
>      `backend/server.py`,
>      `backend/claude_agent/service.py`,
>      `backend/claude_agent/workspace_context.py`,
>      `backend/libs/claude_agent_kit/server/notion_snapshot.py`
> [Output] 可执行的后端任务文档，供后续实现阶段拆分与验证
> [Pos] `task_177_backend_notion-resource-connector-contract-data-layer` in `docs/task`
> [Sync] 2026-07-04: refreshed after `SUO-176` unblock and aligned to the live backend route/store/snapshot wiring.

## 1. 任务标题

`SUO-177 Notion 资源连接器后端：合同、持久化与数据层接线`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-177` |
| Title | `实现 Notion 资源连接器后端合同与数据层接线` |
| Type | `backend` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Pending comments | `1` |
| Parent | `SUO-172` |
| Blocked by | `none`（`SUO-176` 已完成，仅保留追踪关系） |
| Labels | `backend, notion, connector, auth, discovery, snapshot, store, sync, workspace-attach` (按标题与设计范围推断) |

## 3. 任务目标

- 将 Notion 资源连接器的后端合同收敛到一条稳定路径：创建、认证、轮询、资源发现、资源选择、同步、快照读取与 workspace attach。
- 让 `/api/connectors*` 路由层只负责请求校验、鉴权与结果转发，避免把业务逻辑散落在 handler 里。
- 让 `backend/notion/` 负责 Notion CLI auth/discovery、selected resource 持久化、canonical snapshot 物化、快照历史保存与 connector-scoped 线程挂载。
- 保证同一 `workspace_id + connector_id + snapshot_version` 下的 `.notion/` 读取来自同一 canonical snapshot，不把 Notion 远端状态当成本地权威缓存。
- 为 Claude Agent 的 workspace attach 提供可复用的 snapshot read / materialize 接线，但不把本 Issue 扩成前端 UI 或写回方案。
- 在现有 backend 代码表面上继续收敛 contract 与持久化语义，而不是另起一套 Notion 子系统。

## 4. 任务范围

### In Scope

- 统一 Notion connector 的创建、列表、更新、删除与用户归属检查。
- 统一 `ntn login --no-browser`、`ntn login poll`、`ntn auth status` 的认证合同与错误映射。
- 统一 database/page 的 discovery 结果归一、selected resource 持久化和同步触发。
- 统一 canonical snapshot 的保存、读取、历史版本与 workspace-local `.notion/` materialization。
- 统一 router registration、server mount、Claude Agent workspace attach 的后端接线。
- 统一 connector 线程挂载、current snapshot pointer 更新与读取回路，确保同一 connector 的 persisted row、selected resources 与 current snapshot identity 对齐。

### Out of Scope

- 前端 dashboard、导航、弹窗、来源视图和所有视觉实现。
- Notion 写回、proposal 批准、冲突合并与任务调度层。
- 多平台资源连接器统一框架。
- 需要真实 Notion 凭证之外的测试环境搭建或运维脚本。
- 前端导航或 UI 重构；如果 consumer contract 还有偏差，只在 backend task 文档里标注，不扩成前端任务。

## 5. 实现步骤

1. 收敛路由与服务边界。
   - 让 `backend/routers/notion.py` 只做入参归一、当前用户鉴权、异常映射和结果透传。
   - 确保 `backend/server.py` 正确挂载 Notion router，并保持现有 OAuth / Claude Agent / session 路由不回退。

2. 收敛认证与发现合同。
   - 保持 `backend/notion/auth.py` 对 `ntn login --no-browser`、`ntn login poll`、`ntn auth status` 的单一包装。
   - 保持 `backend/notion/operations.py` 对 `v1/search`、`v1/databases/<id>/query`、`v1/pages/<id>` 和 block children 的只读封装。
   - 统一 database / page 发现的归一字段，避免 router 与 store 各自解释 payload。

3. 收敛选定资源与快照存储。
   - 让 `backend/notion/store.py` 负责 connector、resource、page、snapshot、thread attachment 的持久化一致性。
   - 确保 `save_snapshot()` 同时更新当前 snapshot 指针、source revision、sync cursor 与最近同步时间。
   - 确保 `get_current_snapshot()`、`list_snapshots()`、`attach_thread_to_connector()` 的行为与路由和 workspace attach 一致。

4. 收敛 canonical snapshot 物化。
   - 让 `backend/notion/sync.py` 按 selected resources 组装 `CanonicalWorkspaceSnapshot`，并把同一 snapshot 写入 workspace-local `.notion/`。
   - 保证 `snapshot.json`、`connector.json`、`index.json`、`databases.json`、`databases/*.json`、`pages/*.json` 的 identity 一致。
   - 当没有可用 snapshot 时，保留可读的 connector metadata 占位内容，而不是静默失败。

5. 收敛 Claude Agent attach 接线。
   - 让 `backend/claude_agent/service.py` 在 workspace attach 阶段读取当前 snapshot，而不是把远端 Notion 状态塞进 agent 本地缓存。
   - 让 `backend/claude_agent/workspace_context.py` 把当前 Notion connector / snapshot identity 暴露给上下文模板。
   - 保持 attach 读取与 `.notion/` 虚拟文件的同一 snapshot identity 对齐。
   - 现有服务层已经 materialize `.notion/`；这一轮只校正 identity、fallback 与 contract 边界，不新增另一条读取路径。

6. 补齐验证与回归覆盖。
   - 复用 `backend/tests/test_notion_auth.py`、`backend/tests/test_notion_store.py`、`backend/tests/test_notion_snapshot_contract.py`、`backend/tests/test_server_claude_agent.py` 做最小回归闭环。
   - 若 route / contract 有覆盖缺口，再补最小的路由级断言，不要直接上全量后端集成测试。
   - 如果现有断言已经覆盖当前 contract，就复用它们，不额外引入宽泛的集成测试。

## 6. 涉及文件路径

### 核心实现面

- `backend/notion/__init__.py`
- `backend/notion/auth.py`
- `backend/notion/operations.py`
- `backend/notion/store.py`
- `backend/notion/sync.py`
- `backend/notion/factory.py`
- `backend/notion/errors.py`

### 路由与服务接线

- `backend/routers/notion.py`
- `backend/server.py`
- `backend/claude_agent/service.py`
- `backend/claude_agent/workspace_context.py`

### Snapshot 合同

- `backend/libs/claude_agent_kit/server/notion_snapshot.py`

### 测试

- `backend/tests/test_notion_auth.py`
- `backend/tests/test_notion_store.py`
- `backend/tests/test_notion_snapshot_contract.py`
- `backend/tests/test_server_claude_agent.py`

## 7. 输入 / 输出说明

### 输入

- 当前登录用户的 `user_id` 与 connector 归属信息。
- 前端提交的 connector 创建、认证、资源选择和同步请求。
- `NOTION_HOME`、`ntn` CLI 可执行文件、`PATH` 与必要的运行时环境。
- 选定的 database/page 资源集合、workspace_id、当前 connector 的 snapshot identity。

### 输出

- Connector CRUD 响应：`connector_id`、`auth_status`、`config`、`current_snapshot_version` 等稳定字段。
- 认证响应：`verificationUrl`、`verificationCode`、`pollIntervalSeconds`、`authenticated/pending/expired` 状态。
- 发现响应：可访问 database/page 的归一列表及 `selected` 标记。
- 选择/同步响应：selected resources 持久化结果、`snapshotIdentity`、`databaseCount`、`pageCount`、`synced`。
- Snapshot 输出：`connector.json`、`snapshot.json`、`index.json`、`databases.json`、`databases/*.json`、`pages/*.json` 与 workspace attach 所需的当前快照元信息。

## 8. 依赖项

- `docs/design/notion-session/overview.md`
- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/resource-connector-er.md`
- `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
- `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
- `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
- `docs/stage/stage_notion-resource-connector.md`（上游阶段计划；`SUO-176` 已完成，保留追踪）
- `backend/routers/deps.py`
- `backend/server.py`
- `backend/notion/auth.py`
- `backend/notion/operations.py`
- `backend/notion/store.py`
- `backend/notion/sync.py`
- `backend/notion/factory.py`
- `backend/libs/claude_agent_kit/server/notion_snapshot.py`
- `backend/claude_agent/service.py`
- `backend/claude_agent/workspace_context.py`
- `backend/tests/test_notion_auth.py`
- `backend/tests/test_notion_store.py`
- `backend/tests/test_notion_snapshot_contract.py`
- `backend/tests/test_server_claude_agent.py`

## 9. 测试策略

- 为 `backend/notion/auth.py` 补认证解析测试，覆盖 `ntn login` 输出解析、poll 分类、`auth status` 失败语义和 `NOTION_HOME` 解析。
- 为 `backend/notion/store.py` 补持久化测试，覆盖 connector CRUD、selected resources、snapshot 保存/读取、thread attach 和 snapshot pointer 更新。
- 为 `backend/notion/sync.py` 与 `backend/libs/claude_agent_kit/server/notion_snapshot.py` 保持快照合同测试，覆盖路径解析、缺页语义、snapshot identity 一致性与过期判断。
- 为 `backend/server.py` 和 `backend/routers/notion.py` 做最小路由注册与请求/响应契约检查，确认 `/api/connectors*` 路由暴露完整。
- 为 `backend/claude_agent/service.py` 做 workspace attach 回归，确认当前 snapshot 会被 materialize 到 `.notion/`，并且不是从远端实时拉取。
- 只跑与 Notion connector 有关的定向测试，不默认扩大到全量后端构建。
- 如果回归测试发现 store / attach 的 current snapshot identity 不一致，优先修正 contract 再扩大验证面。

## 10. 完成标志

- `/api/connectors*` 提供稳定的用户作用域内 Notion connector CRUD、auth、discovery、selection、sync 和 resource removal 能力。
- 同一 connector 的 `resource_connectors`、`connector_resources`、`connector_resource_pages`、`connector_snapshots`、`connector_chat_threads` 数据彼此一致。
- `save_snapshot()` 与 `materialize_workspace_snapshot()` 产生的当前 snapshot identity 一致，且 `.notion/` 读取不需要回源 Notion。
- Claude Agent attach 能从 backend 的 current snapshot 读取 connector state，而不是把远端状态塞进运行时本地缓存。
- 相关定向测试全部通过，且没有把本 Issue 扩展成前端、写回或任务调度实现。
- 任务文档与 issue 线程中的 blocker 状态一致，当前不应再把 `SUO-176` 当作活动阻塞。

## 11. 风险提示

- `ntn` CLI 的 stdout / JSON / exit code 语义如果变化，会同时影响认证、发现和同步三个面，必须靠定向测试兜底。
- 如果 connector store 与 workspace materialization 不是同一 snapshot identity，Agent 可能读到旧 `.notion/` 内容但 DB 已经切到新版本。
- 路由层如果没有严格做当前用户归属检查，可能造成 connector 泄漏或错误 attach。
- `workspace attach` 若在 snapshot 缺失时静默回退，容易掩盖同步失败并让后续读路径看见错误状态。
- 如果后续运行再次出现 workspace attach 与 store snapshot identity 不一致的漂移，需要重新校正当前 contract，而不是继续沿用旧快照。
- 只做当前合同，不要把写回、增量任务和多平台抽象混进这个 Issue，否则会把验收面拉得不可控。
