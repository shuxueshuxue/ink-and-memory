> **迁移来源**: Pawkeyland docs/app/design/AI Model 会话流程图.md — 路径和环境变量已适配 Ink & Memory 工程规范。

# AI Model 会话流程图

> **迁移来源**: Pawkeyland docs/app/design/AI Model 会话流程图.md — 路径和环境变量已适配 Ink & Memory 工程规范。

> **说明**：本文包含通用 AI 会话流程（Phase 1–3，下方各节均适用）和 Pawkeyland 宠物专属流程（Thread Session 享元生命周期、贴纸/动画部分）。宠物专属部分已在对应节添加注释，通用流程照原文保留。

## 基础的业务对话流程

```mermaid
flowchart TB
  %% 主干：强制垂直排列
  subgraph MAIN[" "]
    direction TB
    A["📋 System<br/>系统提示词/上下文/外部服务"]
    B["🤖 AI<br/>Agent"]
    D{"Agent执行<br/>外部信息获取"}
    G["💬 Response<br/>生成响应"]
    C["👤 User<br/>用户消息"]

    A -->|初始化上下文| B
    B -->|发起对话| D
    D -->|处理完成| G
    G -->|返回给用户| C
  end

  %% 右侧回路：用不可见节点做"折线/右侧上行"，避免把User拉到上面
  C -->|输入查询| R1(( ))
  R1 --> R2(( ))
  R2 --> B

  %% 样式
  style A fill:#e1f5ff,stroke:#7aa7ff,stroke-width:1px
  style B fill:#fff3e0,stroke:#f2b36a,stroke-width:1px
  style D fill:#ecebff,stroke:#7a6ff0,stroke-width:1px
  style G fill:#ffe0b2,stroke:#f2b36a,stroke-width:1px
  style C fill:#f3e5f5,stroke:#c08bd6,stroke-width:1px

  %% 让拐点"隐形"，只留下右侧折线路径
  style R1 fill:transparent,stroke:transparent,color:transparent
  style R2 fill:transparent,stroke:transparent,color:transparent

```

## AI服务系统时序图

```mermaid
sequenceDiagram
  autonumber
  actor U as 👤 User（用户）
  participant SYS as 📋 System Runtime / Orchestrator（系统编排）
  participant CTX as 🧠 Prompt & Context Store（提示词/上下文）
  participant AG as 🤖 AI Agent（执行单元）
  participant EXT as 🌐 External Services（外部服务/工具）

  Note over SYS,CTX: 系统启动/会话初始化
  SYS->>CTX: Load System Prompt + Policies + Session Context
  CTX-->>SYS: Prompt/Context Bundle
  SYS->>AG: Initialize(agent, bundle)
  AG-->>SYS: Ready

  Note over U,SYS: 用户发起一次查询（输入查询）
  U->>SYS: User Message / Query
  SYS->>AG: Run(query, session_state)

  alt 需要外部信息（工具/检索/调用）
    AG->>SYS: Request tool/use_external_info(intent)
    SYS->>EXT: Call API / Search / DB Query
    EXT-->>SYS: External Results
    SYS->>AG: Provide(results)
  else 不需要外部信息
    AG-->>SYS: Draft Answer (no external)
  end

  Note over SYS,AG: 生成最终响应（可加审计/格式化）
  AG-->>SYS: Final Answer + Metadata
  SYS-->>U: 💬 Response（返回给用户）

  Note over SYS,CTX: 会话结束后的状态回写（可选）
  SYS->>CTX: Persist(conversation_state, memories)
  CTX-->>SYS: Ack

```

## transfrom模型模板架构

