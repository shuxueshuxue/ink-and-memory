# 部署指南：Google Cloud Run

本文档描述 Ink & Memory 的 Cloud Run 部署架构与操作步骤。当前云发布主入口是 [`../../deploy/google-cloud/deploy.sh`](../../deploy/google-cloud/deploy.sh)，旧的 `deploy/*.sh` 路径仅保留兼容或作为主入口编排的辅助脚本。

---

## 整体架构

```
用户浏览器
    │
    ▼
┌─────────────────────────────────────┐
│  Cloud Run: ink-frontend            │
│  Public: https://ink-frontend.suoxya.com │
│  nginx 1.27-alpine                  │
│  · 服务 / 静态资源                  │
│  · runtime-config.js 注入 API_BASE_URL │
└─────────────────────┬───────────────┘
                      │ 浏览器跨域 HTTPS (API_BASE_URL)
                      ▼
┌─────────────────────────────────────┐
│  Cloud Run: ink-backend             │
│  Public: https://ink-backend.suoxya.com │
│  python:3.10-slim-bookworm + uvicorn:8765 │
│  · REST / SSE / WebSocket API       │
│  · Secret Manager refs (API keys)   │
└─────────────────────┬───────────────┘
                      │ GCS FUSE 挂载
                      ▼
┌─────────────────────────────────────┐
│  Cloud Storage: ink-memory-data-*   │
│  /app/data/                         │
│  ├── ink-and-memory.db   (SQLite)   │
│  ├── file-storage/                  │
│  └── agent-workspace/               │
└─────────────────────────────────────┘
```

---

## 脚本说明

Google Cloud 部署脚本位于项目根目录下的 `deploy/` 文件夹。优先使用平台目录入口，旧根脚本继续兼容已有调用。

| 脚本 | 执行时机 | 作用 |
|------|---------|------|
| `deploy/google-cloud/deploy.sh setup-storage` | **首次部署前**（一次性） | 创建 GCS bucket、服务账号、IAM 授权 |
| `deploy/google-cloud/deploy.sh setup-env` | **首次部署前及 secrets 变更时** | 配置 Secret Manager secrets、Google OAuth/JWT/session secrets 和 Cloud Run 环境变量 |
| `deploy/google-cloud/deploy.sh deploy` | **每次发版** | 并行构建镜像、推送到 Artifact Registry、部署前后端并回写后端 OAuth URL、cookie policy 和 CORS origin |
| `deploy/google-cloud/deploy.sh backup-data` | **停机、修复或同步前** | 下载云端 SQLite/WAL/SHM 到本地 `backend/data/bak_<date>/`，不上传、不重启 |
| `deploy/deploy.sh` | **兼容入口** | 委托执行 `deploy/google-cloud/deploy.sh deploy` |

---

## 前置条件

