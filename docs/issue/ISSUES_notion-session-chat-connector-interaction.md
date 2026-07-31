# Chat / Connector 交互重构 Issue 清单

## 0. 文档元信息

- Issue 清单文件：`docs/issue/ISSUES_notion-session-chat-connector-interaction.md`
- 来源设计稿：
  - 主设计稿：`docs/design/notion-session/connector-interaction.md`
  - 补充设计稿：`docs/design/notion-session/overview.md`
  - 背景设计稿：`docs/design/claude-agent/edit-point/workspace-context.md`
  - 背景设计稿：`docs/design/claude-agent/edit-point/workspace-switch.md`
  - 参考 PRD：`docs/prd/notion-session/resource-connector.md`
  - 参考 PRD：`docs/prd/notion-session/resource-connector-ui-design.md`
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
  - 本文档基于 SUO-194 设计增量修订（2026-07-07）拆解生成，替代原有 `ISSUES_notion-session.md` 中不涉及 Chat/Connector 交互重构的部分。
  - 核心变化：Chat 入口页成为主落点，历史对话与连接器下沉为 landing tabs；输入框下方增加快捷功能 strip；连接器不再以独立主页面承载。
  - 若与设计稿冲突，以 `docs/design/` 中稳定设计稿为准。
  - 若与当前代码冲突，必须记录为阻塞或澄清项，不得静默覆盖。

---

## 1. 关联设计稿信息

- 主设计稿：`docs/design/notion-session/connector-interaction.md`（2026-07-07 更新）
- 重点补充设计稿：`docs/design/notion-session/overview.md`（2026-07-07 更新 §11, §17）
- 关联设计稿：`docs/design/claude-agent/edit-point/workspace-context.md`
- 关联设计稿：`docs/design/claude-agent/edit-point/workspace-switch.md`
- 参考 PRD：`docs/prd/notion-session/resource-connector.md`
- 参考 PRD：`docs/prd/notion-session/resource-connector-ui-design.md`

- 本清单覆盖范围：
  - Chat 入口页重构：历史对话 / 连接器作为 landing tabs
  - ChatView 内嵌 ResourceConnectorPage 作为 connector tab 内容
  - 输入框下方快捷功能 strip（生成图片 / 撰写或编辑 / 查找资料）
  - 连接器认证会话保持（`auth/poll` 幂等、已消费会话收敛）
  - Chat shell 降级与 `shell_error` 可恢复错误态
  - 前端状态机与后端用户态状态映射对齐（SUO-192）
  - agent-browser E2E 验证路径

- 明确排除范围：
  - Notion 写回、proposal/write pipeline（保留设计边界，不落地）
  - Deck 语音交互改造（不在本批 scope）
  - 多平台连接器抽象框架（先只做 Notion）
  - 实时 WebSocket 数据推送（事件驱动刷新 + 手动 sync 足够）
  - 连接器权限分级（本期仅只读）

- 关键约束：
  - Chat 入口页是连接器的新主落点，不是独立页面；`ResourceConnectorPage` 必须嵌入 Chat shell 的 connector tab
  - 快捷功能 strip 是 Chat shell 的二级动作带，不替代 connector 工作台，不承载 connector 生命周期状态
  - `shell_error` 只表示 Chat shell 级故障，不表示 connector 认证/同步/snapshot 状态异常；用户仍应能看到重新加载入口
  - 认证会话保活：`auth/poll` 返回 `consumed` 或 `authenticated` 时，前端应收敛到 `authenticated` 展示
  - 同一 snapshotVersion 下的 `.notion/*` 读取必须来自同一个 canonical snapshot object

- 补充说明：
  - 本清单是 SUO-193 的 issue-phase 子任务（SUO-195），为后续 SUO-196（前端 task）和 SUO-197（stage）提供输入
  - 设计增量 SUO-194 已完成，设计稿 `connector-interaction.md` 和 `overview.md` 已反映最新交互方案
  - `SUO-174`/`SUO-175`/`SUO-176` 已完成后端基础链路，本批在此基础上做前端交互重构

---

## 2. Issue 总览表

