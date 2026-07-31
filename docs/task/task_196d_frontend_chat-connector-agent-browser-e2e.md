# SUO-196D 前端任务文档：Chat / Connector agent-browser E2E 验证

Status: Draft  
Updated: 2026-07-07  
Scope: 前端任务规划 - Chat / Connector 重构的 agent-browser E2E 证据

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/issue/ISSUES_notion-session-chat-connector-interaction.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/stage/stage_notion-resource-connector-interaction.md`,
>      `frontend/src/App.tsx`,
>      `frontend/src/components/chat/ChatView.tsx`,
>      `frontend/src/components/dashboard/ResourceConnectorPage.tsx`,
>      `frontend/src/api/resourceConnectorApi.ts`
> [Output] agent-browser E2E 验证任务文档，定义最小证据与失败诊断
> [Pos] `task_196d_frontend_chat-connector-agent-browser-e2e` in `docs/task`
> [Sync] 2026-07-07: generated as the verification slice for the SUO-196 task family.

## 1. 任务标题

`SUO-196D Chat / Connector agent-browser E2E 验证`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-196` |
| Title | `Chat / Connector 交互重构前端任务编写` |
| Type | `frontend` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Parent | `SUO-193` |
| Blocked by | `SUO-195` |
| Blocker status | `done` |
| Pending comments | `0` |
| Task Slice | `S0d` |

## 3. 任务目标

- 定义一条可复核的 browser E2E 证据链，证明 Chat landing、connector embedded workbench、auth state mapping 和 shell recovery 都能被真实浏览器触达。
- 明确 agent-browser 脚本需要覆盖的最小场景、断言和截图证据，不把“手工看起来可以”当作验收。
- 保证 E2E 任务只验证前端可见和可达的行为，不扩张到 backend 改造、Notion CLI 内部或写回实现。
- 让 `SUO-197` 在 stage 编排时能够直接复用这份证据定义。

## 4. 实现步骤

1. 写清楚最小验证路径：landing shell -> `history` / `connector` tab -> connector create/auth/select -> refresh -> shell recovery。
2. 对每个关键动作要求截图或可追踪的检查点，避免只记录成功结论。
3. 在任务文档里定义失败时的诊断输出：页面状态、控制台异常、网络异常和当前视图。
4. 把桌面和移动端都列为必须覆盖的 smoke 场景，避免只测宽屏。
5. 说明若 `SUO-195-C` 的 auth-session 行为未达成，E2E 只允许将其记录为前置依赖失败，不得把其混同为本任务缺陷。

## 5. 涉及文件路径

| Path | Role |
|---|---|
| `frontend/src/App.tsx` | E2E 入口视图切换 surface。 |
| `frontend/src/components/chat/ChatView.tsx` | landing tabs / shell recovery surface。 |
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | connector embedded workbench surface。 |
| `frontend/src/api/resourceConnectorApi.ts` | connector auth/select/refresh client surface。 |
| `frontend/tests/**` | 如仓库引入最小 browser harness，则只在这里放置。 |

## 6. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | browser 视图、认证流程、资源选择与 shell recovery 的可见行为。 |
| 输入 | agent-browser 的截图和诊断输出能力。 |
| 输出 | 一条或多条可复核的 E2E 证据路径，以及失败时的定位信息。 |
| 输出 | 能支持 `SUO-197` 和后续 stage gate 的验证材料。 |

## 7. 依赖项

- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/overview.md`
- `docs/stage/stage_notion-resource-connector-interaction.md`
- `SUO-195-A`
- `SUO-195-B`
- `SUO-195-C`
- `SUO-195-D`
- `frontend/src/App.tsx`
- `frontend/src/components/chat/ChatView.tsx`
- `frontend/src/components/dashboard/ResourceConnectorPage.tsx`

## 8. 测试策略

- Desktop smoke：验证 landing tabs、connector tab、auth flow、refresh flow 和 shell recovery。
- Mobile smoke：验证短宽度 / 短高度下入口仍可达，关键按钮与恢复入口不会被折叠掉。
- Evidence capture：关键动作后保留截图或日志片段，失败时附控制台与网络诊断。
- Contract smoke：如果前置 auth/state contract 未满足，将其记录为依赖失败而不是 E2E 失败。

## 9. 完成标志

- 这条 E2E 证据路径可以被重复跑通，并能给出明确截图和诊断输出。
- 入口、connector、auth、shell recovery 都有可复核断言。
- 证据定义足以让后续 stage 编排直接复用。

## 10. 风险提示

- 如果只写“手工 smoke”而不要求截图和诊断输出，后续验收不可追溯。
- 如果 E2E 路径包含太多前端以外的前置条件，会把浏览器验证变成集成测试泥潭。
- 如果移动端没有单独定义，短屏布局回归会漏掉。
