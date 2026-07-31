# Notion 资源连接器 Issue 清单

## 0. 文档元信息

- Issue 清单文件：`docs/issue/ISSUES_notion-session.md`
- 来源设计稿：
  - 主设计稿：`docs/design/notion-session/overview.md`
  - 关联设计稿：
    - `docs/design/notion-session/connector-interaction.md`
    - `docs/design/notion-session/resource-connector-er.md`
    - `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
    - `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
    - `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
    - `docs/design/claude-agent/edit-point/workspace-context.md`
    - `docs/design/claude-agent/edit-point/workspace-switch.md`
  - 参考 PRD：
    - `docs/prd/notion-session/resource-connector.md`
    - `docs/prd/notion-session/resource-connector-ui-design.md`
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
  - 本文档由 Notion 资源连接器设计稿拆解生成，作为 task 阶段任务规划输入。
  - 若与设计稿冲突，以 `docs/design/` 中稳定设计稿为准。
  - 若与当前 API / 代码实现冲突，必须记录为阻塞或澄清项，不得静默覆盖。

## 1. 关联设计稿信息

- 主设计稿：`docs/design/notion-session/overview.md`
- 重点补充设计稿：
  - `docs/design/notion-session/connector-interaction.md`
  - `docs/design/notion-session/resource-connector-er.md`
  - `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
  - `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md`
  - `docs/design/claude-agent/notion-point/interaction-snapshot-lifecycle.md`
  - `docs/design/claude-agent/edit-point/workspace-context.md`
  - `docs/design/claude-agent/edit-point/workspace-switch.md`
- 参考 PRD：
  - `docs/prd/notion-session/resource-connector.md`
  - `docs/prd/notion-session/resource-connector-ui-design.md`
- 关联实现路径：
  - `backend/notion/`
  - `backend/routers/notion.py`
  - `backend/routers/claude_agent.py`
  - `backend/claude_agent/service.py`
  - `backend/claude_agent/workspace_context.py`
  - `backend/libs/claude_agent_kit/server/notion_snapshot.py`
  - `frontend/src/App.tsx`
  - `frontend/src/api/resourceConnectorApi.ts`
  - `frontend/src/components/dashboard/`
  - `frontend/src/components/chat/`
  - `frontend/src/constants/storageKeys.ts`

- 本清单覆盖范围：
  - Notion 资源连接器创建、认证、资源发现、资源选择与 snapshot 物化
  - 连接器来源视图、状态展示与前端入口
  - canonical snapshot attach、`.notion/` 只读读取与 connector-scoped chat/context 关系

- 明确排除范围：
  - Notion 写回、proposal/write pipeline 与远程确认回写
  - Deck / 文件上传 / 多平台接入
  - 全文索引、向量检索与资源差异对比
  - 直接把 Notion 状态塞进 `switch_editor` 的会话语义

- 关键约束：
  - 资源连接器的内部权威状态必须是 canonical snapshot，不是 Agent 本地缓存
  - `ntn` CLI、`NOTION_HOME` 和 sandbox allowlist 必须走配置 / 环境注入，不能硬编码
  - 同一 `snapshotVersion` 下的 `.notion/connector.json`、`.notion/index.json`、`.notion/pages/*.json` 必须来自同一 snapshot object
  - shared Issue 必须有唯一主责 Agent，不能把 owner 悬空给 `FrontendTaskAgent + BackendTaskAgent`

- 补充说明：
  - 本次拆解只覆盖 Notion 资源连接器的 MVP 主链路，不把 Deck、写回或多平台扩展并入同一批 Issue。
  - `SUO-176` 作为 shared 连接点，负责把 snapshot 上下文与 chat / workspace attach 贯通到同一条可验证链路。
  - S5 的 E2E 验收与缺口收口已另拆到 `docs/issue/ISSUES_notion-session-e2e.md`，对应 `SUO-186`~`SUO-188`，不并入实现主链路。

## 2. Issue 总览表

| Issue ID | 标题 | 类型 | 优先级 | 标签 | 前置依赖 | 分发去向 |
|---|---|---|---|---|---|---|
| `SUO-174` | 实现 Notion 资源连接器后端：认证、资源发现与 snapshot 落地 | backend | P0 | `backend,notion,connector,auth,snapshot,resources` | 无 | `@BackendTaskAgent` |
| `SUO-175` | 实现 Notion 资源连接器前端：创建、认证与来源视图 | frontend | P0 | `frontend,notion,connector,auth,source-view,ui` | `SUO-174` | `@FrontendTaskAgent` |
| `SUO-176` | 贯通 Notion 快照上下文、聊天入口与连接器线程关系 | shared | P0 | `shared,notion,workspace,snapshot,chat,connector` | `SUO-174`, `SUO-175` | `@BackendTaskAgent` + `@FrontendTaskAgent` |

