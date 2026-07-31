# SUO-174 后端任务文档：Notion 资源连接器的认证、资源发现与 snapshot 落地

Status: Draft  
Updated: 2026-07-04  
Scope: 后端任务规划 - Notion resource connector MVP 的认证、发现与 snapshot 落地

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/resource-connector-er.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`,
>      `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`,
>      `backend/libs/claude_agent_kit/server/notion_snapshot.py`,
>      `backend/routers/device_oauth.py`,
>      `backend/routers/workspace.py`,
>      `backend/server.py`
> [Output] 可执行的后端任务文档，供后续实现阶段直接拆分与执行
> [Pos] `task_176_backend_notion-resource-connector-auth-discovery-snapshot` in `docs/task`
> [Sync] 2026-07-04: generated from the filled requirement template for SUO-174.

## 1. 任务标题

`SUO-174 Notion 资源连接器后端：认证、资源发现与 snapshot 落地`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-174` |
| Title | `实现 Notion 资源连接器后端：认证、资源发现与 snapshot 落地` |
| Type | `backend` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Pending comments | `0` |
| Labels | `backend, notion, connector, auth, snapshot` (按标题与设计范围推断) |

## 3. 任务目标

- 建立 Notion 资源连接器的后端认证入口，围绕 `ntn login`、`ntn login poll`、`ntn auth status` 和 `NOTION_HOME` 形成稳定合同。
- 提供后端资源发现能力，能区分 accessible database、standalone page，以及它们的分页和选择结果。
- 将选定资源物化为 connector-owned canonical snapshot，并让 `.notion/` 虚拟路径从同一 snapshot identity 读取。
- 保持只读优先：本期只做认证、发现和 snapshot 落地，不引入 Notion 写操作或任务调度编排。
- 复用现有 snapshot 合同与 workspace 机制，避免为 Notion 再造一套与 `.editor/` 无关的并行读路径。

## 4. 实现步骤

1. 落地 Notion 认证层。
   - 新建 `backend/notion/auth.py`，封装 `ntn login --no-browser` 的启动、stdout 解析、poll 轮询和 `ntn auth status` 校验。
   - 将 `NOTION_HOME` 解析、默认目录、环境变量拼装和 token 可用性检查收束到单一后端模块。
   - 为 CLI 缺失、超时、认证过期、环境缺失等失败分支定义稳定错误类型。

2. 落地资源发现层。
   - 新建 `backend/notion/operations.py`，封装只读搜索、页面读取和 database query 能力。
   - 采用 Notion API / `ntn api` 的分页语义，分别暴露 `database` 和 `page` 结果，避免把两种对象混成单一资源列表。
   - 保留 standalone page 与 database row page 的差异，确保选择结果可以直接进入 snapshot materialization。

3. 落地 canonical snapshot 数据层。
   - 新建 `backend/notion/data.py`，负责把认证与 discovery 的结果物化为 `CanonicalWorkspaceSnapshot`。
   - 维护 current snapshot 指针、snapshot identity、历史版本和 `source_revision` / `sync_cursor` 元数据。
   - 继续复用 `backend/libs/claude_agent_kit/server/notion_snapshot.py` 里的路径解析与 staleness contract，保证 `.notion/` 读取规则与后端 snapshot 一致。

4. 暴露连接器 API 并注册到应用路由。
   - 新建 `backend/routers/notion.py`，挂载 `/api/connectors`、`/api/connectors/:id/auth/login`、`/api/connectors/:id/auth/poll`、`/api/connectors/:id/databases`、`/api/connectors/:id/pages`、`/api/connectors/:id/resources/select`、`/api/connectors/:id/sync` 等端点。
   - 在 `backend/server.py` 注册新 router，并同步更新 `backend/routers/.folder.md` 的文件表。
   - 路由层只做请求校验、认证与结果转发，业务逻辑继续下沉到 `backend/notion/*` 模块。

5. 接通 snapshot landing 与 workspace 读取面。
   - 将 `backend/libs/claude_agent_kit/server/workspace.py` 的 workspace 初始化与 `.notion/` 目录/占位文件生成对齐。
   - 如果需要把 connector snapshot 暴露给 agent runtime，再追加最小的 context bridge，但不要把这次任务扩成前端或写回实现。
   - 保持 `.notion/` 只读，不把远程 Notion 结果直接当成 agent 本地缓存权威状态。

