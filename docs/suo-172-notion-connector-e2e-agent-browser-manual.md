# SUO-172 Notion 资源连接器 E2E 与 agent-browser 手册

本文档用于固定 `SUO-172` 整体链路的 E2E 验收路径与 `agent-browser` 使用方式，确保后续测试可复现并且可追责。

## 1. 目标与边界

- 目标：覆盖 Notion 资源连接器完整交互闭环  
  `创建连接器 -> 认证 -> 选择可访问 database -> 后端同步 -> Chat 上下文映射`
- 结论边界：本手册记录了真实线上验证与 mock/contract 验证两条线，必须区分。
- 阻断原则：只要无法完成 live auth，明确标记为 `[BLOCKED]`，不得将本地替代结果冒充完整 E2E。

## 2. 统一术语与方法边界

- `Agent` 目标是交付可验证产物，不是重复人类点击行为。
- `源语言`：服务状态、接口协议、文件状态、可见产物。
- `入口`：`agent-browser`、HTTP API、日志与快照文件。
- `Dry Run`：先在不入侵主流程时验证命令可行性（如页面 URL、接口可达性）。
- `Validator`：接口断言、构建、快照比对、截图/字段回归。
- `ARF (Artifact Result Format)`：用于比较 GUI 与 CLI/程序化路径结果是否等价的产物结果格式。

## 2. 核心约束（E2E 必须满足）

- 不改造现有页面跳转与交互语义，按现有 `create/auth/login/poll/select/sync` 流水线测试。
- 任何 `SUO-172` 级联验收必须保留日志、截图、以及关键后端响应字段（尤其是 `connector_id`、`selected_databases/selected_pages`、snapshot identity）。
- 统一使用本会话与统一路径：
  - 前端：`http://127.0.0.1:5173`
  - 后端：`http://127.0.0.1:8765`
  - 必要时命名为 `127.0.0.1:<port>`，避免 DNS 干扰。
- 先完成页面级可达性与接口字段对齐，再谈 live Notion auth 结果。

## 3. ARF 标准（可对比工件）

所有验证都以 ARF 结果输出，便于“GUI 基线”与“程序化基线”比对。

### 3.1 ARF 字段

| 字段 | 说明 |
|---|---|
| `targetSoftware` | 目标软件与版本（本次为 `SUO-172 Notion Connector`） |
| `taskIntent` | 本次验收目标（完整链路） |
| `executionMode` | `GUI` 或 `agent-browser + API` |
| `commandTrace` | 启动参数、关键接口、关键路径命令 |
| `stateTrace` | 各阶段状态快照（init/auth/poll/select/sync/chat） |
| `artifactSet` | 关键截图、HTTP 响应片段、`.notion` 文件集、connector config |
| `validatorResult` | build/test/字段断言结果 |
| `equivalenceScore` | GUI 与程序化产物可比性评分（0~1） |
| `blockers` | 外部环境阻塞与解除 owner |
| `evidenceOwner` | 产物来源 owner 与时间 |

### 3.2 ARF 输出模板（本次固定）

```text
ARF SUO-172:
- targetSoftware: notion-resource-connector
- taskIntent: create -> auth -> select -> sync -> chat context -> notion mapping
- executionMode: agent-browser + API validation
- commandTrace:
  - agent-browser --extension ... --session ... --headed
  - /api/connectors create/auth/login/poll/resources/select
  - frontend resource refresh
- stateTrace:
  - t0: app shell loaded
  - t1: connector created (connector_id)
  - t2: auth URL generated
  - t3: poll result
  - t4: resources selected
  - t5: source refreshed
  - t6: workspace attach/.notion read attempted
- artifactSet:
  - screenshots/*.png (按流程关键帧)
  - connector_id + selected_databases/selected_pages
  - snapshot identity 与 workspace context trace
- validatorResult:
  - unit/integration: pass/fail
  - build: pass/fail
  - manual smoke: pass/fail
- equivalenceScore: 0.00~1.00
- blockers: live notion auth session / notion workspace
- evidenceOwner: CEOOrchestrator + ExecTaskAgent
```

### 3.3 判定规则

- `equivalenceScore >= 0.90` 且无阻塞：可视为完成 GUI 等价验收。
- `equivalenceScore < 0.90`：退回到阻塞项，要求补充字段级或截图级差异说明。
- live auth 阶段如果出现环境阻塞：记录 `blocked`，不得把结果升为 `done`。

## 4. agent-browser 运行基线

默认执行命令（按用户验证有效路径）：

```bash
agent-browser \
  --extension /Users/dmeck/agent-brower/capsolver-extension \
  --extension /Users/dmeck/agent-brower/stealth-extension \
  --session /tmp/suo-172-e2e \
  --headed
```

注意事项（直接来自多次复测结论）：

- `--state` 不要与该参数组合用于本场景。历史验证显示：
  - `--state` + 扩展会触发活动页恢复到 `about:blank`，导致页面实际不在目标上下文。
  - 续继承会持续放大该空白状态（`restore` 行为会放大已损坏上下文）。
