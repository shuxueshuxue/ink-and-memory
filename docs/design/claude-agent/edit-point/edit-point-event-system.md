# Claude Agent × 编辑器集成设计 — 总览

Status: Draft  
Updated: 2026-05-23  
Scope: Design only — 不含实现代码，不含模块重构

---

## 目录

1. [背景与设计重构](#1-背景与设计重构)
2. [文档对象模型](#2-文档对象模型)
3. [三层架构](#3-三层架构)
4. [设计原则](#4-设计原则)
5. [模块索引](#5-模块索引)

---

## 1. 背景与设计重构

### 1.1 原有设计的问题

旧设计试图在 EditorEngine 之上引入一个独立的"EditEvent 事件系统"抽象层，将人类操作与 Agent 操作统一表达为 EditEvent 对象。这个方向存在以下结构性问题：

1. **不必要的抽象层**：EditorEngine 已有清晰的命令接口（`updateTextCell`、`setCommentFeedback` 等），直接映射为 MCP 工具定义即可，无需 EditEvent 包装。
2. **忽视了文件系统读取路径**：Agent 读取文档内容最自然的方式是通过工作空间文件系统（利用 Claude 原生的 `read_file` 能力），而非设计新的 API。
3. **UI Hooks 层定位偏窄**：Hooks 层不只是人类入口，也是 Agent 操作行为可视化与人机协作确认的界面。

### 1.2 新设计的核心转变

| 维度 | 旧设计 | 新设计 |
|------|-------|-------|
| Agent 操作入口 | 新建 EditEvent 事件系统 | EditorEngine 方法 → MCP 工具定义 |
| Agent 读取文档 | 无设计 | EditorState → `.editor/` 虚拟索引适配器（PreToolUse 拦截） |
| UI Hooks 层职责 | 仅人类操作入口 | 人类入口 + Agent 操作可视化 + 人机协作确认面 |
| Agent 操作粒度 | 字符级 | 片段（Cell/Segment）级 |

---

## 2. 文档对象模型

Ink & Memory 的文档抽象层次为 **档案（Archive / Session） > 片段（Segment / Cell）**：

```
档案（Archive / Session）                 ← 一次写作会话，持久化单元
  ├── id: string                          ← 会话唯一 ID（UUID）
  ├── createdAt: string                   ← ISO 时间戳
  ├── selectedState: string | null        ← 当日情感状态
  └── 片段列表（Segments / Cells）         ← 文档正文，有序数组
        ├── 文本片段（TextCell）           ← Agent 操作的最小粒度
        │     id: string
        │     type: 'text'
        │     content: string
        └── 组件片段（WidgetCell）
              id: string
              type: 'widget'
              widgetType: 'chat' | 'greeting' | 'other'
              data: Record<string, unknown>

评论（Commentor）                          ← 附着在片段短语上的 AI 语音评论
  ├── id: string
  ├── phrase: string                      ← 锚定的文本短语（在某文本片段内）
  ├── comment: string                     ← 评论正文
  ├── voiceId / voice / icon / color      ← 语音角色信息
  ├── appliedAt: number | undefined       ← undefined 表示仍在候选队列
  ├── feedback: 'star' | 'kill' | undefined
  └── chatHistory: Message[]              ← 与该评论的对话历史
```

**关键约束：**
- 用户可通过选择片段内的短语触发评论高亮与对话交互
- **Agent 通过 MCP 工具读取和修改片段及评论**，操作粒度为片段级（不直接操作字符流）
- 跨多片段操作拆分为多个独立 MCP 工具调用，每次调用对应一个片段，逐一经人类确认

---

## 3. 三层架构

```
┌──────────────────────────────────────────────────────────────┐
│                   Editor UI / Hooks 层                        │
│                                                              │
│  人类操作入口（键入 / 粘贴 / 评论 / 保存）                      │
│  Agent 操作可视化（待确认操作预览、操作历史）                    │
│  人机协作确认面（Approve / Reject Agent 变更）                  │
│                                                              │
│  useTextCells / useComments / useSessionLifecycle            │
│  AgentActionOverlay（新增：渲染 Agent 待确认操作）              │
└──────────────────────┬───────────────────────────────────────┘
                       │  命令调用 / 状态订阅
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                    EditorEngine 层                            │
│                                                              │
│  唯一状态变更权威（Single Source of Truth）                    │
│  人类路径：通过 Hooks 调用（现有，不变）                        │
│  Agent 路径：通过 MCP 工具调用（新增）                          │
│                                                              │
│  方法接口 → MCP 工具定义（详见 mcp-tools.md）                  │
│  updateTextCell / insertWidgetAtCursor / deleteCell          │
│  addCommentChatMessage / setCommentFeedback                  │
└──────────────────────┬───────────────────────────────────────┘
                       │  EditorState 快照
                       ▼
┌──────────────────────────────────────────────────────────────┐
│                 EditorState / 虚拟索引层                       │
│                                                              │
│  EditorState → `.editor/` 虚拟索引（PreToolUse 拦截 read_file）│
│  editor_index.py（`_init_editor_index` / `handle_read_hook`） │
│                                                              │
│  {AGENT_CWD}/{session_id}/.editor/                           │
│    cells.json / commentors.json / tasks.json / session.json  │
└──────────────────────────────────────────────────────────────┘
```

**各层职责对照：**

| 层 | 人类路径 | Agent 路径 |
|----|---------|----------|
| **UI / Hooks** | 接收键盘/鼠标输入，渲染编辑器，管理 IME/防抖 | 渲染 Agent 待确认操作预览，展示 Approve/Reject UI，显示 Agent 已执行操作高亮 |
| **EditorEngine** | 通过 Hooks 调用命令方法，维护状态 | 通过 MCP 工具调用（经 PreToolUse 拦截 → 人类确认 → 执行） |
| **EditorState / 虚拟索引** | 序列化为 JSON 持久化到后端 DB | 通过 `.editor/` 虚拟索引占位符 + PreToolUse 拦截，Agent `read_file` 时动态返回实时 EditorState 快照 |

---

## 4. 设计原则

1. **Engine 接口即 MCP 工具**：不引入新抽象层，直接将 EditorEngine 的命令方法映射为 MCP 工具定义。工具名称语义化（`write_segment`、`add_comment` 等）。

2. **读取通过虚拟索引，写入通过工具**：Agent 读取文档内容通过 `.editor/` 虚拟索引（`read_file` 触发 PreToolUse 拦截，动态返回实时 EditorState 快照），写入/修改必须通过 MCP 工具，以触发人类确认流程。

3. **Agent 写操作必须经人类确认**：任何由 Agent 发起的写操作，在 EditorEngine 执行前必须通过 `PreToolUse` hook 阻塞，等待人类 Approve/Reject。此规则不可绕过。

4. **冲突显式化，不静默覆盖**：多 Agent 并发操作同一片段时，系统产生冲突信号，由人类仲裁，不做自动合并（参见 `conflict-resolution.md`）。

5. **最小侵入**：人类操作路径现有行为不变，新增 Agent 路径在现有 EditorEngine 和 Tool Confirmation Flow 上叠加。

---

## 5. 模块索引

| 文档 | 职责 |
|------|------|
| [mcp-tools.md](./mcp-tools.md) | EditorEngine → MCP 工具目录；工具 Schema；读/写权限矩阵 |
| [workspace-adapter.md](./workspace-adapter.md) | EditorState → `.editor/` 虚拟索引适配器；PreToolUse 拦截机制；资源映射规范；读写路径分离 |
| [human-agent-collab.md](./human-agent-collab.md) | UI 人机协作设计；Agent 操作可视化；确认流程 |
| [conflict-resolution.md](./conflict-resolution.md) | 多 Agent 并发冲突检测与人类仲裁机制 |
