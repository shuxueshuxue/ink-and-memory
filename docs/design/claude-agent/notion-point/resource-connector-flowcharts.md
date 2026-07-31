# Resource Connector — 业务流程图

Status: Draft  
Updated: 2026-07-07
Scope: 设计 — 资源连接器全链路业务流程图（含四层交互泳道）

> [Input] `docs/design/notion-session/overview.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
> [Output] 资源连接器各核心业务流程的 Mermaid 流程图与泳道图
> [Pos] resource-connector-flowcharts in `docs/design/claude-agent/notion-point`
> [Sync] 2026-06-22: 初始设计 — 业务流程图集
> [Sync] 2026-06-22: 迁移至 claude-agent/notion-point — 工作空间映射相关设计独立管理
> [Sync] 2026-06-28: 业务流程图收敛到 canonical snapshot 模型；Agent 消费不再以本地缓存/lazy load 作为权威数据来源。
> [Sync] 2026-07-07: 业务起点改为 Chat 入口页，下方 landing tabs 承载历史对话与连接器工作台。

---

## 目录

1. [全链路业务流程](#1-全链路业务流程)
2. [认证流程图](#2-认证流程图)
3. [数据同步流程图](#3-数据同步流程图)
4. [Agent 消费流程图](#4-agent-消费流程图)
5. [任务调度流程图](#5-任务调度流程图)
6. [四层协作泳道图](#6-四层协作泳道图)
7. [错误处理流程图](#7-错误处理流程图)
8. [状态转换全景图](#8-状态转换全景图)

---

## 1. 全链路业务流程

### 1.1 端到端流程概览

```mermaid
flowchart TD
    A[用户打开 Chat 入口页] --> B{切换到连接器 Tab}
    B --> C{选择平台}
    C -->|Notion| D[创建 Notion 资源连接器]
    C -->|GitHub| Z1[Future: GitHub 连接器]
    C -->|Google Drive| Z2[Future: GDrive 连接器]

    D --> E[Auth Layer: 发起 ntn login]
    E --> F[用户浏览器确认]
    F --> G{认证成功?}
    G -->|是| H[Auth Layer: 状态→AUTHENTICATED]
    G -->|否/超时| I[Auth Layer: 状态→EXPIRED]
    I --> E

    H --> J[Operation Layer: 搜索可访问 Database]
    J --> K[Operation Layer: 搜索 Standalone Pages]
    K --> L[用户选择要同步的资源]
    L --> M[Task Layer: 提交全量同步任务]
    M --> N[Data Layer: 全量同步远程数据]
    N --> O[Data Layer: 物化 canonical snapshot]
    O --> P[连接器创建完成 ✓]

    P --> Q[用户进入对话]
    Q --> R[Agent init attach current snapshot]
    R --> S[.notion/ 虚拟索引从同一 snapshotVersion 读取]
    S --> T[Agent 展示 Notion 内容]
```

### 1.2 核心业务节点

| 节点 | 负责层 | 关键输出 |
|------|--------|---------|
| 创建连接器 | — | `resource_connectors` 表记录 |
| 认证 | Auth Layer | `AuthCredential` |
| 资源发现 | Operation Layer | Database/Page 列表 |
| 用户选择 | 前端 | `selected_databases` + `selected_pages` |
| 数据同步 | Task Layer + Data Layer | canonical snapshot |
| Agent 消费 | Data Layer | PreToolUse → attached snapshot |

---

## 2. 认证流程图

### 2.1 ntn login 认证时序

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端
    participant BE as 后端 (Auth Layer)
    participant CLI as ntn CLI
    participant NTN as Notion 服务器

    U->>FE: 点击"连接 Notion"
    FE->>BE: POST /api/connectors/:id/auth/login

    BE->>BE: 创建 NOTION_HOME 目录
    BE->>CLI: ntn login --no-browser
    CLI->>NTN: 请求 Device Code
    NTN-->>CLI: verification_url + code
    CLI-->>BE: stdout: URL + Code

    BE->>BE: 解析 verification_url, code
    BE-->>FE: {verification_url, code, poll_interval}
    FE->>U: 展示验证码 + "打开浏览器确认"

    U->>NTN: 浏览器访问 URL，确认验证码

    loop 轮询认证状态 (每 5s)
        FE->>BE: POST /api/connectors/:id/auth/poll
        BE->>CLI: ntn login poll
        alt 用户尚未确认
            CLI-->>BE: exit 1 (pending)
            BE-->>FE: {status: "pending"}
        else 用户已确认
            CLI-->>BE: exit 0 (success)
            CLI->>CLI: 写入 token → NOTION_HOME
            BE->>CLI: ntn auth status
            CLI-->>BE: authenticated
            BE->>BE: 更新状态 → AUTHENTICATED
            BE-->>FE: {status: "authenticated"}
        else 超时
            BE-->>FE: {status: "expired", error: "timeout"}
        end
    end
```

