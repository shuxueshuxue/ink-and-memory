> **迁移来源**: Pawkeyland docs/app/design/claude-agent-session-persistence.md  
> **[Sync] 2026-05-25 v1**: 全面对齐 Ink & Memory 实际实现（SQLite `chat_thread + chat_message`，`better-chatbot` 对齐存储模式）。  
> **[Sync] 2026-05-25 v2**: 对齐 better-chatbot schema：`parts TEXT NOT NULL DEFAULT '[]'`（移除 `content` 列和 `parts_json` 列）；`save_chat_message(parts: list, metadata: dict)` 签名；`list_chat_messages` 返回已解析对象；前端读 `m.parts` 直接使用。  
> **[Sync] 2026-05-25 v3**: 重大设计重构 — `collected_parts` 改为收集**原始 SSE 事件报文**；新增 `_sse_events_to_ui_parts()` 在 `_persist_turn` 时做线性转换；`tool_inv_by_id` 等状态字段从 `_TurnContext` 移除。
> **[Sync] 2026-05-29 v4**: Claude SDK session ID 持久化落地 — `chat_thread` 新增 `claude_session_id TEXT` 和 `agent_contract_version TEXT` 两列；`_persist_turn` 每次成功 turn 后调用 `update_chat_thread_claude_session` 写回 `result.session_id`；`assemble_context` Phase 1 据此决定是否 resume（详见 `claude-agent-context-assembly.md §4.7`）。

# Claude Agent 会话持久化设计

