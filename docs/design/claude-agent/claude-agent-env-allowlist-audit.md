# `INK_AGENT_*` 环境变量白名单清除机制审计报告

> 状态：审计完成（B 类已修复；`SANDBOX_SECCOMP_APPLY_PATH` 机制后被生产证伪并拆除——见 §9；C/F 类待逐键决策）
> 触发事件：2026-07-26 生产环境 `INK_AGENT_SANDBOX_SECCOMP_APPLY_PATH=''` 告警导致沙箱 seccomp 覆盖失效
> 关联文档：`claude-sdk-env-design.md`（§5.5A 生命周期警告）、`claude-agent-workspace-sandbox.md`、`claude-agent-sandbox-network-sdk-gap.md`
> 日期：2026-07-26；§9 补记 2026-07-26 Route A

---

## 1. 摘要

`server.py::_drop_unsupported_agent_env()` 在 uvicorn 启动时**进程级清除**所有不在硬编码白名单（`allowed_ink_names`）内的 `INK_AGENT_*` 环境变量。该白名单自 2026-05-24 引入后未随特性演进维护，导致后续新增的多个运行时配置键在**进程内 `os.environ` 层面静默失效**，而 Docker 镜像/容器/进程启动环境三层快照中它们都正常存在——形成"到处可见、代码读不到"的排查陷阱。本次事故（沙箱 seccomp 覆盖失效）只是该机制缺陷的第一个显性症状。

## 2. 事件复盘

### 2.1 事故链

```
Dockerfile ENV INK_AGENT_SANDBOX_SECCOMP_APPLY_PATH=<shim>（正确）
  → 容器 Config.Env（正确）
    → /proc/1/environ 进程启动环境（正确）
      → server.py 启动 _drop_unsupported_agent_env()
        pop 所有非白名单 INK_AGENT_*               ← 案发现场
          → workspace 初始化读 os.environ → ''
            → settings.json 丢失 sandbox.seccomp.applyPath
              → CLI 回退内嵌 apply-seccomp
                → nested userns 写 /proc/self/setgroups 失败
                  → apply-seccomp: Permission denied
```

### 2.2 关键排查认知（可复用方法论）

Docker/Python 环境下环境变量存在**四个快照层**，逐层对比可定位任意"变量为空"问题：

| 层 | 命令 | 语义 |
|---|---|---|
| ① 镜像 | `docker image inspect <img> --format '{{json .Config.Env}}'` | 构建时烧入 |
| ② 容器 | `docker inspect <c> --format '{{json .Config.Env}}'` | **创建时快照，restart 不更新** |
| ③ 进程启动环境 | `tr '\0' '\n' < /proc/1/environ` | exec 时内核快照，**之后不可变** |
| ④ 进程运行时视图 | Python `os.environ` | **可被进程自身代码修改**（本案） |

本次的迷惑性正来自：①②③全部正确，④被进程自己的启动代码改写。另有补充命令：无 `pgrep` 的 slim 容器内用 `for p in /proc/[0-9]*; do ...; done` 扫描进程环境；`docker logs --timestamps` 对比 `State.StartedAt` 排除旧日志。

### 2.3 排除的假设（排查路径存档）

- ~~镜像未重建/旧镜像~~：镜像、容器、进程启动环境三层均含正确值；
- ~~`.env` 空值覆盖~~：服务器 env 文件无该键；
- ~~enabled 门控~~：settings 中 `sandbox.enabled=true`；
- ~~CLI 不识别配置~~：容器内代码与 shim 均对账无误。

## 3. 机制剖析：设计意图与缺陷

**意图**（`server.py:30-55`，2026-05-24 引入）：清理历史遗留的 Agent 环境变量别名（如 `ANTHROPIC_API_KEY`、过期 `CLAUDE_CODE_*_TOKEN`），防止 stale 配置流入 SDK 子进程。

**缺陷**：

1. **清理点错误**：在 uvicorn 进程内做 `os.environ.pop`，影响的是 **backend 自身运行时读取**，而非仅隔离 SDK 子进程 env（后者有独立的 `options.env` 装配链，见 `sdk_env.py`）；
2. **白名单无维护机制**：硬编码 9 键 + `INK_AGENT_MEM0_` 前缀，无任何"新增键必须登记"的编译期/测试期强制；
3. **失效完全静默**：被清除的键走到各自的默认值或跳过分支，无任何告警（本次是恰好有 warning 日志才暴露）。