```mermaid

graph LR
    subgraph Inputs[输入层]
      S["📋 System Prompt\\n系统提示词"]
      U["👤 User Message\\n用户输入"]
      TDef["🔧 Tool Spec\\n工具定义/Schema"]
    end

    subgraph Model[🤖 AI Model]
      Planner["📑 Planner\\n决定是否用工具"]
      Generator["💬 Generator\\n生成回复或 tool call"]
    end

    subgraph Outputs[输出层]
      Call["🔧 Tool Call\\n模型生成的调用"]
      Resp["✅ Assistant Reply\\n最终回复"]
    end

    S --> Ctx
    U --> Ctx
    TDef --> Ctx
    Ctx --> Planner
    Planner --> Generator
    Generator --> Call
    Generator --> Resp

    style Inputs fill:#e1f5ff
    style Model fill:#fff3e0
    style Outputs fill:#ffe0b2

```

## 有确认事件的业务对话流程

```mermaid
flowchart TB
  %% 主干：强制垂直排列
  subgraph MAIN[" "]
    direction TB
    A["📋 System<br/>系统提示词/上下文/外部服务"]
    B["🤖 AI<br/>Agent"]

    F["📝 对话确认<br/>说明将要做什么/请求授权或补充信息"]
    H{"用户确认？"}

    D{"Agent执行<br/>外部信息获取"}
    G["💬 Response<br/>生成响应"]
    C["👤 User<br/>用户消息"]

    A -->|初始化上下文| B
    B -->|发起对话| F
    F -->|发出确认问题| H

    H -->|✅ 确认/继续| D
    H -->|❌ 取消/修改需求| G

    D -->|处理完成| G
    G -->|返回给用户| C
  end

  %% 右侧回路1：用户输入查询 -> Agent（保持你原来的"输入查询"右侧上行）
  C -->|输入查询| R1(( ))
  R1 --> R2(( ))
  R2 --> B

  %% 右侧回路2：用户对"确认问题"的回复 -> 确认判断（新增）
  C -->|确认/补充| R3(( ))
  R3 --> R4(( ))
  R4 --> H

  %% 样式
  style A fill:#e1f5ff,stroke:#7aa7ff,stroke-width:1px
  style B fill:#fff3e0,stroke:#f2b36a,stroke-width:1px

  style F fill:#eef7ff,stroke:#7aa7ff,stroke-width:1px
  style H fill:#ecebff,stroke:#7a6ff0,stroke-width:1px

  style D fill:#ecebff,stroke:#7a6ff0,stroke-width:1px
  style G fill:#ffe0b2,stroke:#f2b36a,stroke-width:1px
  style C fill:#f3e5f5,stroke:#c08bd6,stroke-width:1px

  %% 让拐点"隐形"，只留下右侧折线路径
  style R1 fill:transparent,stroke:transparent,color:transparent
  style R2 fill:transparent,stroke:transparent,color:transparent
  style R3 fill:transparent,stroke:transparent,color:transparent
  style R4 fill:transparent,stroke:transparent,color:transparent

```

## 有确认事件的AI服务系统时序图

```mermaid
sequenceDiagram
  autonumber
  actor U as 👤 User
  participant SYS as 📋 System Runtime / Orchestrator
  participant CTX as 🧠 Prompt & Context Store
  participant AG as 🤖 AI Agent
  participant EXT as 🌐 External Services

  Note over SYS,CTX: 会话初始化
  SYS->>CTX: Load system prompt + policies + session context
  CTX-->>SYS: Context bundle
  SYS->>AG: Initialize(bundle)
  AG-->>SYS: Ready

  Note over U,SYS: 用户输入
  U->>SYS: User message / query
  SYS->>AG: Run(query, session_state)

  loop Agent执行阶段（可多轮）
    opt 执行中触发确认事件（ask_user）
      AG->>SYS: Need confirmation / missing params / permission
      SYS-->>U: Ask user to confirm / provide details
      U-->>SYS: Confirm / provide details / cancel
      alt 用户确认/补充
        SYS->>AG: Continue with user input
      else 用户取消/停止
        SYS->>AG: Stop execution
      end
    end

    opt 需要外部信息（工具调用）
      AG->>SYS: Request tool call (intent)
      SYS->>EXT: Call API / Search / DB query
      EXT-->>SYS: Results
      SYS->>AG: Provide results
    end
  end

  Note over SYS,U: 生成并返回响应
  AG-->>SYS: Final answer + metadata
  SYS-->>U: 💬 Response

  opt 会话状态回写（可选）
    SYS->>CTX: Persist updated session state
    CTX-->>SYS: Ack
  end

```

