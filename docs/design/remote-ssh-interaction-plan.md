# Remote SSH 一键部署交互方案设计稿

## 目标

本方案修复 Remote SSH 部署体验和域名配置问题：

1. 远端访问采用两个主机 nginx 路由：
   - `ink-backend.suoxya.com` → `127.0.0.1:8765`
   - `ink-frontend.suoxya.com` → `127.0.0.1:8080`
2. 前端浏览器登录接口默认访问 `https://ink-backend.suoxya.com/api/login`，不再访问 Docker 内部地址 `http://ink-backend:8765/api/login`。
3. nginx 安装/更新、远端存储初始化和 Docker Compose 部署由 `deploy/remote-ssh/deploy.sh deploy` 统一编排，减少文档中的多步手工流程。
4. 保留 `setup-nginx`、`setup-storage`、`backup-data`、`sync-data`、`download-data` 等高级子命令，便于单独运维。

## 处理判断

- `http://ink-backend:8765` 只能在 Docker 网络或前端容器内部 nginx 中解析，不能作为浏览器 runtime API base URL。
- Remote SSH 面向公网域名发布时，应默认走“浏览器 → 后端公网域名 → 主机 nginx → 后端容器”的链路。
- 主入口应具备判断能力：当容器端口绑定到 `127.0.0.1` 且对外依赖公网域名时，`deploy` 自动安装/刷新主机 nginx；当远端数据目录不存在或权限需要修复时，`deploy` 自动创建/修复持久化目录。
- `BACKEND_URL=http://ink-backend:8765` 可以继续保留，作为前端容器内部 nginx fallback 代理上游。
- `API_BASE_URL` 必须默认写入公网后端 origin：`https://ink-backend.suoxya.com`。

## 一键交互流程

1. 运维只设置 SSH 与远端目录：
   ```bash
   export REMOTE_SSH_HOST=<server-host-or-ip>
   export REMOTE_SSH_USER=<ssh-user>
   export REMOTE_APP_DIR=/srv/ink-and-memory
   ```
2. 执行同一个入口完成首次安装与后续部署：
   ```bash
   ./deploy/remote-ssh/deploy.sh deploy
   ```
3. `deploy.sh` 内部依次执行：
   - 检查本地和远端前置条件。
   - 根据 `REMOTE_SETUP_NGINX=auto` 判断并执行 nginx setup。
   - 根据 `REMOTE_SETUP_STORAGE=1` 创建/修复远端持久化目录。
   - rsync 代码并保留远端数据。
   - 构建启动 Compose 并验证服务。
4. 验证浏览器登录请求指向：
   ```text
   https://ink-backend.suoxya.com/api/login
   ```

## 数据维护交互

- 底层数据脚本只保留 `backup`、`upload`、`download` 三个动作。
- 仅备份远端数据到本地快照目录，不覆盖本地根数据：
  ```bash
  ./deploy/remote-ssh/deploy.sh backup-data
  ```
- 用本地 `backend/data/` 覆盖/同步远端前，先自动备份远端：
  ```bash
  ./deploy/remote-ssh/deploy.sh sync-data
  ```
  上传完成后按 `deploy.sh` 的启动语义执行 `docker-compose up -d --force-recreate`，让后端重新加载数据库。
- 下载远端 `backend/data/` 到本地前，先自动备份当前本地数据：
  ```bash
  ./deploy/remote-ssh/deploy.sh download-data
  ```

## 验收标准

- `deploy/remote-ssh/deploy.sh deploy` 会在默认 `auto` 模式下编排 nginx setup、storage setup、代码同步、Compose 启动和验证。
- Remote SSH Compose 默认前端端口为 `127.0.0.1:8080`。
- Remote SSH Compose 默认 `API_BASE_URL=https://ink-backend.suoxya.com`。
- 后端 CORS 默认允许 `https://ink-frontend.suoxya.com`。
- 文档主流程只保留一个部署入口，单独脚本降级为高级运维命令。
- Remote SSH 数据维护只暴露 `backup`、`upload`、`download`，其中 `upload` 后必须 force-recreate Compose 服务。