### 2.2 认证状态流转

```mermaid
stateDiagram-v2
    [*] --> INITIAL: 创建连接器
    INITIAL --> PENDING: 发起 ntn login
    PENDING --> AUTHENTICATED: 用户确认 + ntn auth status ✓
    PENDING --> EXPIRED: 超时 (300s)
    AUTHENTICATED --> EXPIRED: API 返回 401 / token 文件丢失
    EXPIRED --> PENDING: 用户重新认证
    AUTHENTICATED --> [*]: 用户主动断开
```

### 2.3 Token 刷新流程

```mermaid
flowchart TD
    A[定时任务: AUTH_VERIFY] --> B[Auth Layer: verify_status]
    B --> C{ntn auth status}
    C -->|exit 0| D[状态保持 AUTHENTICATED]
    C -->|exit 1| E[标记 EXPIRED]
    E --> F[发布事件: AUTH_EXPIRED]
    F --> G[Data Layer: 标记 current snapshot 为 stale]
    F --> H[通知前端: 需要重新认证]
```

---

## 3. 数据同步流程图

### 3.1 全量同步流程

```mermaid
flowchart TD
    A[Task Layer: 提交 FULL_SYNC 任务] --> B[验证认证状态]
    B --> C{AUTHENTICATED?}
    C -->|否| D[任务失败: AUTH_EXPIRED]
    C -->|是| E[Operation Layer: search databases]

    E --> F[获取 Database 列表]
    F --> G[过滤用户选定的 Databases]
    G --> H{还有未同步的 DB?}

    H -->|是| I[Operation Layer: query_database]
    I --> J[获取 DB 下 Row Pages]
    J --> K[Data Layer: 收集 DB row pages]
    K --> L[更新进度: completed_items++]
    L --> H

    H -->|否| M[Operation Layer: search pages]
    M --> N[获取 Standalone Pages]
    N --> O[过滤用户选定的 Pages]
    O --> P[Data Layer: 物化 CanonicalWorkspaceSnapshot]
    P --> Q[Data Layer: 更新 current snapshot pointer]
    Q --> R[任务完成 ✓]
    R --> S[发布事件: SNAPSHOT_MATERIALIZED]
```

### 3.2 增量同步流程

```mermaid
flowchart TD
    A[Task Layer: 提交 INCREMENTAL_SYNC] --> B[加载 SyncCheckpoint]
    B --> C[Operation Layer: search 按 last_edited 排序]
    C --> D[比较 checkpoint.last_sync_at]
    D --> E{有变更页面?}

    E -->|否| F[更新 checkpoint.last_sync_at]
    F --> G[任务完成: 无变更]

    E -->|是| H[收集变更 page_id 列表]
    H --> I{变更数 > 阈值?}
    I -->|是 (>50%)| J[降级为全量同步]
    I -->|否| K[逐页同步变更]

    K --> L[Operation Layer: get changed pages]
    L --> M[Data Layer: 物化新 snapshotVersion]
    M --> N[旧 snapshot → snapshot_superseded]
    N --> O[更新 checkpoint/current pointer]
    O --> P[任务完成 ✓]
```

### 3.3 快照缺页处理

```mermaid
flowchart TD
    A[Agent: read_file .notion/pages/abc.json] --> B[PreToolUse 拦截]
    B --> C[Data Layer: resolve from attached snapshot]
    C --> D{page 在当前 snapshot 中?}

    D -->|是| E[返回 page + snapshot identity]
    D -->|否| F[返回 snapshot-scoped miss]
    F --> G[Agent 提示用户刷新连接器或选择已同步页面]
    G --> H[前端可触发 Sync now]
    H --> I[Data Layer 物化新 snapshotVersion]
```

---

## 4. Agent 消费流程图

### 4.1 Workspace Init → .notion/ 初始化