## 4. 全量键审计分类

基于 backend 运行时代码逐个核实（2026-07-26）：

| 类 | 键 | 状态与证据 |
|---|---|---|
| **A. 白名单内（正常）** | `ENABLE_MEMORY_MCP`、`TTL_S`、`SWEEP_INTERVAL_S`、`SSE_KEEPALIVE_S`、`MAX_TURNS`、`CONTEXT_SESSIONS`、`EVENT_BUS_BACKEND`、`REDIS_URL`、`EVENT_BUS_TTL_S`、`MEM0_*`（前缀） | 不受清除影响 |
| **B. 曾被清除·已修复** | `SANDBOX_EXTRA_ALLOW_READ` | 2026-07-26 补入白名单 + 回归测试 `test_cleanup_preserves_sandbox_runtime_keys`；修复前致 `/app/claude_agent:/app/libs:/app/prompts` 沙箱读路径静默失效。`SANDBOX_SECCOMP_APPLY_PATH` 曾同类修复，后因 settings-seccomp 路线被生产证伪而整体拆除（§9），不再是运行时配置键 |
| **C. 进程内 `os.environ` 读取·非白名单（被静默清除，走默认值）** | `TODO_EMIT_DEBOUNCE_MS`、`TODO_MAX_ITEMS`、`PLAN_EMIT_DEBOUNCE_MS`、`PLAN_MAX_CONTENT_BYTES`、`STOP_WAIT_S`（均 `os.environ.get`，agent_runner/service 层）；`TASK_V2_ENABLED`（`os.getenv`，已降级为 legacy 闸门，默认 off 即预期） | **生产环境配置这些键不生效**，目前无人配置故无症状；调参需求出现时即踩坑 |
| **D. dotenv 文件通道读取（不受进程清除影响）** | `ALLOW_REQUEST_MODEL_OVERRIDE`、SDK 子进程 env 装配相关键（`sdk_env.py` 经 `dotenv_values` 读文件、`options.env` 注入子进程） | 设计使然：文件通道绕过了进程级 pop——**证明清理点本应在子进程 env 装配处** |
| **E. backend 输出给子进程的键（pop 无害）** | `SESSION_ID`、`USER_ID`、`EDITOR_SESSION_ID`、`USER_MESSAGE`、`CONTRACT_VERSION` | 由 backend 在运行时设置注入，启动时清除无影响 |
| **F. 运行时代码未见使用（待确认）** | `CHAT_HISTORY_RETRIEVAL_MODE`、`CHAT_HISTORY_FUZZY_MIN_SCORE`、`CHAT_HISTORY_SEARCH_LIMIT`、`SESSION_RETRIEVAL_MODE`、`SESSION_FUZZY_MIN_SCORE`（`thread_retrieval.py`/`sessions_tool.py` 仅见常量定义，未见 `environ` 读取，疑似 interface-only）；`NOTION_DB_PATH`（运行时代码无引用） | 若属 interface-only，清除无影响；启用对应特性时需先核实读取通道 |

## 5. 影响评估

| 影响面 | 评估 |
|---|---|
| 本次事故（seccomp 覆盖失效） | 已修复（白名单 + 回归测试 + 文档警告） |
| 沙箱额外读路径 | 同源失效，已一并修复 |
| C 类调参键 | 生产配置静默无效；有默认值兜底，无即时故障，属"潜伏型" |
| 系统设计 | D 类证明正确架构是"子进程 env 过滤"而非"进程级 pop"；当前机制与意图错位 |

## 6. 已落地措施（2026-07-26）

