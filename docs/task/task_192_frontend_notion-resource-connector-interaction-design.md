# SUO-192 前端任务文档：IM 资源连接器交互设计

Status: Draft  
Updated: 2026-07-06  
Scope: 设计任务 — 前端视图、状态机、错误回退与认证会话语义

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/prd/notion-session/resource-connector.md`,
>      `frontend/src/components/dashboard/ResourceConnectorPage.tsx`,
>      `frontend/src/api/resourceConnectorApi.ts`
> [Output] 输出 IM 资源连接器可执行交互规范（状态机、文案、异常回退、边界条件）
> [Pos] `task_192_frontend_notion-resource-connector-interaction-design` in `docs/task`
> [Sync] 2026-07-06: 新增 SUO-192 交互设计补充，专门收敛 poll 消费态、stale/missing 资源态、以及快照状态回写行为，避免实现端反复对齐。

## 1. 任务标题

`SUO-192 IM 资源连接器交互设计`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-192` |
| Title | `IM 资源连接器交互设计` |
| Type | `design` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Parent | `IM 资源链接器业务代码实现` |
| Pending comments | `0` |

## 3. 任务目标

- 为资源连接器前端交互定义可执行、可验收的状态机，覆盖：
  - `draft` / `authenticating` / `authenticated` / `syncing` / `synced` / `stale` / `error` / `connector_unavailable`
  - `pending` / `syncing` / `synced` / `stale` / `missing` / `error` 的来源状态。
- 明确 poll 会话的边界行为：`consumed`、`expired`、`failed` 分别收敛到可立即行动的 UI。
- 明确快照不一致与缺页场景的用户提示与恢复动作。
- 固化“连接器交互→快照阅读→来源卡片更新”的文案与交互契约，避免与 `.notion/` 读取约束冲突。

## 4. 交互范围（In Scope）

- 资源连接器主页面的状态展示：空态、连接态、认证中、同步中、已同步、失效、缺页。
- 认证流程边界提示：验证码、打开浏览器、轮询超时/消费态/失败态。
- 资源卡片边界：同步中/成功/过期/缺页的独立文案与 CTA。
- 切换来源 / 刷新快照 / 重新认证的行为优先级与禁止操作。
- 对照 `docs/design/notion-session/connector-interaction.md` 与 `docs/prd/notion-session/resource-connector.md` 的字段统一。

## 5. 交互状态机（交付版本）

### 5.1 连接器状态

| 状态 | 触发事件 | 用户可见表达 | 下一可操作 |
|---|---|---|---|
| `draft` | 新建连接器成功（未调用 auth） | 徽标：未连接；CTA：连接 Notion | 发起认证 |
| `authenticating` | 发起 `auth/login` 或存在未完成会话 | 显示验证码 + “打开浏览器” + 轮询指示 | 继续轮询 / 复制链接 / 取消 |
| `authenticated` | `auth/poll` 返回 authenticated 或 consumed | 显示“已认证” + 资源选择入口 | 选择数据库/页面，触发同步 |
| `syncing` | 发起 sync | 显示 progress（同步中）| 查看实时状态，不允许重复提交相同任务 |
| `synced` | sync 成功落盘 | 显示资源条目 + 页面数 + snapshot 版本 | 发起 chat / 刷新快照 |
| `stale` | 后端提示 snapshot 落后 | 显示“请刷新” | 手动刷新 |
| `expired` | auth 会话过期 | 显示“需重新认证” | 重新发起认证 |
| `error` | 认证/同步错误 | 显示错误原因 | 重试对应动作 |
| `connector_unavailable` | 后端不可达或关键链路熔断 | 显示降级提示 | 重试或切回纯 chat |

### 5.2 来源项状态

| 来源状态 | 呈现 | 约束 |
|---|---|---|
| `pending` | `待同步` 标记，灰化禁用进入详情 | 等待 sync 完成 |
| `syncing` | loading + “同步中” | 避免重复提交 |
| `synced` | `已同步` + 最近同步时间 | 可进入 Chat 与来源详情 |
| `stale` | `snapshot 已过期` | 刷新后可恢复 |
| `missing` | `暂不可用（未 materialized）` | 跳转 refresh action，不回源实时读取 |
| `error` | `同步失败` + retry | 用户触发重试 |

## 6. 关键交互约束（Do / Don’t）

- Do：在 poll 返回 `consumed` 时，若 connector 已有 token，则直接保持 `authenticated`，并不应降级到 `pending`。
- Do：在资源读取路径遇到 `not_materialized_in_snapshot` 时，展示 `重新刷新`，不进行远端即时抓取。
- Do：在没有认证时禁用 chat 入口，避免进入空上下文体验失败。
- Don’t：不要把 Agent 本地摘要或 cache 作为权威状态用于来源是否可用判定。
- Don’t：不要在 `syncing` 时展示“已同步”文案或允许重复创建同一同步任务。

## 7. 交付成果（输出）

- 一版可交付给前端与设计端的状态定义表（本文件 + 关联设计文档补充）。
- Poll 会话边界说明（消费态/失败态）与缺页处理规则。
- 由此更新的 PRD/设计文档同步项（同 commit 共同提交）。

## 8. 完成标志

- 文档里给出的状态机可被前端直接映射到现有 `resourceConnectorApi.ts` 与 `ResourceConnectorPage.tsx` 的状态模型。
- `auth/poll` 的 consumed/failed/expired 回退有明确 CTA。
- 快照 `stale` 与来源 `missing` 均有可操作恢复动作。
- 设计与 PRD/connector-interaction 的状态表一致。
