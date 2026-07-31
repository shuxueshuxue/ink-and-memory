# Exec Report: SUO-191 - Notion 资源连接器前端 E2E 回归验证

Status: blocked
Updated: 2026-07-05
Scope: 前端执行证据与最小修复归档 - Notion 资源连接器创建 / 认证 / 资源选择 / 来源刷新链路

## 1. 执行上下文

| Field | Value |
|---|---|
| Task ID | `SUO-191` |
| 关联 Issue | `SUO-191`（wake payload 指派；`issue status=in_progress`，`pending comments=0`） |
| 关联任务 | `docs/task/task_187_frontend_notion-resource-connector-e2e-regression.md`（同类前端回归任务，作为本次执行的最近任务契约参考） |
| 关联 Stage | `docs/stage/stage_notion-resource-connector-e2e.md` |
| 关联设计稿 | `docs/design/notion-session/overview.md`、`docs/design/notion-session/connector-interaction.md`、`docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`、`docs/prd/notion-session/resource-connector.md`、`docs/prd/notion-session/resource-connector-ui-design.md` |
| 模板路径 | `docs/task/TASK-REQUIREMENT-FORMAT.md` |
| 执行 Agent | `ExecTaskAgent` |
| 执行时间 | `2026-07-05` |
| 执行前补充 | 任务允许范围聚焦在前端 connector 链路回归验证；live Notion auth 在本次浏览器环境中不可完成，因为登录页已跳转到外部 Notion 认证页面，且当前浏览器 profile 未提供可用的 Notion 会话。 |
| 父级门禁影响 | 在当前 `stage_notion-resource-connector-e2e` 收口中，该阻塞被识别为 `local_or_contract_only` 边界，不作为 `SUO-172` 的 execute_gate 阻塞；父级需在 live-only 验收时再补外部会话。 |

## 2. TASK-REQUIREMENT-FORMAT.md 填充摘要

- 输入 Issue: `SUO-191`，目标是执行 Notion 资源连接器前端 E2E 回归验证，并把结果落成可审计证据。
- 输入 Task: 参考 `docs/task/task_187_frontend_notion-resource-connector-e2e-regression.md` 的前端回归边界，覆盖入口、认证、资源选择和来源刷新。
- 填充后的执行目标: 证明 `App.tsx` 入口 -> `ResourceConnectorPage` -> `resourceConnectorApi` 的最小链路可跑通，并确认 selection payload 与后端契约一致。
- 关键约束:
  - 不改后端路由、不改 Notion CLI、不扩展 Deck / 写回 / chat / workspace attach。
  - 仅允许前端 client 的最小兼容修复，以及与该修复直接相关的 folder docs 和执行报告。
  - 若 live Notion auth 无法完成，必须显式标注 blocker，不得把本地 fallback 结果误记为线上 E2E 完成。
- 验收条件:
  - 前端 build 通过。
  - 资源选择保存后，backend connector config 保留真实选择，而不是被空数组覆盖。
  - 浏览器 smoke 能看到 connector 创建、资源选择、来源同步与刷新路径。

## 3. 模型生成的执行任务

- 任务目标: 在不扩大范围的前提下，排查并修复 Notion 资源连接器前端 E2E 回归中的 contract drift，并记录可审计证据。
- 实现范围: `frontend/src/api/resourceConnectorApi.ts` 的 resource selection payload 兼容修复，以及对应 folder docs / exec report。
- 文件范围:
  - `frontend/src/api/resourceConnectorApi.ts`
  - `frontend/src/api/.folder.md`
  - `frontend/src/.folder.md`
  - `docs/exec/.folder.md`
  - `docs/exec/exec_191_frontend_resource_connector_e2e_regression.md`
- 实现步骤:
  1. 复核 connector selection 请求体与 backend route contract 的字段名。
  2. 将前端 `selectConnectorResources` 的 body 改为 backend 期望的 `selected_databases` / `selected_pages`。
  3. 更新受影响 folder docs 与文件头注释，记录这次契约对齐。
  4. 通过 frontend build 与浏览器 smoke 验证 selection persistence 与 refresh 路径。
- 验证方式:
  - `npm run build`（frontend）
  - 浏览器 smoke：本地 dev server 上执行 connector 创建、auth 启动、资源选择、刷新来源，并检查 backend connector config 与 local fallback 状态。

## 4. 实现变更记录

