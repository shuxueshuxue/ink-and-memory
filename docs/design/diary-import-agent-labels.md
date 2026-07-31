# 日记导入脚本：Agent 动态标签推断设计

Status: Implemented  
Updated: 2026-07-19  
Scope: `backend/script/import_diaries.py` — `--label-mode agent` 模式，通过 Claude Agent 服务动态计算导入 session 的 labels；进度条与多线程并发支持

> **[Sync] 2026-07-19**：`_agent_infer_labels` 优先直接读取 `message-final` 帧
> 自带的 `text` 字段（该字段在后端已按 `text-delta` 汇总，不含 thinking/reasoning
> 内容），避免在 SSE 流已经给出最终文本时还要再发一次请求。仅当 `message-final.text`
> 为空时，才回退调用 `GET /api/claude-agent/threads/{id}/messages`
> （`_agent_fetch_final_assistant_text`）查库取文本，并重试
> `AGENT_LABEL_MESSAGES_FALLBACK_ATTEMPTS` 次、间隔
> `AGENT_LABEL_MESSAGES_FALLBACK_DELAY_S` 秒 —— 该端点依赖
> `claude_agent/service.py` 的 `_persist_assistant_turn`，但后端在持久化完成
> **之前**就把 `finish` 帧放入队列（见 `execute_session`），单次立即 GET 仍可能
> 读到尚未写入的 `parts`，重试几次可以避开这个竞态窗口。这个端点因此继续被脚本
> 使用，不做废弃处理。第 8、9 节已按此更新。
>
> **[Sync] 2026-07-19（第二次）**：脚本顶部在 `import auth as _auth` 之前补了
> `load_dotenv(BACKEND_DIR / ".env", override=False)`（与 `server.py` 完全一致）。
> 此前脚本从未加载 `backend/.env`，若执行脚本的 shell 没有单独 `export
> JWT_SECRET=...`，`auth.py` 的 `SECRET_KEY` 会落到硬编码的 dev-secret 默认值，
> 与真正在跑的后端进程（已通过 `server.py` 加载 `.env` 里的真实 `JWT_SECRET`）
> 不一致，导致自动生成的 token 签名对不上，`POST /api/claude-agent/threads`
> 100% 返回 `401 Unauthorized`。第 4 节已按此更新。
>
> **[Sync] 2026-07-19（第三次）**：`--label-mode agent` 的请求体改为
> `"toolChoice": "none"`（标签推断纯粹是文本分类，不需要任何工具），并在
> SSE 读取循环上加了一个 `AGENT_LABEL_STREAM_TIMEOUT_S`（120s）总耗时上限。此前用
> `"auto"` 时模型可能在与本次调用无关的 `cwd` 上发起多轮工具调用，每个
> `tool-event` 帧都会重置 httpx 的单次读超时，导致单个文件的调用可能挂起数分钟，
> 只能手动 Ctrl-C 中断。第 8、9、11 节已按此更新。

---

## 目录

