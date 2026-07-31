# Claude Agent 架构文档

**模块目标**：为 Ink & Memory 提供基于 Claude Code SDK 的流式 AI 写作助手后端能力，  
支持多轮对话、会话保活（Flyweight 会话池）、工具确认、SSE 流式输出，  
独立于现有 PolyCLI agent 模块，不与其产生交叉关联。

---

## 1. 目录结构

两层架构，与 Pawkeyland 源模块对应：

```
backend/
├── libs/
│   └── claude_agent_kit/               # Kit 层 ← 迁移自 Pawkeyland libs/claude_agent_kit/
│       ├── __init__.py                 # 公共导出（类型、Runner、Workspace）
│       ├── types.py                    # AgentRunOptions/Result/Callbacks/ToolEventPayload
│       ├── messages/                   # SDK user message content builder
│       ├── server/
│           ├── agent_runner.py         # ClaudeAgentRunner — SDK 封装
│           ├── sdk_env.py              # backend/.env 注入和 runtime env 映射
│           └── workspace.py            # 会话工作区目录管理
│       └── .folder.md
│
└── claude_agent/                       # 应用层 ← 迁移自 Pawkeyland application/claude_agent/
    ├── __init__.py                     # 公共导出（应用层 + kit 层 re-export）供 server.py 使用
    ├── observer.py                     # SessionLifecycleObserver、SessionObserverRegistry
    ├── tool_confirmation_store.py      # ToolConfirmationStore — asyncio.Future 工具确认
    ├── thread_pool.py                  # AgentRunState、AgentRunStatePool、Sweeper — TTL 会话池
    ├── context_builder.py              # ClaudeAgentContextBuilder — 写作会话 system_prompt
    ├── service.py                      # ClaudeAgentService — Phase 1 & 3 业务逻辑
    ├── thread_factory.py               # ClaudeAgentThreadFactory — 四阶段编排入口
    └── .folder.md
```

**单向依赖**：`claude_agent/` → `libs/claude_agent_kit/`，kit 层不依赖应用层。  
**隔离说明**：`claude_agent` 模块与现有 PolyCLI `agent` 会话完全独立，不共享注册表、状态或导入。

---

## 2. API 发布点

所有端点前缀 `/api/claude-agent/*`，在 `server.py` 内直接注册（与现有路由同文件，无子路由模块）。

| Method   | Path                                | Handler                       | 认证 | 描述                             |
|----------|-------------------------------------|-------------------------------|------|----------------------------------|
| `POST`   | `/api/claude-agent`                 | `claude_agent_stream`         | JWT  | SSE 流式聊天，委托 ThreadFactory |
| `GET`    | `/api/claude-agent/chat-history`    | `claude_agent_chat_history`   | JWT  | 按 user_id 加载历史消息          |
| `GET`    | `/api/claude-agent/threads`         | `claude_agent_list_threads`   | JWT  | 列出 Chat thread；可选 `query` / `retrieval_mode` 搜索标题与消息文本 |
| `POST`   | `/api/claude-agent/message-latency` | `claude_agent_message_latency`| JWT  | 上报浏览器延迟指标               |
| `GET`    | `/api/claude-agent/session`         | `claude_agent_session_status` | JWT  | 查询 Thread Session 保活快照     |
| `DELETE` | `/api/claude-agent/session`         | `claude_agent_session_close`  | JWT  | 主动销毁会话                     |
| `POST`   | `/api/claude-agent/threads/{thread_id}/stop` | `claude_agent_stop_thread` | JWT  | 主动停止当前运行 turn，不删除 thread |
| `POST`   | `/api/claude-agent/tool-confirm`    | `claude_agent_tool_confirm`   | JWT  | 工具人工确认/拒绝                |

---

## 3. 后端分层设计

