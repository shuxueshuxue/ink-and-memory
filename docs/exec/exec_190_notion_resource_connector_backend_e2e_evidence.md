# Exec Report: SUO-190 - Notion 资源连接器后端 E2E 证据验证

Status: done  
Updated: 2026-07-05  
Scope: 后端证据验证与执行归档 - Notion 资源连接器后端链路 E2E smoke / contract evidence

## 1. 执行上下文

| Field | Value |
|---|---|
| Task ID | `SUO-190` |
| 关联 Issue | `SUO-190`（wake payload 指派；`issue status=in_progress`，`pending comments=0`） |
| 关联任务 | `docs/task/task_186_backend_notion-resource-connector-e2e-evidence.md`（本次执行对齐的本地后端 evidence task） |
| 关联 Stage | `docs/stage/stage_notion-resource-connector-e2e.md` |
| 关联设计稿 | `docs/design/notion-session/overview.md`、`docs/design/notion-session/connector-interaction.md`、`docs/design/notion-session/resource-connector-er.md`、`docs/design/claude-agent/notion-point/resource-connector-layer-design.md`、`docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`、`docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`、`docs/design/claude-agent/edit-point/workspace-context.md`、`docs/design/claude-agent/edit-point/workspace-switch.md` |
| 模板路径 | `docs/task/TASK-REQUIREMENT-FORMAT.md` |
| 执行 Agent | `ExecTaskAgent` |
| 执行时间 | `2026-07-05` |
| 执行前补充 | 当前工作区没有 `.notion/` 目录，因此本次仅能做仓库内的 mock-backed / contract-backed 证据验证，不做真实 `ntn` 在线 smoke。 |

## 2. TASK-REQUIREMENT-FORMAT.md 填充摘要

- 输入 Issue: `SUO-190`，目标是收敛 Notion 资源连接器后端链路的可复用 E2E 证据。
- 输入 Task: 后端 E2E 证据验证，沿用现有 route-flow、store、snapshot contract、service attach、server smoke 证据链。
- 填充后的执行目标: 证明 `create -> auth -> discovery -> selection -> sync -> snapshot attach` 的后台证据链可重复复现，并且 `connector_id` / `snapshot_identity` 一致。
- 关键约束:
  - 不新增后端能力，不改前端，不扩写回、Deck 或多平台抽象。
  - 保持 mock-backed / contract-backed 边界清晰，不把本地 smoke 误记为真实 Notion 在线连通。
  - 若出现 response-shape mismatch，只记录兼容风险并保留最小断言。
- 验收条件:
  - 定向后端测试全部通过。
  - `connector_id`、`snapshot_version`、`source_revision`、`sync_cursor` 的证据可从 route/store/attach 链路中复核。
  - 证据和回滚边界被归档到 `docs/exec/`。

## 3. 模型生成的执行任务

- 任务目标: 使用仓库既有测试证明 Notion connector 后端 E2E 证据链可用，并记录本次验证边界。
- 实现范围: 仅执行验证与归档，不修改运行时代码。
- 文件范围:
  - `backend/tests/test_notion_auth.py`
  - `backend/tests/test_notion_store.py`
  - `backend/tests/test_notion_snapshot_contract.py`
  - `backend/tests/test_notion_connector_router_flow.py`
  - `backend/tests/test_claude_agent_service.py`
  - `backend/tests/test_server_claude_agent.py`
  - `docs/exec/.folder.md`
  - `docs/exec/exec_190_notion_resource_connector_backend_e2e_evidence.md`
  - `docs/.folder.md`
- 实现步骤:
  1. 先确认仓库里已有的 Notion connector / attach / server smoke 测试是否足够覆盖后端 evidence 主线。
  2. 使用后端 venv 运行定向 unittest 套件。
  3. 记录测试结果、关键日志和 mock/live 边界。
  4. 写入执行报告与 exec folder contract。
- 验证方式:
  - `cd backend && .venv/bin/python -m unittest tests.test_notion_auth tests.test_notion_store tests.test_notion_snapshot_contract tests.test_notion_connector_router_flow tests.test_claude_agent_service tests.test_server_claude_agent -v`