## 与有确认事件的前端组件与AI服务系统交互的时序图

```mermaid
sequenceDiagram
  autonumber
  actor U as 👤 User（用户）
  participant FE as 🖥️ Frontend App / UI（前端）
  participant SYS as 📋 System Runtime / Orchestrator（系统编排）
  participant CTX as 🧠 Prompt & Context Store（提示词/上下文）
  participant AG as 🤖 AI Agent（执行单元）
  participant EXT as 🌐 External Services（外部服务/工具）

  Note over SYS,CTX: 会话初始化
  SYS->>CTX: Load system prompt + policies + session context
  CTX-->>SYS: Context bundle
  SYS->>AG: Initialize(bundle)
  AG-->>SYS: Ready

  Note over U,FE: 用户输入
  U->>FE: Send message
  FE->>SYS: Chat request (includes user message)
  SYS->>AG: Run(query, session_state)

  loop Agent执行阶段（可多轮）
    opt 执行中触发确认事件（ask_user）
      AG->>SYS: Need confirmation / missing params / permission
      SYS-->>FE: Ask user to confirm / provide details
      FE-->>U: Render confirmation prompt
      U-->>FE: Confirm / provide details / cancel
      FE-->>SYS: User decision / details
      alt 用户确认/补充
        SYS->>AG: Continue with user input
      else 用户取消/停止
        SYS->>AG: Stop execution
      end
    end

    opt 需要外部信息（Manual Tool Invocation via canUseTool）
      AG->>SYS: Propose tool call (intent)
      Note over SYS: canUseTool 回调拦截工具调用<br/>toolChoice="manual" 时触发
      SYS-->>FE: SSE: tool-input-available
      Note over FE: isManualToolInvocation=true<br/>part.state="input-available"<br/>Show [Approve]/[Reject]
      FE-->>U: Render Approve / Reject controls
      U-->>FE: Click Approve or Reject
      FE->>SYS: POST /api/claude-agent/tool-confirm<br/>{toolCallId, approved: true|false}

      alt approved = true
        Note over SYS: canUseTool 返回<br/>{ behavior: "allow" }
        SYS->>EXT: Execute tool call (API / Search / DB)
        EXT-->>SYS: Results
        SYS->>AG: Provide results
      else approved = false
        Note over SYS: canUseTool 返回<br/>{ behavior: "deny", message: "..." }
        SYS->>AG: Tool blocked, provide rejection reason
      end
    end
  end

  Note over FE,U: 流式返回响应
  AG-->>SYS: Final answer + metadata
  SYS-->>FE: Stream output
  FE-->>U: Render streamed response

  opt 会话状态回写（可选）
    SYS->>CTX: Persist updated session state
    CTX-->>SYS: Ack
  end

```

## Thread Session — sessionId 享元生命周期（Ink & Memory 落地）

> _(Pawkeyland 专属背景说明：原文的落地动机包括"角色扮演状态加载之前"的宠物系统上下文、DB 身份解析、Mem0 binding，这些属于 Pawkeyland 专属。Ink & Memory 中不适用这些步骤，但 Thread Session 的享元模式本身（workspace 初始化、ClaudeAgentRunner 创建的享元复用）同样适用)_