> **关联参考**：[better-chatbot route.ts `onFinish` 回调](https://github.com/cgoinglove/better-chatbot/blob/main/src/app/api/chat/route.ts#L345)  
> **落地路径**：`backend/database.py`（DB 层）、`backend/claude_agent/service.py::_persist_turn`（服务层）  
> **关联设计**：[claude-agent-thread-session-patterns.md](./claude-agent-thread-session-patterns.md)
>
> **会话持久化分两层**：
>
> | 层 | 落地 | 生命周期 | 作用 |
> |---|---|---|---|
> | **进程内 Thread Session（享元 + 状态）** | `backend/claude_agent/thread_pool.py::AgentRunStatePool` | `INK_AGENT_TTL_S`（默认 600 s）keepalive；TTL 超时 / `close_thread` / `aclose` 销毁 | 维护绑定到 `session_id` 的 `ClaudeAgentRunner` + `system_prompt` / `cwd` 享元缓存，后续轮次复用，不再重复构造 |
> | **DB 持久化（chat_thread + chat_message）** | `backend/database.py` + `backend/claude_agent/service.py::_persist_turn` | 与 `thread_id` 同生命周期，跨进程 / 重启持久 | 真源存储：`chat_thread` 保存会话 metadata，`chat_message` 保存每轮 user/assistant 消息（含完整 `parts_json`） |

---

## 1. 设计背景与目标

| 项目 | 说明 |
|------|------|
| 参考实现 | `cgoinglove/better-chatbot → src/app/api/chat/route.ts` 的 `onFinish` 回调 + `chatRepository.upsertMessage` + `convertToSavePart` |
| 目标模块 | `backend/database.py`（`save_chat_message` / `list_chat_messages`）；`backend/claude_agent/service.py::_persist_turn`（Phase 3 末尾 post-run 持久化） |
| 设计目标 | 1. `chat_thread` 只保存会话 metadata（title / user_id）；2. `chat_message` 以一行保存 user/assistant 消息，`parts_json` 存 UIMessage-compatible 完整 parts 列表；3. 前端通过 `GET /api/claude-agent/threads/{id}/messages` 拉取后直接解析为 `UIMessage[]`，无需额外转换 |

---

## 2. 数据库设计（SQLite，已实现，对齐 better-chatbot）

### 2.1 better-chatbot 参考 schema（PostgreSQL）

```typescript
// src/lib/db/pg/schema.pg.ts
export const ChatThreadTable = pgTable("chat_thread", {
  id:        uuid("id").primaryKey().notNull().defaultRandom(),
  title:     text("title").notNull(),
  userId:    uuid("user_id").notNull().references(() => UserTable.id, { onDelete: "cascade" }),
  createdAt: timestamp("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});

export const ChatMessageTable = pgTable("chat_message", {
  id:        text("id").primaryKey().notNull(),          // AI-SDK message ID
  threadId:  uuid("thread_id").notNull().references(...),
  role:      text("role").notNull().$type<UIMessage["role"]>(),
  parts:     json("parts").notNull().array().$type<UIMessage["parts"]>(), // json[] NOT NULL
  metadata:  json("metadata").$type<ChatMetadata>(),                       // nullable
  createdAt: timestamp("created_at").notNull().default(sql`CURRENT_TIMESTAMP`),
});
```

### 2.2 Ink & Memory 实际 schema（SQLite，对齐后）

```sql
-- 会话 metadata 表（与 ChatThreadTable 对齐）
CREATE TABLE IF NOT EXISTS chat_thread (
  id                     TEXT PRIMARY KEY,          -- UUID string
  user_id                INTEGER NOT NULL,          -- INTEGER vs UUID (SQLite user ID)
  title                  TEXT,                      -- nullable: filled on first message
  claude_session_id      TEXT,                      -- Claude SDK session ID for --resume (2026-05-29)
  agent_contract_version TEXT,                      -- Runtime contract version guard  (2026-05-29)
  created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

-- 消息真源表（与 ChatMessageTable 完全对齐，无 content 列）
CREATE TABLE IF NOT EXISTS chat_message (
  id         TEXT PRIMARY KEY,          -- AI-SDK message.id
  thread_id  TEXT NOT NULL,
  role       TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
  parts      TEXT NOT NULL DEFAULT '[]', -- JSON array string
  metadata   TEXT,                      -- JSON object string; nullable
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (thread_id) REFERENCES chat_thread (id) ON DELETE CASCADE
);
```

**运行时迁移（已存在的数据库）**：`init_db()` 在启动时对两个新列各执行一次 `ALTER TABLE chat_thread ADD COLUMN … TEXT`，异常时静默跳过（列已存在）。

### 2.3 与参考实现的差距分析

| 列 | better-chatbot | Ink & Memory | 状态 |
|----|---------------|-------------|------|
| `chat_message.parts` | `json[] NOT NULL` | `TEXT NOT NULL DEFAULT '[]'` | ✅ 对齐（SQLite 无原生 JSON 列类型；效果等价） |
| `chat_message.metadata` | `json nullable` | `TEXT nullable` | ✅ 对齐（序列化/反序列化在 DB 层处理） |
| `chat_message.content` | **不存在**（文本在 parts 里） | **已删除**，完全对齐 | ✅ `parts` 是唯一内容列 |
| `chat_thread.title` | `TEXT NOT NULL` | `TEXT nullable` | ⚠️ 差异（首轮填写；向后兼容） |
| `chat_thread.updated_at` | 不存在 | `DATETIME` | ⚠️ 额外列（用于线程排序；不影响正确性） |
| `chat_thread.claude_session_id` | 不适用 | `TEXT nullable` | ✅ **新增**（Claude SDK resume 使用；2026-05-29） |
| `chat_thread.agent_contract_version` | 不适用 | `TEXT nullable` | ✅ **新增**（契约版本校验，防止跨版本 resume；2026-05-29） |

### 2.4 DB 层函数（`backend/database.py`）

| 函数 | 说明 |
|------|------|
| `create_chat_thread(user_id)` | 创建新会话，返回 `thread_id`（UUID） |
| `get_chat_thread(thread_id, user_id)` | 权限校验 + 返回会话 row（含 `claude_session_id` / `agent_contract_version`） |
| `save_chat_message(thread_id, role, content, *, parts, message_id, metadata)` | `INSERT OR REPLACE`，`parts: list`（序列化在 DB 层），`metadata: dict`，同时 BUMP `chat_thread.updated_at` |
| `list_chat_messages(thread_id)` | 按 `created_at ASC` 返回全部消息；`parts` 已反序列化为 Python list，`metadata` 已反序列化为 dict |
| `update_chat_thread_title(thread_id, title)` | 首轮写入时自动从 user_text 截取标题（前 50 字符） |
| `update_chat_thread_claude_session(thread_id, claude_session_id, agent_contract_version)` | **新增（2026-05-29）**：每次成功 turn 后由 `_persist_turn` 调用，将 `result.session_id` 与当前 `_AGENT_RUNTIME_CONTRACT_VERSION` 写回，供下轮 `assemble_context` 的 resume 判断使用 |

---

## 3. `parts_json` 格式（UIMessage-compatible）

`parts_json` 存储的是与 Vercel AI SDK `UIMessage['parts']` 完全兼容的对象列表，前端解析后可直接用于渲染，**不存原始 SSE 事件流**。

### 3.1 assistant 消息 parts

| part type | 说明 | 关键字段 |
|-----------|------|----------|
| `reasoning` | thinking 块（完整文本） | `id`（uuid），`text` |
| `tool-invocation` | 工具调用（含结果） | `toolCallId`，`toolName`，`state`（`"call"` / `"output-available"` / `"output-error"`），`input`，`output`（可选），`dynamic: true` |
| `text` | 最终文本回复 | `text` |

> 顺序：按事件到达时序追加 — `reasoning` → `tool-invocation` → `text`（text 在 `_persist_turn` 收尾时追加）。  
> `finish`、`error`、`message-metadata` 等事件类型**不写入** `parts_json`。

**assistant 消息 `parts_json` 示例：**

```json
[
  {
    "type": "reasoning",
    "id": "aaaa-bbbb-...",
    "text": "让我先思考一下..."
  },
  {
    "type": "tool-invocation",
    "toolCallId": "toolu_01Abc...",
    "toolName": "bash",
    "state": "output-available",
    "input": { "command": "ls -la" },
    "output": "total 12\ndrwxr-xr-x ...",
    "dynamic": true
  },
  {
    "type": "text",
    "text": "根据以上结果，目录结构如下..."
  }
]
```

### 3.2 user 消息 parts

存储前端传入的原始 `message.parts`（含 `text`、`file`、`source-url` 等附件 parts），由 `ClaudeAgentRunRequest.message_parts` 字段携带，原样序列化后写入 `parts_json`。若 `message_parts` 为空，`parts_json` 置 NULL，前端回放时 fallback 为 `[{ type: "text", text: content }]`。

### 3.3 metadata（assistant 消息）

```json
{
  "usage": {
    "inputTokens": 1024,
    "outputTokens": 512,
    "totalTokens": 1536
  },
  "chatModel": {
    "provider": "anthropic",
    "model": "claude-opus-4-20250514"
  },
  "toolCount": 2
}
```

---

## 4. `_persist_turn` 实现逻辑

`ClaudeAgentService._persist_turn` 在 `execute_session` 成功后异步写库，对齐 better-chatbot 的 `onFinish` 回调模式。

### 4.1 两阶段设计：收集（streaming） → 转换（persist）

```
streaming 阶段（实时）
  每次发 SSE → queue.put(sse_frame)
              + collected_parts.append(raw_event_dict)   ← 原始 SSE 事件报文

persist 阶段（_persist_turn，run 完成后一次性执行）
  ui_parts = _sse_events_to_ui_parts(collected_parts)
           → 线性单遍扫描，无状态副作用
           → 输出 UIMessage-compatible parts list
  database.save_chat_message(parts=ui_parts)
```

**`_sse_events_to_ui_parts()` 转换规则：**

| SSE 事件（collected_parts 中） | 转换后的 UIMessage part |
|-------------------------------|------------------------|
| `text-start` | 创建 `{"type":"text","text":""}` |
| `text-delta` | 追加 `.delta` 到当前 text part |
| `text-end` | 关闭当前 text part（current_text = None） |
| `reasoning-start` | 创建 `{"type":"reasoning","id":...,"text":""}` |
| `reasoning-delta` | 追加 `.delta` 到当前 reasoning part |
| `reasoning-end` | 关闭当前 reasoning part |
| `tool-input-available` | 创建 `{"type":"tool-invocation","state":"call",...}` |
| `tool-output-available` | 原地 patch 匹配的 invocation → `state:"output-available"/"output-error"` |

不收集（无 UIMessage part 等价）：`tool-input-start`、`tool-approval-request`、`message-metadata`、`message-final`、`finish`、`error`。

### 4.2 `_persist_turn` 代码骨架

```python
async def _persist_turn(self, execution, result) -> None:
    def _save() -> None:
        # 1. 写 user 消息
        resolved_user_parts = list(user_parts) if user_parts else [{"type": "text", "text": user_text}]
        database.save_chat_message(
            thread_id, "user",
            parts=resolved_user_parts,
            message_id=user_message_id,
        )

        # 2. 将原始 SSE 事件转换为 UIMessage parts（线性单遍扫描）
        asst_parts = _sse_events_to_ui_parts(turn_ctx.collected_parts)
        if not asst_parts:
            asst_parts = [{"type": "text", "text": assistant_text}] if assistant_text else []

        # 3. 写 assistant 消息
        database.save_chat_message(
            thread_id, "assistant",
            parts=asst_parts,
            metadata=asst_metadata or None,
        )

        # 4. 自动填充 thread 标题（首轮）
        if not thread.get("title"):
            database.update_chat_thread_title(thread_id, user_text[:50])

        # 5. 写回 Claude SDK session ID（供下轮 assemble_context resume 使用）
        #    result.session_id 是 SDK 分配的实际 session ID（非 app thread_id）
        captured_session_id = result.session_id if result else None
        if captured_session_id:
            database.update_chat_thread_claude_session(
                thread_id,
                captured_session_id,
                _AGENT_RUNTIME_CONTRACT_VERSION,
            )

    await loop.run_in_executor(None, _save)
```

### 4.3 collected_parts 示例（text → tool → text 场景）

```python
# streaming 结束后 collected_parts 内容（原始 SSE 事件报文）：
[
    {"type": "text-start",           "id": "text-0"},
    {"type": "text-delta",           "id": "text-0", "delta": "让我检查一下"},
    {"type": "tool-input-available", "toolCallId": "t1", "toolName": "bash",
     "input": {"command": "ls -la"}},
    {"type": "tool-output-available","toolCallId": "t1",
     "output": "file1.txt", "isError": False},
    {"type": "text-start",           "id": "text-0"},
    {"type": "text-delta",           "id": "text-0", "delta": "目录结构如下..."},
    {"type": "text-end",             "id": "text-0"},
]

# _sse_events_to_ui_parts() 输出（写入 chat_message.parts）：
[
    {"type": "text",           "text": "让我检查一下"},
    {"type": "tool-invocation","toolCallId": "t1", "toolName": "bash",
     "state": "output-available", "input": {"command": "ls -la"},
     "output": "file1.txt", "dynamic": True},
    {"type": "text",           "text": "目录结构如下..."},
]
```

---

## 5. 前端历史加载流程（对齐 better-chatbot）

```
GET /api/claude-agent/threads/{thread_id}/messages
  → database.list_chat_messages(thread_id)
  → [{id, role, content, parts: list, metadata: dict|None, created_at}, ...]
  ↑ parts 和 metadata 在 DB 层已反序列化（aligned with better-chatbot selectMessagesByThreadId）

前端 fetchThreadMessages()：
  msgs.map(m => ({
    id:        m.id,
    role:      m.role,
    parts:     Array.isArray(m.parts) && m.parts.length > 0
               ? m.parts                                 // 直接使用（已解析）
               : [{ type: "text", text: m.content }],   // fallback（旧数据兼容）
    metadata:  m.metadata,                               // 已解析为 dict
    createdAt: new Date(m.created_at),
  }))
  → UIMessage[]   直接传入 useChat({ initialMessages })
```

`ChatMessageList.tsx` 渲染时：

| part.type | 渲染组件 / 逻辑 |
|-----------|----------------|
| `"reasoning"` | 折叠 `<details>` 显示 thinking 链（`part.text`） |
| `"tool-invocation"`（`isToolUIPart(part)`） | 终端样式工具结果面板（命令 + 输出 + exit code） |
| `"text"` | Markdown + ReactMarkdown 渲染 |

---

## 6. 与 better-chatbot 参考实现的映射

| better-chatbot（TypeScript） | Ink & Memory（Python） | 说明 |
|---|---|---|
| `ChatMessageTable.parts: json[].notNull()` | `chat_message.parts TEXT NOT NULL DEFAULT '[]'` | SQLite TEXT 模拟 PostgreSQL json[]；DB 层负责序列化/反序列化 |
| `responseMessage.parts.map(convertToSavePart)` | `_sse_events_to_ui_parts(collected_parts)` | AI SDK 从流式 chunks 组装 parts；本项目从 SSE 事件 dict 列表线性转换 |
| `chatRepository.upsertMessage({ parts, metadata })` | `database.save_chat_message(parts=list, metadata=dict)` | 签名对齐；序列化在 DB 层 |
| `onFinish({ responseMessage })` 钩子 | `_persist_turn(execution, result)` | post-run 异步持久化 |
| `chatRepository.selectMessagesByThreadId(id)` | `database.list_chat_messages(thread_id)` | 返回已反序列化的 parts / metadata（无需前端 JSON.parse） |
| AI SDK 自动组装 `responseMessage.parts` | SSE 回调收集原始事件 → `_sse_events_to_ui_parts()` 转换 | 两者均输出 UIMessage-compatible parts |
| `m.parts`（已解析 list）直接用于渲染 | `m.parts`（前端接收已解析 list） | 前端无需 `JSON.parse`，直接传入 `useChat({ initialMessages })` |

---

## 7. Thread Session 与持久化的接合点

| Phase | Factory 触发点 | 持久化交互 |
|-------|--------------|-----------|
| **Phase 1 — Context Assembly** | `Service.assemble_context()` | **新（2026-05-29）**：调用 `database.get_chat_thread()` 加载 `existing_session`，读取 `claude_session_id` / `agent_contract_version` 决定是否 resume；无写操作。首轮享元组装 `system_prompt`，续轮享元短路 |
| **Phase 2 — Runner Creation** | `state.runner = create_agent_runner()` | 无 DB 交互 |
| **Phase 3 — Session Start** | `Service.execute_session()` | run 完成后调用 `_persist_turn`：写入 user + assistant `chat_message` 行；首轮写 `chat_thread.title`；**每次成功 turn 写回 `chat_thread.claude_session_id` + `agent_contract_version`（2026-05-29）** |
| **Phase 4 — Session End** | `close_thread` / TTL Sweeper / `aclose` | 享元销毁不触发 DB 变更；`chat_thread` + `chat_message` 原状保留，下轮重新加载 |

---

## 8. 已知差距与后续优化点

| 项目 | 当前状态 | 后续方向 |
|------|---------|---------|
| Claude SDK `session_id` 续接 | ✅ **已落地（2026-05-29）**：`_persist_turn` 将 `result.session_id` + `_AGENT_RUNTIME_CONTRACT_VERSION` 写入 `chat_thread`；`assemble_context` 读取并通过 `_has_usable_claude_resume` + 本地文件探针决定是否 `--resume` | 可添加"turn-window 满时开新 session"策略（对齐 Pawkeyland `_session_turn_window_is_full`） |
| 多文本块交错 | 所有文本 delta 合并为单一 text part（追加在 parts 末尾） | 若需精确还原多块交错顺序，可在 `on_text_done` 时追加中间 text part |
| `parts_json` 大小 | 无限制（SQLite TEXT 列） | 若工具输出超大，可在 `_persist_turn` 中对 `output` 字段做截断处理 |
| `message_id` 稳定性 | 前端 AI-SDK 提供的 `message_id` 原样存储，`INSERT OR REPLACE` 保幂等 | 重发场景自动覆盖，无需额外去重逻辑 |
