# Chat Thread & Message ER Model

> **Ink & Memory 实现**：Claude Agent 的对话持久化使用 `chat_thread + chat_message` 两张表。
> `chat_thread` 表示一次完整的对话会话（即前端 "New Chat"），`chat_message` 按轮次记录 user/assistant 消息明细。
> `chat_thread.id` 同时作为 Claude SDK 的 `thread_id`（`session_id`），支持跨轮次对话继续。

## 1. 设计目标

| 目标 | 说明 |
|------|------|
| 每次 New Chat 独立 | 前端点击 New Chat → 后端 `POST /api/claude-agent/threads` 创建 `chat_thread`，返回 `thread_id` |
| thread_id 双重用途 | `chat_thread.id` 既是 DB 主键，也是传给 Claude SDK 的 `thread_id`（维持多轮对话上下文） |
| 消息一行一条 | `chat_message` 以 `message_id` 幂等写入 user/assistant 明细 |
| 会话标题自动生成 | 第一轮完成后，从 user message 截取前 50 字符作为 `title` |
| 历史可回放 | `GET /api/claude-agent/threads/{id}/messages` 返回消息列表，前端可重建对话视图 |

## 2. ER 图

```text
users
────────────────────────────────────────────────────────────
 PK  id          INTEGER

        │ 1
        │
        │ N

chat_thread
────────────────────────────────────────────────────────────
 PK  id          TEXT  (UUID, 同时作为 Claude SDK thread_id)
 FK  user_id     INTEGER -> users.id ON DELETE CASCADE
     title       TEXT NULL  (第一轮消息后自动填入)
     created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
     updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP
────────────────────────────────────────────────────────────
 INDEX: (user_id, updated_at DESC)

        │ 1
        │
        │ N

chat_message
────────────────────────────────────────────────────────────
 PK  id          TEXT  (UUID)
 FK  thread_id   TEXT -> chat_thread.id ON DELETE CASCADE
     role        TEXT  ('user' | 'assistant')
     content     TEXT  (完整消息文本)
     parts_json  TEXT  (JSON array, AI SDK UIMessage parts 格式)
     created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
────────────────────────────────────────────────────────────
 INDEX: (thread_id, created_at ASC)
```

## 3. Schema Bootstrap

`database.py` 的 `create_tables()` 函数在启动时创建上述两张表（`IF NOT EXISTS`）。
现有数据库通过 `ALTER TABLE ... ADD COLUMN` 迁移方式向前兼容。

## 4. 读写规则

### 写入
- 每轮 agent 执行成功后，`service.py` 的 `execute_session` 尾部写入 user message + assistant message 各一行。
- `chat_thread.updated_at` 随每轮写入更新。
- `chat_thread.title` 在第一轮写入时截取 user message 前 50 字符自动填入（若此前为 NULL）。

### 读取
- `GET /api/claude-agent/threads` → 按 `updated_at DESC` 返回用户的所有 `chat_thread`（不含消息体）。
- `GET /api/claude-agent/threads/{id}/messages` → 按 `created_at ASC` 返回该 thread 的所有 `chat_message`。
- 前端 `ChatPanel` 组件在挂载时调用此接口加载历史消息，实现聊天记录回放。

### 删除
- `DELETE /api/claude-agent/threads/{id}` → 级联删除该 thread 下所有 `chat_message`。

## 5. API 契约

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/claude-agent/threads` | 创建新 thread，返回 `{thread_id}` |
| `GET`  | `/api/claude-agent/threads` | 列出用户所有 threads |
| `GET`  | `/api/claude-agent/threads/{id}/messages` | 获取 thread 消息列表 |
| `DELETE` | `/api/claude-agent/threads/{id}` | 删除 thread（级联删消息） |
| `POST` | `/api/claude-agent` | 发送消息，body 必须包含 `thread_id` |