```mermaid
flowchart TD
    A[用户进入对话] --> B[workspace.init_workspace]
    B --> C[_init_editor_index 现有逻辑]
    C --> D{connector 配置存在?}

    D -->|否| E[跳过 .notion/ 初始化]
    D -->|是| F{auth_status == AUTHENTICATED?}

    F -->|否| G[注入提示: "Notion 连接器需要重新认证"]
    F -->|是| H[创建 .notion/ 目录结构]

    H --> I[写入 README.md 引导文件]
    I --> J[写入占位 snapshot/index/databases JSON]
    J --> K[Service: attach current canonical snapshot]
    K --> L{snapshot_ready?}

    L -->|否| M[注入提示: 需要同步或重新认证]
    L -->|是| N[注入 workspace_context + snapshot identity]
```

### 4.2 Agent 对话中消费 Notion 数据

```mermaid
sequenceDiagram
    participant User as 用户
    participant Agent as Claude Agent
    participant Service as ClaudeAgentService
    participant Hook as PreToolUse Hook
    participant Data as Data Layer

    User->>Agent: "帮我查看 Notion 阅读笔记"
    Service->>Data: get_current_snapshot(workspaceId, connectorId)
    Data-->>Service: CanonicalWorkspaceSnapshot{snapshotVersion}
    Service-->>Agent: workspace_context + attached snapshot

    Agent->>Hook: Read(".notion/snapshot.json")
    Hook->>Data: resolve from attached snapshot
    Data-->>Hook: snapshot identity
    Hook-->>Agent: JSON 内容

    Agent->>Hook: Read(".notion/connector.json")
    Hook->>Data: resolve from same snapshotVersion
    Data-->>Hook: connector 元信息
    Hook-->>Agent: JSON 内容

    Agent->>Hook: Read(".notion/databases/db-002.json")
    Hook->>Data: resolve from same snapshotVersion
    Data-->>Hook: database pages + snapshot identity
    Hook-->>Agent: db-002.json 内容

    Agent->>Hook: Read(".notion/pages/page-xyz.json")
    Hook->>Data: resolve from same snapshotVersion
    Data-->>Hook: page content or snapshot-scoped miss
    Hook-->>Agent: page-xyz.json 内容

    Agent-->>User: "阅读笔记中有 15 条记录，最近的是《xxx》..."
```

---

## 5. 任务调度流程图

### 5.1 定时任务注册与执行

```mermaid
flowchart TD
    A[连接器认证成功] --> B[Task Layer: register_schedules]
    B --> C[注册 INCREMENTAL_SYNC: */30 * * * *]
    B --> D[注册 AUTH_VERIFY: 0 * * * *]
    B --> E[注册 FULL_SYNC: 0 3 * * *]
    B --> F[注册 SNAPSHOT_ARCHIVE_CLEANUP: 0 4 * * *]

    C --> G{Cron 触发?}
    G -->|是| H[检查并发锁]
    H --> I{同类任务正在运行?}
    I -->|是| J[跳过本次执行]
    I -->|否| K[创建 Task 实体]
    K --> L[TaskOrchestrator.execute]
    L --> M{执行结果}
    M -->|成功| N[状态 → COMPLETED]
    M -->|失败| O{可重试?}
    O -->|是| P[状态 → RETRYING]
    P --> Q[指数退避等待]
    Q --> L
    O -->|否| R[状态 → FAILED]
    R --> S[发布 SYNC_FAILED 事件]
```

### 5.2 批量 Import 工作流

```mermaid
flowchart TD
    A[用户修改资源选择: 新增 Database] --> B[Task Layer: 提交 BATCH_IMPORT]
    B --> C[计算差异: 新增/移除的资源]
    C --> D{有新增资源?}

    D -->|是| E[并发控制: Semaphore(5)]
    E --> F[逐资源提交子任务]
    F --> G[Operation: query_database / get_page]
    G --> H[Data Layer: 收集资源内容]
    H --> I[更新进度: completed++]
    I --> J{所有子任务完成?}
    J -->|否| F
    J -->|是| K[物化新 canonical snapshot]

    D -->|有移除资源| L[Data Layer: 从新 snapshot 中移除资源]
    L --> M[旧 snapshot → snapshot_superseded]

    K --> N[任务完成]
    M --> N
```

---

## 6. 四层协作泳道图

### 6.1 创建连接器完整泳道