- 避免“每次都新建/重建 session”导致登录态丢失。优先 `--session` 持续维护；如需要隔离，显式重新创建 session 名称。
- 真实 Notion auth 阶段若出现外部跳转，不要认为测试失败；应判断是否为 `external session / workspace` 限制。
- 每次关键动作后做 `screenshot`，确保可追溯；若只看到空白页，先排查启动参数，再排查目标 URL。

## 5. 具体操作步骤（按顺序执行）

### 5.1 启动与环境检查

1. 启动后端与前端服务。
2. 打开 `http://127.0.0.1:5173`，确认看到应用主壳（非空白）。
3. 打开 `console`，确认 `Vite` 与 `React` log 在正常运行。

### 5.2 创建并进入连接器工作流

1. 在 Dashboard 进入资源连接器入口。
2. 发起 Notion 连接器创建。
3. 记录返回 `connector_id`，应为真实 UUID（非前端本地伪 UUID）。
4. 校验页面路径/组件是否可见，`ResourceConnectorPage` 能触发可交互控件。

### 5.3 认证启动与状态采样

1. 触发 `auth/login`。
2. 记录 `verification URL`。
3. 若跳转到 Notion 外部登录页，保留截图为 `external auth step`。
4. `auth/poll` 只在外部会话确认后再继续；若返回
   - `status=pending` + `No pending login session found`，标记为环境阻塞（不是前端静态失败）。

### 5.4 资源选择与后端回执

1. 进入 resource selection 页面。
2. 按最小集合勾选 fallback 数据源并提交。
3. 检查后端返回：
   - `selected_databases` 或 `selected_pages` 不能被清空回退为 `[]`。
   - 这是此前一次关键缺陷点，曾因请求体字段使用 `database_ids/page_ids` 导致丢失。

### 5.5 来源刷新与同步检查

1. 触发来源刷新。
2. 在页面可见范围内确认来源卡片可达，不应被纵向容器裁切。
3. 截图核验 `scrollHeight` / `clientHeight`：需出现可滚动状态且下半区可见。

### 5.6 聊天与 `.notion` 贯通验证

1. 进入后续 chat 场景。
2. 检查 workspace attach 是否写入并传播到 `.notion/*` 与上下文读链路。
3. 在当前实现状态下，若未提供稳定外部 Notion workspace，标记为 `[BLOCKED]` 并保留补测要求。

## 6. E2E 已识别问题库（必须在每次测试备注）

1. `agent-browser --state` 导致 about:blank  
   - 表现：`tab/get url/snapshot/screenshot` 均不在目标页面，尽管服务本身正常启动。  
   - 处理：改用无 `--state` 的会话启动参数。

2. `ResourceConnectorPage` 布局与滚动容器问题  
   - 表现：`资源选择` 与 `来源列表` 被遮挡/不可达。  
   - 处理：修复页面滚动归属与容器高度后复测。

3. 资源选择字段 drift  
   - 表现：`/resources/select` 发送 `database_ids/page_ids`，后端接收后 selection 丢失。  
   - 处理：使用 `selected_databases/selected_pages`。

4. 本地 fallback 与真实 Notion 差异  
   - 表现：本地回退可通过 UI，但 `auth` 无法闭环。  
   - 处理：保持两套边界：本地 contract 证据和 live auth 外部环境证据分离。

5. 无法完成授权会话  
   - 表现：跳转 Notion 后出现“无权访问/会话不一致”。  
   - 处理：将阻塞归类为环境所有权问题（需提供可登录 Notion 的 browser session / workspace）。

## 7. 阶段化验收清单（Issue 与 Agent 对齐）

- `SUO-190`：后端 E2E 证据链（contract + tests）
  - 必要证据：`tests.test_notion_connector_router_flow`、`tests.test_notion_snapshot_contract`、`tests.test_claude_agent_service`。
- `SUO-191`：前端 E2E 回归（入口/认证/选择/刷新）
  - 必要证据：`npm run build` + 浏览器 smoke + 关键截图。
- `SUO-188`：共享贯通
  - 仅在 `SUO-190` + `SUO-191` 均给出可复用证据后启用，且需 `.notion/*` 与 snapshot identity 一致性补齐。

## 8. 强制输出

- 关键截图：每段流程至少 1 张（可复用目录 `logs/qa/suo-172-*/screenshots`）。
- 关键接口响应：记录 `connector_id`、`connector config`、`selected_*` 字段与 attach/snapshot trace。
- 关键决策：若存在 live auth 阻塞，写入 blocker owner 与解除动作，不得直接判为 done。

## 9. 参考文件与报告

- 本文档对应父 Issue：`SUO-172`
- 关联执行报告：  
  - [exec_190_notion_resource_connector_backend_e2e_evidence](/Users/dmeck/project/ink-and-memory/docs/exec/exec_190_notion_resource_connector_backend_e2e_evidence.md)  
  - [exec_191_frontend_resource_connector_e2e_regression](/Users/dmeck/project/ink-and-memory/docs/exec/exec_191_frontend_resource_connector_e2e_regression.md)
- 历史布局问题快照（排查参考）：`logs/qa/suo-172-layout/screenshots/`
