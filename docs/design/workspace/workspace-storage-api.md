# Workspace File Management API — 设计文档

> **参考来源**: `glide-the/claude-agent-next-kit → docs/design/storage-api.md`
> **路径**: `backend/routers/workspace.py`
> **最后更新**: 2026-05-25

---

## 📋 概述

Workspace File Management API 提供对话级工作空间的文件管理服务。每个对话（`sessionId`）拥有独立的隔离目录，支持文件的列举、上传、下载、删除和移动操作。

此 API 是从 [`claude-agent-next-kit`](https://github.com/glide-the/claude-agent-next-kit/blob/feat/claude-agent-kit/app/api/workspace/files/route.ts) 的 Next.js 路由迁移到 Python FastAPI 的实现。

---

## 🗂️ 目录结构

```
backend/
├── libs/
│   └── claude_agent_kit/
│       └── server/
│           ├── workspace.py           ← 文件操作核心（list/read/write/delete/move）
│           └── workspace_file_sync.py ← Skills 同步 + 上传保存工具
└── routers/
    └── workspace.py                   ← FastAPI 路由定义
```

---

## 📡 API 端点

### 认证

所有端点均需要 ****** 认证：

```
Authorization: ******
```

---

### 1. 列举工作空间文件

```
GET /api/workspace/files
```

列举工作空间目录中的文件（非递归）或整棵文件树（递归）。

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sessionId` | string | ✅ | 工作空间会话 ID |
| `path` | string | 否 | 相对于工作空间根的子目录路径 |
| `recursive` | string | 否 | 设为 `"1"` 或 `"true"` 启用递归树模式 |

#### 响应示例

```json
{
  "files": [
    {
      "name": "report.pdf",
      "path": "files/report.pdf",
      "isDirectory": false,
      "size": 123456,
      "modifiedAt": "2026-05-25T12:00:00+00:00"
    }
  ],
  "tree": null,
  "recursive": false,
  "workspacePath": "/data/workspaces/conv_abc123",
  "workspaceCreated": false
}
```

#### 响应头

| 头 | 说明 |
|----|------|
| `x-workspace-instance-host` | 处理请求的服务器主机名 |
| `x-workspace-instance-pid` | 处理请求的进程 PID |

---

### 2. 上传文件

```
POST /api/workspace/files
Content-Type: multipart/form-data
```

上传一个或多个文件到工作空间。

#### 表单字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sessionId` | string | ✅ | 工作空间会话 ID |
| `path` | string | 否 | 目标子目录（如 `files`、`skills`） |
| `file` | File+ | ✅ | 一个或多个文件 |
| `relativePath` | string+ | 否 | 每个文件对应的相对路径（与 `file` 字段并行） |

#### 上传到 `files/` 的特殊行为

当 `path=files` 且文件不含子目录时，使用 `save_buffer_to_workspace_files()` 处理：

- 校验 MIME 类型
- 校验文件大小（最大 50 MB）
- 文件名安全清洗
- 自动重命名以避免冲突

#### 响应示例（成功）

```json
{
  "uploaded": ["files/report.pdf"],
  "files": [
    {
      "type": "workspace-file",
      "fileName": "report.pdf",
      "mimeType": "application/pdf",
      "size": 123456,
      "workspacePath": "files/report.pdf",
      "savedAt": "2026-05-25T12:00:00+00:00",
      "hash": "2cf24dba5fb0a30e26e83b2ac5..."
    }
  ],
  "workspacePath": "/data/workspaces/conv_abc123",
  "workspaceCreated": false
}
```

#### 响应示例（MIME 类型不允许）

```json
{
  "error": "File MIME type is not allowed: application/x-msdownload",
  "code": "MIME_TYPE_NOT_ALLOWED",
  "details": {
    "mimeType": "application/x-msdownload"
  }
}
```

#### 支持的 MIME 类型

- **文档**: PDF, Word, Excel, PowerPoint, TXT, CSV, Markdown, JSON
- **图片**: 所有 `image/*` 前缀类型
- **压缩**: ZIP, RAR, 7z, TAR, GZIP
- **媒体**: MP3, WAV, MP4 (audio), OGG, MP4 (video), WebM, QuickTime
- **通用**: `application/octet-stream`

---

### 3. 删除文件或目录

```
DELETE /api/workspace/files
Content-Type: application/json
```

删除工作空间中的文件或目录。

#### 请求体

```json
{
  "sessionId": "conv_abc123",
  "path": "files/old-report.pdf"
}
```

#### 响应示例（成功）

```json
{ "deleted": true }
```

#### 响应示例（未找到）

```json
{ "error": "File not found" }
```

（HTTP 404）

---

### 4. 移动 / 重命名文件

```
PATCH /api/workspace/files
Content-Type: application/json
```

在工作空间内移动或重命名文件/目录。

#### 请求体

```json
{
  "sessionId": "conv_abc123",
  "fromPath": "files/draft.md",
  "toPath": "files/final.md"
}
```

#### 响应示例（成功）

```json
{ "moved": true }
```

---

### 5. 下载文件

```
GET /api/workspace/files/download
```

下载工作空间中的单个文件。

#### 查询参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sessionId` | string | ✅ | 工作空间会话 ID |
| `path` | string | ✅ | 文件的相对路径 |

#### 响应

直接返回文件二进制内容，Content-Type 由文件名推断。

#### 响应头

| 头 | 示例值 |
|----|--------|
| `Content-Type` | `application/pdf` |
| `Content-Length` | `123456` |
| `Content-Disposition` | `attachment; filename="report.pdf"; filename*=UTF-8''report.pdf` |
| `Cache-Control` | `private, no-store` |
| `X-Content-Type-Options` | `nosniff` |

`filename` 始终是 ASCII/Latin-1-safe fallback，`filename*` 使用 RFC 8187 UTF-8 percent-encoding 承载真实文件名；例如中文文件名会通过 `filename*` 保留给浏览器下载使用，避免 ASGI 响应头的 latin-1 编码错误。

---

## 🔐 安全设计

### 路径遍历防护

所有文件操作均通过 `_resolve_workspace_safe_path()` 验证路径安全：

```python
candidate = (workspace_path / rel_path).resolve()
candidate.relative_to(workspace_path.resolve())  # 逃逸时抛出异常
```

### sessionId 校验

`get_or_create_workspace(session_id)` 会拒绝包含 `/`、`\`、`..` 的 sessionId，防止工作空间根目录逃逸。

### 上传安全

- MIME 类型白名单验证
- 文件大小限制（50 MB）
- 文件名安全清洗（去除控制字符、路径分隔符）
- 路径遍历校验

### 压缩包安全（Skills 上传）

上传到 `skills/` 的压缩包经过 `extract_archive_in_skills()` 处理：

- 拒绝绝对路径条目
- 拒绝 `..` 路径穿越
- 拒绝 TAR 软链接/硬链接条目
- 先提取到临时目录，成功后原子重命名

---

## 🏗️ 架构总览

```
┌─────────────────┐
│  HTTP 客户端     │
└────────┬────────┘
         │ ******
         ▼
┌─────────────────┐     ┌──────────────────────────────┐
│  workspace.py   │────▶│  get_or_create_workspace()    │
│  (FastAPI 路由)  │     │  get_workspace_root()         │
└────────┬────────┘     └──────────────────────────────┘
         │
    ┌────┴──────────────────────────────────────────┐
    │                                               │
    ▼                                               ▼
┌────────────────┐                      ┌────────────────────┐
│ workspace.py   │                      │ workspace_file_sync │
│ (libs/...)     │                      │ .py (libs/...)      │
│                │                      │                     │
│ list_*         │                      │ save_buffer_to_     │
│ read_*         │                      │ workspace_files()   │
│ write_*        │                      │ sync_skills_        │
│ delete_*       │                      │ symlinks()          │
│ move_*         │                      └────────────────────┘
└────────┬───────┘
         │
         ▼
┌─────────────────┐
│  本地文件系统    │
│  {AGENT_CWD}/   │
│  {sessionId}/   │
└─────────────────┘
```

---

## 📝 使用场景

### 场景 1: 前端展示工作空间文件列表

```python
# GET /api/workspace/files?sessionId=conv_abc&path=files
files = list_workspace_files(workspace_path, "files")
```

### 场景 2: 用户上传文件到对话工作空间

```python
# POST /api/workspace/files (multipart, path=files)
saved = save_buffer_to_workspace_files(
    workspace_path,
    file_name="report.pdf",
    mime_type="application/pdf",
    content=file_bytes,
)
# 返回 workspace-file 元数据，包含 hash、savedAt 等
```

### 场景 3: 下载 Agent 生成的文件

```python
# GET /api/workspace/files/download?sessionId=conv_abc&path=files/output.xlsx
file_obj = read_workspace_file_content(workspace_path, "files/output.xlsx")
# 返回 WorkspaceFileContent(content=bytes, file_name=str, size=int, modified_at=str)
```

---

## 🔗 相关文档

- [workspace-filesystem.md](./workspace-filesystem.md) — 工作空间目录结构与角色
- [workspace-skills-flow.md](./workspace-skills-flow.md) — Skills 同步完整流程
- [../file-storage/README.md](../file-storage/README.md) — 对象存储（S3/Local）API 设计
