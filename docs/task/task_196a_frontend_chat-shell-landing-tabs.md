# SUO-196A 前端任务文档：Chat shell 着陆页重构

Status: Draft  
Updated: 2026-07-07  
Scope: 前端任务规划 - Chat 入口页 landing tabs、QuickActionStrip、shell_error 降级

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/issue/ISSUES_notion-session-chat-connector-interaction.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `frontend/src/App.tsx`,
>      `frontend/src/components/chat/ChatView.tsx`,
>      `frontend/src/components/chat/ChatPanel.tsx`,
>      `frontend/src/components/dashboard/Sidebar.tsx`,
>      `frontend/src/components/dashboard/VerticalNav.tsx`
> [Output] 可执行的 Chat landing task 文档，定义入口、tab 切换与 shell 降级边界
> [Pos] `task_196a_frontend_chat-shell-landing-tabs` in `docs/task`
> [Sync] 2026-07-07: generated from the SUO-196 family after the issue split blocker cleared.

## 1. 任务标题

`SUO-196A Chat shell 着陆页重构`

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
| Task Slice | `S0a` |

## 3. 任务目标

- 将 Chat 入口页改造成稳定的 landing shell：中间对话输入框、下方 landing tabs、下方快捷功能 strip、可恢复的 shell error 区。
- 让 `history` / `connector` 视图切换成为入口页的唯一状态源，不再依赖隐式页面跳转。
- 将 `QuickActionStrip` 作为二级动作带固定在输入框下方，明确它只承载入口动作，不承载 connector 生命周期。
- 定义 `shell_error` 的可恢复行为：渲染失败时显示恢复入口，保留 tabs 和 connector 入口，不允许整页白屏。

## 4. 实现步骤

1. 以 `App.tsx` 的当前入口状态为起点，定义 landing shell 的最小状态机，只保留 `history` / `connector` 两个主视图。
2. 在 `ChatView.tsx` 中明确输入框、landing tabs 和 `QuickActionStrip` 的垂直关系，避免 tabs 与 action strip 互相挤压。
3. 把 `shell_error` 设计成可恢复错误态：保留入口区域、保留 tab 切换、提供 `Reload shell` / `Retry` 类动作。
4. 只做布局和状态边界的局部修复，不把 connector 生命周期、历史搜索或后端会话逻辑塞入 landing shell。
5. 明确桌面和移动端下的折叠规则，确保短屏时 tabs 和恢复入口仍然可达。

## 5. 涉及文件路径

| Path | Role |
|---|---|
| `frontend/src/App.tsx` | Chat 入口视图状态和 landing shell 切换。 |
| `frontend/src/components/chat/ChatView.tsx` | Landing tabs、QuickActionStrip、shell_error 的主布局。 |
| `frontend/src/components/chat/ChatPanel.tsx` | 若现有面板抽象影响入口布局，只做最小联动。 |
| `frontend/src/components/chat/QuickActionStrip.tsx` | 若已存在则复用，否则作为最小新增组件。 |
| `frontend/src/components/chat/ChatShellError.tsx` | shell-level 可恢复错误条。 |
| `frontend/src/components/dashboard/Sidebar.tsx` | 如入口需要从 dashboard chrome 到达，保持最小同步。 |
| `frontend/src/components/dashboard/VerticalNav.tsx` | 如移动端入口需要同步，保持最小同步。 |

## 6. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | Chat shell 现有布局、设计稿 landing tabs / quick actions / shell fallback 约束。 |
| 输入 | `history` / `connector` 视图状态、shell error 触发条件、恢复动作定义。 |
| 输出 | 一个可稳定渲染的 Chat landing shell，能在错误恢复后回到上次视图。 |
| 输出 | 明确的布局与状态边界，避免将 connector 生命周期塞进入口壳层。 |

## 7. 依赖项

- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/overview.md`
- `SUO-195-A`
- `SUO-195-D`
- `frontend/src/App.tsx`
- `frontend/src/components/chat/ChatView.tsx`

## 8. 测试策略

- 桌面 smoke：加载 Chat landing shell，切换 `history` / `connector`，验证 quick actions 可见。
- 错误恢复 smoke：模拟 `ChatViewContent` 或 landing tabs 初始化失败，确认 shell_error 仍能显示恢复入口。
- 移动端 smoke：短屏下确认 tabs、输入框和恢复动作仍可达。

## 9. 完成标志

- Chat 入口页能稳定显示 landing tabs + QuickActionStrip + 可恢复错误态。
- `history` / `connector` 切换不会造成白屏或把入口壳层吞掉。
- 入口布局在桌面和移动端都满足最小可达性。

## 10. 风险提示

- 如果把 shell_error 做成整页替换，会破坏入口可恢复性。
- 如果 tabs 与 quick actions 共用太多状态，后续 connector tab 会被错误耦合。
- 如果移动端没有单独验证，短屏折叠很容易让恢复动作不可达。