```
HTTP 层 (server.py)
    ↓  ClaudeAgentRequest / ToolConfirmRequest
ThreadFactory (thread_factory.py)
    ↓  每 session 一把 asyncio.Lock，串行化并发请求
    Phase 1  context_builder  → 组装 system_prompt + 写作上下文
    Phase 2  server/agent_runner.py → 创建 ClaudeAgentRunner（cached）
    Phase 3  service.py       → 执行流式对话，写 DB，发 SSE 事件
    Phase 4  (销毁时)          → 触发 SessionObserver
    ↓  AgentRunStatePool (thread_pool.py)
        AgentRunState (Flyweight)
        AgentRunStateSweeper (TTL 清理)
```

### 四阶段生命周期

| 阶段 | 职责 | 触发时机 |
|------|------|----------|
| Phase 1 | 组装 system_prompt、获取近期写作会话上下文 | 每轮请求（首轮完整构建，续轮复用缓存） |
| Phase 2 | 创建 ClaudeAgentRunner（Claude Code SDK 实例）| 首次 session 创建；TTL 过期后重建 |
| Phase 3 | 执行流式对话、持久化消息、发送 SSE 事件 | 每轮请求 |
| Phase 4 | 触发 SessionObserver.on_session_ended | 仅在销毁时（close_thread / TTL 驱逐 / aclose）|

---

## 4. 迁移映射表（Pawkeyland → Ink & Memory）

| Pawkeyland 源路径 | Ink & Memory 目标路径 | 迁移说明 |
|-------------------|-----------------------|----------|
| `application/claude_agent/observer.py` | `backend/claude_agent/observer.py` | 直接迁移，无变化 |
| `application/claude_agent/tool_confirmation_store.py` | `backend/claude_agent/tool_confirmation_store.py` | 直接迁移，无变化 |
| `application/claude_agent/thread_pool.py` | `backend/claude_agent/thread_pool.py` | 简化：移除 pet/persona/mem0/resolved_identity 字段 |
| `application/claude_agent/thread_factory.py` | `backend/claude_agent/thread_factory.py` | 适配：session_id = user_id，移除宠物相关逻辑 |
| `application/claude_agent/context_builder.py` | `backend/claude_agent/context_builder.py` | 重写：用写作会话上下文替换 pet/persona 上下文 |
| `application/claude_agent/service.py` | `backend/claude_agent/service.py` | 大幅简化：移除 pet/persona/mem0/sticker_filter |
| `libs/claude_agent_kit/types.py` | `backend/libs/claude_agent_kit/types.py` | 直接迁移，移除 Pawkeyland 特定注释 |
| `libs/claude_agent_kit/server/agent_runner.py` | `backend/libs/claude_agent_kit/server/agent_runner.py` | 直接迁移，保留 streaming / tool confirmation / error handling |
| `libs/claude_agent_kit/server/workspace.py` | `backend/libs/claude_agent_kit/server/workspace.py` | 适配：保留工作区骨架、项目模板同步、sandbox settings，并接入 skills 同步 |
| `libs/claude_agent_kit/server/workspace_file_sync.py` | `backend/libs/claude_agent_kit/server/workspace_file_sync.py` | 适配：维护 `workspace/skills` ↔ `.claude/skills`，导入 `.claude/skills` 真实写入后重建发现软链接 |
| `libs/claude_agent_kit/server/sdk_env.py` | `backend/libs/claude_agent_kit/server/sdk_env.py` | 改为直接读取 `backend/.env` 中 Claude Code / Anthropic SDK key |
| `libs/volcresource/cfg.py` | _(不迁移)_ | Volcengine 图像/OSS 与专属 runtime 配置均不属于 Ink & Memory 当前范围 |
| `application/claude_agent/state_builder.py` | _(内联至 thread_pool.py)_ | 代码量极小（111行），直接内联 |

**未迁移内容**（见第 9 节）：

- `libs/claude_agent_kit/server/mcp_server.py` — Pawkeyland 宠物专属 MCP
- `libs/claude_agent_kit/server/necklace_*.py` — 项圈硬件 MCP
- `libs/claude_agent_kit/server/memory_*.py` — Mem0 记忆 MCP
- `libs/claude_agent_kit/server/touch_animation_tool.py` — 动画工具

