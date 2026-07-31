# SUO-178 前端任务文档：Notion 资源连接器创建、认证与资源选择流程

Status: Draft  
Updated: 2026-07-04  
Scope: 前端任务规划 - Notion 资源连接器创建、认证、资源选择和来源状态展示

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/resource-connector-er.md`,
>      `docs/prd/notion-session/resource-connector.md`,
>      `docs/prd/notion-session/resource-connector-ui-design.md`,
>      `frontend/src/App.tsx`,
>      `frontend/src/components/dashboard/ResourceConnectorPage.tsx`,
>      `frontend/src/components/dashboard/Sidebar.tsx`,
>      `frontend/src/components/dashboard/VerticalNav.tsx`,
>      `frontend/src/api/resourceConnectorApi.ts`,
>      `frontend/src/constants/storageKeys.ts`
> [Output] 可执行的前端任务文档，供后续实现阶段直接拆分与排期
> [Pos] `task_178_frontend_notion-resource-connector-create-auth-resource-selection` in `docs/task`
> [Sync] 2026-07-04: generated from the filled SUO-178 requirement template after the `SUO-176` planning blocker was resolved.

## 1. 任务标题

`SUO-178 Notion 资源连接器前端：创建、认证与资源选择流程`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-178` |
| Title | `实现 Notion 资源连接器前端创建与资源选择流程` |
| Type | `frontend` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Parent | `SUO-172` |
| Blocked by | `SUO-176` |
| Blocker status | `done` |
| Backend contract dependency | `SUO-177` |
| Labels | `none` |
| Pending comments | `0` |

## 3. 任务目标

- 在当前 dashboard 壳中保留 Notion resource connector 入口，并让 connector 视图成为可直接进入的工作台。
- 完成 connector 创建、Notion 认证、认证轮询、资源选择和来源状态展示的前端闭环。
- 让资源列表和来源卡片正确反映 PRD 里的 `pending_auth`、`pending_sync`、`snapshot_ready`、`stale`、`conflict`、`permission_denied` 和 `connector_unavailable` 状态，并兼容远端优先 + local fallback 的 client 行为。
- 保持所有交互在现有 `App.tsx` / `Sidebar.tsx` / `VerticalNav.tsx` / `ResourceConnectorPage.tsx` 内完成，不引入新的 route 体系。
- 对齐 backend contract `SUO-177` 的接口形状，同时把后端暂未就绪时的 localStorage fallback 作为可用降级路径。
- 不扩大到 Notion 写回、Deck、文件上传或聊天历史回放。

## 4. 任务范围

### In Scope

- `App.tsx` 中的 `connector` view entry 和视图切换。
- `Sidebar.tsx` / `VerticalNav.tsx` 中的入口和导航态同步。
- `ResourceConnectorPage.tsx` 中的创建、认证、资源选择、来源列表、状态 badge、空态和错误态。
- `resourceConnectorApi.ts` 中的 create/auth/poll/list/select/sync/get 归一和 fallback。
- `storageKeys.ts` 中的 connector localStorage key。
- 如后续引入新的组件边界，再按当前 dashboard 约定补文件并同步 folder contract。
- 如果后续新增 `frontend/tests/`，补最小的状态机和 API mock 覆盖；当前仓库没有现成 frontend test 树时，不强制新建目录。

### Out of Scope

- Notion CLI / token 管理 / backend connector internals。
- Notion write-back、proposal/write pipeline、snapshot 物化实现。
- Deck、文件上传、多平台接入或 chat history replay。
- 新增独立 route / subapp / settings page 来承载 connector。

## 5. 实现步骤

1. 保持 `connector` 视图在 `App.tsx` 中可直接打开，并让移动端与桌面导航都能到达同一 connector page。
2. 在 `resourceConnectorApi.ts` 中维持远端优先策略，并把 create/auth/poll/databases/pages/resources/select/sync/get 的响应统一归一到同一 connector state model。
3. 将 `ResourceConnectorPage.tsx` 的状态机与 PRD 对齐，确保创建、认证、选择、同步、空态、错误态和过期态都能稳定渲染。
4. 把 connector 的本地 fallback key 和持久化行为收敛到 `storageKeys.ts`，避免与其他 dashboard state 冲突。
5. 检查 responsive 布局与 copy，保证桌面和 mobile 下的 create modal、auth block、resource selector 和 source list 不溢出、不互相遮挡。
6. 在没有现成 `frontend/tests/` 目录的情况下，执行最小手工 smoke；若后续新增 test tree，再补组件 / API mock。

