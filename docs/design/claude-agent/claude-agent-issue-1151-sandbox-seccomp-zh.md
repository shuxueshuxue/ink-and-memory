# `sandbox.seccomp.applyPath` 在 settings.json 中被忽略 —— 内嵌 apply-seccomp 始终被使用（CLI 2.1.220）

> 本文是 GitHub issue [anthropics/claude-agent-sdk-python#1151](https://github.com/anthropics/claude-agent-sdk-python/issues/1151) 的中文版本，与英文版内容对应。
> 英文版：同目录 `claude-agent-issue-1151-sandbox-seccomp-en.md`

## 摘要

`sandbox.seccomp.applyPath` / `sandbox.seccomp.bpfPath` 配置键——CLI 自己宣传的 seccomp 辅助程序覆盖机制（"从 sandbox-runtime 复制 vendor/seccomp/* 并在 settings.json 中设置 `sandbox.seccomp.bpfPath` 和 `applyPath`"）——在 2.1.220 的 CLI 内嵌 Linux 沙箱路径中被**静默忽略**。settings→runtime 转换器将 seccomp 配置硬编码为内嵌执行器（`/proc/self/fd/*`），因此没有任何受支持的方式可以替换或禁用 apply-seccomp。在 Docker / 嵌套 userns 环境中，这导致沙箱内 Bash 命令必然失败：

```
apply-seccomp: write /proc/self/setgroups (nested userns is capability-restricted; caller must provide CAP_SYS_ADMIN): Permission denied
```

## 环境

- `@anthropic-ai/claude-code` **2.1.220**（linux-x64，npm，单个 275MB 自包含二进制）
- `claude-agent-sdk`（Python）0.2.128（问题在 CLI 侧，经 SDK 子进程与直接调用均可复现）
- Docker（Debian bookworm 基础镜像，`cap_add: SYS_ADMIN`，`seccomp=unconfined`，`apparmor=unconfined`；宿主机 `kernel.apparmor_restrict_unprivileged_userns=0`）

## 预期行为

按 CLI 内置提示文案（二进制中可见："or copy vendor/seccomp/* from sandbox-runtime and set `sandbox.seccomp.bpfPath` and `applyPath` in settings.json"），在被加载的 settings.json 中设置以下内容，应使沙箱调用指定可执行文件替代内嵌 apply-seccomp：

```json
{
  "sandbox": {
    "enabled": true,
    "seccomp": { "applyPath": "/usr/local/share/claude-agent/apply-seccomp-passthrough" }
  }
}
```

（我们的用例：passthrough shim，将 apply-seccomp 中和为空操作——这是嵌套 userns Docker 环境中写 `/proc/self/setgroups` 不可能成功时的标准解法，正是该配置覆盖看起来被设计来服务的场景。）

## 实际行为

该键从未被读取。内嵌 apply-seccomp（经 `/proc/self/fd/` 执行）始终运行，沙箱命令以上述 setgroups Permission denied 错误失败。

## 证据

1. **转换器不读该键**。在 Linux 二进制上：
   ```
   strings claude.exe | grep -c "sandbox?.seccomp"     → 0
   strings claude.exe | grep -c "/proc/self/fd/"        → 16
   ```
   转换器从不触碰 `sandbox.seccomp`，而同级字段均正常读取。
2. **转换器硬编码内嵌执行器**。在（更可读的）macOS 构建中，sandbox 配置转换器返回 `seccomp: jCu()`——即内嵌的 `{applyPath: "/proc/self/fd/3", argv0: "apply-seccomp"}`——而所有同级字段都来自 `e.sandbox?.<field>`（`ignoreViolations`、`enableWeakerNestedSandbox`、`enableWeakerNetworkIsolation`、`allowAppleEvents` 等）。`seccomp` 是唯一不从 settings 读取的字段。
3. **功能性实证**。将 `sandbox.seccomp.applyPath` 指向一个带日志的 shim（`#!/bin/sh; echo "$@" >> /tmp/shim.log; exec "$@"`），在沙箱命令运行并失败的全过程中**零次调用**。
4. **提示文案存在但未接线**。`strings` 同时能看到 `sandbox.seccomp.bpfPath and applyPath in settings.json` 与消费方日志文案（`[SeccompFilter] Using apply-seccomp binary from explicit path: …`）——显式路径的代码路径存在，但 settings 键在内嵌路径上永远到不了它。该键推测只对通过不同代码路径读取同一 settings schema 的独立版 `srt`（sandbox-runtime CLI）有效。

## 影响

- **CLI 2.1.220 在 Docker / 嵌套 userns 环境中没有任何受支持的方式运行 Linux Bash 沙箱**，沙箱命令确定性失败。
- 旧逃生通道已消失：≤2.1.108 在磁盘上提供 `vendor/seccomp/apply-seccomp`，部署方可以替换；2.1.220 的单文件二进制移除了这个面（辅助程序经 `/proc/self/fd/` 执行）。
- 这个看似有文档的配置覆盖是一个陷阱：**静默无效**——配置被接受、settings.json 里能看到它，但行为从不改变，极难诊断。

## 建议修复（任一即可）

1. 在内嵌转换器中响应 settings 的 `sandbox.seccomp.applyPath` / `bpfPath`（可按你认为安全的作用域限制，例如仅 user/managed settings），而不是硬编码内嵌执行器；
2. 或提供显式覆盖通道（环境变量 / CLI 参数）指定 apply-seccomp 路径；
3. 或恢复 seccomp 辅助程序的磁盘 vendor 位置，使部署方可以补丁；
4. 至少，当 settings 中存在 `sandbox.seccomp` 但被忽略时**输出警告**——静默无效的配置是最糟糕的一种。

## 复现步骤

1. Docker 容器（bookworm）：`npm install -g @anthropic-ai/claude-code@2.1.220 bubblewrap socat`；
2. 在项目 `.claude/settings.json` 写入 `"sandbox": {"enabled": true, "seccomp": {"applyPath": "/path/to/logging-shim"}}`；
3. 通过 CLI 运行任意沙箱 Bash 命令（例如通过 Agent SDK 并将 `cwd` 指向该项目）；
4. 观察：命令以 `apply-seccomp: write /proc/self/setgroups … Permission denied` 失败；shim 从未被调用（无日志输出）。

## 我们当前采用的 Workaround（Docker 内 apply-seccomp passthrough 补丁）

当前将 CLI 锁定在 **2.1.108**，并在镜像构建时将其**磁盘上的** `vendor/seccomp/apply-seccomp` 补丁为 passthrough——证明在相同环境下沙箱其余部分工作正常。完整方案：

```dockerfile
# Claude Code + sandbox-runtime。
# 将 apply-seccomp 补丁为 passthrough，规避 Docker 嵌套 userns / setgroups 失败。
ARG CLAUDE_CODE_VERSION=2.1.108
RUN set -eux; \
    apt-get update && apt-get install -y --no-install-recommends \
        nodejs npm bubblewrap socat; \
    npm install -g \
        "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
        "@anthropic-ai/sandbox-runtime"; \
    # 构建期断言：平台二进制必须真实可运行
    #（2.1.220 的教训：optional 依赖可能静默缺失，留下死壳 wrapper）。
    claude --version; \
    # 中和 apply-seccomp：把所有 vendored 辅助程序替换为 passthrough。
    APPLY_SECCOMP_ROOT="$(npm root -g)/@anthropic-ai/claude-code/vendor/seccomp"; \
    test -d "$APPLY_SECCOMP_ROOT"; \
    find "$APPLY_SECCOMP_ROOT" -type f -name apply-seccomp -print \
        -exec sh -c 'printf "%s\n" "#!/bin/sh" "exec \"\$@\"" > "$1"; chmod +x "$1"' sh {} \; ; \
    echo "Patched Claude Code apply-seccomp passthrough:"; \
    find "$APPLY_SECCOMP_ROOT" -type f -name apply-seccomp -print -exec head -n 2 {} \; ; \
    npm cache clean --force
```

容器运行时参数（compose 等价配置）：

```yaml
cap_add:
  - SYS_ADMIN      # bubblewrap 在 Docker 内建立 mount namespace 所需
security_opt:
  - seccomp=unconfined
  - apparmor=unconfined
```

补丁的作用与安全性说明：

- 沙箱的网络/文件系统隔离由 **bwrap**（`--unshare-net`、bind mount）加宿主机侧过滤代理执行——**不依赖 seccomp**。apply-seccomp 只是在其上叠加 unix socket 封锁。
- 将 apply-seccomp 替换为 `#!/bin/sh` + `exec "$@"` 使 seccomp 步骤变为空操作，同时 bwrap 隔离完全保留（CLI 对 seccomp 辅助程序缺失本来就按警告处理而非错误——"seccomp not available - unix socket access not restricted"）。
- **该 workaround 在 2.1.220 上不可行**：CLI 是单一自包含二进制，磁盘上不再有 `vendor/seccomp/`，辅助程序经 `/proc/self/fd/` 执行，而 settings 驱动覆盖（`sandbox.seccomp.applyPath`）被静默忽略——这正是本 issue 报告的 bug。
