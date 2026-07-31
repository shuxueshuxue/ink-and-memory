> [Input] `docs/design/memory/reflections-analysis-prd.md`,
>         `docs/design/lifecycle/claude-agent-lifecycle.md`,
>         `docs/design/claude-agent/claude-agent-session-persistence.md`,
>         `docs/design/claude-agent/sse-reconnect-and-event-bus.md`,
>         `docs/design/memory/reflections-agent-patterns-design.md`,
>         `docs/design/memory/reflections-agent-sse-eventbus-design.md`
> [Output] Reflections-agent business interaction design: problem judgment, first-release
>          implementation order, four-phase business lifecycle, persistence-first flow,
>          API draft, sequence diagrams, and anti-overdesign check.
> [Pos] reflections-agent-business-design in `docs/design/memory`
> [Sync] 2026-06-25: split from the original all-in-one draft. This file now keeps only
>         the business interaction design; design-pattern details and SSE/EventBus details
>         live in separate companion documents.

# Reflections-agent 业务交互设计稿

## 0. 任务规划 Prompt（本轮执行前置）

```text
You are an Expert Prompt Architect. Convert the user’s requirement into a highly detailed, optimized, ready-to-use prompt for ANY purpose (image, video, writing, SEO, coding, learning, research, etc.). Instructions Identify what the user is trying to achieve. Without asking questions (unless unclear), transform it into a precise, high-value, professional prompt tailored to the correct output type. Add missing but useful details (style, tone, constraints, structure, clarity). Ensure the prompt is copy-paste ready for the intended AI tool. Deliver: Optimized Prompt - the final refined prompt Optional Enhancers - optional add-ons that the user can include

OUTPUT FORMAT Optimized Prompt: [Expert-level prompt based on the requirement]

USER REQUIREMENT:
把上一版 Reflections-agent 设计稿拆分为三个边界清晰的文档：1）保留原有业务交互设计稿，专注业务目标、四阶段业务生命周期、持久化优先流程、API 与业务时序；2）新增设计模式设计稿，专注 Reflections-agent 如何使用生命周期、状态机、Observer、Repository、Runner/Executor、Workspace Adapter 等模式；3）新增 SSE/EventBus 设计稿，专注断线重连、事件总线、事件模型、订阅与回放、Observer 事件分发。按照推荐首版实现顺序组织内容：先持久化 task/result，再实现后端 task engine 四阶段，再接入 SSE/EventBus，最后补 Observer 接口和最小 TaskPersistenceObserver。只做设计稿拆分与细化，不实现音频/视频业务，不做过度设计。
```

---

## 1. 文档拆分边界

上一版设计稿把业务流程、设计模式、SSE/EventBus、Observer 和持久化方案放在一个文件中，阅读路径偏重。现拆成三份文档：

| 文档 | 职责 | 不包含 |
|---|---|---|
| 本文：`reflections-agent-interaction-design.md` | 业务问题判断、四阶段业务生命周期、首版实现顺序、API、业务时序、验收边界 | Observer 代码接口细节、SSE replay 细节 |
| `reflections-agent-patterns-design.md` | 生命周期、状态机、Observer、Repository、Runner/Executor、Workspace Adapter 等设计模式 | 页面 API 细节、SSE 协议细节 |
| `reflections-agent-sse-eventbus-design.md` | EventBus、SSE 订阅、断线重连、事件类型、回放、Observer 分发链路 | 业务字段完整 schema、UI 页面布局 |

---

## 2. 问题判断与处理结论

### 2.1 当前问题

Reflections 页面当前更像前端触发并等待结果的页面业务。原 PRD 已定义 echoes、traits、patterns 三个分区、Memory Workspace 文件结构和输出契约，但没有把“分析运行”明确建模为后端可追踪、可恢复、可持久化的异步任务。

