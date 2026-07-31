# SUO-182 后端任务文档：Notion 资源连接器创建后响应契约与 404 回归修复

Status: Draft  
Updated: 2026-07-04  
Scope: 后端任务规划 - Notion 资源连接器创建后响应契约、connector identity 传递与后续接口 404 回归修复

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/resource-connector-er.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`,
>      `backend/routers/notion.py`,
>      `backend/notion/__init__.py`,
>      `backend/notion/factory.py`,
>      `backend/notion/store.py`,
>      `backend/notion/sync.py`,
>      `backend/notion/errors.py`,
>      `backend/tests/test_notion_store.py`,
>      `backend/tests/test_notion_snapshot_contract.py`,
>      `backend/tests/test_server_claude_agent.py`,
>      `frontend/src/api/resourceConnectorApi.ts`
> [Output] 可执行的后端任务文档，供后续实现阶段直接拆分与执行
> [Pos] `task_182_backend_notion-resource-connector-post-create-404-regression` in `docs/task`
> [Sync] 2026-07-04: generated from the filled requirement template for SUO-182.
> [Sync] 2026-07-04: live issue state rechecked after generation; `SUO-182` and parent `SUO-172` are both `done`, so this artifact is now closed historical context.

## 1. 任务标题

`SUO-182 Notion 资源连接器创建后响应契约与 404 回归修复`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-182` |
| Title | `修复资源连接器创建后后续接口 404 回归` |
| Type | `backend` |
| Priority | `high` |
| Status | `done` |
| Work mode | `standard` |
| Pending comments | `0` |
| Parent | `SUO-172` |
| Parent title | `IM 资源链接器业务代码实现` |
| Parent status | `done` |
| Blocks | `resolved (historical linkage to SUO-172)` |
| Labels | `backend, notion, connector, regression, 404, api-contract` (按标题与设计范围推断) |
| Backend contract baseline | `SUO-177` |

## 3. 任务目标

- 让 `POST /api/connectors` 返回一个可被消费端稳定解析的创建响应，避免前端创建后退回本地 synthetic connector id。
- 保证创建完成后，返回的同一个 connector id 可以立即用于 `/api/connectors/{id}`、`/auth/login`、`/auth/poll`、`/databases`、`/pages`、`/resources/select` 和 `/sync`，不再因为 id 不一致出现 404。
- 将创建响应、连接器持久化记录和后续路由 lookup 收敛到同一条 backend contract 上。
- 保持设计稿中的 connector lifecycle 不变，只修复 create-response 与 post-create lookup 的契约偏差。
- 明确这次修复曾是 `SUO-172` 的阻断解除条件之一，让后续实现可以直接消费同一个 persisted connector id。
- 为这类回归补齐定向 contract tests，防止“创建成功但后续接口 404”的问题再次出现。

## 4. 任务范围

### In Scope

- `POST /api/connectors` 的响应 envelope 和 connector identity 语义。
- `backend/notion/store.py` 中创建后可立即回查的 persisted connector 记录。
- `backend/notion/factory.py` / `backend/routers/notion.py` 中的路由级 identity 透传与 404 语义。
- 创建后紧跟的 `GET /api/connectors/{id}` 与至少一个子路由的定向回归测试。
- 必要时为当前消费端提供兼容响应形状，避免 local fallback connector id。

### Out of Scope

- Notion 认证流程本身的协议重写。
- 资源发现、资源选择、snapshot 物化的算法改造。
- 前端 dashboard、导航、视觉层重构。
- Deck / file upload / write-back 等其他 connector 能力。
- 新平台连接器抽象。

## 5. 实现步骤

1. 收敛创建响应的单一权威身份。
   - 审视 `backend/routers/notion.py` 的 `create_connector` 路由与 `backend/notion/factory.py`、`backend/notion/store.py` 的返回值。
   - 明确 `POST /api/connectors` 应返回哪个稳定字段作为后续所有 `/api/connectors/{id}` 子路由的唯一依据。
   - 让创建响应对当前消费端是可解析的，不再触发本地 synthetic connector 兜底。

2. 对齐后续路由的 lookup 语义。
   - 确认 `get_connector`、`start_auth`、`poll_auth`、`list_databases`、`list_pages`、`select_resources`、`sync` 都基于同一个 persisted connector id。
   - 保证 newly-created connector 在同一用户上下文下可以立刻被查到，不因为响应 shape 或 owner 解析错误而 404。
   - 若需要，补一个兼容字段或兼容数组，避免现有消费端误判为“未创建成功”。

