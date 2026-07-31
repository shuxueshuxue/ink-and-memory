# SUO-196B 前端任务文档：Connector 嵌入适配

Status: Draft  
Updated: 2026-07-07  
Scope: 前端任务规划 - ResourceConnectorPage 嵌入 Chat shell connector tab

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/issue/ISSUES_notion-session-chat-connector-interaction.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `frontend/src/components/dashboard/ResourceConnectorPage.tsx`,
>      `frontend/src/components/chat/ChatView.tsx`,
>      `frontend/src/App.tsx`,
>      `frontend/src/api/resourceConnectorApi.ts`,
>      `frontend/src/constants/storageKeys.ts`
> [Output] 可执行的 connector 嵌入 task 文档，定义复用与嵌入边界
> [Pos] `task_196b_frontend_connector-embedded-mode` in `docs/task`
> [Sync] 2026-07-07: generated after the issue split completed and the frontend task family resumed.

## 1. 任务标题

`SUO-196B Connector 嵌入适配`

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
| Task Slice | `S0b` |

## 3. 任务目标

- 将现有 `ResourceConnectorPage` 收敛为可嵌入的 connector workbench，而不是独立页面优先的壳。
- 在 Chat shell 的 connector tab 内复用现有 connector client、状态和资源列表逻辑，不重新发明第二套连接器 surface。
- 保持创建、认证、资源选择、来源列表、刷新这些核心流程不丢失，同时把独立页面入口降级为兼容入口或提示入口。
- 确保 connector 的 local fallback 只作为退化路径，不掩盖真实 backend contract drift。

## 4. 实现步骤

1. 明确嵌入模式与独立模式的边界：默认使用嵌入式 workbench，独立入口只保留最小兼容语义。
2. 把 `ResourceConnectorPage.tsx` 里的布局拆出稳定的内核，让 Chat shell 的 connector tab 能直接复用。
3. 保持 `resourceConnectorApi.ts` 的创建、认证、poll、资源选择、刷新接口归一，不让嵌入模式绕开既有 client contract。
4. 将 `storageKeys.ts` 中 connector 相关 fallback key 与 Chat shell 入口隔离，避免不同视图互相污染。
5. 只做嵌入与入口调度相关的局部修复，不把 Notion CLI、写回或多平台接入拉进来。

## 5. 涉及文件路径

| Path | Role |
|---|---|
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | Connector workbench 主体，改造成可嵌入模式。 |
| `frontend/src/components/chat/ChatView.tsx` | Connector tab 容器与嵌入点。 |
| `frontend/src/App.tsx` | 入口视图切换与兼容入口处理。 |
| `frontend/src/api/resourceConnectorApi.ts` | Connector client contract 和 state 归一。 |
| `frontend/src/constants/storageKeys.ts` | Connector fallback key 隔离。 |

## 6. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | Chat shell 的 connector tab 容器、现有 `ResourceConnectorPage`。 |
| 输入 | backend 返回的 connector 状态、auth poll 结果、资源选择与来源刷新结果。 |
| 输出 | 可在 Chat shell 中直接使用的嵌入式 connector workbench。 |
| 输出 | 若保留独立入口，则应明确它是兼容/迁移入口，不是主使用路径。 |

## 7. 依赖项

- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/overview.md`
- `SUO-195-B`
- `SUO-195-C`
- `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
- `frontend/src/api/resourceConnectorApi.ts`

## 8. 测试策略

- 嵌入 smoke：从 Chat connector tab 进入 workbench，确认 create / auth / select / refresh 连续可用。
- 兼容 smoke：如保留独立入口，确认其不会成为主要路径，但仍能安全跳转或提示迁移。
- contract smoke：确认 client 归一没有把真实 connector UUID 和 source 状态丢掉。

## 9. 完成标志

- Connector workbench 能在 Chat shell 中嵌入使用。
- 现有 client contract 和资源选择流程保持可用。
- fallback 不再遮蔽真实 contract drift。

## 10. 风险提示

- 如果把嵌入逻辑和独立路由逻辑混在一起，后续维护会出现双 surface。
- 如果 local fallback 被当作主链路，会掩盖 backend response drift。
- 如果嵌入容器与 shell 高度耦合，后续 tab 切换容易回归。
