# Notion 资源连接器 E2E 验收与缺口拆解 Issue 清单

## 0. 文档元信息

- Issue 清单文件：`docs/issue/ISSUES_notion-session-e2e.md`
- 来源设计稿：
  - 主设计稿：`docs/design/notion-session/overview.md`
  - 重点补充设计稿：`docs/design/notion-session/connector-interaction.md`
  - 关联设计稿：`docs/design/notion-session/resource-connector-er.md`
  - 关联设计稿：`docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
  - 关联设计稿：`docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
  - 关联设计稿：`docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
  - 关联设计稿：`docs/design/claude-agent/edit-point/workspace-context.md`
  - 关联设计稿：`docs/design/claude-agent/edit-point/workspace-switch.md`
  - 阶段计划：`docs/stage/stage_notion-resource-connector.md`
  - 前端 PRD：`docs/prd/notion-session/resource-connector.md`
  - 前端 PRD：`docs/prd/notion-session/resource-connector-ui-design.md`
- 参考 Issue 基线：
  - `docs/issue/ISSUES_notion-session.md`
- 生成 Agent：`IssueDispatcher`
- 所属流水线阶段：`issue`
- 上游阶段：`design`
- 下游阶段：`task`
- 下游 Agent：
  - `FrontendTaskAgent`
  - `BackendTaskAgent`
- 共享设计稿来源：`docs/design/`
- 是否作为当前实现合同：`是`
- 备注：
  - 本文档是针对 `SUO-185` 的增量拆解，专注 S5 验收与缺口收口，不替代主实现链路清单。
  - 现有实现主链路仍以 `docs/issue/ISSUES_notion-session.md` 为准；本文件只补齐 E2E 验收证据、责任边界与 blocker。
  - 新生成的子 issue 为 `SUO-186`、`SUO-187`、`SUO-188`。

## 1. 关联设计稿信息

- 主设计稿：`docs/design/notion-session/overview.md`
- 重点补充设计稿：`docs/design/notion-session/connector-interaction.md`
- 关联设计稿：`docs/design/notion-session/resource-connector-er.md`
- 关联设计稿：`docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
- 关联设计稿：`docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
- 关联设计稿：`docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
- 关联设计稿：`docs/design/claude-agent/edit-point/workspace-context.md`
- 关联设计稿：`docs/design/claude-agent/edit-point/workspace-switch.md`
- 阶段计划：`docs/stage/stage_notion-resource-connector.md`
- 前端 PRD：`docs/prd/notion-session/resource-connector.md`
- 前端 PRD：`docs/prd/notion-session/resource-connector-ui-design.md`
- 参考 Issue 基线：`docs/issue/ISSUES_notion-session.md`
- 关联实现路径：
  - `backend/notion/`
  - `backend/routers/notion.py`
  - `backend/claude_agent/service.py`
  - `backend/claude_agent/workspace_context.py`
  - `backend/libs/claude_agent_kit/server/notion_snapshot.py`
  - `frontend/src/App.tsx`
  - `frontend/src/api/resourceConnectorApi.ts`
  - `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
  - `frontend/src/components/chat/`
  - `backend/tests/`

- 本清单覆盖范围：
  - Notion 资源连接器的 E2E 验收证据收口
  - 前端 connector 页面级回归与可达性验证
  - 后端 auth / discovery / snapshot / store 的证据整理
  - workspace attach、`.notion/` 读取与 chat/context 的贯通验证
  - 真实 Notion 外部环境 blocker 的显式记录

- 明确排除范围：
  - Notion 写回、proposal/write pipeline 与远程确认回写
  - Deck、文件上传、多平台市场与多平台统一抽象
  - 重新设计 connector 的页面架构或新增路由体系
  - 将 mock-only 单测误标成真实线上 E2E

- 关键约束：
  - shared Issue 必须有唯一主责 Agent，不能把 owner 悬空给 `FrontendTaskAgent + BackendTaskAgent`
  - backend / frontend / shared 的边界必须明确，不能把一个 E2E 问题揉成单个大单
  - `session_updated` / snapshot / `.notion/` 相关链路必须保持同一 identity，不得用本地临时状态替代
  - live Notion smoke 依赖外部环境时，必须显式标记 `[BLOCKED]`

- 补充说明：
  - `SUO-186` 和 `SUO-187` 是并行的证据收口 issue；`SUO-188` 是跨层共享 issue。
  - 本文件不重复实现链路细节，只把“已有证据、缺口 owner、阻塞归属”拆出来，供 `StagePlanner` 和下游 task 文档消费。
  - `docs/issue/ISSUES_notion-session.md` 继续作为实现主链路清单，本文件只补 S5 验收。

## 2. Issue 总览表

| Issue ID | 标题 | 类型 | 优先级 | 标签 | 前置依赖 | 分发去向 |
|---|---|---|---|---|---|---|
| `SUO-186` | 验证 Notion 资源连接器后端链路 E2E 证据 | backend | P1 | `backend,notion,connector,e2e,contract,snapshot,verification` | `SUO-174`, `SUO-177` | `@BackendTaskAgent` |
| `SUO-187` | 验证 Notion 资源连接器前端链路 E2E 回归 | frontend | P1 | `frontend,notion,connector,e2e,regression,ui,verification` | `SUO-178` | `@FrontendTaskAgent` |
| `SUO-188` | 贯通 Notion 快照 attach、`.notion/` 读取与聊天上下文 E2E | shared | P1 | `shared,notion,snapshot,workspace,chat,e2e,verification` | `SUO-186`, `SUO-187`, `SUO-177`, `SUO-178` | `@BackendTaskAgent` + `@FrontendTaskAgent` |

## 3. Issue 明细

### `SUO-186`

- 标题：验证 Notion 资源连接器后端链路 E2E 证据
- 类型：backend
- 优先级：P1
- 标签：`backend,notion,connector,e2e,contract,snapshot,verification`
- 描述：
  收敛 Notion 资源连接器后端链路的真实验收证据，覆盖创建、认证、资源发现、资源选择、同步、snapshot 落地与 `.notion/` 合同。当前仓库里已经有 `test_notion_auth`、`test_notion_store`、`test_notion_snapshot_contract`、`test_notion_connector_router_flow` 这些后端证据，但本 Issue 需要把它们整理成一条可以被 task/stage 复用的 E2E 链路，并明确哪些部分仍然依赖 Mock 或外部环境。

- 验收条件：
  - 后端 auth / discovery / select / sync / snapshot 相关证据能被整理成一条可追溯链路。
  - `/api/connectors*` 路由、`notion_snapshot` 合同、`store` 持久化和 `workspace` materialization 的责任边界清晰。
  - 如果缺少真实 Notion CLI / 网络环境，则在阻塞记录里明确写出 Mock-only 现状与补测 owner，而不是把局部单测误判为线上 E2E。

- 前置依赖：`SUO-174`, `SUO-177`

- 关联路径：
  - `backend/tests/test_notion_auth.py`
  - `backend/tests/test_notion_store.py`
  - `backend/tests/test_notion_snapshot_contract.py`
  - `backend/tests/test_notion_connector_router_flow.py`
  - `backend/tests/test_server_claude_agent.py`
  - `backend/routers/notion.py`
  - `backend/notion/`
  - `backend/libs/claude_agent_kit/server/notion_snapshot.py`
  - `docs/stage/stage_notion-resource-connector.md`

- 分发去向：`@BackendTaskAgent`

- 主责 Agent：
  - `BackendTaskAgent`

- 协作 Agent：
  - 无

- 设计决策引用：
  - `docs/design/notion-session/overview.md §4-5`
  - `docs/design/notion-session/connector-interaction.md §3-5`
  - `docs/design/claude-agent/notion-point/resource-connector-layer-design.md §3-4`
  - `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md §2-3`
  - `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md §2-5`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - `[BLOCKED]` 仅当真实 Notion smoke 需要外部环境时再记录
  - `ntn` CLI 已在当前环境验证可用，当前阻塞只剩 `NOTION_HOME` / 外部 workspace / live smoke 环境
  - 该 Issue 不新增后端能力，只整理并证明现有链路的 E2E 证据

### `SUO-187`

- 标题：验证 Notion 资源连接器前端链路 E2E 回归
- 类型：frontend
- 优先级：P1
- 标签：`frontend,notion,connector,e2e,regression,ui,verification`
- 描述：
  收敛 Notion 资源连接器前端页的创建、认证、资源选择、来源状态和响应式交互回归。当前 `ResourceConnectorPage` 与 `resourceConnectorApi` 已有实现，但缺少一条把页面入口、认证轮询、资源选择与来源卡片串起来的明确验收链，也缺少一个可重复的页面级回归记录。

- 验收条件：
  - 从 `App.tsx` 的 connector 视图入口可以进入同一资源连接器工作台。
  - 创建 connector、启动 Notion 认证、轮询成功、加载资源列表、保存选择和刷新来源的前端状态可逐步复现。
  - 桌面与移动端的 connector 页面布局不会让资源选择和来源卡片溢出或不可达。

- 前置依赖：`SUO-178`

- 关联路径：
  - `frontend/src/App.tsx`
  - `frontend/src/api/resourceConnectorApi.ts`
  - `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
  - `frontend/src/components/dashboard/Sidebar.tsx`
  - `frontend/src/components/dashboard/VerticalNav.tsx`
  - `frontend/src/constants/storageKeys.ts`
  - `frontend/tests/`
  - `docs/prd/notion-session/resource-connector.md`
  - `docs/prd/notion-session/resource-connector-ui-design.md`