| Issue ID | 标题 | 类型 | 优先级 | 标签 | 前置依赖 | 分发去向 |
|---|---|---|---|---|---|---|
| `SUO-195-A` | Chat 入口页重构：landing tabs + 快捷功能 strip + shell_error 降级 | frontend | P0 | `frontend,chat,connector,landing,ui,shell-error` | 无 | `@FrontendTaskAgent` |
| `SUO-195-B` | ResourceConnectorPage 嵌入 Chat shell connector tab | frontend | P0 | `frontend,chat,connector,embed,ui` | `SUO-195-A` | `@FrontendTaskAgent` |
| `SUO-195-C` | 认证会话保持与前端的用户态状态映射对齐 | shared | P1 | `shared,notion,auth,frontend,backend,state-machine` | `SUO-195-A` | `@BackendTaskAgent` + `@FrontendTaskAgent` |
| `SUO-195-D` | Chat / Connector 交互重构 agent-browser E2E 验证 | frontend | P1 | `frontend,e2e,agent-browser,chat,connector` | `SUO-195-A`, `SUO-195-B`, `SUO-195-C` | `@FrontendTaskAgent` |

---

## 3. Issue 明细

### `SUO-195-A`

- 标题：Chat 入口页重构：landing tabs + 快捷功能 strip + shell_error 降级
- 类型：frontend
- 优先级：P0
- 标签：`frontend,chat,connector,landing,ui,shell-error`
- 描述：
  将 Chat 页面从「对话框为主」重构为「Chat landing + 连接器工作台」的新入口模型。具体变更：
  1. Chat 入口页中间保留对话输入框，下方新增 landing tabs（历史对话 / 连接器）
  2. 输入框下方增加快捷功能 strip（生成图片 / 撰写或编辑 / 查找资料）
  3. 实现 `shell_error` 可恢复错误态：当 `ChatViewContent`、快捷功能区域或 landing tabs 初始化失败时，显示可恢复错误条，保留 tab/connector 入口，避免整页留白
  4. 历史对话 tab 展示 thread list 和 search dialog trigger
  5. 连接器 tab 作为 connector 工作台入口，后续由 SUO-195-B 嵌入 ResourceConnectorPage

  本 Issue 是交互重构的基础，后续 Issue 依赖其 landing tabs 和 shell 结构。

- 验收条件：
  - Chat 入口页加载后，默认显示输入框 + 快捷功能 strip + landing tabs（历史对话 / 连接器）
  - 点击「历史对话」tab 显示历史对话列表，点击「连接器」tab 显示连接器工作台入口
  - 快捷功能 strip 三个按钮（生成图片 / 撰写或编辑 / 查找资料）可点击，不替代 connector 生命周期状态
  - 模拟 `ChatViewContent` 渲染失败场景，验证 `shell_error` 态是否显示可恢复错误条（含 `Reload shell` / `Retry` 按钮），且 tab/connector 入口不被折叠
  - 桌面端与移动端布局均稳定渲染，landing tabs 切换流畅无白屏

- 前置依赖：无

- 关联路径：
  - `frontend/src/App.tsx`
  - `frontend/src/components/chat/ChatView.tsx`
  - `frontend/src/components/chat/` 目录下新增或改造的 landing tab 组件
  - `frontend/src/components/chat/QuickActionStrip.tsx`（新增）
  - `frontend/src/components/chat/ChatShellError.tsx`（新增）
  - `frontend/src/components/dashboard/`（如涉及导航变更）

- 分发去向：`@FrontendTaskAgent`

- 主责 Agent：
  - `FrontendTaskAgent`

- 协作 Agent：
  - 无

- 设计决策引用：
  - `docs/design/notion-session/connector-interaction.md §3.1, §3.4`
  - `docs/design/notion-session/overview.md §11.1, §11.2`
  - `docs/design/notion-session/connector-interaction.md §11.1, §11.4`

- 备注：
  - `[CLARIFICATION_NEEDED]` 快捷功能 strip 点击后的具体行为（是否直接发起对应 Agent 对话）需与产品确认，当前只要求 UI 落点和可点击态
  - `[CLARIFICATION_NEEDED]` 历史对话 tab 的 thread list 数据来源是否复用现有 `ChatPanel` 的 thread 加载逻辑，需确认

---

### `SUO-195-B`

- 标题：ResourceConnectorPage 嵌入 Chat shell connector tab
- 类型：frontend
- 优先级：P0
- 标签：`frontend,chat,connector,embed,ui`
- 描述：
  将现有的 `ResourceConnectorPage`（独立页面）改造为可嵌入 Chat shell connector tab 的组件。具体变更：
  1. 移除 `ResourceConnectorPage` 作为独立页面的路由入口（或保留但标记为 deprecated）
  2. 新增 `ConnectorTabPanel` 组件，内嵌 `ResourceConnectorPage` 的核心功能（创建 / 认证 / 资源选择 / 来源列表 / 删除）
  3. 连接器认证、同步、来源展示等交互逻辑保持与现有实现一致
  4. connector tab 中的嵌入式工作台应能与 Chat shell 的 `shell_error` 降级联动

  本 Issue 依赖 SUO-195-A 提供的 connector tab 容器。

