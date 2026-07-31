# Test Suite

## Overview

Organized test suite for the Ink & Memory backend deck system.

## Test Structure

```
tests/
├── __init__.py                          # Test package init
├── test_database.py                     # Database layer tests (CRUD operations)
├── test_api_endpoints.py                # API integration tests (HTTP endpoints)
│
│ # Claude Agent module tests (migrated from Pawkeyland scripts/)
├── test_claude_agent_workspace.py       # Workspace lifecycle: root resolution, skeleton, idempotency
├── test_workspace_router.py             # Workspace router: download header encoding
├── test_claude_agent_context_builder.py # Context builder: system_prompt assembly, session rendering
├── test_sessions_tool.py                # Agent get_sessions_range retrieval params and vector boundary
├── test_notion_snapshot_contract.py     # Notion canonical snapshot path resolution and staleness checks
├── test_notion_auth.py                  # Notion CLI auth helpers and login polling
├── test_notion_store.py                 # Notion connector persistence and snapshot identity
├── test_notion_connector_router_flow.py # Notion connector router business flow (create/auth/discover/select/sync)
├── test_chat_thread_retrieval.py        # Chat history thread search retrievers and vector boundary
├── test_claude_agent_runner.py          # Runner: streaming callbacks, session_id, error handling
├── test_claude_agent_thread_factory.py  # Factory: flyweight cache, TTL eviction, Phase 1-4 contracts
├── test_server_claude_agent.py          # Server smoke: route registration, auth enforcement, models
└── test_seo_content.py                  # SEO robots/sitemap/llms content generators
```

## Running Tests

### Run All Tests
```bash
cd backend
chmod +x run_tests.sh
./run_tests.sh
```

### Run Individual Tests

**Database Layer Only:**
```bash
source .venv/bin/activate
python tests/test_database.py
```

**API Endpoints Only** (requires server running):
```bash
# Terminal 1: Start server
source .venv/bin/activate
python server.py

# Terminal 2: Run tests
source .venv/bin/activate
python tests/test_api_endpoints.py
```

**Claude Agent — Workspace (no server/SDK needed):**
```bash
source .venv/bin/activate
python tests/test_claude_agent_workspace.py -v
```

**Workspace Router (no server/SDK needed):**
```bash
source .venv/bin/activate
python tests/test_workspace_router.py -v
```

**Claude Agent — Context Builder (no server/SDK needed):**
```bash
source .venv/bin/activate
python tests/test_claude_agent_context_builder.py -v
```

**Notion Connector — Snapshot Contract (no server/SDK needed):**
```bash
source .venv/bin/activate
python tests/test_notion_snapshot_contract.py -v
```

**Claude Agent — Session Retrieval Tool (no server/SDK needed):**
```bash
source .venv/bin/activate
python tests/test_sessions_tool.py -v
```

**Notion Connector — Auth / Store (no server/SDK needed):**
```bash
source .venv/bin/activate
python tests/test_notion_auth.py -v
python tests/test_notion_store.py -v
```

**Notion Connector — Router Flow (no server/SDK needed):**
```bash
source .venv/bin/activate
python tests/test_notion_connector_router_flow.py -v
```

**Claude Agent — Chat History Retrieval (no server/SDK needed):**
```bash
source .venv/bin/activate
python tests/test_chat_thread_retrieval.py -v
```

**Claude Agent — Runner (mocks SDK, no server needed):**
```bash
source .venv/bin/activate
python tests/test_claude_agent_runner.py -v
```

**Claude Agent — Thread Factory (mocks SDK, no server needed):**
```bash
source .venv/bin/activate
python tests/test_claude_agent_thread_factory.py -v
```

**Claude Agent — Server Routes (import-level smoke, no SDK needed):**
```bash
source .venv/bin/activate
python tests/test_server_claude_agent.py -v
```

**SEO Content Generators (no server needed):**
```bash
source .venv/bin/activate
python tests/test_seo_content.py -v
```

## Test Coverage

