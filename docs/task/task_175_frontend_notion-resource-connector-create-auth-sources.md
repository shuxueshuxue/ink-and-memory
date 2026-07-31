# SUO-175 前端任务文档：Notion 资源连接器创建、认证与来源视图

Status: Draft  
Updated: 2026-07-04  
Scope: 前端任务规划 - Notion 资源连接器的创建、认证、资源选择和来源状态展示

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/prd/notion-session/resource-connector.md`,
>      `docs/prd/notion-session/resource-connector-ui-design.md`,
>      `frontend/src/api/resourceConnectorApi.ts`,
>      `frontend/src/App.tsx`,
>      `frontend/src/components/dashboard/Sidebar.tsx`,
>      `frontend/src/components/dashboard/VerticalNav.tsx`,
>      `frontend/src/lib/apiBase.ts`,
>      `frontend/src/constants/storageKeys.ts`
> [Output] 可执行的前端任务文档，供后续实现阶段直接拆分与排期
> [Pos] `task_175_frontend_notion-resource-connector-create-auth-sources` in `docs/task`
> [Sync] 2026-07-04: regenerated from the filled SUO-175 requirement template and aligned to the current dashboard shell and connector client surfaces.

## 1. 任务标题

`SUO-175 Notion 资源连接器前端：创建、认证与来源视图`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-175` |
| Title | `实现 Notion 资源连接器前端：创建、认证与来源视图` |
| Type | `frontend` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Pending comments | `0` |

## 3. 任务目标

- 在现有 dashboard 壳中提供一个可进入的 Notion 资源连接器入口，不依赖手动拼接 URL。
- 完成 connector 创建、Notion 认证、认证轮询、数据库 / 页面资源选择、来源视图列表与同步状态展示。
- 把来源视图的空态、加载态、认证过期态、认证中态、同步中态、已同步态和错误态做成可验证的界面状态。
- 通过单一前端 client 统一接入 `/api/connectors` 系列端点，并保留本地 fallback，避免 UI 被后端联调进度卡住。
- 与 PRD / UI 设计保持一致，但只覆盖本 Issue 需要的前端主链路，不提前把聊天、Deck 或写回纳入范围。

## 4. 任务范围

### In Scope

- 在 `App.tsx` 和现有 dashboard 导航中增加资源连接器入口或视图切换。
- 使用 `frontend/src/api/resourceConnectorApi.ts` 完成创建、认证、轮询、资源列表、资源选择和刷新 wiring。
- 在 `frontend/src/components/dashboard/` 下实现 connector page / panel、创建弹窗、认证面板、资源选择器、来源列表、来源卡片和空状态。
- 通过 `frontend/src/constants/storageKeys.ts` 维护本地 fallback 所需的持久化 key。
- 为桌面和移动端补齐响应式布局、状态文案和 warm paper 视觉语言。

### Out of Scope

- Notion CLI、token 管理和后端 connector 实现。
- Notion 写回、proposal/write pipeline 或 snapshot 物化逻辑。
- Deck、文件上传、多平台接入或聊天历史回放。
- 把 connector 状态塞进现有 workspace/chat 会话语义，除非后续 Issue 单独要求共享。

## 5. 实现步骤

1. 在 `App.tsx` 的视图状态和 dashboard 导航中增加 connector 入口，明确资源连接器页面/面板的挂载点。
2. 完成 `frontend/src/api/resourceConnectorApi.ts` 的响应归一、本地 fallback 和错误兜底，确保 create/auth/poll/databases/pages/select/sync 的调用面稳定。
3. 补齐 `frontend/src/constants/storageKeys.ts` 中的 connector 持久化 key，避免 fallback 与现有本地存储键冲突。
4. 在 `frontend/src/components/dashboard/` 下组合 connector shell 与子组件，按 PRD 拆出创建、认证、资源选择、来源列表、来源卡片和空状态。
5. 将状态映射到 PRD 要求的视觉和交互语义，重点覆盖 loading、empty、expired、authenticating、synced、syncing 和 error。
6. 如仓库存在前端测试目录，则补充最小组件 / API mock 覆盖；若不存在，只保留可执行的测试建议，不额外扩目录。

## 6. 涉及文件路径