## 6. 涉及文件路径

| Path | Role |
|---|---|
| `frontend/src/App.tsx` | 资源连接器视图入口与 app shell 切换。 |
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | 资源连接器主工作台，承载创建、认证、资源选择和来源状态。 |
| `frontend/src/components/dashboard/Sidebar.tsx` | 桌面 dashboard 导航入口与视图切换。 |
| `frontend/src/components/dashboard/VerticalNav.tsx` | 移动端 / 折叠导航入口。 |
| `frontend/src/api/resourceConnectorApi.ts` | connector API client、认证轮询、资源发现、选择与同步归一。 |
| `frontend/src/constants/storageKeys.ts` | connector 本地 fallback 的 storage key。 |
| `frontend/tests/**` | 可选测试目录；当前仓库没有现成目录，仅在后续创建时使用。 |

## 7. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | 用户输入 connector 名称，点击连接 Notion，浏览器确认认证，选择可访问数据库 / 页面，手动触发刷新同步。 |
| 输入 | 后端返回的 connector id、verification URL / code、poll 状态、database 列表、page 列表、source 列表和 sync 状态。 |
| 输出 | 新建 connector 记录、认证态切换、资源选择结果、来源卡片、同步状态 badge、错误提示与空态文案。 |
| 输出 | localStorage fallback 的 connector state，便于后端联调未完成时继续验证前端交互。 |

## 8. 依赖项

- `docs/design/notion-session/overview.md`
- `docs/design/notion-session/connector-interaction.md`
- `docs/design/notion-session/resource-connector-er.md`
- `docs/prd/notion-session/resource-connector.md`
- `docs/prd/notion-session/resource-connector-ui-design.md`
- `SUO-176`（已 `done`，用于前置规划收敛）
- `SUO-177`（backend contract / data layer，当前联动依赖）
- `frontend/src/api/resourceConnectorApi.ts`
- `frontend/src/constants/storageKeys.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/dashboard/ResourceConnectorPage.tsx`

## 9. 测试策略

- 手工 smoke: create -> auth -> poll -> load databases/pages -> select -> sync -> source cards。
- 回退 smoke: backend 不可达时验证 localStorage fallback 仍可创建、认证和选择资源。
- 响应式 smoke: 检查 desktop/mobile 下 create modal、auth 卡片、resource list 和 source cards 的布局。
- 视觉核对: 对照 PRD 的 warm paper 风格、状态胶囊和空态提示。
- 当前仓库没有现成 `frontend/tests/` 目录，因此只保留最小 smoke 标准；后续如新增测试树，再补 state-machine / API mock 覆盖。

## 10. 完成标志

- 可以从现有 dashboard shell 进入 Notion 资源连接器页面。
- 可以创建 connector 并完成 Notion auth / poll。
- 可以列出并选择可访问的 databases 和 standalone pages。
- 可以在来源视图看到已连接资源、同步状态和最近更新时间。
- connector 相关状态与 PRD 一致，且不会把 write-back / deck / file upload 提前混入本 issue。
- 远端接口不可用时，前端 fallback 仍可完整走通主要交互。

## 11. 风险提示

- backend contract 仍可能调整，因此 `resourceConnectorApi.ts` 必须继续保持归一层，避免组件直接硬编码接口字段。
- 认证轮询需要明确 expired / error 的退路，避免 UI 卡在无限 polling。
- 如果把资源选择和 connector 生命周期塞进现有 workspace/chat 状态，容易产生 session 语义耦合；当前 issue 应保持前端局部状态优先。
- 资源接口返回形状可能同时存在数组和 envelope，client 归一逻辑需要继续兼容。
