# SUO-187 前端任务文档：Notion 资源连接器前端链路 E2E 回归验证

Status: Draft  
Updated: 2026-07-05  
Scope: 前端任务规划 - Notion 资源连接器页面入口、创建 / 认证 / 资源选择 / 来源刷新链路的回归验证

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`,
>      `docs/prd/notion-session/resource-connector.md`,
>      `docs/prd/notion-session/resource-connector-ui-design.md`,
>      `docs/stage/stage_notion-resource-connector.md`,
>      `frontend/src/App.tsx`,
>      `frontend/src/api/resourceConnectorApi.ts`,
>      `frontend/src/components/dashboard/ResourceConnectorPage.tsx`,
>      `frontend/src/components/dashboard/Sidebar.tsx`,
>      `frontend/src/components/dashboard/VerticalNav.tsx`,
>      `frontend/src/constants/storageKeys.ts`
> [Output] 可执行的前端任务文档，供后续实现阶段直接拆分与排期
> [Pos] `task_187_frontend_notion-resource-connector-e2e-regression` in `docs/task`
> [Sync] 2026-07-05: generated from the filled SUO-187 requirement template after confirming the live issue payload and parent linkage.

## 1. 任务标题

`SUO-187 Notion 资源连接器前端：E2E 回归验证`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-187` |
| Title | `验证 Notion 资源连接器前端链路 E2E 回归` |
| Type | `frontend` |
| Priority | `medium` |
| Status | `done` |
| Work mode | `standard` |
| Parent | `SUO-185` |
| Parent title | `补齐 Notion 资源连接器完整业务链 E2E 验收与缺口拆解` |
| Parent status | `done` |
| Blocks | `SUO-185` |
| Blocked by | `none` |
| Labels | `none` |
| Pending comments | `0` |

## 3. 任务目标

- 验证当前前端 connector 链路从 `App.tsx` 的入口可以稳定进入同一个资源连接器工作台，不再依赖手动拼接路径或隐式页面状态。
- 复核创建 connector、启动 Notion 认证、轮询认证成功、加载资源列表、保存选择、刷新来源这些前端步骤是否能连续复现，不在链路中断开。
- 确认 `ResourceConnectorPage` 在桌面与移动端下都能把资源选择区、来源卡片区和滚动内容保留在可达范围内，不出现下半区不可交互或被固定壳层裁切的问题。
- 核对 `resourceConnectorApi.ts` 的响应归一和 local fallback 是否仍然保留真实 backend connector UUID 与选择状态，避免回归被本地 synthetic id 掩盖。
- 为 `SUO-185` 补齐可复核的前端 E2E 证据，让父 issue 可以基于明确的链路验收继续推进。

## 4. 任务范围

### In Scope

- `frontend/src/App.tsx` 中的 `connector` 视图入口、视图切换与固定壳层滚动可达性。
- `frontend/src/components/dashboard/ResourceConnectorPage.tsx` 中的创建、认证、资源选择、来源列表、来源卡片、空状态与响应式布局。
- `frontend/src/api/resourceConnectorApi.ts` 中的 create / auth / poll / databases / pages / select / refresh 归一和 backend/local fallback 兼容。
- `frontend/src/constants/storageKeys.ts` 中 connector 持久化 key 的隔离与清理边界。
- 若发现入口或壳层需要最小调整以恢复链路可达性，只做与 E2E 回归直接相关的局部修复。
- 若仓库后续引入最小 browser-e2e 或 smoke harness，则只编码这条 connector 链路，不扩张为完整前端测试平台。

### Out of Scope

- Notion CLI、token 管理、backend connector internals 或任何后端路由改造。
- Notion 写回、proposal/write pipeline、Deck、文件上传、多平台接入或 chat/workspace attach 重构。
- 重新设计 connector 的信息架构、视觉语言或主题系统。
- 为其它 dashboard 功能引入新的路由体系、登录流或大规模状态机改造。

## 5. 实现步骤

1. 从 `App.tsx` 的 connector 入口实际走一遍页面切换，确认进入后显示的是同一个 `ResourceConnectorPage` 工作台，而不是新的分叉壳层。
2. 逐步跑通 create -> auth/login -> auth/poll -> list databases/pages -> select resources -> refresh sources 的前端链路，确认 `resourceConnectorApi.ts` 的返回值没有把后端 connector UUID 或 source 选择状态丢成本地假 id。
3. 检查 `ResourceConnectorPage.tsx` 在常见桌面宽度和窄屏高度下的滚动与可达性，修复会遮挡资源选择或来源卡片的局部 overflow / fixed shell 问题。
4. 复核 `storageKeys.ts` 中 connector 相关的本地持久化 key，确保本次回归验证不会被旧的 fallback state 污染。
5. 收集最小可接受的 E2E 证据：构建结果、桌面 smoke、移动端 smoke，以及能证明资源选择和来源刷新仍然可达的截图或检查单。
6. 如果后续要把这条链路自动化，优先复用现有页面和 client contract，只补最小的 browser smoke 或 regression harness，不单独开一套更重的测试框架。