3. 补齐定向回归测试。
   - 在现有 route smoke tests 上增加 create-response contract 断言。
   - 让测试覆盖“创建 -> 取回 -> 访问至少一个子路由”的链路，验证返回 id 可用而不是局部 fallback id。
   - 若 auth / discovery 不适合真实调用，用 mock 或最小 stub 保证测试只验证 404 回归边界。

4. 同步文档与契约说明。
   - 更新 task 模板和 task 文档头部，明确这是 create-response / post-create 404 回归修复。
   - 在相关设计引用中保留 current consumer contract 的说明，避免后续再把 response wrapper 改回去。

## 6. 涉及文件路径

### 核心实现面

- `backend/routers/notion.py`
- `backend/notion/__init__.py`
- `backend/notion/factory.py`
- `backend/notion/store.py`
- `backend/notion/errors.py`
- `backend/notion/sync.py`

### 兼容性参考

- `frontend/src/api/resourceConnectorApi.ts`

### 测试

- `backend/tests/test_server_claude_agent.py`
- `backend/tests/test_notion_store.py`
- `backend/tests/test_notion_snapshot_contract.py`
- `backend/tests/test_notion_connector_create_contract.py`（proposed）

## 7. 输入 / 输出说明

### 输入

- 用户通过 `POST /api/connectors` 提交的连接器名称与平台信息。
- 当前登录用户的身份信息，以及 connector 归属校验结果。
- `resource_connectors` 表中刚写入的 persisted row。
- 现有消费端对创建响应的解析方式，尤其是当前是否会因为 response wrapper 不匹配而退回本地 connector。
- `SUO-172` 的后续实现对同一 connector id 的消费方式。

### 输出

- 一个可解析的创建响应，能够明确携带 persisted connector identity。
- 一个不会把创建后 id 变成 synthetic/local id 的后续调用链。
- `GET /api/connectors/{id}` 与至少一个子路由的稳定可达性，避免 404。
- 对应的 contract tests，证明“创建后后续接口”链路可用。
- 让后续实现阶段可以直接把这份 task 文档作为 `SUO-172` 的恢复依据。

## 8. 依赖项

- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/resource-connector-er.md`
- `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
- `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
- `SUO-172`，当前父 issue（已 done，历史 unblock target）
- `SUO-177`，作为当前 Notion 资源连接器 backend contract baseline
- `backend/routers/notion.py`
- `backend/notion/factory.py`
- `backend/notion/store.py`
- `backend/tests/test_server_claude_agent.py`
- `backend/tests/test_notion_store.py`

## 9. 测试策略

- 为 `POST /api/connectors` 补 create-response contract test，验证返回 payload 中的 connector identity 是 persisted 的，而不是本地生成的占位 id。
- 使用 create 返回的 id 调用 `GET /api/connectors/{id}`，确认 route 解析和 user ownership 检查通过，且不会 404。
- 使用 create 返回的 id 再调用一个子路由，例如 `/auth/login` 或 `/databases`，通过 mock 让测试只验证路由可达性，不依赖真实 Notion 凭据。
- 如引入兼容字段，补一条测试确保现有消费端可从该响应中提取真实 connector。
- 保留现有 route registration smoke tests，避免只测 payload 不测路由树。

## 10. 完成标志

- `POST /api/connectors` 的返回结果可以被消费端稳定解析为同一个 persisted connector。
- 使用创建响应里的 id 访问 `/api/connectors/{id}` 和至少一个后续子路由时，不再出现 404。
- 创建后不需要 synthetic/local connector id 兜底即可完成后续调用链。
- contract tests 已覆盖 create -> get -> subroute 的最小回归路径。
- task 文档已明确 `SUO-172` 的 unblock 语义（历史态），后续实现团队可以直接据此回溯主链路。
- task 模板与 task 文档已同步到 SUO-182 的 backend regression 语义。

## 11. 风险提示

- 如果 backend 只改成设计稿中的对象形状，而没有兼容当前消费端的解析方式，前端仍可能回退到本地 synthetic connector id，404 回归会继续出现。
- 如果测试只验证 `POST /api/connectors` 成功而不继续验证同一个 id 的后续子路由，response shape 的回归仍可能漏掉。
- 当前仓库里已有 pending connector 记录，手工验证时容易把“创建成功”误判为“后续接口可用”，需要以 create 返回的 id 为唯一真值。
- 不要把这个 issue 扩成新的 connector architecture 重构；本次只修复 create-response 与 post-create lookup 的契约。
- `SUO-172` 的后续实现必须读取这份 task 文档中的 contract 约束，否则 parent issue 仍可能再次撞到同类 404。