### Claude Agent — Workspace (`test_claude_agent_workspace.py`)
- ✅ `get_workspace_root` — AGENT_CWD 优先，fallback 到 `ink-agent-workspaces`
- ✅ `init_workspace` — 创建 files/logs/.claude 骨架，幂等，自动修复
- ✅ `get_or_create_workspace` — 同 session 返回相同路径
- ✅ `_validate_session_id` — 拒绝 `/` `\\` `..` 路径穿越

### Workspace Router (`test_workspace_router.py`)
- ✅ `GET /api/workspace/files/download` — 中文等非 Latin 文件名使用 Latin-1-safe `filename` fallback + UTF-8 `filename*`

### Claude Agent — Context Builder (`test_claude_agent_context_builder.py`)
- ✅ `_render_session_entry` — 日期/标题/摘要字段渲染
- ✅ `build_system_prompt` — 包含写作助手角色定位、近期会话块
- ✅ `build_system_prompt(..., configured_system_prompt=...)` — Settings SYSTEM_PROMPT 作为低优先级配置块渲染
- ✅ 空会话回退为 "No recent entries found"
- ✅ `context_session_count` 截断（只取前 N 条）
- ✅ DB 异常时优雅降级（不抛，返回无会话 prompt）
- ✅ `build_user_message` — 运行时上下文前缀、时区注入

### Claude Agent — Session Retrieval Tool (`test_sessions_tool.py`)
- ✅ 日期范围旧调用保持兼容
- ✅ `query` 使用正文文本做字符模糊匹配并过滤无关候选
- ✅ `labels` 支持 `label_match=all`
- ✅ `retrieval_mode=auto` 在未配置向量库时降级 fuzzy
- ✅ `retrieval_mode=vector` 返回未配置错误且不访问数据库

### Claude Agent — Chat History Retrieval (`test_chat_thread_retrieval.py`)
- ✅ Chat thread title fuzzy search
- ✅ Persisted message-text fuzzy search
- ✅ `search_scope=title` excludes message-only matches
- ✅ `retrieval_mode=auto` downgrades unconfigured vector query to fuzzy
- ✅ `retrieval_mode=vector` reports unavailable without a vector store

### Claude Agent — Runner (`test_claude_agent_runner.py`)
- ✅ `on_text_delta` — AssistantMessage 文本块触发，full_text 正确累积
- ✅ `on_text_done` — 流结束后收到完整拼接文本
- ✅ `on_tool_event` — tool_use 块触发，携带正确 ToolEventPayload (name/id/input)
- ✅ 多个 tool_use 块各自独立触发事件
- ✅ `on_tool_confirmation_request` — tool_choice='manual' 时触发；auto 时不触发
- ✅ SDK 异常触发 `on_error` + `AgentRunResult(success=False)` + 后台 `logger.exception` 堆栈日志
- ✅ `BaseExceptionGroup` 包装 CLI 失败（文档化行为，需 runner 扩展后生效）
- ✅ 纯 `CancelledError` / 纯取消 BaseExceptionGroup 被重新抛出（on_error 不吞）
- ✅ `session_id` 从 ResultMessage 提取
- ✅ StreamEvent text_delta / thinking_delta 被 runner 分发
- ✅ `INK_AGENT_MEM0_*` / `INK_AGENT_ENABLE_MEMORY_MCP` 优先于旧 Mem0 env 别名
- ✅ `ANTHROPIC_AUTH_TOKEN` 作为 Claude Code SDK auth 诊断依据
- ✅ SDK dotenv helper 只向子进程转发 Claude Code / Anthropic 相关 key

### Claude Agent — Thread Factory (`test_claude_agent_thread_factory.py`)
- ✅ Phase 2：runner 在 session 内创建一次，跨 turn 复用
- ✅ TTL 过期驱逐：`INK_AGENT_TTL_S` 控制
- ✅ `close_thread`：销毁 session，清除 runner 缓存
- ✅ Phase 1 extrinsic state：每 turn 写入后清空
- ✅ Phase 4 observer hooks：`session_ended` 在销毁时触发
- ✅ 不同 session_id 独立隔离

