# TASK-REQUIREMENT-FORMAT

Status: Filled Template
Updated: 2026-07-07
Scope: Frontend task prompt template for the SUO-196 Chat / Connector task family

> [Input] `docs/issue/ISSUES_notion-session-chat-connector-interaction.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`,
>      `docs/prd/notion-session/resource-connector.md`,
>      `docs/prd/notion-session/resource-connector-ui-design.md`,
>      `docs/stage/stage_notion-resource-connector-interaction.md`,
>      `frontend/src/App.tsx`,
>      `frontend/src/components/chat/ChatView.tsx`,
>      `frontend/src/components/chat/ChatPanel.tsx`,
>      `frontend/src/components/dashboard/ResourceConnectorPage.tsx`,
>      `frontend/src/api/resourceConnectorApi.ts`,
>      `frontend/src/constants/storageKeys.ts`,
>      `frontend/src/components/dashboard/Sidebar.tsx`,
>      `frontend/src/components/dashboard/VerticalNav.tsx`
> [Output] Generate:
>      `docs/task/task_196_frontend_chat-connector-interaction-overview.md`,
>      `docs/task/task_196a_frontend_chat-shell-landing-tabs.md`,
>      `docs/task/task_196b_frontend_connector-embedded-mode.md`,
>      `docs/task/task_196c_frontend_connector-auth-session-state-mapping.md`,
>      `docs/task/task_196d_frontend_chat-connector-agent-browser-e2e.md`
> [Pos] task-requirement-template in `docs/task`

## Issue Snapshot

| Field | Value |
|---|---|
| Issue ID | `SUO-196` |
| Title | `Chat / Connector 交互重构前端任务编写` |
| Type | `frontend` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Pending comments | `0` |
| Parent | `SUO-193` |
| Parent title | `IM资源连接器交互设计` |
| Parent status | `in_progress` |
| Blocks | `SUO-197` |
| Blocked by | `SUO-195` |
| Blocker status | `done` |
| Labels | `none` |
| Runtime note | `checkout claimed by harness; task family resumed after issue split finished` |

## Task Framing

Use the source design docs above to generate a small family of frontend task documents for the Chat / Connector interaction refactor.

Hard constraints:

- Keep the task family focused on the frontend chain: `App.tsx` entry -> `ChatView` landing tabs / `QuickActionStrip` -> `ResourceConnectorPage` embedded connector workbench -> `resourceConnectorApi` -> selection/source refresh -> browser E2E evidence.
- Do not expand scope into backend route changes, Notion CLI internals, write-back, Deck/file-upload, or broader navigation redesign.
- Treat `SUO-195-C` as a cross-functional dependency, not as backend task planning owned here. Frontend docs may describe the UI/state contract that consumes the backend behavior, but should not define backend implementation details.
- Reuse the existing frontend app shell and connector client; if response-shape mismatch or local fallback behavior hides contract drift, call it out as a compatibility risk instead of widening scope.
- The generated docs must tell downstream implementation exactly what to verify, what minimal fixes are allowed, and what evidence to attach before `SUO-197` can advance.

## Required Output Shape

The generated task family must include:

1. One overview / manifest doc for the whole Chat / Connector bundle
2. A landing-tabs task doc for `App.tsx` + `ChatView`
3. An embedded-connector task doc for `ResourceConnectorPage`
4. A frontend auth-session state mapping task doc
5. An agent-browser E2E verification task doc

Each task document must include:

1. 任务标题
2. 关联 Issue
3. 任务目标
4. 实现步骤
5. 涉及文件路径
6. 输入 / 输出说明
7. 依赖项
8. 测试策略
9. 完成标志
10. 风险提示

## Suggested Implementation Surface

- Frontend shell entry and view switching in `frontend/src/App.tsx`
- Chat landing tabs, quick actions, and shell recovery in `frontend/src/components/chat/ChatView.tsx` and nearby chat components
- Connector workbench and responsive layout in `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
- Connector CRUD / auth polling / resource selection / refresh client in `frontend/src/api/resourceConnectorApi.ts`
- Local fallback storage isolation in `frontend/src/constants/storageKeys.ts`
- Existing dashboard chrome surfaces if they affect connector reachability in `frontend/src/components/dashboard/Sidebar.tsx` and `frontend/src/components/dashboard/VerticalNav.tsx`
- A minimal browser-e2e harness under `frontend/tests/**` if the repo introduces one during this task family

## Generation Notes

- Reuse the current connector page and client contract; do not invent a second connector surface.
- Keep the file naming convention `task_<序号>_frontend_<slug>.md`.
- Keep the documents concise enough for execution, but explicit enough that downstream implementation does not need to infer the E2E boundary.
- If a response-shape mismatch exists, call it out as a compatibility risk instead of silently widening scope.
- Make the parent/child relationship explicit in the overview doc so the downstream implementation understands how the frontend task family feeds `SUO-197` and how the auth-session contract depends on `SUO-195-C`.
