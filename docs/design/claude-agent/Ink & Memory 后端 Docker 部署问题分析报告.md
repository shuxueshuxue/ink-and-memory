下面是一份可直接放进项目记录里的分析报告。核心结论很明确：**运行期的 `apply-seccomp / setgroups` 是 Claude Code sandbox-runtime 在 Docker 嵌套 user namespace 下的问题；当前构建失败的 `exit code: 100` 则是 apt 阶段问题，两者不是同一个错误。**

# Ink & Memory 后端 Docker 部署问题分析报告

## 1. 背景

Ink & Memory 后端依赖 Claude Code / Claude Agent 运行写作协作、MCP 工具调用、SSE 流式响应与文档写操作确认。产品文档中也明确把 Claude AI、MCP 工具接口、SSE 流式响应、人类确认机制列为技术信任背书，说明这条链路不是附属功能，而是核心运行路径。

当前部署环境为 Docker Compose 远程部署，后端容器 `ink-backend` 中安装：

```dockerfile
@anthropic-ai/claude-code
@anthropic-ai/sandbox-runtime
bubblewrap
socat
```

目标是让 Claude Agent 可以在后端容器中执行受控 Bash / 文件工具 / MCP 工具。

------

## 2. 已观察到的问题

### 问题 A：运行期 Claude sandbox 报错

错误信息：

```text
apply-seccomp: write /proc/self/setgroups
(nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN):
Permission denied
```

影响范围：

```text
Claude Agent 中的 Bash / shell 子进程执行失败
Claude Code sandbox 无法正常启动
Agent 工具链中涉及子进程的操作被阻断
```

这个错误不是 Python 代码异常，也不是 FastAPI 本身的问题。

------

### 问题 B：Docker build 阶段 apt 安装失败

最新构建错误：

```text
apt-get install ... did not complete successfully: exit code: 100
```

失败位置已经确认在这一段：

```dockerfile
apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    libssl-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    curl \
    jq \
    git \
    ripgrep \
    ca-certificates \
    nodejs \
    npm \
    bubblewrap \
    socat
```

这说明当前构建还没有执行到：

```dockerfile
npm install -g @anthropic-ai/claude-code ...
apply-seccomp patch
```

所以现在有两个层次的问题：

```text
运行期问题：Claude Code sandbox / apply-seccomp / nested userns
构建期问题：apt-get install exit code 100
```

必须分开处理。

------

## 3. 已排除项

### 3.1 Docker 外层权限不足基本排除

你已经执行过：

```bash
docker inspect ink-backend --format 'CapAdd={{json .HostConfig.CapAdd}} SecurityOpt={{json .HostConfig.SecurityOpt}}'
```

输出：

```text
CapAdd=["CAP_NET_ADMIN","CAP_SYS_ADMIN","CAP_SYS_PTRACE"]
SecurityOpt=["seccomp=unconfined","apparmor=unconfined","label=disable"]
```

容器内也测过：

```bash
grep -E 'CapEff|Seccomp' /proc/self/status
```

输出：

```text
CapEff: 000001ffffffffff
Seccomp: 0
```

这说明 Docker 外层 seccomp 已经关闭，Capability 也不是空的。

GitHub issue #48304 里也记录了同类结论：`seccomp=unconfined`、`apparmor=unconfined`、`cap_add: SYS_ADMIN` 在这个问题上无效；问题发生在 Claude Code 调用 `bwrap` 后又调用 `apply-seccomp`，形成嵌套 user namespace，并在写 `/proc/self/setgroups` 时被内核拒绝。([GitHub](https://github.com/anthropics/claude-code/issues/48304))

------

## 4. 根因判断

### 4.1 运行期根因

根因是：

```text
Claude Code Linux sandbox-runtime 在 Docker 容器内创建嵌套 user namespace；
apply-seccomp 在嵌套 userns 内写 /proc/self/setgroups；
Linux 内核拒绝该操作；
导致 Claude sandbox 内所有 Bash 命令失败。
```

GitHub issue #48304 的链路描述是：

```text
Claude Code -> bwrap --unshare-net -> userns layer 1
bwrap exec apply-seccomp -> apply-seccomp 再次 unshare -> userns layer 2
apply-seccomp 写 /proc/self/setgroups -> EACCES
```

