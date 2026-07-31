# deploy

## 定位

`deploy/` 是 Ink & Memory 的平台化发布脚本入口。新入口按运行平台分目录组织，旧的 Google Cloud Run 根路径保留为兼容包装，实际云发布实现放在 `deploy/google-cloud/`。

## 推荐入口

| 平台 | 入口 | 说明 |
|------|------|------|
| 本地发布 | [`local/deploy.sh`](local/deploy.sh) | 检查、构建、启动、验证、停止本地 backend/frontend 进程 |
| Docker 发布 | [`docker/deploy.sh`](docker/deploy.sh) | 包装根目录 [`../docker-compose.yml`](../docker-compose.yml) 的构建、启动、验证、清理；默认通过 Mihomo TUN `tun-proxy` 路由 backend 出站；backend 容器包含 Claude Code bubblewrap Bash sandbox 所需 runtime 权限 |
| Remote SSH 发布 | [`remote-ssh/deploy.sh`](remote-ssh/deploy.sh) | 一键编排 SSH/rsync、主机 nginx、远端存储初始化、Docker Compose 构建启动与验证；默认通过 Mihomo TUN `tun-proxy` 路由 backend 出站，并写入生产 OAuth URL、Secure cookie 和前端域名 CORS；高级场景可用其 `setup-nginx` / `setup-storage` / `backup-data` / `sync-data` / `download-data` 子命令 |
| Google Cloud 发布 | [`google-cloud/deploy.sh`](google-cloud/deploy.sh) | 完整 Cloud Run 发布入口，默认使用 `ink-backend.suoxya.com` / `ink-frontend.suoxya.com`，提供构建、推送、部署、OAuth/CORS/cookie 回写、dry-run/check/verify/rollback |

## 兼容入口

以下旧路径继续可用，供已有文档、脚本或个人习惯调用：

| 旧脚本 | 新入口中的对应命令 | 实际实现 |
|--------|-------------------|----------|
| [`setup-storage.sh`](setup-storage.sh) | `./deploy/google-cloud/deploy.sh setup-storage` | [`google-cloud/setup-storage.sh`](google-cloud/setup-storage.sh) |
| [`setup-env.sh`](setup-env.sh) | `./deploy/google-cloud/deploy.sh setup-env` | [`setup-env.sh`](setup-env.sh)，暂保留在根目录供云入口编排 |
| [`deploy.sh`](deploy.sh) | `./deploy/google-cloud/deploy.sh deploy` | [`google-cloud/deploy.sh`](google-cloud/deploy.sh) |
| [`sync-data.sh`](sync-data.sh) | `./deploy/google-cloud/deploy.sh sync-data` | [`google-cloud/sync-data.sh`](google-cloud/sync-data.sh) |

云端 SQLite 故障或停机维护前，先执行只下载备份：

```bash
./deploy/google-cloud/deploy.sh backup-data
```

该命令会把 `gs://${GCS_BUCKET}/ink-and-memory.db*` 下载到 `backend/data/bak_YYYYMMDD_HHMMSS/`，不会上传本地数据，也不会重启 Cloud Run。

## 通用约定

每个平台入口都支持：

```bash
./deploy/<platform>/deploy.sh --help
./deploy/<platform>/deploy.sh --dry-run <command>
./deploy/<platform>/deploy.sh --check
```

脚本不写死项目 ID、bucket、主机、服务名或密钥。需要覆盖默认值时使用环境变量、Compose 配置或平台脚本参数。

生产 Google OAuth 固定要求：

```text
WEBUI_URL=https://ink-frontend.suoxya.com
API_BASE_URL=https://ink-backend.suoxya.com
COOKIE_SECURE=true
COOKIE_SAMESITE=none
INK_CORS_ALLOW_ORIGINS=https://ink-frontend.suoxya.com
INK_CORS_ALLOW_CREDENTIALS=true
```

`GOOGLE_CLIENT_SECRET`、`JWT_SECRET`、`SESSION_SECRET_KEY` 在 Cloud Run 路径由 Secret Manager 注入；Remote SSH 路径从远端 `backend/.env` / Compose 环境读取，不应写入仓库。

Docker Compose 类发布默认依赖 `deploy/clash/config.yaml`。该文件从本机 Clash
profile 复制生成，包含代理节点和订阅信息，已被 `deploy/clash/.gitignore`
忽略；发布前需合并 `deploy/clash/config.tun-snippet.yaml` 中的 `tun`
配置，并确认宿主机存在 `/dev/net/tun`。

Docker Compose 类入口的 backend 容器需要 `SYS_ADMIN`、`seccomp=unconfined`
和 `apparmor=unconfined`，用于允许 Claude Code 的 bubblewrap Bash sandbox
创建 mount namespace。该权限只授予 backend 容器；thread workspace 边界仍由
`.claude/settings.json` sandbox 配置和 PreToolUse 权限策略控制。
