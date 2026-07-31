# 工作空间与 Skills 同步 — 全流程图

> **迁移来源**: `glide-the/claude-agent-next-kit → docs/design/workspace-skills-flow.md`
> **适配说明**: 从 Next.js / TypeScript 迁移到 Python / FastAPI 架构。
> **[Sync] 2026-06-16**: 同步入口会先导入 `.claude/skills/` 下真实文件/目录，
> 再重建从 `workspace/skills/` 到 `.claude/skills/` 的软链接。

## 概述

本文档描述了对话工作空间初始化、文件管理、Agent 执行以及 Skills 自动同步的完整数据流。

---

## 核心流程图

```mermaid
flowchart TD
    A[用户发起对话] --> B[前端生成 conversationId]
    B --> C[WorkspaceContext.setActiveConversation]
    C --> D[FileSidebar 自动切换 sessionId]

    D --> E["GET /api/workspace/files?sessionId={conversationId}"]
    E --> F["get_or_create_workspace(conversationId)"]
    F --> G{工作空间是否已存在?}
    G -- 否 --> H["init_workspace(conversationId)"]
    G -- 是 --> I[返回已有路径]

    H --> H1["创建 files/ 目录"]
    H --> H2["创建 logs/ 目录"]
    H --> H3["创建 skills/ 目录"]
    H --> H4["同步 .claude/ 到工作空间"]
    H --> H5["复制 .mcp.json 到工作空间（首次）"]
    H3 --> H6["sync_skills_symlinks()"]
    H6 --> H6A["导入 .claude/skills/ 中的真实写入"]
    H6A --> H7["扫描 skills/ 中的文件和文件夹"]
    H7 --> H8["为每个条目创建软链接"]
    H8 --> H9["{workspace}/.claude/skills/{name}"]
    H6 --> H10["清理过期软链接"]

    H --> I

    I --> J[FileSidebar 显示文件列表]

    K[用户上传文件] --> L["POST /api/workspace/files"]
    L --> M["写入 {AGENT_CWD}/{conversationId}/files/{filename}"]
    M --> J

    N[用户发送消息] --> O["POST /api/claude-agent"]
    O --> P["get_or_create_workspace(conversationId)"]
    P --> Q["agent_runner.run_streaming(cwd=workspace_path)"]
    Q --> R["Agent 读写 {conversationId}/ 下的文件"]
    R --> S["Agent 可能生成新文件"]
    S --> J

    style H3 fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    style H6 fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    style H6A fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    style H8 fill:#e8f5e9,stroke:#4caf50,stroke-width:2px
    style H9 fill:#fff3e0,stroke:#ff9800,stroke-width:2px
```

---

## Skills 同步机制详情

```mermaid
flowchart LR
    subgraph "workspace/{sessionId}/"
        WS["skills/"]
        S1["my-skill.md"]
        S2["research-tools/"]
    end

    subgraph "workspace/{sessionId}/.claude/"
        PS["skills/"]
        L1["my-skill.md → symlink"]
        L2["research-tools/ → symlink"]
        R1["new-skill/ (real entry before sync)"]
    end

    WS --> S1
    WS --> S2
    S1 -.->|symlink| L1
    S2 -.->|symlink| L2
    R1 -->|import then symlink rebuilt| WS

    style L1 fill:#e3f2fd,stroke:#2196f3
    style L2 fill:#e3f2fd,stroke:#2196f3
```

### 为什么用软链接？

Claude SDK 被调用时设置 `cwd = workspace_path`，因此 Claude 从
`{workspace_path}/.claude/skills/` 读取 skills。

我们让用户/Agent 在更直观的 `{workspace}/skills/` 目录操作，然后自动软链接到
`{workspace}/.claude/skills/` 供 Claude 发现。若 Agent 直接在 Claude Code
canonical 目录 `{workspace}/.claude/skills/` 创建真实文件或目录，下一次同步会先把
该条目导入 `{workspace}/skills/`，再恢复为软链接。

**关键优势**：
1. 每个对话工作空间完全隔离，无命名冲突
2. 同时支持**文件和文件夹**软链接
3. 无需 sessionId 前缀 — 工作空间本身就是隔离边界
4. 每次同步自动清理失效的链接
5. 支持 Agent 直接写入 `.claude/skills/` 后回写到用户可见的 `skills/`

### 同步触发时机