```mermaid
sequenceDiagram
    participant FE as 前端
    participant Task as Task Layer
    participant Auth as Auth Layer
    participant Ops as Operation Layer
    participant Data as Data Layer
    participant Bus as Event Bus

    Note over FE,Bus: === Entry: Chat landing connector tab ===
    Note over FE,Bus: === Phase 1: 认证 ===
    FE->>Auth: init_login(user_id)
    Auth->>Auth: ntn login --no-browser
    Auth-->>FE: LoginInitResult{url, code}
    FE->>FE: 展示验证码，等待用户确认
    FE->>Auth: poll_login(user_id)
    Auth->>Auth: ntn login poll → exit 0
    Auth-->>FE: AuthCredential{AUTHENTICATED}
    Auth->>Bus: publish(AUTH_COMPLETED)

    Note over FE,Bus: === Phase 2: 资源发现 ===
    FE->>Ops: search(filter=database)
    Ops->>Ops: ntn api v1/search
    Ops-->>FE: SearchResult{databases[]}
    FE->>Ops: search(filter=page)
    Ops->>Ops: ntn api v1/search
    Ops-->>FE: SearchResult{pages[]}
    FE->>FE: 用户选择要同步的资源

    Note over FE,Bus: === Phase 3: 数据同步 ===
    FE->>Task: submit(FULL_SYNC, connector_id)
    Task->>Auth: verify_status(user_id)
    Auth-->>Task: AuthCredential{AUTHENTICATED}
    Task->>Ops: query_database(db_id) × N
    Ops-->>Task: Row Pages[]
    Task->>Data: sync_full(workspace_id, connector_id)
    Data->>Data: 物化 canonical snapshot
    Data-->>Task: SyncResult{snapshot_identity}
    Task->>Bus: publish(SNAPSHOT_MATERIALIZED)
    Task-->>FE: Task{COMPLETED}
```

### 6.2 Agent 对话消费泳道

```mermaid
sequenceDiagram
    participant Agent as Claude Agent
    participant Service as ClaudeAgentService
    participant Hook as PreToolUse
    participant Data as Data Layer
    participant Bus as Event Bus

    Note over Agent,Bus: === Workspace Init ===
    Service->>Data: get_current_snapshot(workspaceId, connectorId)
    Data-->>Service: CanonicalWorkspaceSnapshot{snapshotVersion}
    Service-->>Agent: workspace_context + attached snapshot

    Note over Agent,Bus: === Agent 读取 ===
    Agent->>Hook: Read(".notion/snapshot.json")
    Hook->>Data: resolve from attached snapshot
    Data-->>Hook: snapshot identity
    Hook-->>Agent: snapshot.json 内容

    Agent->>Hook: Read(".notion/index.json")
    Hook->>Data: resolve from same snapshotVersion
    Data-->>Hook: index + snapshot identity
    Hook-->>Agent: index.json 内容

    Note over Agent,Bus: === Page Read ===
    Agent->>Hook: Read(".notion/pages/page-001.json")
    Hook->>Data: resolve from same snapshotVersion
    Data->>Bus: publish(PAGE_ACCESSED)
    Data-->>Hook: page content or snapshot-scoped miss
    Hook-->>Agent: page-001.json 内容
```

---

## 7. 错误处理流程图

### 7.1 统一错误处理策略

```mermaid
flowchart TD
    A[操作执行] --> B{返回结果}
    B -->|成功| C[正常流程]
    B -->|失败| D{错误类型判断}

    D -->|AuthTokenExpiredError| E[Auth Layer: 标记 EXPIRED]
    E --> F[Event Bus: AUTH_EXPIRED]
    F --> G[Data Layer: 标记 current snapshot stale]
    F --> H[通知前端: 需重新认证]

    D -->|RateLimitError| I{重试次数 < max?}
    I -->|是| J[指数退避等待]
    J --> K[retry_delay × 2^(retry_count)]
    K --> A
    I -->|否| L[任务失败: 限流超过最大重试]

    D -->|OperationTimeoutError| M{重试次数 < max?}
    M -->|是| J
    M -->|否| N[任务失败: 超时]

    D -->|ResourceNotFoundError| O[Data Layer: 物化移除该资源的新 snapshot]
    O --> P[旧 snapshot → snapshot_superseded]

    D -->|AuthCLINotFoundError| Q[返回友好错误]
    Q --> R[提示用户安装 ntn CLI]

    D -->|OperationConflictError| S[保持旧 snapshot 只读]
    S --> T[进入 conflict，要求刷新或重新生成 proposal]
```

### 7.2 认证降级策略