1. `server.py` 白名单补入 B 类键（含注释说明事故；`SANDBOX_SECCOMP_APPLY_PATH` 后于同日 Route A 移除——见 §9）；
2. 回归测试 `test_cleanup_preserves_sandbox_runtime_keys`（`test_server_claude_agent.py`，注意本机因缺 `itsdangerous` 该文件整体 skip，CI 执行；Route A 后该用例仅保留 `SANDBOX_EXTRA_ALLOW_READ` 断言）；
3. `claude-sdk-env-design.md` §5.5A 新增**环境变量生命周期警告**：新增 `INK_AGENT_*` 运行时配置键必须同步登记白名单；
4. 本审计报告存档。

## 9. 补记：settings-seccomp 路线证伪与 Route A（2026-07-26）

本报告 §2 事故链的修复（`sandbox.seccomp.applyPath` settings 覆盖 + shim）**当日即在生产被证伪**，证据链：

1. Linux npm CLI 2.1.220 二进制 `strings | grep -c "sandbox?.seccomp"` → **0**（settings→runtime 转换器从不读取 `sandbox.seccomp`）；`grep -c "/proc/self/fd/"` → **16**（内嵌 apply-seccomp 执行器）；
2. macOS bundled 2.1.220 转换器返回 `seccomp: jCu()`（硬编码内嵌配置，不像兄弟字段那样读 `e.sandbox?.*`）；
3. shim 打日志实测：CLI 从未调用 `/usr/local/share/claude-agent/apply-seccomp-passthrough`；
4. 宿主机 `kernel.apparmor_restrict_unprivileged_userns` 已为 0，排除宿主机拦截——setgroups 失败是 bwrap 嵌套 userns 无 caps 的固有问题，正是 2.1.108 vendor passthrough 存在的原因。

**Route A（最终方案）**：npm CLI 回退 2.1.108 并恢复 vendor apply-seccomp passthrough 补丁；`INK_AGENT_SANDBOX_SECCOMP_APPLY_PATH`、shim、`workspace.py` 的 `sandbox.seccomp` 发射逻辑全部拆除；Dockerfile 新增构建期 `claude --version` 断言。`cli_path` 锁定（`sdk_env.apply_cli_path_to_options`）保留——它保证 SDK 配对的正是这个打过补丁的 npm CLI。`SANDBOX_EXTRA_ALLOW_READ` 修复不受影响，继续有效。

## 7. 建议

**短期（逐键决策）**

- C 类：逐一确认产品意图——若属于支持的调参面，补入白名单；若属内部常量，改为代码常量而非 env 键，消除歧义；
- F 类：核实读取通道后按 C/E 归类处理；
- `TASK_V2_ENABLED`：legacy 闸门，建议在后续清理迭代中移除。

**长期（机制改进）**

1. **把清理点移到正确位置**：废弃进程级 `os.environ.pop`，改为在 SDK 子进程 env 装配处（`sdk_env.py`）做显式 allowlist 过滤——backend 自身运行时读取从此不受白名单耦合；
2. **测试期强制**：新增一个审计测试，扫描代码中所有 `os.environ.get("INK_AGENT_*")` 与白名单的差集，差集非空即失败（把"登记义务"从文档约束升级为 CI 约束）；
3. `allowed_ink_names` 加注释指针指向本报告，说明历史包袱。

## 8. 附：env 问题排查命令手册

```bash
# 四层快照对比
docker image inspect <img> --format '{{json .Config.Env}}' | tr ',' '\n' | grep <KEY>
docker inspect <c> --format '{{json .Config.Env}}' | tr ',' '\n' | grep <KEY>
docker exec <c> sh -c 'tr "\0" "\n" < /proc/1/environ | grep <KEY>'
# 进程运行时视图：在 backend 内临时打印或看代码读取点日志

# slim 容器（无 pgrep）进程扫描
docker exec <c> sh -c 'for p in /proc/[0-9]*; do c=$(tr "\0" " " < $p/cmdline 2>/dev/null); \
  case "$c" in *python*|*uvicorn*) echo "== $p: $c"; \
  tr "\0" "\n" < $p/environ 2>/dev/null | grep <KEY>; esac; done'

# 时间线对照（排除旧日志/旧容器）
docker logs --timestamps <c> 2>&1 | grep <KEY> | tail -2
docker inspect <c> --format '{{.State.StartedAt}}'

# 容器内代码对账
docker exec <c> sed -n '<起始行>,<结束行>p' <容器内代码路径>
```
