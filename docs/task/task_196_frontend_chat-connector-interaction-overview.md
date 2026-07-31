# SUO-196 前端任务文档总览：Chat / Connector 交互重构

Status: Draft  
Updated: 2026-07-07  
Scope: 前端任务总览 - Chat landing、connector workbench、auth state mapping、browser E2E

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/issue/ISSUES_notion-session-chat-connector-interaction.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`,
>      `docs/prd/notion-session/resource-connector.md`,
>      `docs/prd/notion-session/resource-connector-ui-design.md`,
>      `docs/stage/stage_notion-resource-connector-interaction.md`
> [Output] Chat / Connector 交互重构的前端 task 家族总览与边界收口
> [Pos] `task_196_frontend_chat-connector-interaction-overview` in `docs/task`
> [Sync] 2026-07-07: generated after `SUO-195` split completion; frontend task family resumed from the resolved blocker.

## 1. 任务标题

`SUO-196 前端任务文档总览：Chat / Connector 交互重构`

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
| Parent status | `in_progress` |
| Blocks | `SUO-197` |
| Blocked by | `SUO-195` |
| Blocker status | `done` |
| Pending comments | `0` |

## 3. 任务目标

- 将 `SUO-195` 拆解后的前端实现范围收敛为一组可执行 task 文档，避免实现端直接从 Issue 清单猜边界。
- 明确 Chat landing、connector workbench、auth-state 映射和 E2E 验证的任务边界，确保每个 slice 都能回溯到设计稿和 issue split。
- 保持 frontend-only 视角，不把 backend auth-session 的具体实现写进前端 task 文档里，只描述前端需要消费的状态语义。
- 为 `SUO-197` 提供可直接消费的 task 输入，使 stage 规划可以继续编排。

## 4. 实现步骤

1. 先交付本总览文档，再按 slice 交付 landing、connector、auth-state、E2E 四份 task 文档。
2. 在每个 slice 里明确允许修改的文件、禁止扩大到的范围、以及可接受的最小修复面。
3. 对 auth-session 语义只写 frontend 映射和展示规则，后端持久化和 poll 幂等作为 `SUO-195-C` 的外部依赖。
4. 把 browser E2E 的证据要求写成可执行清单，而不是模糊的“手工验证通过”。
5. 每份 slice 都要能独立被下游实现者消费，同时在总览中保持统一的命名和依赖说明。

## 5. 涉及文件路径

| Path | Role |
|---|---|
| `docs/task/task_196a_frontend_chat-shell-landing-tabs.md` | Chat landing tabs / QuickActionStrip / shell recovery slice |
| `docs/task/task_196b_frontend_connector-embedded-mode.md` | Embedded connector workbench slice |
| `docs/task/task_196c_frontend_connector-auth-session-state-mapping.md` | Frontend auth-session contract slice |
| `docs/task/task_196d_frontend_chat-connector-agent-browser-e2e.md` | Agent-browser verification slice |
| `frontend/src/App.tsx` | Entry and view switching surface |
| `frontend/src/components/chat/ChatView.tsx` | Landing tabs and shell-level UI surface |
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | Connector workbench surface |
| `frontend/src/api/resourceConnectorApi.ts` | Connector client / auth polling / refresh surface |

## 6. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | 设计稿 `connector-interaction.md` / `overview.md` / `interaction-snapshot-lifecycle.md`，以及 `SUO-195` issue 拆解结果。 |
| 输入 | 当前 frontend 代码中的 `App.tsx`、`ChatView.tsx`、`ResourceConnectorPage.tsx`、`resourceConnectorApi.ts`。 |
| 输出 | 四份可执行 slice task 文档 + 一份总览文档，形成 SUO-196 task family。 |
| 输出 | 每份 slice 都清楚标注风险、依赖和最小验证证据，避免 implementation 侧二次猜测。 |

## 7. 依赖项

- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/overview.md`
- `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
- `docs/prd/notion-session/resource-connector.md`
- `docs/prd/notion-session/resource-connector-ui-design.md`
- `SUO-195-A`
- `SUO-195-B`
- `SUO-195-C`
- `SUO-195-D`
- `SUO-197`

## 8. 测试策略

- 总览文档不承载代码验证，但要在 slice 文档中统一要求 E2E 证据格式。
- 所有 slice 的测试策略都必须能落到桌面和移动端的最小 browser smoke。
- 对 auth-session slice，测试必须覆盖 `consumed` / `authenticated` / `expired` 的前端收敛规则。

## 9. 完成标志

- 4 份 slice 文档都已生成并且路径稳定。
- 每份 slice 都明确了自己的实现边界，不会彼此冲突。
- `SUO-197` 可以直接引用这组 task 文档继续 stage 编排。

## 10. 风险提示

- 如果 slice 之间的边界不清晰，下游实现会把 Chat shell、connector workbench 和 auth-state 映射混成一条线。
- 如果把 backend auth-session 的实现细节写进前端 task 文档，会越过 FrontendTaskAgent 的职责边界。
- 如果 E2E 证据要求不够具体，后续验收会变成“能跑就行”，无法作为 stage gate。