```mermaid
flowchart TD
    A[任何 API 调用] --> B{响应状态}
    B -->|401 Unauthorized| C[Auth Layer: verify_status]
    C --> D{ntn auth status}
    D -->|exit 0 有效| E[可能是权限问题]
    E --> F[记录错误, 跳过该资源]
    D -->|exit 1 无效| G[Token 确实过期]
    G --> H[Auth: status → EXPIRED]
    H --> I[暂停所有进行中的 Task]
    I --> J[等待用户重新认证]
    J --> K[Auth: status → AUTHENTICATED]
    K --> L[恢复暂停的 Task]
```

---

## 8. 状态转换全景图

### 8.1 连接器生命周期

```mermaid
stateDiagram-v2
    [*] --> Created: POST /api/connectors

    state Created {
        [*] --> Configuring
        Configuring --> AuthPending: 发起认证
    }

    state Active {
        [*] --> Authenticated
        Authenticated --> Syncing: 触发同步
        Syncing --> Authenticated: 同步完成
        Syncing --> SyncFailed: 同步失败
        SyncFailed --> Syncing: 重试
        SyncFailed --> Authenticated: 放弃重试
    }

    state Degraded {
        [*] --> AuthExpired
        AuthExpired --> ReAuth: 用户重新认证
    }

    Created --> Active: 认证成功
    Active --> Degraded: Token 过期
    Degraded --> Active: 重新认证成功
    Active --> [*]: 用户删除连接器
    Degraded --> [*]: 用户删除连接器
```

### 8.2 Snapshot 状态生命周期

```mermaid
stateDiagram-v2
    [*] --> pending_sync: 创建连接器

    pending_sync --> synced: 远程同步成功
    synced --> snapshot_ready: 物化 canonical snapshot
    snapshot_ready --> agent_attached: Agent init / workspace attach
    agent_attached --> derived_context_ready: Agent 裁剪/摘要

    derived_context_ready --> write_proposed: 产生 proposal
    write_proposed --> write_pending_remote: 用户批准
    write_pending_remote --> write_confirmed: Notion 确认
    write_confirmed --> synced: 重新同步

    snapshot_ready --> snapshot_superseded: 新版本生成
    agent_attached --> stale: sourceRevision 变化
    write_proposed --> conflict: base identity 不匹配

    snapshot_ready --> permission_denied: 权限不足
    snapshot_ready --> connector_unavailable: 数据层不可用
```

### 8.3 任务状态全景

```mermaid
stateDiagram-v2
    [*] --> CREATED: submit()

    CREATED --> RUNNING: execute()
    RUNNING --> COMPLETED: 所有步骤成功
    RUNNING --> RETRYING: 可重试错误发生
    RUNNING --> FAILED: 不可重试错误

    RETRYING --> RUNNING: 退避等待后重试
    RETRYING --> FAILED: 超过 max_retries

    CREATED --> CANCELLED: cancel()
    RUNNING --> CANCELLED: cancel()

    COMPLETED --> [*]
    FAILED --> [*]
    CANCELLED --> [*]
```

---

## 附录: 流程图索引

| 流程图 | 覆盖层 | 核心关注点 |
|--------|--------|-----------|
| 1.1 端到端概览 | 全部 | 用户视角的完整旅程 |
| 2.1 认证时序 | Auth | ntn login 协议细节 |
| 2.2 认证状态流转 | Auth | 状态机 |
| 2.3 Token 刷新 | Auth + Task | 定时校验 |
| 3.1 全量同步 | Task + Ops + Data | 同步工作流 |
| 3.2 增量同步 | Task + Data | 变更检测 |
| 3.3 快照缺页 | Data | snapshot-scoped miss |
| 4.1 Workspace Init | Data + Auth | 初始化 |
| 4.2 Agent 消费 | 全部 | Agent 读取链路 |
| 5.1 定时调度 | Task | Cron + 并发 |
| 5.2 批量 Import | Task + Ops + Data | 资源变更 |
| 6.1 创建泳道 | 全部 | 四层协作 |
| 6.2 消费泳道 | 全部 | 四层协作 |
| 7.1 错误处理 | 全部 | 统一错误策略 |
| 7.2 认证降级 | Auth + Task | 降级恢复 |
| 8.1 连接器生命周期 | 全部 | 全局状态 |
| 8.2 Snapshot 生命周期 | Data | 快照版本与冲突策略 |
| 8.3 任务状态 | Task | 任务管理 |

---