| 文件 | 操作 | 说明 |
|---|---|---|
| `frontend/src/api/resourceConnectorApi.ts` | update | 将资源选择请求体从 `database_ids/page_ids` 改为 backend 期望的 `selected_databases/selected_pages`，避免 `/resources/select` 保存后丢失选择。 |
| `frontend/src/api/.folder.md` | update | 记录 resource connector client 现在使用 backend selection payload contract。 |
| `frontend/src/.folder.md` | update | 记录 frontend app shell 内的 resource selection payload 对齐修复。 |
| `docs/exec/.folder.md` | update | 记录新增 SUO-191 exec 报告与 live-auth blocker 边界。 |
| `docs/exec/exec_191_frontend_resource_connector_e2e_regression.md` | create | 归档本次前端 E2E 回归验证、最小修复、测试结果、阻塞与回滚建议。 |

## 5. 测试与验证

- 已执行测试:
  - `npm run build` in `frontend`
  - 浏览器 smoke（本地 dev server + 真实页面）
- 测试结果:
  - `npm run build` 退出码 `0`
  - `tsc -b && vite build` 成功完成
  - Vite 仅输出既有 chunk size / dynamic import 提示，无构建失败
- 关键浏览器证据:
  - 创建 connector 成功，后端返回真实 UUID `c497f3c4-d6f8-4f0a-a7ed-70075bb0fd8e`
  - 认证启动后，真实 Notion verification URL 打开到外部登录页，说明 live auth 依赖外部会话
  - 修复前 selection 请求体使用错误字段名，导致 backend config 里的 selection 丢失
  - 修复后 `/api/connectors/{id}/resources/select` 成功接收 `selected_databases` / `selected_pages`
  - backend connector config 保留了 `selected_databases` 与 `selected_pages`
  - local fallback 状态下 UI 可见 3 个 synced source cards，并可刷新来源
- 未执行测试及原因:
  - 未完成真实 Notion 登录闭环
  - 原因: 当前浏览器 profile 不包含可用的 Notion 登录态，且外部 Notion 登录页需要独立会话/凭据
- 手动验证步骤:
  1. 从 dashboard 进入 connector view。
  2. 创建连接器并启动 auth。
  3. 选择 fallback 数据源并点击保存。
  4. 确认 backend connector config 记住选择而不是空数组。
  5. 点击刷新来源，确认 local fallback source cards 维持 synced。

## 6. 风险与阻塞

- 风险:
  - local fallback 仍可能掩盖后端 response-shape drift，必须继续绑定真实 backend UUID 和 persisted selection 观察。
  - 如果 future UI change 再次修改 selection payload，`/resources/select` 仍可能回到 silent drop。
- 阻塞:
  - live Notion auth 无法在当前浏览器 profile 完成。
  - 外部 Notion 登录页未提供当前会话所需的可用认证上下文。
- 需要上游澄清的问题:
  - 是否需要单独的带 Notion 会话的浏览器 profile，或者由环境 owner 提供已登录的 Notion 工作区 session。

## 7. 完成状态

- [x] 已完成最小实现修复
- [x] 已完成 frontend build 验证
- [x] 已完成浏览器 smoke
- [x] 已记录变更
- [ ] 已满足全部 E2E 验收条件
- [ ] 可进入 review / audit

## 8. 回滚建议

- 回滚文件:
  - `frontend/src/api/resourceConnectorApi.ts`
  - `frontend/src/api/.folder.md`
  - `frontend/src/.folder.md`
  - `docs/exec/.folder.md`
  - `docs/exec/exec_191_frontend_resource_connector_e2e_regression.md`
- 回滚方式:
  - 将 selection body 的 `selected_databases` / `selected_pages` 改回旧字段名，删除对应 sync 注释与 exec 记录。
  - 如需完全撤销本次执行记录，再删除新增 exec 报告并恢复 docs folder sync。
- 注意事项:
  - 回滚后 backend connector selection persistence 会再次丢失。
  - 回滚前应确认没有其他并行任务依赖本次 frontend contract 对齐。

## 9. 执行完成报告

- 状态: `blocked`
- 交付物:
  - 前端 resource selection contract drift 已修复。
  - build 与 browser smoke 已留下可复核证据。
  - exec 报告与 folder contract 已归档。
- 验证证据:
  - `npm run build` 退出码 `0`
  - backend connector config 记住 `selected_databases` / `selected_pages`
  - 浏览器 smoke 中 source cards 与 refresh path 可达
- 阻塞说明:
  - 真实 Notion auth 无法在当前浏览器会话中完成，因此本次只能给出“已修复并通过本地/后端合同验证”的结论，不能把 live E2E 标为完成。
  - 可进入 review / audit: 否，需先补齐 live Notion session 或明确接受 local fallback 作为验收边界
  - 注：对 `SUO-172` 来说本次以 `local_or_contract_only` 收口已满足父级 execute_gate。