## 6. 涉及文件路径

| Path | Role |
|---|---|
| `frontend/src/App.tsx` | 资源连接器入口、视图切换和壳层可达性检查面。 |
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | 连接器主工作台，承载创建、认证、资源选择和来源状态。 |
| `frontend/src/components/dashboard/Sidebar.tsx` | 与 connector reachability 相关的 dashboard chrome 检查面。 |
| `frontend/src/components/dashboard/VerticalNav.tsx` | 与 connector reachability 相关的移动 / 折叠导航检查面。 |
| `frontend/src/api/resourceConnectorApi.ts` | connector API client、认证轮询、资源发现、选择与刷新归一。 |
| `frontend/src/constants/storageKeys.ts` | connector 本地 fallback 的 storage key 隔离。 |
| `frontend/tests/**` | 可选的最小 browser-e2e / smoke harness；当前仓库没有现成树，仅在引入时使用。 |

## 7. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | 用户在 `App.tsx` 中点击 connector 入口、输入 connector 名称、触发 Notion auth、确认 browser code、选择可访问资源、刷新来源。 |
| 输入 | backend 返回的 connector id、verification URL / code、poll 状态、database/page 列表、source 列表和 sync 状态。 |
| 输入 | 桌面与移动端 viewport，以及本地 fallback 是否被激活。 |
| 输出 | 一条可重复的前端 E2E 回归链路，能证明 connector 页面入口、认证、选择和来源刷新都仍然可达。 |
| 输出 | 资源卡片和来源列表在窄屏下不被裁切，且必要的滚动区域可以到达。 |
| 输出 | 若仍存在 response-shape mismatch，则在任务文档和 issue 证据中明确标为 compatibility risk，而不是扩大实现范围。 |

## 8. 依赖项

- `docs/design/notion-session/overview.md`
- `docs/design/notion-session/connector-interaction.md`
- `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
- `docs/prd/notion-session/resource-connector.md`
- `docs/prd/notion-session/resource-connector-ui-design.md`
- `docs/stage/stage_notion-resource-connector.md`
- `SUO-185` as the immediate parent evidence gate
- `frontend/src/App.tsx`
- `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
- `frontend/src/api/resourceConnectorApi.ts`
- `frontend/src/constants/storageKeys.ts`

## 9. 测试策略

- 构建检查: `npm run build` 通过，确保 connector 工作台和入口在当前前端编译图里仍然可用。
- 桌面 smoke: 从 `App.tsx` 入口进入 connector 工作台，完成 create -> auth -> poll -> select -> refresh 的完整浏览器路径。
- 移动端 smoke: 在窄宽度和较短高度下复查同一条路径，确保资源选择区和来源卡片可以滚动到达。
- contract smoke: 确认 `resourceConnectorApi.ts` 对 backend response 的归一仍保留真实 connector UUID 和资源选择状态，不被 local fallback 覆盖掉。
- 若增加最小 browser harness，则只覆盖这条 connector E2E 路径，不引入覆盖整个 dashboard 的大规模测试网格。

## 10. 完成标志

- `App.tsx` 的 connector 入口可进入同一资源连接器工作台，且桌面 / 移动端都能到达。
- connector 创建、Notion 认证、认证轮询、资源选择和来源刷新链路能连续复现。
- 来源卡片与资源选择在固定壳层和窄屏下仍然可达，不再出现下半区不可交互的回归。
- `resourceConnectorApi.ts` 的响应归一不再丢失 backend connector UUID，local fallback 仅作为退化路径而不是主链路。
- 任务证据能够支持 `SUO-185` 继续收口，而不是把这条 E2E 链路误判为已完成。

## 11. 风险提示

- `resourceConnectorApi.ts` 现有 local fallback 可能掩盖 backend contract drift，必须先验证真实响应再接受 fallback 结果。
- `ResourceConnectorPage.tsx` 大量使用 inline layout 样式，修复时容易把回归范围扩大成视觉重构，需要严格限制改动面。
- 当前仓库没有现成 `frontend/tests/` 目录，若要自动化证明这条链路，需控制新增测试范围，不要引入一整套新框架。
- Notion auth 或本地 CLI 状态仍可能带来外部环境波动，但这类问题应记录为环境依赖，不应混淆为前端链路设计问题。
- 如果只验证桌面路径而忽略窄屏滚动，`SUO-185` 需要的完整 E2E 证据仍然不足。
