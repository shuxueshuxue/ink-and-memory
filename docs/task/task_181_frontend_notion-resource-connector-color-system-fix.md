# SUO-181 前端任务文档：Notion 资源连接器页面颜色系统修复

Status: Draft  
Updated: 2026-07-04  
Scope: 前端任务规划 - 资源连接器页面颜色系统收敛与 token 对齐

> [Input] `docs/task/TASK-REQUIREMENT-FORMAT.md`,
>      `docs/prd/color_system/README.md`,
>      `docs/prd/color_system/light-theme.md`,
>      `docs/prd/notion-session/resource-connector.md`,
>      `docs/prd/notion-session/resource-connector-ui-design.md`,
>      `frontend/src/components/dashboard/ResourceConnectorPage.tsx`,
>      `frontend/src/App.tsx`,
>      `frontend/src/components/TopNavBar.tsx`,
>      `frontend/src/styles/tokens.css`
> [Output] 可执行的前端任务文档，供后续实现阶段直接拆分与排期
> [Pos] `task_181_frontend_notion-resource-connector-color-system-fix` in `docs/task`
> [Sync] 2026-07-04: generated from the filled SUO-181 requirement template after the resource connector color-system drift report was triaged.

## 1. 任务标题

`SUO-181 Notion 资源连接器前端：颜色系统偏差修复`

## 2. 关联 Issue

| Field | Value |
|---|---|
| Issue ID | `SUO-181` |
| Title | `修复资源连接器页面颜色系统偏差` |
| Type | `frontend` |
| Priority | `medium` |
| Status | `in_progress` |
| Work mode | `standard` |
| Parent | `SUO-172` |
| Parent title | `IM 资源链接器业务代码实现` |
| Parent status | `blocked` |
| Blocked by | `none` |
| Labels | `none` |
| Pending comments | `0` |

## 3. 任务目标

- 将资源连接器页面的颜色、边框、背景、阴影、hover、focus 与状态表达收敛到 `docs/prd/color_system` 和现有暖纸张视觉语言。
- 清理 `ResourceConnectorPage.tsx` 中的 feature-scoped 自定义 RGBA、渐变和阴影写法，改用共享语义 token。
- 保持连接器业务行为不变，不改 API、数据流、导航结构或页面分层，只做视觉系统收敛。
- 如果 `App.tsx` 或 `TopNavBar.tsx` 在连接器入口附近带有同类配色漂移，一并收敛到同一套 token。
- 确保 light/dark 主题下的 connector 页面视觉一致性，避免引入新的孤立色板。

## 4. 任务范围

### In Scope

- `ResourceConnectorPage.tsx` 的页面壳、状态 pill、卡片、按钮、空状态、选择弹窗和 hover/focus 表现。
- 将页面中的颜色映射到 `frontend/src/styles/tokens.css` 里已有的语义 token。
- `App.tsx` 与 `TopNavBar.tsx` 中与 connector 页面同语境的背景、边框或按钮色偏差审查。
- 如确有 token 覆盖缺口，仅补最小的语义 token 映射，并同步到 color-system 文档语义，不引入 feature-only palette。
- 必要时同步更新被修改的 frontend 文件头注释，以保持仓库注释约定一致。

### Out of Scope

- 连接器 API、认证、资源选择、同步、状态机或数据契约调整。
- 导航体系重构、新 route、新布局框架或新的视觉探索方向。
- 修改 `docs/prd/color_system` 或 `docs/prd/notion-session` 的产品定义内容。
- 增加与当前问题无关的全局主题改造。
- 任何孤立十六进制色值或只服务于单个组件的私有色板。

## 5. 实现步骤

1. 审核 `ResourceConnectorPage.tsx` 中所有颜色、背景、边框、阴影、hover 与 focus 声明，标出所有 feature-scoped RGBA / 渐变 / 阴影常量。
2. 将这些声明逐项映射到 `tokens.css` 与 `docs/prd/color_system/light-theme.md` 已定义的语义 token，优先复用 `--color-bg-paper`、`--color-border-paper`、`--color-shadow-soft`、`--color-shadow-medium`、`--color-action-primary`、`--color-state-*` 等已有语义。
3. 收敛状态 pill、section card、source row、CTA button、empty state、modal surface 的颜色和层级，避免同一语义在不同组件里出现多个近似色值。
4. 检查 `App.tsx` 与 `TopNavBar.tsx` 中 connector 入口附近的视觉表现，只修复与 page shell 冲突的部分，不扩大到无关的 dashboard 视图。
5. 如果确实缺少可表达某个 connector 状态的 token，补最小语义映射到 `tokens.css`，并避免引入只被单个组件使用的私有颜色变量。
6. 跑前端构建并做 light / dark / hover / focus / empty-state / selection-modal 的最小视觉 smoke，确认页面不再依赖 feature-specific palette。