## 3. Issue 明细

### `SUO-174`

- 标题：实现 Notion 资源连接器后端：认证、资源发现与 snapshot 落地
- 类型：backend
- 优先级：P0
- 标签：`backend,notion,connector,auth,snapshot,resources`
- 描述：
  建立 Notion 资源连接器的后端基础链路，覆盖 `ntn login` / `ntn login poll` / `ntn auth status`、`NOTION_HOME` 管理、可访问 database / page 的发现、资源选择结果持久化，以及 connector-owned canonical snapshot 的物化与落盘。该 Issue 负责把 Notion 的远程事实源收敛成后端可消费的稳定合同，供前端来源视图和后续 runtime attach 使用。

- 验收条件：
  - 能创建 Notion connector，并通过后端接口完成认证发起、轮询与状态回写。
  - 能分别列出可访问的 databases 与 standalone pages，并支持分页 / 错误分类。
  - 能持久化用户选定的资源集合，并在选择变化后生成新的 canonical snapshot identity。
  - `.notion` 相关 snapshot 读写合同可返回 `snapshot_version`、`source_revision`、`sync_cursor`、`fetched_at`，缺页时返回 snapshot-scoped miss，而不是远程 lazy load。
  - 认证、发现、snapshot materialization 与错误分支均有后端测试覆盖。

- 前置依赖：无

- 关联路径：
  - `backend/notion/`
  - `backend/routers/notion.py`
  - `backend/server.py`
  - `backend/routers/.folder.md`
  - `backend/libs/claude_agent_kit/server/notion_snapshot.py`
  - `backend/tests/`

- 分发去向：`@BackendTaskAgent`

- 主责 Agent：
  - `BackendTaskAgent`

- 协作 Agent：
  - 无

- 设计决策引用：
  - `docs/design/notion-session/overview.md §1-5`
  - `docs/design/notion-session/connector-interaction.md §3-5`
  - `docs/design/notion-session/resource-connector-er.md §1-2`
  - `docs/design/claude-agent/notion-point/resource-connector-layer-design.md §2-4`
  - `docs/design/claude-agent/notion-point/resource-connector-flowcharts.md §2-3`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - `[BLOCKED]` 无
  - 这里不把 Notion 写回、Deck 或多平台扩展并入后端主链路。

### `SUO-175`

- 标题：实现 Notion 资源连接器前端：创建、认证与来源视图
- 类型：frontend
- 优先级：P0
- 标签：`frontend,notion,connector,auth,source-view,ui`
- 描述：
  在现有 dashboard 壳中落地 Notion 资源连接器前端体验：连接器入口、创建弹窗、认证引导与轮询、资源选择器、来源视图、来源卡片、空状态和同步状态展示。该 Issue 只覆盖连接器 shell 与来源管理，不提前把 chat tab、写回或 Deck / file upload 并入同一批实现。

- 验收条件：
  - 用户可以从现有 dashboard 进入资源连接器页面或面板，不需要手动拼接 URL。
  - 可以创建 connector，并驱动 Notion 认证 / 轮询 / 过期态 / 成功态 UI。
  - 可以浏览可访问的 databases 与 standalone pages，并把选中的资源显示到来源列表中。
  - 来源视图可正确展示 empty / loading / authenticating / expired / syncing / synced / error 等状态。
  - 桌面与移动端布局都能稳定渲染，且前端本地 fallback 不会和后端联调用法冲突。

- 前置依赖：`SUO-174`

- 关联路径：
  - `frontend/src/App.tsx`
  - `frontend/src/api/resourceConnectorApi.ts`
  - `frontend/src/components/dashboard/`
  - `frontend/src/components/dashboard/Sidebar.tsx`
  - `frontend/src/components/dashboard/VerticalNav.tsx`
  - `frontend/src/constants/storageKeys.ts`
  - `frontend/tests/`

- 分发去向：`@FrontendTaskAgent`

- 主责 Agent：
  - `FrontendTaskAgent`

- 协作 Agent：
  - `BackendTaskAgent`

- 设计决策引用：
  - `docs/prd/notion-session/resource-connector.md §1-7`
  - `docs/prd/notion-session/resource-connector-ui-design.md`
  - `docs/design/notion-session/connector-interaction.md §4-5`
  - `docs/design/notion-session/resource-connector-er.md §1-2`
  - `docs/design/notion-session/overview.md §5-7`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - `[BLOCKED]` 无
  - Chat tab 与 connector-scoped threads 不并入本 Issue，留给 `SUO-176` 处理。

### `SUO-176`