1. [背景与目标](#1-背景与目标)
2. [整体流程](#2-整体流程)
3. [CLI 参数总览](#3-cli-参数总览)
4. [Token 生成机制](#4-token-生成机制)
5. [数据库预检：跳过已存在 session](#5-数据库预检跳过已存在-session)
6. [进度条](#6-进度条)
7. [多线程并发](#7-多线程并发)
8. [HTTP 调用序列](#8-http-调用序列)
9. [SSE 流解析](#9-sse-流解析)
10. [标签合并策略](#10-标签合并策略)
11. [错误降级策略](#11-错误降级策略)
12. [与原有 auto 模式的对比](#12-与原有-auto-模式的对比)
13. [实现文件索引](#13-实现文件索引)

---

## 1. 背景与目标

### 1.1 问题

原有 `--label-mode auto` 依赖硬编码的 `LABEL_RULES`（关键词 → 标签映射表）进行内容分类。  
这种静态匹配方案有以下局限：

- 业务标签变化时需要修改代码；
- 对长文本的语义理解能力有限，仅靠关键词频率打分；
- 无法感知上下文、文风、隐含主题。

### 1.2 设计目标

| 目标 | 说明 |
|------|------|
| 动态推断 | Claude 根据全文语义归纳主题，不依赖硬编码词表 |
| 复用现有接口 | 调用 `POST /api/claude-agent/threads` + `POST /api/claude-agent`，无需新增后端接口 |
| Token 自动生成 | 脚本内部通过 `auth.create_access_token()` 生成 JWT，无需用户手动获取 |
| 避免无效调用 | 导入前查询数据库，已存在且不带 `--replace` 的 session 跳过 agent 调用 |
| 进度可见 | tqdm 进度条实时显示处理阶段和写库阶段 |
| 多线程并发 | `--workers N` / `-j N` 并发处理，agent 模式下线性提速 |

---

## 2. 整体流程

```
main()
  │
  ├─ 构建 AgentLabelContext（仅 --label-mode agent）
  │     ├─ backend_url  (--backend-url / INK_MEMORY_BACKEND_URL)
  │     ├─ token        (--api-token / INK_MEMORY_IMPORT_API_TOKEN 或自动生成)
  │     └─ max_labels
  │
  ├─ fetch_existing_sessions()          ← 提前查询 DB，得到 existing_session_ids
  │
  ├─ collect_diary_entries(
  │       ..., agent_ctx, existing_session_ids, replace, workers)
  │     │
  │     ├─ 扫描 *.md 文件，解析日期 → sorted dated_paths
  │     │
  │     └─ 处理循环（tqdm 进度条，workers=1 串行 / workers>1 ThreadPoolExecutor）
  │           │
  │           └─ _process_entry_task(task)
  │                 ├─ session_id = make_session_id(...)
  │                 ├─ 若 session_id ∈ existing_session_ids 且 not replace
  │                 │     → labels = []  （跳过 agent 调用）
  │                 └─ 否则 infer_labels(... agent_ctx ...)
  │                           ├─ front matter + hashtag 显式标签
  │                           └─ _agent_infer_labels(body, ...)
  │                                 ├─ POST /api/claude-agent/threads
  │                                 └─ 流式 POST /api/claude-agent → SSE → labels
  │
  ├─ plan_entries(entries, existing, replace)
  │
  └─ import_entries(...)    （tqdm 进度条 + tqdm.write 逐条输出）
        └─ database.save_session(labels=...)
```

---

## 3. CLI 参数总览

| 参数 | 简写 | 环境变量 | 默认值 | 说明 |
|------|------|----------|--------|------|
| `--label-mode` | — | `INK_MEMORY_IMPORT_LABEL_MODE` | `auto` | `auto` / `agent` / `none` |
| `--backend-url` | — | `INK_MEMORY_BACKEND_URL` | `http://localhost:8000` | agent 模式后端地址 |
| `--api-token` | — | `INK_MEMORY_IMPORT_API_TOKEN` | *(自动生成)* | Bearer JWT |
| `--workers` | `-j` | `INK_MEMORY_IMPORT_WORKERS` | `1` | 并发线程数 |
| `--max-labels` | — | `INK_MEMORY_IMPORT_MAX_LABELS` | `5` | 每条 session 最大标签数 |

**可用 label 模式**：`auto`（关键词匹配）、`agent`（Claude 语义推断）、`none`（不写标签）。

**典型用法（agent + 4 线程）**：

```bash
python backend/script/import_diaries.py \
  --source-dir ~/diary \
  --email user@example.com \
  --label-mode agent \
  --workers 4 \
  --max-labels 5
```

---

## 4. Token 生成机制

为了调用需要认证的 `/api/claude-agent` 接口，脚本在 `--api-token` 未指定时自动生成 JWT：

```python
def _build_agent_token(user_id: int) -> str:
    db = database.get_db()
    row = db.execute("SELECT email FROM users WHERE id = ?", (user_id,)).fetchone()
    return _auth.create_access_token(user_id, row["email"])
```

- 调用 `auth.create_access_token(user_id, email)` 生成标准 HS256 JWT（有效期 7 天）；
- Token 携带 `user_id` 和 `email`，与前端登录使用相同的签名密钥（`JWT_SECRET`）；
- 如果用户已有长期 token（如从前端复制），可通过 `--api-token` 或环境变量直接传入。

**签名密钥来源（重要）**：`auth.py` 在模块导入时按
`os.environ.get("JWT_SECRET") or os.environ.get("JWT_SECRET_KEY") or
"dev-secret-change-in-production-123456789"` 解析 `SECRET_KEY`；真正在跑的
后端进程是通过 `server.py` 顶部的 `load_dotenv(backend/.env, override=False)`
把该值注入到进程环境的。脚本作为独立进程运行，`import auth as _auth` 之前必须
先做同样的 `load_dotenv(BACKEND_DIR / ".env", override=False)`，否则脚本进程读不到
`backend/.env` 里的真实 `JWT_SECRET`，`SECRET_KEY` 会落到 dev-secret 默认值，
签出的 token 与后端验证时用的密钥不一致，`verify_access_token()` 校验失败，
表现为 `POST /api/claude-agent/threads` 返回 `401 Unauthorized`（脚本本身不会
报错，因为 JWT 编码永远成功，只有服务端验签会失败）。

---

## 5. 数据库预检：跳过已存在 session

`fetch_existing_sessions()` 在 `collect_diary_entries` **之前**执行，得到 `existing_session_ids` 集合。  
处理每条文件时，先用确定性算法计算 `session_id`，若已存在且不带 `--replace` 则跳过 agent 调用：

```
_process_entry_task(task)
  │
  ├─ session_id = make_session_id(user_id, source_dir, path, day)
  │
  ├─ session_id ∈ existing_session_ids AND not replace
  │     → labels = []   （不调用 agent，不读 front matter）
  │
  └─ 否则
        → infer_labels(...)   正常推断
```

**效果**：重复运行导入时，已存在的 session 在处理阶段直接跳过，不产生额外的 Claude API 调用和等待时间。

---

## 6. 进度条

使用 `tqdm`（已在项目依赖中），进度条写 `stderr`，逐条日志输出走 `stdout`，互不干扰：

### 处理阶段（`collect_diary_entries`）

```
Processing:  72%|███████▏  | 30/42 [00:01<00:00, 38.2file/s] [思考笔记本-5-17.md]
```

- `--label-mode agent` 时描述变为 `Labeling (agent)`；
- 多线程时描述变为 `Labeling (agent) (×4)`；
- 单线程时 postfix 实时显示当前文件名。

### 写库阶段（`import_entries`）

```
Importing:  80%|████████  | 34/42 [00:02<00:01] [2026-05-17 思考笔记本]
INSERT  2026-05-17  [folder-name]  2026-05-17 思考笔记本  .../思考笔记本-5-17.md  labels=[思考笔记]
```

每条 INSERT / REPLACE / SKIP 通过 `tqdm.write()` 输出，不破坏进度条渲染。

---

## 7. 多线程并发

### 7.1 设计

| 组件 | 说明 |
|------|------|
| `_EntryTask` dataclass | 封装单条文件处理所需的全部输入，方便线程池传参 |
| `_process_entry_task(task)` | 纯函数：读文件 → 判断是否已存在 → 推断标签 → 返回 `DiaryEntry \| None` |
| `ThreadPoolExecutor.map` | 保序并发，结果顺序与输入一致 |

### 7.2 workers=1（默认）

```python
for task in tqdm(work_items, ...):
    bar.set_postfix_str(task.path.name)
    result = _process_entry_task(task)
```

### 7.3 workers>1

```python
with ThreadPoolExecutor(max_workers=workers) as executor:
    results = list(tqdm(executor.map(_process_entry_task, work_items), total=...))
```

`executor.map` 保证结果顺序，`tqdm` 包装迭代器在每个 future 完成时推进进度条。

### 7.4 线程安全

- `_process_entry_task` 无共享写状态；
- `httpx.Client` 在每次调用内创建和关闭，不跨线程共享；
- `database.get_db()` 每次调用返回独立连接，SQLite WAL 模式支持并发读；
- 写库阶段（`import_entries`）保持单线程，避免 SQLite 写锁竞争。

### 7.5 推荐配置

| 场景 | 推荐 `--workers` |
|------|-----------------|
| `--label-mode auto` / `none` | `1`（I/O 极快，无需并发） |
| `--label-mode agent`，< 20 条 | `2–4` |
| `--label-mode agent`，> 50 条 | `4–8`（受 Claude API 并发限制） |

---

## 8. HTTP 调用序列

每篇日记独立创建一个新 thread，保证上下文隔离：

```
脚本（线程 N）                  后端 FastAPI
 │                                  │
 │  POST /api/claude-agent/threads   │
 │  Authorization: Bearer <token>    │
 │ ──────────────────────────────→   │
 │  ← { "thread_id": "uuid-xxx" }   │
 │                                  │
 │  POST /api/claude-agent           │
 │  { id: thread_id, message: prompt, toolChoice: "none" }│
 │  Accept: text/event-stream        │
 │ ──────────────────────────────→   │
 │    ← data: {"type":"text-delta","id":"...","delta":"孤独\n"}
 │    ← data: {"type":"message-final","text":"孤独\n成长\n",...}
 │    ← data: {"type":"finish", ...}
 │                                  │
 │  读取 message-final.text；若为空则重试调用    │
 │  GET /threads/{id}/messages 兜底           │
```

- `_agent_create_thread`：`httpx.Client` 同步 POST，超时 30s；
- `_agent_infer_labels`：`httpx.Client.stream` 流式 POST，`toolChoice: "none"`，
  单次调用总耗时上限 `AGENT_LABEL_STREAM_TIMEOUT_S`（120s）；优先直接消费同一个
  响应流拿 `message-final.text`，仅当该文本为空时才重试调用
  `GET /threads/{id}/messages`（`_agent_fetch_final_assistant_text`）兜底。

---

## 9. SSE 流解析

后端 `/api/claude-agent` 以 `text/event-stream` 格式返回 JSON 帧（字段名以
`backend/claude_agent/service.py` 顶部注释为准，`text-delta` 帧携带的是 `delta`
字段，不是 `text`）：

```
data: {"type": "text-delta", "id": "...", "delta": "孤独\n"}
data: {"type": "message-final", "text": "孤独\n成长\n", "usage": {...}, "sessionId": "..."}
data: {"type": "finish", "finishReason": "stop"}
```

脚本不逐帧拼接 `text-delta`（避免依赖易变的增量字段名），而是直接读取
`message-final` 帧自带的完整 `text`：

```python
assistant_text = ""
for raw_line in resp.iter_lines():
    if not raw_line.startswith("data: "):
        continue
    frame = json.loads(raw_line[len("data: "):])
    frame_type = frame.get("type")
    if frame_type == "message-final":
        assistant_text = frame.get("text", "")
    elif frame_type in ("finish", "error"):
        break
```

`message-final.text` 由后端在 `agent_runner.py` 中只从 `text_delta` 累积而来，
thinking/reasoning 内容走独立的 `tool-event` 帧，不会混入。拿到文本后按行分割，
每行通过 `normalize_label()` 清理空白与特殊字符。

> 兜底路径（仍在使用，未废弃）：若 `message-final.text` 为空，`_agent_infer_labels`
> 会调用 `_agent_fetch_final_assistant_text`，即 `GET
> /api/claude-agent/threads/{id}/messages`，取最后一条 `role=assistant` 消息里
> `type=text` 的 parts 拼接成文本。因为后端把 `finish` 帧放入队列的时机早于
> `_persist_assistant_turn` 完成持久化（`claude_agent/service.py`
> `execute_session`），单次立即 GET 仍可能读到尚未写入的消息、拿到空 `parts`；
> 因此这个回退调用会重试 `AGENT_LABEL_MESSAGES_FALLBACK_ATTEMPTS`（3）次，每次间隔
> `AGENT_LABEL_MESSAGES_FALLBACK_DELAY_S`（0.3s），仍拿不到文本才放弃（该文件当次
> 标签仅含 front matter / hashtag 显式标注）。

---

## 10. 标签合并策略

`agent` 模式下，标签按以下优先级填充（上限 `max_labels`）：

| 来源 | 顺序 | 说明 |
|------|------|------|
| YAML front matter `tags`/`labels` 字段 | 1（最高） | 用户显式标注，无条件保留 |
| 正文 `#hashtag` | 2 | 用户行内标注 |
| Claude Agent 推断 | 3 | 语义分类，补足剩余槽位 |

`add_label()` 负责去重（大小写不敏感）和截断（`max_labels`）。

**Prompt 模板**（`AGENT_LABEL_PROMPT`）：

```
{text}      ← 完整正文，不截断
```

---

## 11. 错误降级策略

任何异常均被上层 `infer_labels` 捕获，不中断导入流程：

```python
try:
    for label in _agent_infer_labels(...):
        add_label(labels, label, max_labels)
except Exception as exc:
    print(f"WARNING: agent label inference failed for {path.name}: {exc}", file=sys.stderr)
```

| 场景 | 降级行为 |
|------|----------|
| 后端未启动 / 连接被拒 | 打印 WARNING，标签仅含显式标注 |
| Token 过期或无效（401） | `httpx.HTTPStatusError` 被捕获，打印 WARNING |
| Agent 返回 error 帧（未先发 message-final） | 跳出循环，`assistant_text` 为空 → 走 `GET /messages` 兜底重试，仍为空则标签仅含显式标注 |
| SSE 流总耗时超过 `AGENT_LABEL_STREAM_TIMEOUT_S`（120s） | 读取循环主动抛出 `TimeoutError` 并被捕获，打印 WARNING（不再依赖 httpx 单次读超时，避免工具调用帧不断重置计时导致长时间挂起） |
| `GET /messages` 兜底也失败 / 仍为空 | 打印 WARNING，标签仅含显式标注 |

---

## 12. 与原有 auto 模式的对比

| 维度 | `auto` | `agent` |
|------|--------|---------|
| 标签词表 | 硬编码 `LABEL_RULES`（18 条规则） | Claude 语义推断，无硬编码 |
| 业务标签可扩展性 | 需修改代码 | 无需代码变更 |
| 语义理解能力 | 关键词频率 | 全文语义 |
| 网络依赖 | 无 | 需要后端服务运行 |
| 执行速度（单线程） | 毫秒级 | 每条 5–30s |
| 多线程加速 | 无明显收益 | 线性加速（受 API 并发限制） |
| 重复运行跳过 | 不跳过 agent（无 agent） | DB 预检，已存在 session 跳过调用 |
| 失败时降级 | 不适用 | 自动回退到 front matter + hashtag |
| 适用场景 | 离线批量导入、快速预览 | 需要高质量语义分类时 |

---

## 13. 实现文件索引

| 文件 | 变更内容 |
|------|---------|
| `backend/script/import_diaries.py` | 新增 `AgentLabelContext`、`_EntryTask`、`_process_entry_task`、`_build_agent_token`、`_agent_create_thread`、`_agent_infer_labels`；更新 `infer_labels`、`collect_diary_entries`（workers + 进度条 + DB 预检）、`import_entries`（tqdm + tqdm.write）、`parse_args`（--workers/-j）、`main`（提前 fetch_existing_sessions） |
| `backend/auth.py` | 无变更，`create_access_token` 被脚本直接调用 |
| `backend/routers/claude_agent.py` | 无变更，现有接口直接复用 |

### 13.1 相关文档

- [session-labels-and-retrieval.md](./claude-agent/session-labels-and-retrieval.md) — `user_sessions.labels` 字段设计与 Agent 跨 session 检索
- [claude-agent-api-contracts.md](./claude-agent/claude-agent-api-contracts.md) — `/api/claude-agent` 接口 SSE 帧格式规范