- 验收条件：
  - 点击 Chat 入口页的「连接器」tab，展示嵌入的 connector 工作台（创建 / 认证 / 资源选择 / 来源列表 / 删除）
  - 连接器认证流程（verification code 展示 → 浏览器确认 → poll 轮询 → authenticated 态）在嵌入式场景下正常工作
  - 连接器来源列表（databases + standalone pages）可正常展示、刷新和删除
  - 嵌入式 connector 工作台与 Chat shell 的 `shell_error` 降级联动：当 connector 区域渲染失败时，shell_error 态可见且可恢复
  - 现有独立 `ResourceConnectorPage` 路由如不移除，访问时给出「已迁移到 Chat 页面」提示

- 前置依赖：`SUO-195-A`

- 关联路径：
  - `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
  - `frontend/src/components/chat/ConnectorTabPanel.tsx`（新增）
  - `frontend/src/App.tsx`（路由调整）
  - `frontend/src/api/resourceConnectorApi.ts`
  - `frontend/src/components/chat/ChatView.tsx`

- 分发去向：`@FrontendTaskAgent`

- 主责 Agent：
  - `FrontendTaskAgent`

- 协作 Agent：
  - 无

- 设计决策引用：
  - `docs/design/notion-session/connector-interaction.md §3.1, §4.1`
  - `docs/design/notion-session/overview.md §11.1`
  - `docs/design/notion-session/connector-interaction.md §11.2`

- 备注：
  - `[CLARIFICATION_NEEDED]` 现有 `ResourceConnectorPage` 独立路由是否完全移除，还是保留 deprecated 入口并 redirect，需确认
  - 本 Issue 不涉及后端接口变更，只做前端组件嵌入和路由调整

---

### `SUO-195-C`

- 标题：认证会话保持与前端的用户态状态映射对齐
- 类型：shared
- 优先级：P1
- 标签：`shared,notion,auth,frontend,backend,state-machine`
- 描述：
  对齐前端用户态状态映射与后端认证会话保持语义，解决 `ntn login poll` 单次会话消费后前端重复轮询导致状态回退的问题。具体变更：
  1. 后端 `POST /api/connectors/:id/auth/poll` 幂等处理：已认证直接返回 `authenticated`，已消费会话标记 `consumed` 并保留认证成果
  2. 前端基于 `connector.auth_status` + `config.auth_session` 进行 UI 判定，不以「重复 pending」作为唯一阻塞根因
  3. 对齐 §11.1 用户态状态映射表：前端 UI 状态（draft / authenticating / authenticated / syncing / synced / stale / error）与后端触发器一一对应
  4. 认证会话保活规则落地：前端遇到 `already_consumed` 错误码时收敛到 `authenticated` 展示

  本 Issue 是 shared 类型，BackendTaskAgent 主责后端 poll 幂等和状态模型，FrontendTaskAgent 协作前端状态映射对齐。

- 验收条件：
  - 后端 `POST /auth/poll` 在会话已消费时返回 `status="consumed"` 或 `error code="already_consumed"`，且 `connector.auth_status` 保持 `authenticated`
  - 后端 `POST /auth/poll` 在已认证时直接返回 `authenticated`，不做冗余轮询
  - 前端基于 `connector.auth_status` + `config.auth_session` 判定 UI 状态，`pending` 不再是唯一阻塞态
  - 前端遇到 `already_consumed` 时立即收敛到 `authenticated` 展示（若 connector 已有 token）
  - 过期态 `expired` 前端只显示 `Re-auth`，保留最近快照但明确「仅历史只读」
  - 状态机流转覆盖 §11.4 最小事件图的所有路径

- 前置依赖：`SUO-195-A`

- 关联路径：
  - `backend/routers/notion.py`（poll 端点）
  - `backend/notion/auth.py`（poll 幂等逻辑）
  - `frontend/src/api/resourceConnectorApi.ts`（poll 调用）
  - `frontend/src/components/dashboard/ResourceConnectorPage.tsx`（状态映射）
  - `frontend/src/components/chat/ConnectorTabPanel.tsx`（状态映射）
  - `docs/design/notion-session/connector-interaction.md §11.1-11.4`

- 分发去向：`@BackendTaskAgent` + `@FrontendTaskAgent`

- 主责 Agent：
  - `BackendTaskAgent`

- 协作 Agent：
  - `FrontendTaskAgent`

- 设计决策引用：
  - `docs/design/notion-session/connector-interaction.md §3.3, §11.1-11.4`
  - `docs/design/notion-session/overview.md §4.2`

- 备注：
  - `[CLARIFICATION_NEEDED]` 无
  - `[BLOCKED]` 无
  - 主责 Agent 为 BackendTaskAgent，因为后端 poll 幂等是前端状态收敛的前提

---

### `SUO-195-D`

- 标题：Chat / Connector 交互重构 agent-browser E2E 验证
- 类型：frontend
- 优先级：P1
- 标签：`frontend,e2e,agent-browser,chat,connector`
- 描述：
  为 Chat / Connector 交互重构编写 agent-browser E2E 验证用例，覆盖以下场景：
  1. Chat 入口页加载 → landing tabs 切换 → 快捷功能 strip 可见
  2. 连接器 tab → 创建 connector → 认证流程 → 资源选择 → 来源列表展示
  3. `shell_error` 降级 → 可恢复错误条 → Reload shell
  4. 历史对话 tab → thread list 展示
  5. 认证会话保持：poll 已消费 → 前端收敛到 authenticated

  本 Issue 依赖 SUO-195-A/B/C 的实现完成，是 stage 规划（SUO-197）的前提。

- 验收条件：
  - agent-browser 脚本可自动完成 Chat 入口页加载并验证 landing tabs 存在
  - agent-browser 脚本可切换 connector tab 并验证嵌入式 connector 工作台可见
  - agent-browser 脚本可点击快捷功能 strip 按钮并验证响应（不报错）
  - agent-browser 脚本可模拟 shell_error 场景并验证可恢复错误条出现
  - agent-browser 脚本可完成 connector 创建 → 认证 → 资源选择 → 来源列表的全链路验证
  - 所有 E2E 脚本有截图证据和断言失败时的诊断输出

- 前置依赖：`SUO-195-A`, `SUO-195-B`, `SUO-195-C`

- 关联路径：
  - `frontend/tests/e2e/` 或 `tests/e2e/` 目录下新增 Chat/Connector 交互测试
  - `docs/design/notion-session/connector-interaction.md`（验证依据）
  - `$AGENT_HOME/agent-browser-e2e-test-manual.md`（测试工具参考）

- 分发去向：`@FrontendTaskAgent`

- 主责 Agent：
  - `FrontendTaskAgent`

- 协作 Agent：
  - 无

- 设计决策引用：
  - `docs/design/notion-session/connector-interaction.md §3.1, §3.4, §11.1-11.4`
  - `docs/design/notion-session/overview.md §11.1-11.3`

- 备注：
  - `[CLARIFICATION_NEEDED]` agent-browser 测试是否需要在真实 Notion auth 环境下运行，还是可用 mock auth 状态，需确认
  - 本 Issue 不直接修改业务代码，只产出 E2E 验证脚本和证据

---

## 4. 共享任务与依赖说明

- `SUO-195-A` 是本批的基础：Chat 入口页重构为后续 connector tab 嵌入和 shell_error 降级提供容器结构。
- `SUO-195-B` 依赖 `SUO-195-A` 的 connector tab 容器，负责把现有 ResourceConnectorPage 嵌入 Chat shell。
- `SUO-195-C` 是 shared 类型，BackendTaskAgent 主责 poll 幂等和状态模型，FrontendTaskAgent 协作前端状态映射对齐。
- `SUO-195-D` 依赖 A/B/C 全部完成，是 E2E 验证和 stage 规划的前提。
- 若后续发现快捷功能 strip 的具体行为（如点击后是否直接发起 Agent 对话）需要独立设计，必须拆出新 Issue，不允许在本批里静默扩张 scope。
- 若发现 shell_error 降级与现有 ChatView 错误处理有冲突，必须记录 Issue 评论，不得直接覆盖现有错误边界。

---

## 5. 分发去向说明

- `BackendTaskAgent`：
  - 领取 `SUO-195-C` 中后端相关部分（poll 幂等、状态模型、错误码）。
  - 负责 `SUO-195-C` 的后端验收条件验证。

- `FrontendTaskAgent`：
  - 领取 `SUO-195-A`、`SUO-195-B`、`SUO-195-D`。
  - 负责 `SUO-195-C` 中前端相关部分（状态映射、UI 判定逻辑）。

- `Shared Issue` 处理规则：
  - `SUO-195-C` 主责 Agent 为 `BackendTaskAgent`，协作 Agent 为 `FrontendTaskAgent`。
  - 不允许 shared Issue 无主责。
  - 若主责不清，必须标记 `[CLARIFICATION_NEEDED]`。

---

## 6. 推荐推进顺序

1. 先完成 `SUO-195-A`（Chat 入口页重构），这是后续所有工作的容器基础。
2. 再推进 `SUO-195-B`（connector tab 嵌入），在 A 的 landing tabs 容器上接入 connector 工作台。
3. 并行推进 `SUO-195-C`（认证会话保持），后端 poll 幂等和前端状态映射可分别由 BackendTaskAgent 和 FrontendTaskAgent 同步开发。
4. 最后推进 `SUO-195-D`（E2E 验证），在 A/B/C 全部完成后验证完整交互链路。
5. P1 Issue 不得阻塞 P0 主链路。

推荐顺序：

```text
SUO-195-A (P0, frontend)
  ↓