- 分发去向：`@FrontendTaskAgent`

- 主责 Agent：
  - `FrontendTaskAgent`

- 协作 Agent：
  - `BackendTaskAgent`

- 设计决策引用：
  - `docs/prd/notion-session/resource-connector.md §2-5`
  - `docs/prd/notion-session/resource-connector-ui-design.md`
  - `docs/design/notion-session/overview.md §11`
  - `docs/design/notion-session/connector-interaction.md §4-6`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - `[BLOCKED]` 无
  - 如果 `frontend/tests/` 仍未建立，则本 Issue 至少要沉淀一份可复用 smoke 记录，而不是把 UI 状态只停留在手工印象

### `SUO-188`

- 标题：贯通 Notion 快照 attach、`.notion/` 读取与聊天上下文 E2E
- 类型：shared
- 优先级：P1
- 标签：`shared,notion,snapshot,workspace,chat,e2e,verification`
- 描述：
  把 Notion 资源连接器的 canonical snapshot 变成 Agent 初始化与聊天上下文的权威输入：workspace attach 必须读取同一 snapshot identity，`.notion/*` 读取必须从 attach 的 snapshot 解析，连接器下的 chat 线程关系也必须可被稳定查询和展示。该 Issue 是跨层 shared gap，负责把“选中哪个 connector”真正变成“本轮 Agent 看到哪个 snapshot”。