issue 中明确说这是 nested user namespace 下的硬限制，不是单纯 sysctl、AppArmor 或 Docker seccomp profile 能解决的问题。([GitHub](https://github.com/anthropics/claude-code/issues/48304))

------

### 4.2 构建期根因

目前构建失败的直接原因是：

```text
apt-get install 返回 exit code 100
```

常见原因按概率排序：

```text
1. 宿主机磁盘空间不足
2. Debian / 阿里云镜像源访问失败
3. apt index 与 package 源不一致
4. DNS / 网络波动
5. 某个包在当前源不可用
```

你之前服务器已经出现过空间不足迹象：

```text
Space needed ... / 0 B available
Error: You don't have enough free space in /var/cache/apt/archives
```

所以第一优先级应检查磁盘与 Docker build cache。

------

## 5. 项目内部相关代码影响

Ink & Memory 后端会从 `system_config` 读取 `workspace_enabled`，再把它传入 `get_or_create_workspace(... sandbox_enabled=workspace_sandbox_enabled)`。也就是说，当前项目已经具备“通过设置控制 Claude Code Bash sandbox 是否启用”的入口。

同时项目记录里也写到：`service.py` 在 cwd 解析前读取 `workspace_enabled`，用于写入正确的 Claude Code Bash sandbox 设置；并且 SSE errorText 已经会拼接 runner 异常 notes，以便 `apply-seccomp` 这类 sandbox 诊断信息能直接返回前端。

这说明问题不是产品逻辑完全缺失，而是部署层需要针对 Claude Code sandbox-runtime 做兼容处理。

------

## 6. 推荐解决方案

### 方案一：Dockerfile patch `apply-seccomp`

这是当前最匹配 issue #48304 的方案。

GitHub issue 提供的 workaround 是把 `apply-seccomp` 替换成 passthrough script：

```sh
#!/bin/sh
exec "$@"
```

它的效果是：

```text
保留 bwrap 的 namespace 隔离；
跳过 apply-seccomp 这一层；
避免 nested userns 写 /proc/self/setgroups；
让 Claude Code Bash 工具恢复可用。
```

issue 中明确给出该 workaround，并说明它能保留 bwrap 的 network / mount / pid / session namespace 隔离，只跳过 seccomp 层。([GitHub](https://github.com/anthropics/claude-code/issues/48304))

------

### Dockerfile 建议修改

先不要动 apt 阶段，等 apt 过了再进入 npm patch。

推荐 Dockerfile 分成三段：

```dockerfile
ARG CLAUDE_CODE_VERSION=2.1.108

ENV DEBIAN_FRONTEND=noninteractive
```

#### 第一段：系统依赖

```dockerfile
RUN set -eux; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i \
            -e "s|http://deb.debian.org/debian|${DEBIAN_MIRROR}|g" \
            -e "s|http://deb.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
            -e "s|http://security.debian.org/debian-security|${DEBIAN_SECURITY_MIRROR}|g" \
            /etc/apt/sources.list.d/debian.sources; \
    fi; \
    cat /etc/apt/sources.list.d/debian.sources || true; \
    apt-get -o Acquire::Retries=5 update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libffi-dev \
        libssl-dev \
        libjpeg62-turbo-dev \
        zlib1g-dev \
        curl \
        jq \
        git \
        ripgrep \
        ca-certificates \
        nodejs \
        npm \
        bubblewrap \
        socat \
    && mkdir -p /sbin /usr/sbin /usr/local/sbin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
```

#### 第二段：Claude Code 安装与 patch

```dockerfile
RUN set -eux; \
    npm config set registry "${NPM_REGISTRY}"; \
    npm install -g \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
        "@anthropic-ai/sandbox-runtime"; \
    APPLY_SECCOMP_ROOT="$(npm root -g)/@anthropic-ai/claude-code/vendor/seccomp"; \
    test -d "$APPLY_SECCOMP_ROOT"; \
    find "$APPLY_SECCOMP_ROOT" -type f -name apply-seccomp -print \
        -exec sh -c 'printf "%s\n" "#!/bin/sh" "exec \"\$@\"" > "$1"; chmod +x "$1"' sh {} \; ; \
    echo "Patched Claude Code apply-seccomp passthrough:"; \
    find "$APPLY_SECCOMP_ROOT" -type f -name apply-seccomp -print -exec head -n 2 {} \; ; \
    npm cache clean --force
```

这里不用写死：

```text
/usr/lib/node_modules/.../x64/apply-seccomp
```

而是用：

```bash
find "$APPLY_SECCOMP_ROOT" -type f -name apply-seccomp
```

这样能兼容不同 npm 全局路径，也能兼容未来 `x64 / arm64` 目录差异。

------

## 7. 当前最优执行顺序

### Step 1：先解决 apt 构建失败

执行：

```bash
docker compose -f deploy/remote-ssh/docker-compose.yml build \
  --no-cache \
  --progress=plain \
  ink-backend 2>&1 | tee /tmp/ink-backend-build.log
```

筛错误：

```bash
grep -n -A5 -B5 -Ei \
'E:|Err:|No space|Unable to locate|Temporary failure|Hash Sum|Release file|404|Failed|not enough|No such file' \
/tmp/ink-backend-build.log
```

查磁盘：

```bash
df -h
docker system df
sudo du -hxd1 /var/lib/docker 2>/dev/null | sort -h
```

清理缓存：

```bash
docker builder prune -af
docker image prune -af
docker container prune -f
```

如果确认是源问题，临时切回 Debian 官方源：

```bash
docker compose -f deploy/remote-ssh/docker-compose.yml build \
  --no-cache \
  --progress=plain \
  --build-arg DEBIAN_MIRROR=http://deb.debian.org/debian \
  --build-arg DEBIAN_SECURITY_MIRROR=http://deb.debian.org/debian-security \
  ink-backend
```

------

### Step 2：apt 过了以后验证 apply-seccomp patch

构建成功后执行：

```bash
docker exec ink-backend sh -lc '
APPLY_SECCOMP_ROOT="$(npm root -g)/@anthropic-ai/claude-code/vendor/seccomp"
find "$APPLY_SECCOMP_ROOT" -type f -name apply-seccomp -print -exec cat {} \;
'
```

期望输出：

```sh
#!/bin/sh
exec "$@"
```

------

### Step 3：验证运行期

```bash
docker exec ink-backend sh -lc '
whoami
id
grep -E "CapEff|CapBnd|Seccomp|NoNewPrivs" /proc/self/status
claude --version || true
python3 -c "print(\"python ok\")"
ls /app | head
'
```

然后在产品里触发一次 Claude Agent Bash 工具，确认不再出现：

```text
apply-seccomp: write /proc/self/setgroups
```

------

## 8. 备选方案

### 备选方案 A：关闭 Claude Code Bash sandbox

通过项目已有的 `workspace_enabled=false` 关闭 sandbox。

优点：

```text
最快恢复可用
不需要 patch Claude Code 安装目录
逻辑上由系统配置控制
```

缺点：

```text
Claude Bash 工具失去 Claude Code 内层 sandbox
只能依赖 Docker 外层隔离
```

适合临时恢复服务，不适合长期作为唯一方案。

------

### 备选方案 B：固定 Claude Code 到 2.1.91

issue 中记录该问题是回归，最后可用版本为 `2.1.91`，问题版本示例为 `2.1.108`。([GitHub](https://github.com/anthropics/claude-code/issues/48304))

可以改为：

```dockerfile
ARG CLAUDE_CODE_VERSION=2.1.91
```

优点：

```text
绕开新版本 apply-seccomp 行为
```

缺点：

```text
旧版本可能缺功能
未来 SDK / CLI 行为不稳定
不是根治
```

------

### 备选方案 C：继续调整 Docker seccomp profile

不推荐作为主路径。

原因：

```text
你已经设置 seccomp=unconfined
容器内 Seccomp: 0
GitHub issue 明确说明 seccomp=unconfined 也无效
```

所以自定义 seccomp profile 不会比 `unconfined` 更宽。它只能用于排障证明，不能作为主要修复方案。

------

## 9. 风险评估

### patch apply-seccomp 的风险

风险点：

```text
跳过 Claude Code 自带 seccomp 层
降低一部分 syscall 级限制
```

仍然保留的隔离：

```text
Docker 容器边界
bwrap namespace 隔离
容器 CPU / 内存限制
端口绑定限制
项目写操作确认机制
```

但你当前 Compose 使用了：

```yaml
privileged: true
```

这会显著扩大容器权限。patch 跑通后，建议逐步收紧：

```yaml
privileged: false
cap_add:
  - SYS_ADMIN
  - SYS_PTRACE
  - NET_ADMIN
security_opt:
  - seccomp=unconfined
  - apparmor=unconfined
```

如果 patch 后不再需要 `SYS_ADMIN`，再继续去掉。

------

## 10. 最终结论

这次问题应该分成两层处理：

```text
第一层：当前 build 失败
原因是 apt-get install exit code 100。
先查磁盘、镜像源、plain 日志。
这一步和 apply-seccomp 没关系。

第二层：运行期 Claude Agent Bash 失败
原因是 Claude Code sandbox-runtime 的 apply-seccomp 在 Docker nested userns 中写 /proc/self/setgroups 被拒绝。
Docker 的 cap_add / seccomp=unconfined / apparmor=unconfined 已经不是主问题。
推荐按 GitHub issue #48304 的 workaround，在 Dockerfile 中把 apply-seccomp patch 成 passthrough script。
```

执行优先级：

```text
1. 用 --progress=plain 查清 apt exit code 100
2. 清理磁盘 / 修复 apt 源
3. 构建通过后安装 Claude Code
4. patch apply-seccomp
5. 验证容器内 apply-seccomp 内容
6. 触发 Claude Agent Bash 工具验证
7. 跑通后逐步收紧 privileged 权限
```

这条路径比继续调 Docker seccomp profile 更靠谱。现在不要再把两个错误混在一起：**先修 build，再修 runtime sandbox。**