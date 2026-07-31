# 数据同步指南：本地 ↔ Cloud Storage

后端运行时数据存储在 GCS bucket（通过 Cloud Storage FUSE 挂载到 `/app/data/`）。本文说明如何在本地和云端之间同步数据。

---

## 数据目录结构

```
本地：backend/data/                    云端：gs://ink-memory-data-<PROJECT_ID>/
├── ink-and-memory.db   (SQLite DB)    ├── ink-and-memory.db
├── file-storage/                      ├── file-storage/
└── agent-workspace/                   └── agent-workspace/
```

---

## 前置条件

```bash
# 确认 .storage-env 存在（由 setup-storage.sh 生成）
source .storage-env
echo $GCS_BUCKET   # 应输出 bucket 名称
```

---

## 上传本地数据到云端

推荐使用平台入口执行自动上传数据库和重启：

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/google-cloud/deploy.sh sync-data
```

`deploy/google-cloud/sync-data.sh` 是实际实现，`deploy/sync-data.sh` 仅兼容旧路径；通过主入口执行时会先做 Google Cloud 发布前置检查。自动脚本会先把云端 SQLite 主文件及存在的 WAL/SHM 文件下载到 `backend/data/bak_YYYYMMDD_HHMMSS/`，再上传本地 SQLite 主文件及存在的 WAL/SHM 文件，并用 `gcloud run services update --update-env-vars` 触发后端重启；它会忽略 `.cloud-env` 中旧的 `INK_CORS_ALLOW_ORIGINS` / `INK_CORS_ALLOW_CREDENTIALS`，再按默认固定前端域名写回 `INK_CORS_ALLOW_ORIGINS=https://ink-frontend.suoxya.com`。

如遇到线上日志出现 `sqlite3.DatabaseError: database disk image is malformed`，先执行只下载备份，不上传、不重启：

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/google-cloud/deploy.sh backup-data
```

输出目录形如：

```text
backend/data/bak_20260612_163607/
├── ink-and-memory.db
├── ink-and-memory.db-wal  # 如云端存在
└── ink-and-memory.db-shm  # 如云端存在
```

该命令会尽量运行 `sqlite3 "PRAGMA integrity_check;"`。即使检查提示损坏，也会保留下载文件，供后续恢复分析；不要在未备份前覆盖 GCS 数据。

固定域名验证：

```bash
curl -fsS https://ink-backend.suoxya.com/api/health
```

Claude Agent 鉴权排障：

如果数据同步重启后线上日志出现：

```text
Claude SDK has no auth key in subprocess env
```

优先确认 `.cloud-env` 的 `CLOUD_SECRET_REFS` 包含 `ANTHROPIC_AUTH_TOKEN=ink-anthropic-auth-token:latest`。缺失时先重新运行：

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/google-cloud/deploy.sh setup-env
./deploy/google-cloud/deploy.sh deploy
```

Cloud Run 中 Secret Manager 会把 `ANTHROPIC_AUTH_TOKEN` 注入为后端进程环境变量；后端 SDK env helper 会在启动 Claude Code 子进程前，把该进程环境变量显式合并到 `ClaudeAgentOptions.env`。

如需完整同步 `file-storage/` 和 `agent-workspace/`，仍使用下面的手动命令。

```bash
source .storage-env

# 上传数据库
gsutil cp backend/data/ink-and-memory.db \
  gs://${GCS_BUCKET}/ink-and-memory.db

# 上传 file-storage 和 agent-workspace
gsutil -m rsync -r backend/data/file-storage/    gs://${GCS_BUCKET}/file-storage/
gsutil -m rsync -r backend/data/agent-workspace/ gs://${GCS_BUCKET}/agent-workspace/
```

> **注意**：Cloud Run 后端写入数据时，直接操作 GCS bucket。如果服务正在运行，上传数据库前最好先停止服务，避免写入冲突。

---

## 从云端下载数据到本地

推荐使用脚本生成 `bak_日期` 目录，避免覆盖当前本地数据：

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/google-cloud/deploy.sh backup-data
```

兼容旧路径：

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/sync-data.sh backup-cloud
```

新实现也可以直接调用：

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/google-cloud/sync-data.sh backup-cloud
```

以下手动命令会直接覆盖本地数据库文件，只有在明确要恢复到 `backend/data/` 时使用：

```bash
source .storage-env

# 下载数据库
gsutil cp gs://${GCS_BUCKET}/ink-and-memory.db \
  backend/data/ink-and-memory.db

# 下载所有数据（完整备份）
gsutil -m rsync -r gs://${GCS_BUCKET}/file-storage/    backend/data/file-storage/
gsutil -m rsync -r gs://${GCS_BUCKET}/agent-workspace/ backend/data/agent-workspace/
```

---

## 查看云端数据

```bash
source .storage-env

# 查看 bucket 内容和大小
gsutil ls -l gs://${GCS_BUCKET}/
gsutil du -sh gs://${GCS_BUCKET}/

# 只查看数据库文件信息
gsutil ls -l gs://${GCS_BUCKET}/ink-and-memory.db
```

---

## 查看数据库内容

下载到本地后，用命令行或图形工具查看：

```bash
# 查看所有表
sqlite3 backend/data/ink-and-memory.db ".tables"

# 查看会话数量
sqlite3 backend/data/ink-and-memory.db \
  "SELECT COUNT(*) as total FROM user_sessions;"

# 查看最近 5 条会话
sqlite3 backend/data/ink-and-memory.db \
  "SELECT id, created_at FROM user_sessions ORDER BY created_at DESC LIMIT 5;"
```

图形工具推荐 [DB Browser for SQLite](https://sqlitebrowser.org)（免费），直接打开 `.db` 文件即可浏览表结构和数据。

---

## 手动备份

```bash
source .storage-env

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
gsutil cp gs://${GCS_BUCKET}/ink-and-memory.db \
  gs://${GCS_BUCKET}/backups/ink-and-memory_${TIMESTAMP}.db

echo "Backup saved: gs://${GCS_BUCKET}/backups/ink-and-memory_${TIMESTAMP}.db"
```

GCS bucket 已开启版本控制，每次覆盖写入都会保留历史版本，可在 Cloud Console 的 bucket 详情页恢复。

---

## SQLite WAL 模式说明

后端使用 WAL（Write-Ahead Logging）模式，运行时会产生三个文件：

| 文件 | 说明 |
|------|------|
| `ink-and-memory.db` | 主数据库文件 |
| `ink-and-memory.db-wal` | WAL 日志（活跃写入时存在） |
| `ink-and-memory.db-shm` | 共享内存文件（活跃写入时存在） |

**下载时**：如果服务正在运行，`-wal` 和 `-shm` 文件也需要一起下载，否则本地打开的数据库可能不完整。

```bash
source .storage-env

# 完整下载（含 WAL 文件）
gsutil cp "gs://${GCS_BUCKET}/ink-and-memory.db*" backend/data/
```

脚本化备份命令默认下载同一组 `ink-and-memory.db*` 文件到 `backend/data/bak_YYYYMMDD_HHMMSS/`，不会覆盖 `backend/data/ink-and-memory.db`。