| 风险 | 影响 | 处理方向 |
|---|---|---|
| 前端交互与分析任务生命周期耦合 | 页面卸载、刷新、网络中断时，用户容易误以为任务中断或结果丢失 | 后端 async task 为准，前端只订阅状态与读取结果 |
| 缺少统一生命周期 | 难以表达 queued/running/completed/failed，也难以复用 Claude Agent 模型 | 引入 Reflections-agent 四阶段生命周期 |
| 缺少任务级持久化 | 后续音频、视频模块无法可靠监听 Reflections 产物 | DB task/result/event 为真源，EventBus 只做同步通知 |

### 2.2 处理结论

Reflections 应从“前端页面动作”调整为“后端 Reflections-agent 异步任务”：

1. 前端点击 Generate Reflections 后只创建 `reflection_task`。
2. 后端 Task Engine 按四阶段执行，前端断开不取消任务。
3. UI 以 `reflection_result` 为展示真源。
4. EventBus/SSE 用于实时状态同步，不承担最终存储。
5. Observer 模式只预留模块监听边界，首版不实现音频/视频业务。

---

## 3. 推荐首版实现顺序

本次设计以“最小可落地、避免过度设计”为原则，首版按以下顺序实现。

### 3.1 Step 1 — 先实现 `reflection_task` + `reflection_result` 持久化

**目标**：先把任务与结果变成后端 truth source，避免 UI 内存状态成为事实来源。

必须包含：

- `reflection_task`：保存任务 metadata、状态、sections、workspace、input snapshot、错误摘要。
- `reflection_result`：保存 echoes/traits/patterns 的结构化洞察。
- 基础查询：latest task、task detail、task results。

暂不必须：

- 完整事件流表。
- SSE 断线重连。
- 音频/视频 Observer。

### 3.2 Step 2 — 再实现后端 Task Engine 四阶段

**目标**：让任务真正由后端执行，而不是页面同步等待。

必须包含：

- Phase 1：上下文组装。
- Phase 2：Runner/Executor 创建。
- Phase 3：section 串行分析执行。
- Phase 4：任务结束、状态收束与资源释放。

首版 section 执行顺序固定为 `echoes → traits → patterns`，不做并发调度。

### 3.3 Step 3 — 再接入 SSE/EventBus

**目标**：前端能看到实时进度，但任务不依赖 SSE 连接存活。

必须包含：

- task/section 基础事件发布。
- 前端必须采用 `create(auto_start=false) → subscribe SSE → start task` 顺序，确保实时事件不是只靠完成后的 replay。
- SSE 断开后可通过 task detail/results 恢复页面状态。

首版可以先使用进程内 EventBus；多实例部署时再升级 Redis Stream。

### 3.4 Step 4 — 最后补 Observer 接口和最小 `TaskPersistenceObserver`

**目标**：建立后续模块监听边界，但不提前实现复杂业务。

必须包含：

- `ReflectionTaskObserver` 抽象接口。
- `TaskPersistenceObserver`：把关键事件写入 `reflection_task_event`。
- Observer 异常隔离：Observer 失败不得导致 Reflections 主任务失败。

暂不做：

- 音频任务消费实现。
- 视频任务消费实现。
- 动态插件系统。

---

## 4. Reflections-agent 四阶段业务生命周期

```text
Phase 1                  Phase 2                  Phase 3                    Phase 4
上下文组装                Executor 创建             异步分析执行                任务结束/清理
─────────────────        ───────────────          ─────────────────────       ─────────────────
assemble_context          create_executor          execute_reflection_task     finalize_task
├─ 用户与权限校验          ├─ 创建 task runner       ├─ 按 section 执行 Agent     ├─ 写最终状态
├─ 读取日记/会话素材        ├─ 绑定 workspace cwd     ├─ 持久化 section 结果      ├─ 释放进程内状态
├─ 写 workspace prompt     ├─ 初始化 task state      ├─ 发布 task events         ├─ 发出最终事件
└─ 创建/更新 task 记录      └─ 准备事件通道           └─ 记录错误与部分成功        └─ workspace 保留/TTL
```

### 4.1 Phase 1 — 上下文组装

