# Docker Clash / Mihomo TUN

本目录用于 Docker TUN 代理。真实 `config.yaml` 包含订阅、节点、密码等敏感信息，已被 `.gitignore` 忽略，不要提交。

## 准备配置

从本机 Clash profile 复制一份到仓库的忽略路径：

```bash
mkdir -p deploy/clash
cp /Users/dmeck/.config/clash/profiles/1754902792612.yml deploy/clash/config.yaml
chmod 600 deploy/clash/config.yaml
```

当前 profile 顶层已有 `mixed-port`、`proxies`、`proxy-groups`、`rules`，但没有 `tun:`。启动 Compose 前，把 `config.tun-snippet.yaml` 里的非敏感字段合并进 `deploy/clash/config.yaml`。

如果要访问 Mihomo controller，`external-controller` 需要监听 `0.0.0.0:9090`；如果只在容器内部使用，可继续保持更严格的监听地址。

## 本地 Docker 启动

```bash
./deploy/docker/deploy.sh start
```

等价手动命令：

```bash
docker compose -f docker-compose.yml up --build -d
```

启动后：

- `tun-proxy` 使用 `metacubex/mihomo:latest` 和 `/dev/net/tun`。
- `ink-backend` 使用 `network_mode: service:tun-proxy`，后端所有出站流量经过 Mihomo TUN。
- 后端主机端口由 `tun-proxy` 发布，默认仍是 `127.0.0.1:8765`。
- 前端 nginx fallback 通过 `http://tun-proxy:8765` 访问后端。

## Remote SSH 启动

```bash
export REMOTE_SSH_HOST=<server-host-or-ip>
export REMOTE_APP_DIR=/srv/ink-and-memory
./deploy/remote-ssh/deploy.sh deploy
```

默认会把本地 `deploy/clash/config.yaml` 随仓库同步到远端，并由 `deploy/remote-ssh/docker-compose.yml` 启动 `tun-proxy`。如远端已有独立配置文件，可覆盖：

```bash
export REMOTE_CLASH_CONFIG_FILE=/srv/clash/config.yaml
./deploy/remote-ssh/deploy.sh deploy
```

## 验证

```bash
docker exec ink-backend sh -lc 'python - <<PY
import urllib.request
print(urllib.request.urlopen("https://accounts.google.com/.well-known/openid-configuration", timeout=10).status)
PY'
```

预期返回 `200`。如果失败，先检查宿主机是否存在 `/dev/net/tun`，以及 `deploy/clash/config.yaml` 是否包含 `tun.enable: true`。