> 关联设计：[claude-agent-thread-session-patterns.md](./claude-agent-thread-session-patterns.md)、[claude-agent-session-persistence.md §10](./claude-agent-session-persistence.md#10-thread-session--进程内-sessionid-享元层)
>
> 落地动机：在标准"Init → Run → External Info → Response"模型上，把 *上下文加载之前* 的重型组件（workspace 初始化、系统上下文构建、ClaudeAgentRunner 创建）提取为 `session_id` 享元，由 `ClaudeAgentThreadFactory` + `AgentRunStatePool` 维护。

### 4 阶段生命周期总览

```mermaid
stateDiagram-v2
    direction TB
    [*] --> Phase1_FirstTurn : 首轮 / TTL 重建后第 1 轮<br/>(state.turn_count == 0)

    state "Phase 1 — Context Assembly (首轮)" as Phase1_FirstTurn {
        [*] --> BuildSystemPrompt : _context_builder.system_prompt
        BuildSystemPrompt --> InitWorkspace : get_or_create_workspace
        InitWorkspace --> BuildExtrinsic : user_message + AgentRunOptions + 5 callbacks + _TurnContext
        BuildExtrinsic --> [*] : 全部回写 state
    }

    Phase1_FirstTurn --> Phase2 : Service 返回 _TurnExecution

    state "Phase 2 — Runner Creation" as Phase2 {
        [*] --> CheckRunner : state.runner is None?
        CheckRunner --> CreateRunner : YES → create_agent_runner()
        CheckRunner --> ReuseRunner : NO  → 复用 state.runner
        CreateRunner --> [*] : 写回 state.runner
        ReuseRunner --> [*]
    }

    Phase2 --> Phase3 : execution.runner = state.runner

    state "Phase 3 — Session Start" as Phase3 {
        [*] --> RunStreaming : Service.execute_session<br/>state.runner.run_streaming(opts, callbacks)
        RunStreaming --> StreamSSE : SDKMessage → callbacks → queue
        StreamSSE --> Persist : 成功 → _persist_conversation
        Persist --> [*] : queue.put(None) sentinel
    }

    Phase3 --> TurnEnd : Factory finally
    TurnEnd : 清空 extrinsic 三件套 + turn_context\nstate.mark_idle()\nturn_count++, last_active_at 刷新\n**不发 Phase 4 钩子**

    TurnEnd --> Phase1_NextTurn : 续轮（TTL 内，state 仍 IDLE）
    state "Phase 1 — Context Assembly (续轮)" as Phase1_NextTurn {
        [*] --> ShortCircuit : 享元短路：system_prompt / cwd 直接读取
        ShortCircuit --> RebuildExtrinsic : 仅重建 user_message / AgentRunOptions / callbacks / turn_context
        RebuildExtrinsic --> [*]
    }
    Phase1_NextTurn --> Phase2

    TurnEnd --> Phase4 : close_thread / TTL Sweeper / aclose

    state "Phase 4 — Session End (State 销毁)" as Phase4 {
        [*] --> EmitBeforeEnded : emit_before_session_ended(session_id)
        EmitBeforeEnded --> Destroy : pool.destroy(session_id) → mark_destroyed()<br/>state.runner = None, turn_context = None
        Destroy --> EmitAfterEnded : emit_after_session_ended(session_id, {reason, destroyed, turn_count?})
        EmitAfterEnded --> [*]
    }
    Phase4 --> [*]
```

> _(Pawkeyland 原文中 Phase 1 首轮还包含 `ResolveIdentity` / `BuildPersistedPet` / `ResolveMem0` / `Mem0Preflight` 步骤，属于 Pawkeyland 专属，Ink & Memory 中不适用)_

### 时序图（含享元命中 / 不命中分支）

```mermaid
sequenceDiagram
    autonumber
    actor Client as 👤 调用方
    participant Factory as ⚙️ ClaudeAgentThreadFactory
    participant Pool as 📦 AgentRunStatePool
    participant State as 🧬 AgentRunState (Flyweight)
    participant Svc as 🧠 ClaudeAgentService
    participant Runner as 🛠️ ClaudeAgentRunner
    participant SDK as 🌐 Claude Code SDK
    participant DB as 💾 chat_session + claude_message
    participant Obs as 👁️ SessionObserverRegistry

    Client->>Factory: run_streaming(request)
    Factory->>Pool: evict_expired() (TTL 清理)
    Factory->>Pool: get_or_create(session_id) → state

    Note over Factory,Obs: Phase 1 — Context Assembly
    Factory->>Obs: emit_before_context_assembly(session_id, metadata)
    Factory->>Svc: assemble_context(request, state, queue)

    alt state.turn_count == 0（首轮 / TTL 重建后）
        Svc->>Svc: build_system_prompt → state.system_prompt
        Svc->>Svc: get_or_create_workspace → state.cwd
    else state.turn_count > 0（续轮，享元命中）
        Note over Svc,State: 跳过 system_prompt / cwd 重建，**仅** 重建 extrinsic
    end

    Svc->>DB: load_conversation_by_user → existing.claude_session_id
    Svc->>State: state.{user_message, callbacks, run_options, turn_context} 写回
    Svc-->>Factory: _TurnExecution(runner=None)
    Factory->>Obs: emit_after_context_assembly(session_id, metadata)

    Note over Factory,Runner: Phase 2 — Runner Creation
    Factory->>Obs: emit_before_runner_created(session_id)
    alt state.runner is None
        Factory->>Runner: create_agent_runner()
        Factory->>State: state.runner = runner
    else 享元命中
        Note over Factory,State: 复用 state.runner
    end
    Factory->>Obs: emit_after_runner_created(session_id, state.runner)

    Note over Factory,SDK: Phase 3 — Session Start
    Factory->>State: mark_running()
    Factory->>Obs: emit_before_session_started(session_id, opts)
    Factory->>Svc: execute_session(execution) [后台 Task]
    Svc->>Runner: state.runner.run_streaming(opts, callbacks)
    Runner->>SDK: query_stream(...)
    loop SSE 流
        SDK-->>Runner: SDKMessage
        Runner-->>Svc: callbacks → state.turn_context.queue
        Svc-->>Factory: queue 漏斗
        Factory-->>Client: yield SSE event
    end
    Runner-->>Svc: AgentRunResult(captured_session_id)
    Svc->>DB: _persist_conversation (UPSERT chat_session + APPEND claude_message)
    Svc->>Factory: queue.put(None) sentinel
    Factory->>Obs: emit_after_session_started(session_id)

    Note over Factory,State: 每轮收尾（不是 Phase 4）
    Factory->>State: 清空 extrinsic + turn_context
    Factory->>State: mark_idle() → turn_count++, last_active_at 刷新

    Note over Client,Obs: 等待下一轮 / TTL 销毁

    alt close_thread / TTL Sweeper / aclose
        Factory->>Obs: emit_before_session_ended(session_id)
        Factory->>Pool: destroy(session_id) → mark_destroyed
        Factory->>Obs: emit_after_session_ended(session_id, {reason, turn_count?, destroyed:True})
    end
```

> _(Pawkeyland 原文时序图中 Phase 1 首轮还包含 `IdentityService` / `load_agent_pet` / `PetMemoryService` / `Mem0 preflight` 步骤，属于 Pawkeyland 专属，Ink & Memory 中不适用)_

### 设计模式分工

| 模式 | 落地类 | 职责 |
|---|---|---|
| **Observer** | `SessionLifecycleObserver` / `SessionObserverRegistry` / `LoggingObserver` | 8 个生命周期钩子（4 阶段 × before/after），把工厂的"生产者"语义和服务的"消费者"语义解耦；外部业务（日志、持久化、监控、A/B）以 Observer 形态接入 |
| **Flyweight + State** | `AgentRunState` / `AgentRunStatePool` / `AgentRunStateSweeper` | 跨轮共享 intrinsic 组件（system_prompt / cwd / runner），按 `session_id` 享元；State 模式管理 `IDLE / RUNNING / DESTROYED` 转移 |
| **Builder** | `AgentRunStateBuilder` | 流式构造 `AgentRunState`；`with_session_id(session_id)` 由 Pool 在 `get_or_create` 时调用 |
| **Factory** | `ClaudeAgentThreadFactory` | 唯一对外入口；隐藏 Observer 注册、Pool 管理、`asyncio.Lock` 排队、Sweeper 调度等内部细节，对外仅暴露 `run_streaming(request)` / `confirm_tool` / `close_thread` / `aclose` / `register_observer` |

> _(Pawkeyland 原文中 Flyweight 还包含 `persisted_pet_info` / `mem0_user_id` / `resolved_identity`，属于 Pawkeyland 专属，Ink & Memory 中不适用)_

---

## 宠物专属表情贴纸提示词生成交互流程

> _(Pawkeyland 专属，Ink & Memory 中不适用)_
>
> 以下流程图描述 Pawkeyland 宠物 Agent 的贴纸 token 渲染机制，保留为设计参考。Ink & Memory 中没有贴纸/动画机制，无需实现。

### 场景 A：对话内嵌贴纸（sticker token 渲染）

```mermaid
flowchart TB
  subgraph INIT[会话初始化]
    direction TB
    SP["📋 system_policies.txt<br/>注入：sticker_enum 9 项枚举<br/>token 格式：[sticker:sticker_id]"]
    B["🤖 Claude Agent"]
    SP -->|会话级注入| B
  end

  subgraph CONV[每轮对话]
    direction TB
    UM["👤 user_message<br/>[当前环境] / [宠物状态] / [长期记忆]"]
    DECIDE{"情绪匹配<br/>贴纸枚举？"}
    TOKEN["📎 生成带贴纸 token 的文本<br/>例：好开心 [sticker:kaixin]"]
    PLAIN["💬 纯文本回复<br/>（无合适贴纸时）"]

    UM --> B
    B --> DECIDE
    DECIDE -->|✅ 有匹配| TOKEN
    DECIDE -->|❌ 无匹配| PLAIN
  end

  subgraph RENDER[前端渲染]
    direction TB
    FE["🖥️ 前端解析 [sticker:sticker_id]"]
    IMG["🖼️ 渲染贴纸图像<br/>（sticker_enum.json → media_key → CDN URL）"]
    FE --> IMG
  end

  TOKEN --> FE

  style SP fill:#e1f5ff,stroke:#7aa7ff
  style B fill:#fff3e0,stroke:#f2b36a
  style UM fill:#f3e5f5,stroke:#c08bd6
  style DECIDE fill:#ecebff,stroke:#7a6ff0
  style TOKEN fill:#ffe0b2,stroke:#f2b36a
  style FE fill:#e8f5e9,stroke:#66bb6a
  style IMG fill:#e8f5e9,stroke:#66bb6a
```

> _(Pawkeyland 专属，Ink & Memory 中不适用)_

### 场景 B（不适用）

> 宠物贴纸图像在**角色创建时**（`POST /api/character/create`）由 `PetMediaService` 一次性生成并存入 OSS。Claude Agent 对话期间**不触发**贴纸生成，仅通过 `[sticker:sticker_id]` token 引用已有图像（见场景 A）。

> _(Pawkeyland 专属，Ink & Memory 中不适用)_

### 贴纸提示词上下文注入位置总览

```mermaid
graph LR
    subgraph Inputs[输入层]
      SP["📋 system_prompt<br/>system_policies.txt<br/>贴纸枚举 + token 规则"]
      UM["👤 user_message 前缀<br/>[当前环境] pet_id<br/>[宠物当前状态] curr_mood"]
    end

    subgraph Model[🤖 Claude Agent]
      Planner["📑 Planner<br/>决定：是否插入贴纸 token"]
      Generator["💬 Generator<br/>生成含 [sticker:xxx] 文本"]
    end

    subgraph Outputs[输出层]
      Token["📎 贴纸 token<br/>[sticker:sticker_id]<br/>→ 前端渲染已有图像"]
      Resp["✅ 纯文本回复<br/>无合适贴纸时"]
    end

    SP --> Planner
    UM --> Planner
    Planner --> Generator
    Generator --> Token
    Generator --> Resp

    style Inputs fill:#e1f5ff
    style Model fill:#fff3e0
    style Outputs fill:#ffe0b2
```

> _(Pawkeyland 专属，Ink & Memory 中不适用)_