- 校验用户身份和 session 访问权限。
- 根据请求确定 sections，默认 `echoes/traits/patterns`。
- 查询候选日记/写作记录，生成轻量 `sessions_context`：只包含真实 session ID、日期、标题和 labels，不包含正文；Agent 后续按 ID/日期/labels 通过检索工具拉取正文。
- 创建 `{AGENT_CWD}/{reflection_task_id}/memory/` 工作空间。
- 写入分区 prompt 文件与 `analysis_state.json`。
- 创建或更新 `reflection_task`，状态流转到 `ASSEMBLING` / `QUEUED`。

### 4.2 Phase 2 — Executor 创建

- 获取 task lock，防止同一个 task 重复执行。
- 创建 `ReflectionsAgentRunner` 或轻量执行器包装。
- 绑定 task workspace。
- 初始化进程内 task state。
- 如果 Step 3 已接入 EventBus，则创建 task-scoped EventBus。

### 4.3 Phase 3 — 异步分析执行

- 更新 task 状态为 `RUNNING`。
- 串行执行 `echoes → traits → patterns`。
- 每个 section 完成后立即校验并写入 `reflection_result`。
- 单个 section 失败时记录错误，继续执行其他 section；全部失败才标记 `FAILED`。
- 部分成功时标记 `PARTIAL_FAILED`，UI 仍可展示成功 section。

### 4.4 Phase 4 — 任务结束与清理

- 写入最终状态、完成时间、错误摘要和耗时。
- 释放 runner、lock、subscriber 等进程内资源。
- workspace 首版默认保留用于调试，后续用 TTL 清理。
- 发布最终 task event；但前端 SSE 断开不等于 Phase 4。

---

## 5. 持久化设计（业务视角）

### 5.1 `reflection_task`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | `reflection_task_id` |
| `user_id` | INTEGER | 任务所属用户 |
| `status` | TEXT | `CREATED/ASSEMBLING/QUEUED/RUNNING/COMPLETED/PARTIAL_FAILED/FAILED` |
| `sections` | TEXT JSON | 本次执行分区列表 |
| `input_snapshot` | TEXT JSON | session ids、时间范围、模型参数摘要 |
| `workspace_path` | TEXT | task workspace |
| `agent_contract_version` | TEXT | Reflections-agent 契约版本 |
| `error_summary` | TEXT nullable | 失败摘要 |
| `created_at` | DATETIME | 创建时间 |
| `started_at` | DATETIME nullable | 开始时间 |
| `completed_at` | DATETIME nullable | 结束时间 |
| `updated_at` | DATETIME | 更新时间 |

### 5.2 `reflection_result`

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | result id |
| `task_id` | TEXT FK | 对应 task |
| `user_id` | INTEGER | 冗余便于查询和权限过滤 |
| `section` | TEXT | `echoes/traits/patterns` |
| `title` | TEXT | 洞察标题 |
| `description` | TEXT | 洞察描述 |
| `related_session_ids` | TEXT JSON | 关联 session ids |
| `evidence` | TEXT | 证据摘要 |
| `confidence` | TEXT | `high/medium/low` |
| `created_at` | DATETIME | 创建时间 |

### 5.3 `reflection_task_event`（Step 4 引入）

`reflection_task_event` 不应阻塞 Step 1/2。首版可以在 Observer 接入时补充，用于事件审计和 SSE 回放增强。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | TEXT PK | event id |
| `task_id` | TEXT FK | 对应 task |
| `event_type` | TEXT | 事件名 |
| `payload` | TEXT JSON | 事件 payload |
| `created_at` | DATETIME | 事件时间 |

---

## 6. API 交互草案

| API | 方法 | Step | 职责 |
|---|---|---:|---|
| `/api/reflections/tasks` | `POST` | 1/2 | 创建 Reflections 异步任务；前端实时流场景使用 `auto_start=false` |
| `/api/reflections/tasks/{task_id}/start` | `POST` | 2/3 | 在 SSE 订阅建立后启动任务，避免错过实时事件 |
| `/api/reflections/tasks/{task_id}` | `GET` | 1 | 查询任务状态、sections 进度、错误摘要 |
| `/api/reflections/tasks/{task_id}/results` | `GET` | 1 | 获取该任务的结构化结果 |
| `/api/reflections/latest` | `GET` | 1 | 获取用户最近一次 completed/partial_failed 结果 |
| `/api/reflections/tasks/{task_id}/events` | `GET SSE` | 3 | 订阅任务事件流 |
| `/api/reflections/tasks/{task_id}/retry` | `POST` | 后续 | 对失败任务重试，复用 input snapshot 或创建新 task |