- [Google Cloud SDK (gcloud CLI)](https://cloud.google.com/sdk/docs/install) 已安装
- Docker 已安装并运行
- 已创建 Google Cloud 项目并开启计费
- 已执行 `gcloud auth login`

---

## 首次部署步骤

### 1. 初始化存储

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/google-cloud/deploy.sh setup-storage
```

执行内容：
- 启用 `storage.googleapis.com`、`run.googleapis.com`、`iam.googleapis.com` API
- 在指定区域（默认 `asia-east1`）创建 GCS bucket `ink-memory-data-<PROJECT_ID>`
- 开启 bucket 版本控制（防止数据意外覆盖）
- 预建 `file-storage/`、`agent-workspace/` 目录占位符
- 创建专用服务账号 `ink-backend-sa`，授予 `Storage Object Admin`
- 将 bucket 名和 SA 邮箱写入根目录 `.storage-env`（已加入 `.gitignore`）

### 2. 配置环境变量

```bash
./deploy/google-cloud/deploy.sh setup-env
```

脚本会交互式询问配置项，从 `backend/.env` 读取已有值作为默认（直接回车确认）：

**交互确认值 → Secret Manager**

| 变量 | Secret 名称 | 说明 |
|------|------------|------|
| `ANTHROPIC_BASE_URL` | `ink-anthropic-base-url` | Anthropic 兼容 API 基础地址 |
| `ANTHROPIC_AUTH_TOKEN` | `ink-anthropic-auth-token` | Anthropic 兼容 API 认证 token |
| `ANTHROPIC_MODEL` | `ink-anthropic-model` | 默认模型 |
| `ANTHROPIC_DEFAULT_HAIKU_MODEL` | `ink-anthropic-haiku-model` | Haiku 默认模型 |
| `ANTHROPIC_DEFAULT_SONNET_MODEL` | `ink-anthropic-sonnet-model` | Sonnet 默认模型 |
| `ANTHROPIC_DEFAULT_OPUS_MODEL` | `ink-anthropic-opus-model` | Opus 默认模型 |
| `AGENT_CWD` | `ink-agent-cwd` | Agent 工作区路径，Cloud Run 默认 `/app/data/agent-workspace` |
| `FILE_STORAGE_LOCAL_DIR` | `ink-file-storage-dir` | 文件存储路径，Cloud Run 默认 `/app/data/file-storage` |
| `GOOGLE_CLIENT_SECRET` | `ink-google-client-secret` | Google OAuth Web Client Secret |
| `JWT_SECRET` | `ink-jwt-secret` | 本系统 access token 签名密钥 |
| `SESSION_SECRET_KEY` | `ink-session-secret-key` | OAuth state/session cookie 签名密钥 |
| `OAUTH_TOKEN_ENCRYPTION_KEY` | `ink-oauth-token-encryption-key` | 预留：如后续保存 Google token，必须用于加密 |

**配置值 → Cloud Run 环境变量**

| 来源 | 默认值/行为 | 说明 |
|------|-------------|------|
| `TZ` | `UTC` | `setup-env.sh` 固定写入 `.cloud-env` |
| `backend/.env` 中非 Secret Manager key | 原值透传 | 除上表交互确认 key 和 `TZ` 外，其他 key 会写入 `.cloud-env` 的 `CLOUD_ENV_VARS` |
| `GOOGLE_CLIENT_ID` | 来自 `backend/.env` | Google OAuth Web Client ID，非 secret |
| `WEBUI_URL` | 部署脚本写入 `https://ink-frontend.suoxya.com` | OAuth callback 成功后的前端跳转目标 |
| `API_BASE_URL` | 部署脚本写入 `https://ink-backend.suoxya.com` | Google OAuth callback URI 构造依据 |
| `COOKIE_SECURE` | `true` | 生产 HTTPS cookie 必须开启 Secure |
| `COOKIE_SAMESITE` | `none` | 前后端分域时允许跨站 cookie |
| `INK_CORS_ALLOW_ORIGINS` | `https://ink-frontend.suoxya.com` | 生产后端只允许可信前端 origin |
| `INK_CORS_ALLOW_CREDENTIALS` | `true` | Google OAuth cookie 登录需要允许浏览器 credentials |

输出写入根目录 `.cloud-env`（已加入 `.gitignore`）。

`setup-env` 不把 `WEBUI_URL`、`API_BASE_URL`、`COOKIE_SECURE`、`COOKIE_SAMESITE`、`INK_CORS_ALLOW_ORIGINS` / `INK_CORS_ALLOW_CREDENTIALS` 写入 `.cloud-env`。这些变量由 `deploy/google-cloud/deploy.sh deploy` 按固定公开域名更新到后端，避免后续数据同步或普通环境变量刷新把生产 OAuth/CORS/cookie 配置覆盖回本地默认值。

Google Console 必须配置：

```text
Authorized JavaScript origins:
  https://ink-frontend.suoxya.com

Authorized redirect URIs:
  https://ink-backend.suoxya.com/oauth/google/callback
```

### 3. 部署

```bash
./deploy/google-cloud/deploy.sh deploy
```

执行流程：

```
Step 1  设置 GCP 项目
Step 2  启用 Cloud Run / Artifact Registry / Cloud Build API
Step 3  确认 Artifact Registry 仓库存在（idempotent）
Step 4  配置 Docker 认证
Step 5  并行构建后端镜像 + 前端镜像
Step 6  并行推送两个镜像
Step 7  部署后端服务 → 获取 BACKEND_URL（run.app 服务 URL，作为 nginx fallback）
        部署前端服务（默认注入 API_BASE_URL=https://ink-backend.suoxya.com）
        回写后端 WEBUI_URL / API_BASE_URL / cookie policy / INK_CORS_ALLOW_ORIGINS
        默认 WEBUI_URL=https://ink-frontend.suoxya.com
        默认 API_BASE_URL=https://ink-backend.suoxya.com
        默认 COOKIE_SECURE=true, COOKIE_SAMESITE=none
        默认 INK_CORS_ALLOW_ORIGINS=https://ink-frontend.suoxya.com
```

部署完成后输出：
```
Original Cloud Run frontend gateway : https://ink-frontend-xxxx-xx.a.run.app/
Original Cloud Run backend gateway  : https://ink-backend-xxxx-xx.a.run.app
Public frontend                     : https://ink-frontend.suoxya.com/
Public backend                      : https://ink-backend.suoxya.com
API base                            : https://ink-backend.suoxya.com
CORS                                : https://ink-frontend.suoxya.com
```

---

## 后续发版

只需重新执行第 3 步：

```bash
./deploy/google-cloud/deploy.sh deploy
```

- secrets 更新时重跑第 2 步：`./deploy/google-cloud/deploy.sh setup-env`
- 存储结构无需重建（bucket 和 SA 已存在，脚本幂等）

---

## 环境变量覆盖

所有可选覆盖项均通过 `export` 设置：

```bash
export GCP_PROJECT_ID=my-project
export GCP_REGION=us-central1        # 默认 asia-east1
export REPO_NAME=my-registry-repo    # 默认 ink-and-memory
export BACKEND_SERVICE=my-backend    # 默认 ink-backend
export FRONTEND_SERVICE=my-frontend  # 默认 ink-frontend
export BUCKET_NAME=my-bucket         # 默认 ink-memory-data-<PROJECT_ID>
export SA_NAME=my-sa                 # 默认 ink-backend-sa
export BACKEND_PUBLIC_ORIGIN=https://ink-backend.suoxya.com    # 默认固定后端公开域名
export FRONTEND_PUBLIC_ORIGIN=https://ink-frontend.suoxya.com  # 默认固定前端公开域名
export FRONTEND_API_BASE_URL=https://api.example.com      # 可选覆盖；默认 BACKEND_PUBLIC_ORIGIN
export BACKEND_CORS_ALLOW_ORIGINS=https://app.example.com # 可选覆盖；默认 FRONTEND_PUBLIC_ORIGIN
export INK_CORS_ALLOW_CREDENTIALS=true                    # 默认 true，OAuth cookie 登录需要
export BACKEND_COOKIE_SECURE=true                         # 默认 true
export BACKEND_COOKIE_SAMESITE=none                       # 默认 none，前后端分域需要
```

`FRONTEND_PUBLIC_ORIGIN` / `BACKEND_CORS_ALLOW_ORIGINS` 应填写浏览器 Origin（协议 + 主机 + 可选端口），不要包含路径；部署脚本会自动去掉末尾 `/`。

## OAuth 发布验证

发布完成后至少验证：

```bash
curl -I https://ink-backend.suoxya.com/api/health
curl -I 'https://ink-backend.suoxya.com/oauth/google/login?return_to=/'
curl -I https://ink-frontend.suoxya.com/runtime-config.js
```

预期：

- `/api/health` 返回 `200`。
- `/oauth/google/login` 返回 `302`，`Location` 指向 `accounts.google.com`，并包含 `redirect_uri=https%3A%2F%2Fink-backend.suoxya.com%2Foauth%2Fgoogle%2Fcallback`。
- `runtime-config.js` 中 `apiBaseUrl` 为 `https://ink-backend.suoxya.com`。
- 浏览器点击 `Continue with Google` 后能进入 Google，并在 callback 后回到 `https://ink-frontend.suoxya.com`。

### Docker 构建源覆盖

前后端 Dockerfile 默认使用国内镜像源加速构建；这些源均可通过 `docker build --build-arg` 覆盖：

| Build arg | 默认值 | 作用范围 |
|-----------|--------|----------|
| `DEBIAN_MIRROR` | `https://mirrors.aliyun.com/debian` | 后端 apt Debian 主源 |
| `DEBIAN_SECURITY_MIRROR` | `https://mirrors.aliyun.com/debian-security` | 后端 apt security 源 |
| `PYPI_INDEX_URL` | `https://mirrors.aliyun.com/pypi/simple/` | 后端 pip 主源 |
| `PYPI_TRUSTED_HOST` | `mirrors.aliyun.com` | 后端 pip trusted host |
| `NPM_REGISTRY` | `https://registry.npmmirror.com` | 前端 npm install、后端 Claude Code CLI 安装 |

示例：

```bash
docker build \
  --build-arg NPM_REGISTRY=https://registry.npmjs.org \
  --build-arg DEBIAN_MIRROR=http://deb.debian.org/debian \
  --build-arg DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security \
  -t ink-backend:local ./backend
```

---

## 数据持久化

后端使用 **Cloud Storage FUSE** 将 GCS bucket 挂载到容器的 `/app/data/`，三类数据的路径映射：

| 数据 | 容器路径 | GCS bucket 路径 |
|------|---------|----------------|
| SQLite 数据库 | `/app/data/ink-and-memory.db` | `ink-memory-data-<project>/` |
| 文件存储 | `/app/data/file-storage/` | `ink-memory-data-<project>/file-storage/` |
| Agent 工作区 | `/app/data/agent-workspace/` | `ink-memory-data-<project>/agent-workspace/` |

> **注意：** SQLite 使用 WAL 模式（`.db-wal`、`.db-shm` 辅助文件）。后端服务限制为 `max-instances=1`，避免多实例并发写入同一 GCS 路径导致数据损坏。

---

## 容器镜像构建

### 后端（`backend/Dockerfile`）

基于 `python:3.10-slim-bookworm`，安装系统依赖（gcc、libffi、openssl、libjpeg、zlib、curl、jq、git、ripgrep、nodejs、npm、bubblewrap、socat），安装 Python 依赖与 `@anthropic-ai/claude-code` / `@anthropic-ai/sandbox-runtime`，暴露端口 8765。`bubblewrap` / `socat` 是 Claude Code Linux Bash sandbox 依赖；Docker Compose / Remote SSH Docker 部署会额外启用 nested sandbox 兼容模式，并给 backend 容器授予 `SYS_ADMIN`、`seccomp=unconfined`、`apparmor=unconfined` 以允许 bubblewrap 创建 mount namespace。镜像还显式确保 `/sbin`、`/usr/sbin`、`/usr/local/sbin` 存在，避免 bubblewrap 构造 rootfs 时在 `/newroot/sbin` 挂载 tmpfs 失败。构建阶段会先用 `DEBIAN_MIRROR` / `DEBIAN_SECURITY_MIRROR` 替换 apt 源，并通过 `PYPI_INDEX_URL`、`NPM_REGISTRY` 加速 Python/npm 依赖安装。

### 前端（`frontend/Dockerfile`）

两阶段构建：
1. **构建阶段**：`node:22-alpine`，先用 `NPM_REGISTRY` 设置 npm registry，再执行 `npm install && npm run build`，输出到 `dist/`
2. **服务阶段**：`nginx:1.27-alpine`，拷贝 `dist/` 到 `/usr/share/nginx/html/`，容器启动时生成 `runtime-config.js` 注入 `API_BASE_URL`，同时保留 `nginx.conf.template` 的 `BACKEND_URL` 同源代理 fallback

nginx 配置要点：
- 前端默认通过 `runtime-config.js` 读取 `API_BASE_URL`，浏览器直接跨域请求固定后端域名 `https://ink-backend.suoxya.com`
- `runtime-config.js` 和 SPA HTML 入口设置为 `no-store`，避免浏览器沿用旧入口或旧的空 `apiBaseUrl` 后把 POST/PUT 请求打回前端静态服务并触发 `Method Not Allowed`
- `nginx.conf.template` 保留 `/api/` 和 `/polycli/` 反向代理，用作同源调用 fallback
- 静态资源设置 1 年强缓存（`immutable`）

### 前端请求返回 Method Not Allowed

优先判断请求是否打到了错误服务：

```bash
curl -fsS https://ink-backend.suoxya.com/api/health
curl -fsS https://ink-frontend.suoxya.com/runtime-config.js?runtime=1
```

`runtime-config.js` 中的 `apiBaseUrl` 应为 `https://ink-backend.suoxya.com`。如果为空，前端会回退到同源 `/api` / `/polycli` 路径；若同源代理未正确指向后端，POST/PUT 请求可能落到前端静态服务，从而返回 `405 Method Not Allowed`。重新发布前端镜像并强制刷新浏览器缓存即可验证；新模板已对该文件禁用缓存。

---

## 本地 Docker Compose 运行

```bash
# 复制并填写后端配置
cp backend/models.json.example backend/models.json

docker compose up --build
# 访问 http://localhost/
```

`docker-compose.yml` 中前端保留 `BACKEND_URL=http://ink-backend:8765` 作为 nginx fallback，同时设置 `API_BASE_URL=http://127.0.0.1:8765`，浏览器默认直接跨域请求本机后端端口。

Claude-agent 的 Bash sandbox 在 Docker 中由 bubblewrap 创建 mount namespace。
根目录 `docker-compose.yml` 的 backend 服务因此设置：

```yaml
cap_add:
  - SYS_ADMIN
security_opt:
  - seccomp=unconfined
  - apparmor=unconfined
```

这组权限只授予 backend 容器，用于避免 `bwrap: Failed to make / slave:
Permission denied`。它不改变 Claude-agent 的 thread workspace 边界；
业务文件访问仍由 `{AGENT_CWD}/{thread_id}` sandbox 配置和 PreToolUse 权限策略控制。

若看到 `bwrap: Can't mount tmpfs on /newroot/sbin: No such file or directory`，
说明 bubblewrap 已进入 rootfs 构造阶段，但标准系统目录没有出现在沙箱运行时视图中。
当前后端会把存在的 `/sbin`、`/usr/sbin`、`/usr/local/sbin` 加入 sandbox
只读运行时 allowlist；如果 `/sbin` 是 symlink，也会同时保留 literal
alias 和 canonical target。镜像构建也会创建这些目录。