- 标题：贯通 Notion 快照上下文、聊天入口与连接器线程关系
- 类型：shared
- 优先级：P0
- 标签：`shared,notion,workspace,snapshot,chat,connector`
- 描述：
  把 Notion 资源连接器的 canonical snapshot 变成 Agent 初始化与聊天上下文的权威输入：workspace attach 必须读取同一 snapshot identity，`.notion/*` 读取必须从 attach 的 snapshot 解析，连接器下的 chat 线程关系也必须可被稳定查询与展示。该 Issue 是 BackendTaskAgent 与 FrontendTaskAgent 的共享边界，负责把“选中哪个 connector”真正变成“本轮 Agent 看到哪个 snapshot”。

- 验收条件：
  - workspace attach 会从连接器数据层读取 current canonical snapshot，并把 snapshot identity 注入到 `workspace_context`。
  - `Read(".notion/snapshot.json")`、`Read(".notion/index.json")`、`Read(".notion/pages/<id>.json")` 都只解析已 attach 的 snapshot，不直接远程拉取。
  - connector-scoped chat/thread 关系可从后端稳定读取，并能回到对应 connector 上下文。
  - 前端聊天表面能够显示当前 connector / snapshot 版本，并在切换 connector 后于下一轮 Agent init 生效。
  - 相关集成测试可以证明同一 `snapshotVersion` 在 backend attach、`.notion/` 读取和 chat 上下文中保持一致。

- 前置依赖：`SUO-174`, `SUO-175`

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
  - `backend/tests/test_notion_snapshot_contract.py`
  - `backend/tests/test_server_claude_agent.py`

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
  - `docs/design/claude-agent/edit-point/workspace-switch.md §6`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - `[BLOCKED]` 无
  - 这一项只收敛 connector 选择、snapshot attach 与 thread 关系，不扩展 Notion 写回或多平台能力。

## 4. 共享任务与依赖说明

- `SUO-174` 是本批最底层的后端基础；没有认证、发现与 snapshot 落地，就没有可供前端和 runtime 消费的权威数据。
- `SUO-175` 依赖 `SUO-174` 的稳定 API / snapshot 合同，前端可以先做壳层和本地 fallback，但最终必须回到同一后端合同。
- `SUO-176` 依赖 `SUO-174` 与 `SUO-175`，因为 snapshot attach、chat 上下文和 connector 线程关系都需要稳定的 backend 数据层与可见的 connector 选择状态。
- shared Issue 必须明确主责 Agent；本批将 backend attach / snapshot 主链路放在 `BackendTaskAgent`，前端只负责当前 connector / snapshot 的展示与切换入口。
- 若后续发现 chat history、Deck、file upload 或 write-back 需要独立的设计边界，必须拆出新 Issue，不允许在本批里静默扩张。

## 5. 分发去向说明

- `BackendTaskAgent`：
  - 领取 `SUO-174`。
  - 负责 `SUO-176` 中 backend 侧的 snapshot attach、workspace_context、connector thread 数据层与相关测试。

- `FrontendTaskAgent`：
  - 领取 `SUO-175`。
  - 负责 `SUO-176` 中前端侧的 current connector 展示、snapshot 状态展示与 chat surface 联动。

- `Shared Issue` 处理规则：
  - shared 类型 Issue 必须明确主责 Agent。
  - 另一个 Agent 作为协作方。
  - 不允许 shared Issue 无主责。
  - 若主责不清，必须标记 `[CLARIFICATION_NEEDED]`。

## 6. 推荐推进顺序

1. 先完成 `SUO-174`，把后端认证、发现与 snapshot 合同收口。
2. 再推进 `SUO-175`，让前端 shell、认证流与来源视图能稳定接入同一后端合同。
3. 最后推进 `SUO-176`，把 snapshot attach、chat 入口与 connector 线程关系贯通到同一运行链路。

推荐理由：

- 先稳定后端合同，可以减少前端壳层和 shared attach 的反复改动。
- 再做前端来源视图，可以在真实接口之上对齐状态语义，而不是靠臆测的 mock 结构。
- shared issue 放到最后，可以把已冻结的 backend / frontend 合同接起来，避免 owner 边界来回漂移。

## 7. 阻塞与澄清记录

- `[BLOCKED]` 无
- `[CLARIFICATION_NEEDED]` 无
- 当前设计稿已经足够支撑 Notion 资源连接器的 issue 拆解，没有出现需要回退 `design` 的硬缺口。
- 若后续 `docs/stage/stage_notion-resource-connector.md` 需要更细的排期粒度，应由 StagePlanner 在 task 之后拆分，不在 issue 清单里静默改写边界。

## 8. Issue-First 协作说明

* Issue 是最小调度单元。
* 同一 Issue 任一时刻只允许一个主责 Agent。
* shared Issue 必须有主责 Agent 与协作 Agent。
* 必须通过 Issue 评论区补充上下文、阻塞、回退和评审意见。
* 必须通过 `@mention` 唤醒目标 Agent。
* 不假设 Agent 之间存在隐式共享内存。
* 不允许绕过 Issue 直接下发 task。