---

## 7. 业务时序流程图

```mermaid
sequenceDiagram
    autonumber
    participant UI as Reflections Page
    participant API as Reflections API
    participant Engine as ReflectionsTaskEngine
    participant DB as SQLite DB
    participant WS as Memory Workspace
    participant Runner as ReflectionsAgentRunner
    participant Bus as EventBus/SSE

    UI->>API: POST /api/reflections/tasks {sections, filters, auto_start:false}
    API->>DB: create reflection_task(status=CREATED)
    API->>Bus: create task-scoped EventBus
    API-->>UI: 202 Accepted {task_id, status:CREATED}

    UI->>API: GET /api/reflections/tasks/{task_id}/events
    API->>Bus: subscribe(task_id)
    API-->>UI: SSE reflection.stream.connected

    UI->>API: POST /api/reflections/tasks/{task_id}/start
    API->>Engine: enqueue(task_id)
    API-->>UI: 202 Accepted {task_id}

    Engine->>DB: update task status=ASSEMBLING
    Engine->>DB: read user session metadata
    Engine->>WS: write prompt files + metadata-only sessions_context + analysis_state.json
    Engine->>DB: update task status=QUEUED
    Engine->>Bus: publish reflection.context.ready
    Bus-->>UI: SSE reflection.context.ready

    Engine->>DB: update task status=RUNNING
    Engine->>Bus: publish reflection.task.started
    Bus-->>UI: SSE reflection.task.started

    loop section in echoes, traits, patterns
        Engine->>Bus: publish reflection.section.started
        Bus-->>UI: SSE reflection.section.started
        Engine->>Runner: run_section(section, metadata-only sessions_context, workspace)
        Runner-->>Engine: JSON insights
        Engine->>Engine: validate schema and related_session_ids
        Engine->>DB: insert reflection_result rows
        Engine->>WS: update analysis_state.json
        Engine->>Bus: publish reflection.section.completed
        Bus-->>UI: SSE reflection.section.completed
    end

    Engine->>DB: update task status=COMPLETED, completed_at=now
    Engine->>Bus: publish reflection.task.completed
    Bus-->>UI: SSE reflection.task.completed and stream closes
    UI->>API: GET /api/reflections/tasks/{task_id}/results
    API->>DB: list reflection_result by task_id
    API-->>UI: render Reflections report
``

---

## 8. 方案验收与反过度设计检查

| 检查项 | 结论 | 说明 |
|---|---|---|
| 是否以后端异步任务为准 | 符合 | task 创建后由 Engine 执行，前端采用订阅后启动，避免错过实时 SSE |
| 是否按推荐顺序组织 | 符合 | Step 1 持久化、Step 2 Task Engine、Step 3 SSE/EventBus、Step 4 Observer |
| 是否拆分文档 | 符合 | 业务、设计模式、SSE/EventBus 三份文档职责分离 |
| 是否参考 Claude Agent 四阶段 | 符合 | Reflections 四阶段对应上下文、执行器、执行、结束清理 |
| 是否避免过度设计 | 符合 | 首版不做分布式工作流、section 并发、音频/视频真实消费 |

首版明确不做：

- 不实现音频、视频模块真实消费。
- 不引入复杂 DAG/workflow engine。
- 不做 section 并发调度。
- 不做 Observer 动态插件系统。
- 不把 EventBus 当最终存储。


## Language-bound Section Output

- Frontend task creation passes the current UI language (`i18n.language`) as `language`.
- Backend normalizes the language to `en` or `zh` and stores it in `reflection_task.input_snapshot`.
- For `echoes`, `traits`, and `patterns`, each `MEMORY_ANSWER_PROMPT.md` receives a runtime language requirement so user-facing `title`, `description`, and `evidence` match the current frontend language while JSON keys remain English.