SUO-195-B (P0, frontend)
  ↓
SUO-195-C (P1, shared) ← 可与 B 部分并行
  ↓
SUO-195-D (P1, frontend)
```

---

## 7. 阻塞与澄清记录

### [CLARIFICATION_NEEDED] SUO-195-A

- 歧义点：快捷功能 strip 点击后的具体行为（是否直接发起对应 Agent 对话，还是仅展示提示）
- 可能解释 A：点击后直接发起对应 Agent 对话（生成图片 → 调用图像生成 Agent）
- 可能解释 B：点击后仅展示功能提示，不触发实际对话（MVP 阶段）
- 默认采用解释：解释 B（MVP 阶段只要求 UI 落点和可点击态）
- 需要确认方：`CEOOrchestrator` / 产品
- 是否阻塞 task 阶段：否，task 阶段可先按解释 B 实现

### [CLARIFICATION_NEEDED] SUO-195-A

- 歧义点：历史对话 tab 的 thread list 数据来源是否复用现有 `ChatPanel` 的 thread 加载逻辑
- 可能解释 A：直接复用 `ChatPanel` 的 `loadThreads` 逻辑
- 可能解释 B：新增独立的 thread list 组件，数据来源相同但展示独立
- 默认采用解释：解释 A（复用现有逻辑，减少重复代码）
- 需要确认方：`FrontendTaskAgent`
- 是否阻塞 task 阶段：否

### [CLARIFICATION_NEEDED] SUO-195-B

- 歧义点：现有 `ResourceConnectorPage` 独立路由是否完全移除
- 可能解释 A：完全移除独立路由，统一走 Chat 入口页的 connector tab
- 可能解释 B：保留 deprecated 入口并 redirect 到 Chat 页面
- 默认采用解释：解释 B（保留 deprecated 入口，给出迁移提示）
- 需要确认方：`CEOOrchestrator` / 产品
- 是否阻塞 task 阶段：否

### [CLARIFICATION_NEEDED] SUO-195-D

- 歧义点：agent-browser 测试是否需要在真实 Notion auth 环境下运行
- 可能解释 A：需要真实 Notion auth（端到端完整验证）
- 可能解释 B：可用 mock auth 状态（只验证前端交互，不依赖外部服务）
- 默认采用解释：解释 B（先用 mock auth 验证前端交互，真实 auth 作为后续扩展）
- 需要确认方：`CEOOrchestrator`
- 是否阻塞 task 阶段：否

---

## 8. Issue-First 协作说明

* Issue 是最小调度单元。
* 同一 Issue 任一时刻只允许一个主责 Agent。
* shared Issue 必须有主责 Agent 与协作 Agent。
* 必须通过 Issue 评论区补充上下文、阻塞、回退和评审意见。
* 必须通过 `@mention` 唤醒目标 Agent。
* 不假设 Agent 之间存在隐式共享内存。
* 不允许绕过 Issue 直接下发 task。

---

## 9. 与现有 Issue 清单的关系

本清单（`ISSUES_notion-session-chat-connector-interaction.md`）是 `ISSUES_notion-session.md` 的增量补充，专用于 SUO-193 的 Chat / Connector 交互重构子任务。

- `SUO-174`/`SUO-175`/`SUO-176`（在 `ISSUES_notion-session.md` 中）已完成后端基础链路，本清单在此基础上做前端交互重构。
- 本清单不重复拆解后端认证/发现/snapshot 基础能力，只聚焦 Chat 入口页重构、connector tab 嵌入、认证会话保持和 E2E 验证。
- 后续 `SUO-196`（前端 task）应基于本清单生成 task 文档。
- 后续 `SUO-197`（stage 规划）应基于本清单和 `ISSUES_notion-session.md` 做依赖拓扑分析。