| Path | Role |
|---|---|
| `frontend/src/App.tsx` | 增加资源连接器视图状态和壳层入口。 |
| `frontend/src/api/resourceConnectorApi.ts` | 统一 connector 创建、认证、资源发现、选择和刷新 client。 |
| `frontend/src/constants/storageKeys.ts` | 增加 connector 本地 fallback 相关的 storage key。 |
| `frontend/src/components/dashboard/Sidebar.tsx` | 在桌面 dashboard 导航中暴露 connector 入口。 |
| `frontend/src/components/dashboard/VerticalNav.tsx` | 在移动端 / 折叠导航中暴露 connector 入口。 |
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | 连接器主壳层，承载 header、tabs 和来源视图。 |
| `frontend/src/components/dashboard/ResourceConnectorHeader.tsx` | 连接器标题、名称编辑和主要动作。 |
| `frontend/src/components/dashboard/ResourceConnectorCreateModal.tsx` | 创建 connector 的命名与提交界面。 |
| `frontend/src/components/dashboard/ResourceConnectorAuthSheet.tsx` | Notion 认证引导、验证码 / 链接和轮询状态。 |
| `frontend/src/components/dashboard/ResourceConnectorResourcePicker.tsx` | 数据库 / 页面选择界面。 |
| `frontend/src/components/dashboard/ResourceConnectorSourceList.tsx` | 来源列表和分组状态展示。 |
| `frontend/src/components/dashboard/ResourceConnectorSourceCard.tsx` | 单条来源卡片与状态 badge。 |
| `frontend/src/components/dashboard/ResourceConnectorEmptyState.tsx` | 无来源时的 PRD 风格空态。 |
| `frontend/src/components/dashboard/ResourceConnectorState.ts` | connector 视图状态、状态机和映射辅助。 |
| `frontend/tests/**` | 可选的组件 / API mock 覆盖，如果该目录存在。 |

## 7. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | 用户输入 connector 名称、点击连接 Notion、在浏览器确认认证、选择可访问数据库 / 页面、触发刷新同步。 |
| 输入 | 后端返回的 connector id、verification URL / code、poll 状态、database 列表、page 列表、source 列表和 sync 状态。 |
| 输出 | 新建 connector 记录、认证态切换、来源视图中的资源卡片、同步状态 badge、错误提示与空态文案。 |
| 输出 | 可被后续 dashboard 子视图复用的当前 connector 选择状态，以及可回退到本地存储的 fallback 结果。 |

## 8. 依赖项

| Dependency | Why it is needed |
|---|---|
| `docs/design/notion-session/overview.md` | 提供 canonical snapshot、`.notion/` 读取边界与认证 / 同步模型。 |
| `docs/design/notion-session/connector-interaction.md` | 给出创建、认证、选择资源、同步与来源视图流程。 |
| `docs/prd/notion-session/resource-connector.md` | 定义产品定位、页面结构与功能范围。 |
| `docs/prd/notion-session/resource-connector-ui-design.md` | 定义视觉语言、组件结构与微交互。 |
| `docs/task/TASK-REQUIREMENT-FORMAT.md` | 当前 issue 的填充模板，需要与最终任务文档一致。 |
| `frontend/src/api/resourceConnectorApi.ts` | 前端 connector client 的唯一归一层。 |
| `frontend/src/lib/apiBase.ts` | 统一 API 基址，避免 connector client 直写环境路径。 |
| Existing dashboard shell | 需要和现有 `App.tsx`、`Sidebar.tsx`、`VerticalNav.tsx` 与主题系统保持一致。 |

## 9. 测试策略

- 组件测试：覆盖创建表单、认证面板、资源选择器、来源卡片状态与空态。
- API mock 测试：模拟 create -> auth/login -> auth/poll -> databases/pages -> resources/select -> sync 的完整流转。
- 响应式检查：验证桌面和移动端下页面壳、弹窗和来源卡片不溢出、不遮挡。
- 回归检查：确保现有写作、聊天、设置与 Deck 等视图不被 connector 入口破坏。
- 视觉核对：对照 `resource-connector-ui-design.md` 的暖纸张风格、轻阴影、虚线空态和卡片状态。

## 10. 完成标志

- 能从现有前端壳进入资源连接器页面或面板。
- 能创建 connector 并触发 Notion 认证。
- 能列出可访问的数据库 / 页面并选择来源。
- 能在来源视图看到已连接来源及其同步状态。
- 能区分空态、加载态、认证过期态、认证中态、同步中态、已同步态和错误态。
- 任务范围内不包含 Notion 写回、Deck、文件上传或聊天实现。

## 11. 风险提示

- 后端 connector API 可能仍在演进，前端应将接口契约收敛成单一 client 层，避免分散直连。
- 资源连接器状态如果直接塞进现有 `WorkspaceContext`，容易和 session 语义耦合，建议只在需要共享时引入最小扩展。
- 视觉稿里的完整页面包含聊天区，但本 Issue 的标题只覆盖创建、认证与来源视图，避免把聊天功能提前纳入。
- 资源列表后续可能需要分页或增量刷新，本次只做可用的基础列表展示。

## 12. 验收说明

- 任务文档的范围必须能从 Issue 标题和 PRD 直接回溯，不引入超出当前 Issue 的功能点。
- 文件路径必须与当前仓库结构兼容，新的资源连接器组件可放在 `frontend/src/components/dashboard/` 等允许目录下。
- 若后续需要补充聊天、Deck 或多来源类型，再以新的 Issue 拆分，不在本任务内扩张。