## 4. 变更记录

| 文件 | 操作 | 说明 |
|---|---|---|
| `docs/.folder.md` | update | 将 `exec/` 纳入 docs 目录契约，并补充同步说明。 |
| `docs/exec/.folder.md` | create | 新增 exec 报告目录契约，定义执行报告的用途与文件类型。 |
| `docs/exec/exec_190_notion_resource_connector_backend_e2e_evidence.md` | create | 归档本次 SUO-190 后端 E2E 证据验证结果、风险与回滚建议。 |

## 5. 测试与验证

- 已执行测试:
  - `cd backend && .venv/bin/python -m unittest tests.test_notion_auth tests.test_notion_store tests.test_notion_snapshot_contract tests.test_notion_connector_router_flow tests.test_claude_agent_service tests.test_server_claude_agent -v`
- 测试结果:
  - 退出码 `0`
  - `Ran 64 tests in 0.084s`
  - `OK`
- 关键证据:
  - `tests.test_notion_connector_router_flow.TestNotionConnectorRouterFlow.test_connector_router_happy_path` 通过，覆盖 create / auth / discover / select / sync / final get 证据链。
  - `tests.test_claude_agent_service.TestClaudeAgentServiceNotionAttach.test_workspace_attach_materializes_notion_snapshot_into_workspace_files` 通过，覆盖 workspace attach / `.notion/` 物化逻辑。
  - `tests.test_notion_snapshot_contract.NotionSnapshotContractTest.test_snapshot_identity_and_write_staleness` 通过，覆盖 snapshot identity 与写入陈旧性 contract。
- 运行日志中的预期信息:
  - `Failed to load user agent settings from system_config; skipping. Error: system_config unavailable`
  - `Ignoring client-provided Claude Agent cwd because Workspace Mode is disabled. requested=/tmp/client-workspace`
  - `tool_result for unregistered toolCallId=tool-call-1 ... Auto-registering.`
  - 以上均未导致测试失败。
- 未执行测试及原因:
  - 未执行真实 `ntn` / `api.notion.com` 在线 smoke。
  - 原因: 当前 workspace 没有 `.notion/` 目录，且本次 task 的证据边界是仓库内 mock-backed contract / integration 测试。
- 手动验证步骤:
  - 无额外手工 UI 验证；本次以 unittest 结果作为可复核证据。

## 6. 风险与阻塞

- 风险:
  - mock-backed 证据不能证明外部 Notion 服务的真实网络连通性。
  - 当前 workspace 缺少 `.notion/`，因此无法补一个真实 connector smoke 作为同一轮证据。
- 阻塞:
  - 无仓库内阻塞，验证链路已完成。
- 需要上游澄清的问题:
  - 如果上游需要 live Notion smoke，需要单独提供带 `.notion/` 的工作空间或明确的外部环境 owner。

## 7. 完成状态

- [x] 已完成证据验证
- [x] 已完成执行归档
- [x] 已记录变更清单
- [x] 已记录测试结果
- [x] 已明确 mock/live 边界
- [x] 可进入 review / audit

## 8. 回滚建议

- 回滚文件:
  - `docs/.folder.md`
  - `docs/exec/.folder.md`
  - `docs/exec/exec_190_notion_resource_connector_backend_e2e_evidence.md`
- 回滚方式:
  - 删除本次新增的 exec 报告和 exec folder contract。
  - 从 `docs/.folder.md` 中移除 `exec/` 条目与同步说明。
- 注意事项:
  - 本次没有修改运行时代码，因此回滚不会影响后端行为。

## 9. 执行完成报告

- 状态: `done`
- 交付物:
  - 本地后端 E2E 证据链验证完成。
  - 执行报告已归档。
  - docs 目录契约已更新。
- 验证证据:
  - 定向 unittest 套件全绿，退出码 `0`。
  - 关键 Notion connector / attach / snapshot contract / server smoke 测试均通过。
- 可进入 review / audit: 是
- 备注:
  - 由于当前工具集无法直接写回本仓库外部的 issue 线程，本次仅通过 docs/exec 留下可审计证据。
