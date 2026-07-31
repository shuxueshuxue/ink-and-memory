# Exec Report: SUO-183 - 修复 ResourceConnectorPage 滚动容器导致资源选择与来源列表不可交互

## 1. 执行上下文
- Task ID: `SUO-183`
- 关联 Issue: `SUO-172` 的前端回归修复上下文；当前回归点为 `ResourceConnectorPage` 下半区不可交互
- 关联任务: `docs/task/task_178_frontend_notion-resource-connector-create-auth-resource-selection.md`
- 关联阶段: `docs/stage/stage_notion-resource-connector.md`
- 关联设计稿: `docs/design/notion-session/overview.md`、`docs/design/notion-session/connector-interaction.md`、`docs/design/notion-session/resource-connector-er.md`
- 模板路径: `docs/task/TASK-REQUIREMENT-FORMAT.md`
- 执行 Agent: `ExecTaskAgent`
- 执行时间: `2026-07-05`

## 2. TASK-REQUIREMENT-FORMAT.md 填充摘要
- 输入 Issue: `SUO-183`，回归现象是 connector 页面下半区被固定视口裁切，资源选择与来源列表无法继续交互
- 输入 Task: `SUO-178` 的前端资源连接器任务文档，以及 `SUO-176` 阶段计划
- 填充后的执行目标: 让 `ResourceConnectorPage` 在固定的 connector app shell 内可滚动，确保资源选择和来源列表都能进入视口并继续交互
- 关键约束: 仅修改前端 shell、前端组件头注释和对应 folder docs；不改 backend / design / stage / task 文档，不扩展到新的路由或数据契约
- 验收条件: 连接器视口可滚动；资源选择区可见且可点击；来源列表可滚动进入视口；前端构建通过；浏览器 smoke 通过

## 3. 模型生成的执行任务
- 任务目标: 修复 connector 固定视口的 overflow 归属，让页面滚动发生在 app shell，而不是被 `overflow: hidden` 裁切
- 实现范围: `App.tsx` 的 connector viewport、`ResourceConnectorPage.tsx` 的文件头说明、`frontend/src/.folder.md`、`frontend/src/components/dashboard/.folder.md`
- 文件范围:
  - `frontend/src/App.tsx`
  - `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
  - `frontend/src/.folder.md`
  - `frontend/src/components/dashboard/.folder.md`
- 实现步骤:
  1. 将 connector view shell 从 `overflow: hidden` 改为 `overflowY: auto`，保留横向裁切和 fixed 布局
  2. 保持 `ResourceConnectorPage` 内容结构不变，只让它适配可滚动的 shell
  3. 更新受影响文件头注释与 folder contract，记录本次滚动边界修复
  4. 用 build 和浏览器 smoke 验证 lower sections 可达、可点
- 验证方式:
  - `pnpm -C frontend build`
  - Playwright smoke against a temp Vite-served harness with mocked connector API responses

## 4. 实现变更记录
| 文件 | 操作 | 说明 |
|---|---|---|
| `frontend/src/App.tsx` | update | 将 connector fixed shell 改为可纵向滚动，并保留横向裁切与 touch momentum scrolling；补充 sync 注释。 |
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | update | 补充 sync 注释，说明页面需要兼容可滚动的 app shell。 |
| `frontend/src/.folder.md` | update | 记录 connector viewport scroll shell 的行为变化。 |
| `frontend/src/components/dashboard/.folder.md` | update | 记录 connector shell 改为可滚动后，资源选择与来源列表仍可达。 |

## 5. 测试与验证
- 已执行测试: `pnpm -C frontend build`
- 测试结果: 通过，`tsc -b && vite build` 成功结束；仅有既有 chunk size / dynamic import 提示，无构建失败
- 已执行浏览器 smoke: 使用临时 Vite-harness 载入真实 `ResourceConnectorPage`，并通过 mocked `/api/connectors` 数据制造长页面
- 浏览器 smoke 结果:
  - `scrollHeight = 4765`
  - `clientHeight = 698`
  - 初始 `scrollTop = 0`
  - 资源选择区滚动后进入视口，首个数据库按钮可见且可点击
  - 进一步滚动到来源列表后，`来源列表` 标题可见，首个 source card 进入视口
- 未执行测试及原因: 未跑后端测试；本次修复仅涉及前端滚动边界，不改数据契约或后端逻辑
- 手动验证步骤: 在桌面视口下滚动 connector shell，确认资源选择卡片和来源列表都能进入视口并继续操作

## 6. 风险与阻塞
- 风险: connector shell 现在承担滚动责任，后续如果页面头部高度变化，需要重新确认短屏和移动端的可视区域
- 风险: 该修复未改数据流，若后续资源/来源内容再显著增高，可能仍需要更细的局部滚动分区
- 阻塞: 无
- 需要上游澄清的问题: 无

## 7. 完成状态
- [x] 已完成实现
- [x] 已完成测试
- [x] 已记录变更
- [x] 已满足验收条件
- [x] 可进入 review / audit

## 8. 回滚建议
- 回滚文件:
  - `frontend/src/App.tsx`
  - `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
  - `frontend/src/.folder.md`
  - `frontend/src/components/dashboard/.folder.md`
- 回滚方式: 将 connector shell 的 `overflowY: auto` 改回 `overflow: hidden`，并删除对应 sync 注释与 folder 记录
- 注意事项: 回滚后 lower resource-selection / source-list 区域会再次被固定视口裁切，需要同时撤回本次浏览器 smoke 结论

## 9. 执行完成报告
- 状态: `done`
- 交付物: connector 固定视口滚动修复已落地，资源选择与来源列表恢复可达
- 验证证据: 前端 build 通过；Playwright smoke 证明 connector shell 可滚动到 lower sections，且 source list 也能进入视口
- 可进入 review / audit: 是
