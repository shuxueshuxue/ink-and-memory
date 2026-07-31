# SUO-196C 前端任务文档：认证会话状态映射

Status: Draft  
Updated: 2026-07-07  
Scope: 前端任务规划 - connector auth session UI mapping and poll contract consumption

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/issue/ISSUES_notion-session-chat-connector-interaction.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`,
>      `frontend/src/api/resourceConnectorApi.ts`,
>      `frontend/src/components/dashboard/ResourceConnectorPage.tsx`,
>      `frontend/src/components/chat/ChatView.tsx`,
>      `frontend/src/constants/storageKeys.ts`
> [Output] 前端 auth session 状态映射 task 文档，明确 UI 消费语义与退路
> [Pos] `task_196c_frontend_connector-auth-session-state-mapping` in `docs/task`
> [Sync] 2026-07-07: generated for the SUO-196 task family after the issue split completed.

## 1. 任务标题

`SUO-196C 认证会话状态映射`

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
| Task Slice | `S0c` |

## 3. 任务目标

- 明确前端如何消费 `connector.auth_status`、`config.auth_session` 和 poll 返回值，避免 `pending` 变成唯一阻塞态。
- 把 `consumed`、`authenticated`、`expired`、`error` 等认证边界状态映射成可理解、可恢复的 UI。
- 规定前端只消费后端已给出的 auth session 语义，不把后端持久化实现写进前端 task 文档。
- 保证 auth 轮询不会因为 local fallback 或缓存状态而把真实连接状态掩盖掉。

## 4. 实现步骤

1. 在 task 文档里定义一个明确的前端状态表，列出 `draft`、`authenticating`、`authenticated`、`syncing`、`expired`、`error` 等状态的 UI 表现。
2. 说明 `auth/poll` 返回 `consumed` 时，若 connector 已有 token，则前端应收敛到 `authenticated`，而不是回退到 `pending`。
3. 说明 `auth/poll` 返回 `expired` 或 `already_consumed` 时，UI 应给出重试或重新认证入口，而不是无限轮询。
4. 把 `resourceConnectorApi.ts` 的归一逻辑和 `ResourceConnectorPage.tsx` 的状态展示绑定起来，避免 API 与 UI 各自解释状态。
5. 把 backend auth-session 持久化和 poll 幂等视作 `SUO-195-C` 的外部依赖，不在这里展开后端实现方案。

## 5. 涉及文件路径

| Path | Role |
|---|---|
| `frontend/src/api/resourceConnectorApi.ts` | auth poll / status normalization consumer. |
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | auth state rendering and CTA mapping. |
| `frontend/src/components/chat/ChatView.tsx` | embedded connector tab consumption of auth state. |
| `frontend/src/constants/storageKeys.ts` | auth-related fallback isolation if needed. |

## 6. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | auth poll / status payload、connector auth status、session config。 |
| 输入 | backend 已定义的 consumed / authenticated / expired 语义。 |
| 输出 | 前端状态表和 UI 映射规则，供实现直接引用。 |
| 输出 | 可判断是否重试、重新认证或保持已认证的前端行为边界。 |

## 7. 依赖项

- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/overview.md`
- `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
- `SUO-195-C`
- `frontend/src/api/resourceConnectorApi.ts`
- `frontend/src/components/dashboard/ResourceConnectorPage.tsx`

## 8. 测试策略

- 状态收敛 smoke：验证 `consumed` -> `authenticated`、`expired` -> re-auth、`pending` -> complete 的前端收敛规则。
- contract smoke：验证 client 归一没有把 backend 已认证状态误判为 pending。
- UI smoke：验证认证失败后仍然保留可恢复入口，不进入死循环轮询。

## 9. 完成标志

- 前端 auth state mapping 文档足够明确，implementation 不需要猜测 consumed / expired 的 UI 语义。
- 认证轮询的前端收敛规则可以直接用于 `resourceConnectorApi.ts` 和 `ResourceConnectorPage.tsx`。
- backend 责任边界和 frontend 消费边界都被明确写出。

## 10. 风险提示

- 如果前端把 `pending` 当成唯一阻塞态，会导致已经完成的认证被错误回退。
- 如果把 backend auth-session 持久化细节写进前端文档，会越界到后端任务规划。
- 如果 local fallback 的 auth 状态与远端状态混用，会造成 UI 与真实连接态不一致。