6. 补齐测试与 contract 覆盖。
   - 新增认证、资源发现、snapshot materialization、路由和 workspace 读取的单元测试。
   - 复用并扩展 `backend/tests/test_notion_snapshot_contract.py`，验证路径解析、缺页语义和 staleness 判断。
   - 通过最小集成测试证明连接器创建、认证、发现、选择、同步和 snapshot 读回串起来可用。

## 5. 涉及文件路径

### 新增模块

- `backend/notion/__init__.py`
- `backend/notion/auth.py`
- `backend/notion/operations.py`
- `backend/notion/data.py`
- `backend/notion/errors.py`
- `backend/notion/factory.py`

### 路由与应用接入

- `backend/routers/notion.py`
- `backend/server.py`
- `backend/routers/.folder.md`

### Snapshot 与 workspace 连接

- `backend/libs/claude_agent_kit/server/notion_snapshot.py`
- `backend/libs/claude_agent_kit/server/workspace.py`
- `backend/claude_agent/service.py`（仅在 runtime 必须直接 attach snapshot 时联动）

### 测试

- `backend/tests/test_notion_snapshot_contract.py`
- `backend/tests/test_notion_auth.py`
- `backend/tests/test_notion_operations.py`
- `backend/tests/test_notion_data.py`
- `backend/tests/test_notion_router.py`
- `backend/tests/test_workspace_router.py`

## 6. 输入 / 输出说明

### 输入

- 用户在 Notion 资源连接器 UI 中提供的认证配置和选择结果。
- 后端环境中的 `NOTION_HOME`、`PATH`、`ntn` CLI 可执行文件和必要网络访问。
- 当前 workspace / connector 的 snapshot identity 与选定资源列表。

### 输出

- 认证结果：`pending`、`authenticated`、`expired` 等稳定状态。
- 资源发现结果：可访问 database 与 page 的分页列表，以及用户选择的资源集合。
- Snapshot 结果：`CanonicalWorkspaceSnapshot`、`snapshot_version`、`source_revision`、`sync_cursor`、`fetched_at`。
- `.notion/` 读结果：connector、snapshot、index、databases、pages 等虚拟路径的稳定 JSON 视图。

## 7. 依赖项

- `docs/design/notion-session/overview.md`
- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/resource-connector-er.md`
- `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
- `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
- `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
- `backend/libs/claude_agent_kit/server/notion_snapshot.py`
- `backend/routers/device_oauth.py`（只作为 router/认证实现风格参考）
- `backend/routers/workspace.py`（workspace 初始化与 sandbox 参考）
- `backend/routers/claude_agent.py`（若 snapshot 要进入 agent runtime，则作为联动参考）

## 8. 测试策略

- 为认证层补单测：验证 `ntn login` 输出解析、poll 超时、状态查询和错误分支。
- 为资源发现层补单测：验证分页参数、page/database 区分、query 负载和空结果处理。
- 为 snapshot 层补单测：验证 `CanonicalWorkspaceSnapshot` 物化、路径解析、缺页语义和 stale 判断。
- 为 router 层补单测：验证 `/api/connectors` 系列端点的请求/响应契约和认证失败路径。
- 做一个最小集成测试：认证成功后选定资源，触发同步，确认 `.notion/index.json` / `.notion/pages/<id>.json` 读到同一 snapshot identity。

## 9. 完成标志

- 可以通过后端接口完成 Notion 连接器认证、资源发现和资源选择。
- 同一 connector / snapshot identity 下，`connector.json`、`snapshot.json`、`index.json`、`databases.json` 和 `pages/*.json` 的读取结果一致。
- 认证失败、资源缺失、snapshot stale 和 CLI 异常都有稳定错误语义，不会静默降级为未知状态。
- 新增测试全部通过，且没有引入写回路径、任务调度或前端实现依赖。

## 10. 风险提示

- `ntn` CLI 的 stdout / JSON 输出格式若变化，会直接影响认证与发现解析器，需要专门的契约测试兜底。
- Notion 的 database/page 语义不同，资源发现如果抽象过度，后续 snapshot materialization 会丢失结构信息。
- snapshot 需要保持强一致的 identity；如果同步后直接重用旧版本，agent 读到的内容会和后端不一致。
- Workspace Mode、sandbox 网络策略和 `NOTION_HOME` 目录权限会影响认证与同步的可用性，需要在测试里覆盖最小环境约束。
- 本期不做写回，后续如果补 `operations.py` 的写能力，必须重新评估冲突、幂等与确认流程，不要沿用只读假设。