---

## 5. 配置与环境变量

所有运行时配置通过环境变量解析，不硬编码业务值。  
Ink & Memory 的 Claude Code SDK 鉴权和模型配置直接使用 `ANTHROPIC_*`；`INK_AGENT_*` 仅用于本项目的会话和 Mem0 配置。

### 5.1 Agent SDK 配置

直接在 `backend/.env` 中配置 Claude Code SDK 所需的 `ANTHROPIC_*` 变量；`server/sdk_env.py` 会把这些 key 合并到 SDK 子进程环境。

| 环境变量（`.env`）| 默认值 | 用途 |
|-------------------|--------|------|
| `ANTHROPIC_AUTH_TOKEN` | 无 | Claude Auth Token |
| `ANTHROPIC_BASE_URL` | 无（官方端点）| API Base URL（代理场景使用）|
| `ANTHROPIC_MODEL` | 无（SDK 默认）| 模型名 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | 无 | 可选 Haiku 默认模型别名 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | 无 | 可选 Sonnet 默认模型别名 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | 无 | 可选 Opus 默认模型别名 |
| `API_TIMEOUT_MS` | `3000000` | SDK API 超时 |
| `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC` | `1` | 禁用非必要 Claude Code 流量 |

### 5.2 会话保活配置

| 环境变量 | 默认值 | 用途 |
|----------|--------|------|
| `INK_AGENT_TTL_S` | `600` | Thread Session 保活 TTL（秒） |
| `INK_AGENT_SWEEP_INTERVAL_S` | `60` | 后台 Sweeper 清理周期（秒） |
| `INK_AGENT_SSE_KEEPALIVE_S` | `15` | SSE keepalive 注释帧间隔（秒） |

### 5.3 功能配置

| 环境变量 | 默认值 | 用途 |
|----------|--------|------|
| `INK_AGENT_MAX_TURNS` | `100` | 每轮对话最大 Agent turn 数 |
| `AGENT_CWD` | `{tmpdir}/claude-agent-workspaces` | 工作区根目录（绝对路径）|
| `INK_AGENT_CONTEXT_SESSIONS` | `5` | 注入写作上下文的最近会话数 |

### 5.4 Mem0 记忆配置

当前迁移版 Claude Agent Kit 仍保留 memory MCP/hook 配置入口，因此 `.env.example` 保留以下 Mem0 服务配置；请求态身份和消息（`INK_AGENT_MEM0_USER_ID` / `INK_AGENT_USER_MESSAGE` / `MEM0_USER_ID`）由运行时注入，不写入 `.env`。旧 `PAWKEYLAND_*` Mem0 变量仍作为兼容 fallback 读取，但不再作为模板推荐命名。

| 环境变量 | 默认值 | 用途 |
|----------|--------|------|
| `INK_AGENT_MEM0_ENABLED` | `true` | 是否启用 Mem0 服务配置 |
| `INK_AGENT_MEM0_API_KEY` | 无 | Mem0 API Key |
| `INK_AGENT_MEM0_API_HOST` | 无 | Mem0 API Host |
| `INK_AGENT_MEM0_CONNECT_TIMEOUT_MS` | `1500` | Mem0 连接超时 |
| `INK_AGENT_MEM0_READ_TIMEOUT_MS` | `8000` | Mem0 读取超时 |
| `INK_AGENT_MEM0_TOP_K` | `10` | 记忆召回数量 |
| `INK_AGENT_ENABLE_MEMORY_MCP` | `1` | 是否启用 memory stdio MCP |

---

## 6. 数据流