## 6. 涉及文件路径

| Path | Role |
|---|---|
| `frontend/src/components/dashboard/ResourceConnectorPage.tsx` | 主修复面，收敛 connector 页面颜色系统。 |
| `frontend/src/styles/tokens.css` | 共享 token source of truth，必要时补最小语义映射。 |
| `frontend/src/App.tsx` | App shell 与 connector entry 的背景 / 色调审查面。 |
| `frontend/src/components/TopNavBar.tsx` | 顶栏与 connector 页面相邻区域的视觉一致性审查面。 |
| `docs/prd/color_system/README.md` | 颜色系统总入口参考。 |
| `docs/prd/color_system/light-theme.md` | 亮色主题 token 与视觉规范参考。 |
| `docs/prd/notion-session/resource-connector.md` | 连接器页面产品范围和状态定义参考。 |
| `docs/prd/notion-session/resource-connector-ui-design.md` | 暖纸张视觉语言、组件结构与微交互参考。 |
| `frontend/tests/**` | 可选回归测试目录；仅在已存在或后续新增时使用。 |

## 7. 输入 / 输出说明

| Type | Details |
|---|---|
| 输入 | 现有 connector page 实现、token 定义、color-system PRD、resource-connector PRD/UI design、light/dark 主题行为。 |
| 输入 | connector 页面中的创建、认证、选择、来源浏览和空状态交互。 |
| 输出 | 资源连接器页面的颜色、边框、背景、阴影、hover、focus 与状态胶囊全部回到共享 token 体系。 |
| 输出 | 页面视觉与 `docs/prd/color_system` 一致，不再依赖孤立 feature palette。 |

## 8. 依赖项

- `docs/prd/color_system/README.md`
- `docs/prd/color_system/light-theme.md`
- `docs/prd/notion-session/resource-connector.md`
- `docs/prd/notion-session/resource-connector-ui-design.md`
- `frontend/src/styles/tokens.css`
- `frontend/src/components/dashboard/ResourceConnectorPage.tsx`
- `frontend/src/App.tsx`
- `frontend/src/components/TopNavBar.tsx`
- `SUO-172` as contextual parent issue

## 9. 测试策略

- 构建检查：`pnpm -C frontend build`
- 视觉 smoke：分别在 light 和 dark theme 下检查 connector 页面、状态 pill、卡片、CTA、空状态和选择弹窗。
- 交互 smoke：检查 hover / focus 反馈是否仍然符合颜色系统和可访问性要求。
- 代码审查式验证：确认 `ResourceConnectorPage.tsx` 中的 feature-specific RGBA / gradient / shadow 写法已被删除或收敛到共享 token。
- 如存在 frontend test tree，再补一个最小的视觉或 snapshot 回归覆盖 connector 页面状态。

## 10. 完成标志

- Connector page 的颜色、边框、背景和阴影主要来源于共享 token，而不是本地 feature palette。
- 资源连接器页面在 light / dark 两套主题下的关键状态保持一致。
- `App.tsx` 与 `TopNavBar.tsx` 中的 connector-adjacent 视觉不再和页面主体冲突。
- `pnpm -C frontend build` 通过。
- 视觉 smoke 能确认空状态、选择弹窗、hover / focus 与状态 pill 的色彩表达一致。

## 11. 风险提示

- 该页面目前大量使用 inline style，重构时容易把局部收敛误扩大成布局改动。
- 如果只改 `ResourceConnectorPage.tsx` 而不复查共享 token，dark theme 可能继续出现色偏。
- 过度替换为自定义颜色常量会再次产生 feature-scoped palette，违背色彩系统收敛目标。
- 若 `App.tsx` / `TopNavBar.tsx` 只是共享主题背景而非真实偏差，不要为对齐 connector 页面而误伤其他 dashboard 视图。