### Claude Agent — Service / Route (`test_claude_agent_service.py`, `test_server_claude_agent.py`)
- ✅ `get_system_config.system_prompt` 注入 Phase 1 system_prompt 组装
- ✅ Settings SYSTEM_PROMPT 变化时重建 cached system_prompt
- ✅ `workspace_enabled=false` 时跳过 `get_or_create_workspace`，`AgentRunOptions.cwd=None`
- ✅ 附件请求在 Workspace Mode 关闭时不初始化 workspace、不调用 workspace file sync
- ✅ Workspace attach materializes canonical Notion snapshot into workspace-local `.notion/`
- ✅ Notion connector router registration and auth enforcement remain exposed through `server.py`

### Claude Agent — Server (`test_server_claude_agent.py`)
- ✅ 6 个 `/api/claude-agent/*` 路由已注册
- ✅ 启动时清理不支持的 Agent env key，同时保留 Mem0/session 配置
- ✅ `ClaudeAgentRequestBody` 默认值和必填字段
- ✅ `ToolConfirmRequestBody` 合约
- ✅ `claude_agent_thread_factory` 实例已创建
- ✅ startup/shutdown 钩子已注册
- ✅ 无 JWT 时返回 401

### Notion Connector (`test_notion_snapshot_contract.py`, `test_notion_auth.py`, `test_notion_store.py`)
- ✅ `.notion/` 虚拟路径解析和 snapshot-scoped miss 语义
- ✅ Notion CLI home/env 解析以及 login/poll/auth status 辅助函数
- ✅ SQLite connector CRUD、认证状态持久化、资源选择持久化、snapshot identity 存储和 thread attach

### Notion Connector — Router Flow (`test_notion_connector_router_flow.py`)
- ✅ FastAPI connector business flow covering create, auth/login, auth/poll, database discovery, page discovery, resource selection, and sync persistence

### SEO Content (`test_seo_content.py`)
- ✅ Public URL normalization for `INK_PUBLIC_BASE_URL`
- ✅ `robots.txt` allows AI search crawlers while excluding private API paths
- ✅ `sitemap.xml` contains only public app URLs
- ✅ `llms.txt` describes the app, backend API origin, health endpoint, and authenticated API boundary
- ✅ Frontend public URL expectations use the origin root, not `/ink-and-memory/`

### Database Layer (`test_database.py`)
- ✅ Get system decks
- ✅ Get deck with voices
- ✅ Fork deck (system → user)
- ✅ Update deck (user-owned)
- ✅ Create voice in user deck
- ✅ Update voice (user-owned)
- ✅ Fork voice to user deck
- ✅ Delete voice (user-owned)
- ✅ Delete deck with cascade (user-owned)

### API Endpoints (`test_api_endpoints.py`)
- ✅ Authentication (register/login)
- ✅ GET /api/decks (list all)
- ✅ GET /api/decks/{id} (get with voices)
- ✅ POST /api/decks/{id}/fork (fork deck)
- ✅ PUT /api/decks/{id} (update deck)
- ✅ DELETE /api/decks/{id} (delete deck)
- ✅ POST /api/voices (create voice)
- ✅ PUT /api/voices/{id} (update voice)
- ✅ DELETE /api/voices/{id} (delete voice)
- ✅ POST /api/voices/{id}/fork (fork voice)
- ✅ Permission checks (401/404 for unauthorized)

## Requirements

- Python virtual environment with dependencies
- SQLite database (auto-created if missing)
- Port 8765 available for test server

## Troubleshooting

**"Server failed to start"**
- Check if port 8765 is already in use: `lsof -i:8765`
- Kill existing process: `lsof -ti:8765 | xargs kill -9`
- Check `models.json` exists in backend directory

**"Database tests failed"**
- Ensure database is properly initialized: `python database.py`
- Check database file permissions

**"API tests return 502"**
- Server may have crashed - check `/tmp/test_server.log`
- Verify PolyCLI is installed: `pip show polycli`