```
POST /api/claude-agent
    │
    ├─ get_current_user()  ← JWT 认证
    │
    ├─ ClaudeAgentRequest 解析
    │   └─ user_id, message, resume, max_turns, cwd, model
    │
    ├─ claude_agent_thread_factory.run_streaming(request)
    │   │
    │   ├─ Phase 1: context_builder
    │   │   ├─ 查询 database.list_sessions(user_id) → 近期写作会话
    │   │   └─ 拼装 system_prompt（Ink & Memory 写作助手角色）
    │   │
    │   ├─ Phase 2: server/agent_runner.py
    │   │   └─ ClaudeAgentRunner(session_id, cwd)
    │   │       └─ env: ANTHROPIC_* → Claude SDK subprocess
    │   │
    │   └─ Phase 3: service.py
    │       ├─ runner.run_streaming(opts, callbacks)
    │       │   └─ claude_agent_sdk.query() → AsyncGenerator[SDKMessage]
    │       ├─ 写 SSE 事件流
    │       │   ├─ text-delta, text-done
    │       │   ├─ tool-event
    │       │   ├─ message-final
    │       │   └─ finish / error
    │       └─ （可扩展）持久化消息到 DB
    │
    └─ StreamingResponse (text/event-stream)
```

---

## 7. 错误处理

| 场景 | 处理方式 | SSE 事件 |
|------|----------|----------|
| JWT 认证失败 | FastAPI `HTTPException(401)` | — |
| session_id 非法字符 | `ValueError` → `HTTPException(400)` | — |
| SDK 执行错误 | 捕获异常，记录日志 | `error` 事件 |
| 工具确认超时 | `TimeoutError` → 默认拒绝 | `error` 事件 |
| SSE 客户端断连 | `GeneratorExit` → cancel_pending | — |
| TTL 过期 | Sweeper 驱逐，触发 Phase 4 Observer | — |

---

## 8. 测试与验证策略

与现有 `backend/tests/` 保持一致，使用自定义 Python 脚本（无 pytest）。

| 测试文件（建议路径） | 测试内容 |
|----------------------|----------|
| `backend/tests/test_claude_agent.py` | HTTP 端点集成测试（需要 server:8765 和有效 SDK 配置）|
| `backend/tests/ci-smoke.sh` 扩展 | 新增 claude-agent register → stream → close 冒烟 |

---

## 9. 未迁移内容

| 内容 | 不迁移原因 |
|------|-----------|
| Mem0 gateway 实现 | 当前仅保留 Claude Agent memory MCP/hook 配置入口；正式网关实现未迁入 |
| 项圈 MCP (`necklace_*.py`) | IoT 硬件，Ink & Memory 无此设备 |
| 触摸动画工具 (`touch_animation_tool.py`) | Pawkeyland UI 专属，Ink & Memory 无动画层 |
| 宠物 MCP (`mcp_server.py`) | Pawkeyland 宠物领域专属，与 Ink & Memory 无关 |
| `state_builder.py` | 代码极少（111行），内联至 thread_pool.py |
| `session_files.py` | JSONL 会话文件解析，当前版本通过 DB 替代 |
| `libs/volcresource/cfg.py` | Pawkeyland 专属资源和 runtime 配置，Ink & Memory 当前不迁移 |
| `api/contracts.py` | Pawkeyland 路由契约，Ink & Memory 直接用 Pydantic 在 server.py |

---

## 10. 与现有 agent 模块的隔离说明

| 维度 | PolyCLI agent（现有）| claude_agent（新增）|
|------|----------------------|---------------------|
| 注册方式 | `@session_def(...)` → `/polycli` 挂载 | `@app.post/get/delete(...)` → `/api/claude-agent/*` |
| SDK | PolyCLI / PolyAgent | claude_agent_sdk |
| 会话管理 | PolyCLI session registry | AgentRunStatePool（Flyweight）|
| 鉴权 | `auth_callback=auth.verify_access_token` | `Depends(get_current_user)`（同现有 REST 路由）|
| 数据库 | `server.py` 内直接调用 database | `service.py` 内调用 database（只读写作会话）|
| 导入关系 | `claude_agent` **不导入** PolyCLI 任何模块 | PolyCLI 模块 **不导入** claude_agent |