- 验收条件：
  - workspace attach 会从连接器数据层读取 current canonical snapshot，并把 snapshot identity 注入到 `workspace_context`。
  - `Read(".notion/snapshot.json")`、`Read(".notion/index.json")`、`Read(".notion/pages/<id>.json")` 都只解析已 attach 的 snapshot，不直接远程拉取。
  - 前端聊天表面能够显示当前 connector / snapshot 版本，并在切换 connector 后于下一轮 Agent init 生效。
  - 相关验证可以证明同一 `snapshotVersion` 在 backend attach、`.notion/` 读取和 chat 上下文中保持一致。

- 前置依赖：`SUO-186`, `SUO-187`, `SUO-177`, `SUO-178`

- 关联路径：
  - `backend/claude_agent/service.py`
  - `backend/claude_agent/workspace_context.py`
  - `backend/routers/claude_agent.py`
  - `backend/routers/notion.py`
  - `backend/notion/store.py`
  - `backend/notion/sync.py`
  - `backend/libs/claude_agent_kit/server/notion_snapshot.py`
  - `frontend/src/components/chat/`
  - `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
  - `frontend/src/lib/claude-agent-transport.ts`
  - `backend/tests/test_claude_agent_service.py`
  - `backend/tests/test_claude_agent_context_builder.py`

- 分发去向：`@BackendTaskAgent` + `@FrontendTaskAgent`

- 主责 Agent：
  - `BackendTaskAgent`

- 协作 Agent：
  - `FrontendTaskAgent`

- 设计决策引用：
  - `docs/design/notion-session/overview.md §5-7`
  - `docs/design/notion-session/connector-interaction.md §6-8`
  - `docs/design/claude-agent/notion-point/resource-connector-layer-design.md §3-6`
  - `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md §2-5`
  - `docs/design/claude-agent/edit-point/workspace-context.md §11`
  - `docs/design/claude-agent/edit-point/workspace-switch.md §6-9`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - `[BLOCKED]` 无
  - 这是 shared Issue，必须保证唯一主责是 `BackendTaskAgent`，不能写成无 owner 的联合口径

## 4. 共享任务与依赖说明

- `SUO-186` 与 `SUO-187` 是并行证据收口 issue，可以先独立完成。
- `SUO-188` 依赖 `SUO-186` 和 `SUO-187`，因为它要证明同一 snapshot identity 在 backend attach、`.notion/` 读取和 chat/context 中保持一致。
- `SUO-186` 的证据以 backend contract 和 store/snapshot 测试为主，不负责前端 smoke。
- `SUO-187` 的证据以 connector page / API client / responsive 回归为主，不负责 backend snapshot materialization。
- 若后续发现 chat history、Deck、file upload 或 write-back 需要独立的设计边界，必须拆出新 Issue，不允许在本批里静默扩张。
- 真实 Notion smoke 只能作为 blocker 解除后的补证路径，不能替代本地 contract / mock evidence。

## 5. 分发去向说明

- `BackendTaskAgent`：
  - 领取 `SUO-186`。
  - 负责 `SUO-188` 中 backend 侧的 snapshot attach、workspace_context、connector thread 数据层与相关验证。

- `FrontendTaskAgent`：
  - 领取 `SUO-187`。
  - 负责 `SUO-188` 中前端侧的 current connector 展示、snapshot 状态展示与 chat surface 联动。

- `Shared Issue` 处理规则：
  - shared 类型 Issue 必须明确主责 Agent。
  - 另一个 Agent 作为协作方。
  - 不允许 shared Issue 无主责。
  - 若主责不清，必须标记 `[CLARIFICATION_NEEDED]`。

## 6. 推荐推进顺序

1. 先并行完成 `SUO-186` 与 `SUO-187`，分别收口后端和前端的 E2E 证据。
2. 再推进 `SUO-188`，把 snapshot attach、`.notion/` 读取与 chat/context 贯通到同一条链路。
3. 最后再补真实 Notion 外部环境 smoke，如果环境未就绪则保持 `[BLOCKED]` 记录。

推荐理由：

- 后端与前端的证据收口互不阻塞，可以先并行推进。
- shared chain 需要两侧证据稳定后再做，否则会反复回退。
- 外部环境 smoke 是补证，不应反向拖住本地 contract 与回归证据。

## 7. 阻塞与澄清记录

### [BLOCKED] 真实 Notion CLI / 浏览器确认 / scope smoke

- 阻塞原因：
  - 真实 Notion smoke 依赖外部 workspace、`NOTION_HOME` 可读写、sandbox allowlist 和 `api.notion.com` 网络可达。
  - `ntn` CLI 已在当前环境验证可用（`/Users/dmeck/.local/bin/ntn`），因此当前 blocker 不是 CLI 缺失，而是 live smoke 所需的外部环境未就绪。
  - 当前仓库里的证据主要是 mock / contract / route-level 回归，不能直接等价为 live Notion E2E。
- 影响范围：
  - 无法把 `SUO-186` / `SUO-187` 的本地证据自动升级为线上真实 smoke。
  - 无法在没有外部环境的情况下确认 Notion 认证页、scope 权限和 browser-confirm 的最终闭环。
- 当前责任 Agent：
  - `BackendTaskAgent`（`SUO-186`）
  - `FrontendTaskAgent`（`SUO-187`）
- 需要唤醒的 Agent：
  - `BackendTaskAgent`
  - `FrontendTaskAgent`
- 建议处理方式：
  - 提供可用的 Notion workspace / 凭证环境。
  - 确保 sandbox allowlist 包含 `api.notion.com` 和 `NOTION_HOME` 读写路径，并设置有效的 `NOTION_HOME`。
  - 通过真实浏览器确认链路补录一条 live smoke 证据，再回写到 `SUO-186` / `SUO-187` / `SUO-188`。
- 是否需要回退到 design：
  - 否。设计稿已经足够，当前阻塞来自外部环境，不是设计缺口。

### [CLARIFICATION_NEEDED] 无

- 歧义点：
  - 当前没有需要回退设计稿的结构性歧义。
- 需要确认方：
  - 无
- 是否阻塞 task 阶段：
  - 否，task 阶段可以先基于本地证据推进。

## 8. Issue-First 协作说明

* Issue 是最小调度单元。
* 同一 Issue 任一时刻只允许一个主责 Agent。
* shared Issue 必须有主责 Agent 与协作 Agent。
* 必须通过 Issue 评论区补充上下文、阻塞、回退和评审意见。
* 必须通过 `@mention` 唤醒目标 Agent。
* 不假设 Agent 之间存在隐式共享内存。
* 不允许绕过 Issue 直接下发 task。