| 时机 | 触发函数 | 说明 |
|------|----------|------|
| 工作空间初始化 | `init_workspace()` → `sync_skills_symlinks()` | 首次创建时自动同步 |
| 访问已有工作空间 | `get_or_create_workspace()` → `init_workspace()` → `sync_skills_symlinks()` | 每次访问重新同步 |
| 写入 skills/ | `write_workspace_file()` → `sync_skills_symlinks()` | 上传 skill 文件后自动同步 |
| 直接写入 `.claude/skills/` | 下一次 `get_or_create_workspace()` / `init_workspace()` → `sync_skills_symlinks()` | 文件列表刷新或下一轮 workspace 初始化时导入真实写入 |
| 删除 skills/ | `delete_workspace_file()` → `sync_skills_symlinks()` | 删除后清理链接 |
| 移动涉及 skills/ | `move_workspace_file()` → `sync_skills_symlinks()` | 移动后更新链接 |

---

## 数据通道总览

```mermaid
sequenceDiagram
    participant U as 用户/浏览器
    participant FS as FileSidebar
    participant CTX as WorkspaceContext
    participant API as /api/workspace/files
    participant AGENT as /api/claude-agent
    participant WS as workspace.py
    participant DISK as 文件系统

    U->>CTX: 选择/创建对话 (conversationId)
    CTX->>FS: 传递 sessionId = conversationId
    FS->>API: GET /files?sessionId={cid}
    API->>WS: get_or_create_workspace(cid)
    WS->>DISK: mkdir files/ + logs/ + skills/
    WS->>DISK: sync .claude/ + .mcp.json
    WS->>DISK: sync_skills_symlinks → import .claude/skills real entries + symlink to .claude/skills/
    WS-->>API: workspace_path
    API-->>FS: 文件列表

    U->>FS: 上传文件
    FS->>API: POST /files (sessionId=cid)
    API->>DISK: 写入 {cwd}/{cid}/files/{name}
    API-->>FS: 刷新列表

    U->>AGENT: 发送消息 (conversationId=cid)
    AGENT->>WS: get_or_create_workspace(cid) → 复用同一目录
    AGENT->>DISK: agent_runner.run_streaming(cwd=workspace_path)
    Note over AGENT,DISK: Agent 可读写 {cid}/ 下所有文件；直接写入 .claude/skills 会在下次同步导入 skills/
    AGENT-->>FS: 流式返回 → FileSidebar 自动刷新
```

---

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AGENT_CWD` | `{tmpdir}/ink-agent-workspaces` | 工作空间根目录；生产环境建议设为持久化路径 |

```
AGENT_CWD=/data/workspaces (生产环境)
  └── {conversationId}/            ← Claude SDK cwd
      ├── .claude/                 ← 从项目根同步
      │   └── skills/              ← 软链接目标目录
      │       ├── my-skill.md      → symlink → skills/my-skill.md
      │       └── research-tools/  → symlink → skills/research-tools/
      ├── .mcp.json                ← 从项目根复制（首次）
      ├── files/                   ← 用户上传 + Agent 生成
      ├── logs/                    ← Agent 日志
      └── skills/                  ← 对话级 skills（用户操作此目录）
            ├── my-skill.md
            └── research-tools/    ← 支持文件夹
                └── web-search.md
```

---

## 上传与工作空间同步

### 保存路径规则

文件上传后通过 `POST /api/workspace/files`（`path=files`），文件落盘到：

`{AGENT_CWD}/{conversationId}/files/{finalName}`

规则如下：

- 始终写入工作空间 `files/` 目录
- 文件名会做安全清洗（去除路径分隔符、控制字符等）
- 同名冲突自动重命名（如 `report-1.pdf`、`report-2.pdf`）
- 路径安全校验，禁止路径穿越
- 上传限制：最大 `50MB`，并校验允许的 MIME 类型

### 错误处理

文件同步失败时，接口返回统一错误结构：

```json
{
  "error": "File MIME type is not allowed: application/x-msdownload",
  "code": "MIME_TYPE_NOT_ALLOWED",
  "details": {
    "mimeType": "application/x-msdownload"
  }
}
```

常见错误码（`WorkspaceFileSyncErrorCode`）：

- `INVALID_ATTACHMENT`
- `INVALID_WORKSPACE_PATH`
- `FILE_TOO_LARGE`
- `MIME_TYPE_NOT_ALLOWED`
- `DOWNLOAD_FAILED`
- `WRITE_FAILED`
- `INTERNAL_ERROR`

### 上传时序图

```mermaid
sequenceDiagram
    participant U as User
    participant UI as FileSidebar
    participant WAPI as /api/workspace/files
    participant LIB as workspace_file_sync.py
    participant DISK as Workspace FS

    U->>UI: 点击/拖拽文件
    UI->>WAPI: POST multipart(sessionId, path=files, file)
    WAPI->>LIB: save_buffer_to_workspace_files()
    LIB->>DISK: 写入 {cid}/files/{finalName}
    DISK-->>WAPI: savedPath + hash
    WAPI-->>UI: uploaded + files(metadata)
```
