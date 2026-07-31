# Claude Agent SDK × npm CLI 兼容性报告

> 状态：定稿（最终配对已生产验证，2026-07-29）
> 范围：`claude-code-sdk` / `claude-agent-sdk`（Python SDK）与 `@anthropic-ai/claude-code`（npm CLI）的版本配对兼容性
> 关联文档：`claude-agent-sandbox-network-sdk-gap.md`、`claude-agent-workspace-sandbox.md`、`claude-sdk-env-design.md`、`claude-agent-env-allowlist-audit.md`
> 日期：2026-07-29

---

## 1. 最终结论（TL;DR）

**当前生产验证配对**（2026-07-29 线上功能验证通过）：

| 组件 | 版本 | 说明 |
|---|---|---|
| Python SDK | `claude-agent-sdk == 0.2.128` | `claude-code-sdk` 的更名后继包 |
| npm CLI | `@anthropic-ai/claude-code == 2.1.108` | 带 vendor apply-seccomp passthrough 补丁 |
| 配对锁定 | `cli_path` 解析（`sdk_env.apply_cli_path_to_options`） | 防止 SDK bundled CLI 抢占配对 |
| 构建保障 | Dockerfile 构建期断言 `claude --version` | optional 依赖静默缺失在构建期失败 |

**核心教训：SDK 与 CLI 是两条独立演进的版本线，控制协议（control protocol）是它们的契约接合面——任何一侧版本漂移都可能静默破坏握手、hook 输出契约或权限应答序列化，且故障方向表现为"静默失败"而非显式报错。**

## 2. 兼容性矩阵

| SDK \ CLI | 2.1.108（vendor 补丁） | 2.1.220 |
|---|---|---|
| `claude-code-sdk 0.0.25` | ⚠️ 基本可用但 **can_use_tool 应答方言过旧**（`{"allow":true}` 被 CLI schema 拒绝 → fail-closed，生产 403 bug） | ❌ 同左，且 CLI 内嵌 apply-seccomp 在 Docker 必败 |
| `claude-agent-sdk 0.2.128` | ✅ **生产验证配对**（需 cli_path 锁定 + vendor 补丁） | ❌ 多重不兼容（见 §3.3/§3.4） |

> 说明：SDK 的 `MINIMUM_CLAUDE_CODE_VERSION = "2.0.0"`（`subprocess_cli.py:31`），低于时仅 warning 不阻断；SDK 内无硬性版本门，因此**兼容性验证责任完全在使用方**。

## 3. 已发现的兼容问题（全部生产实证）

### 3.1 can_use_tool 控制应答序列化方言（严重度：高，功能阻断）

- **现象**：沙箱网络确认卡"同意"后请求仍被代理拦截（`403 blocked-by-allowlist`）。
- **根因**：`claude-code-sdk 0.0.25` 把回调结果序列化为旧方言 `{"allow": true}` / `{"allow": false, "reason"}`（`_internal/query.py:215-222`）；CLI 侧 `permissionToolOutputSchema` 期望 `{behavior:'allow', updatedInput}` / `{behavior:'deny', message}`，zod 校验失败 → `createSandboxAskCallback` catch 静默 `return false`。
- **修复**：SDK 升级到 0.2.128（序列化已对齐，对安装包源码逐行验证）。
- **教训**：权限应答是 schema 校验的强契约，**失败方向是静默 deny**——任何 SDK/CLI 升级都必须重新核对这条序列化。

### 3.2 HookJSONOutput 类型契约破坏（严重度：高，安全相关）

- **现象**：PostToolUse observer 抛 `TypeError: 'types.UnionType' object is not callable`；**PreToolUse 的 deny 决策静默丢失，用户拒绝后工具仍被执行**。
- **根因**：SDK 0.2.128 将 `HookJSONOutput` 改为 `AsyncHookJSONOutput | SyncHookJSONOutput` Union（types.py:561），不可调用；业务代码 25 处 `HookJSONOutput(...)` 构造调用全部抛异常，hook 异常退出后 CLI 按无决策处理继续执行。
- **修复**：全部改为官方文档的纯 dict 字面量契约；新增 `TestHookDictLiteralContract` 回归测试钉死。
- **教训**：hook 输出是"失败即放行"的危险面，**deny 丢失比功能崩溃更隐蔽**；测试 stub 曾把 Union 伪装成可构造类导致 CI 失明，回归测试必须对真实 SDK 类型做形状断言。

### 3.3 SDK bundled CLI 抢占配对（严重度：中，隐蔽）

- **现象**：迁移后 Docker 内 `apply-seccomp: Permission denied` 复发。
- **根因**：SDK 0.2.128 的 `_find_cli()` **bundled 优先**（`subprocess_cli.py:152-155`），wheel 自带 CLI 2.1.220 未打 vendor 补丁，shadow 了打过补丁的 npm CLI 2.1.108。
- **修复**：`cli_path` 解析锁定（env 覆盖 → `shutil.which("claude")` → bundled 兜底）。
- **教训**：SDK 的"开箱即用"默认会静默改变运行时二进制来源；**CLI 来源必须显式锁定并可观测**（当前缺口：无启动日志输出 resolved cli_path）。

### 3.4 CLI 2.1.220 打包结构变更（严重度：高，路线级）

- **现象**：2.1.108 的 vendor apply-seccomp 补丁无处附着；settings 驱动覆盖（`sandbox.seccomp.applyPath`）也完全无效。
- **根因（strings 取证）**：
  1. 2.1.220 npm 包变为壳 + optional 平台包，Linux 版是**单个 275MB 自包含二进制**，磁盘无 `vendor/seccomp/`；
  2. settings→runtime 转换器**硬编码** `seccomp: <embedded fd executor>`，不读 `sandbox.seccomp`（Linux 二进制 `strings | grep -c "sandbox?.seccomp"` = 0；`/proc/self/fd/` = 16；生产 shim 零调用实锤）；
  3. optional 平台包缺失时 npm **不报错**，留下死壳 wrapper（`command not found`）——催生了构建期断言。
- **修复**：路线 A——回退 2.1.108 + 恢复 vendor 补丁（生产验证通过）。
- **教训**：对 CLI 的行为验证必须以**目标平台目标版本的二进制**为准（macOS 与 Linux 构建的混淆符号不同，`jCu`/`sss` 不可跨平台引用；语义级字符串才稳定）。

### 3.5 部署层环境变量生命周期（严重度：中，已修复）

- **现象**：`INK_AGENT_SANDBOX_SECCOMP_APPLY_PATH=''` 告警——Docker ENV/容器/进程启动环境三层正常，`os.environ` 却为空。
- **根因**：`server.py::_drop_unsupported_agent_env()` 启动时清除非白名单 `INK_AGENT_*` 键（详见 `claude-agent-env-allowlist-audit.md`）。
- **教训**：排查 env 问题必须区分**四个快照层**（镜像/容器/进程启动/进程运行时）。

## 4. 当前配对的已知残留风险

| 风险 | 状态 | 缓解 |
|---|---|---|
| SDK 0.2.128 initialize 握手携带新可选字段（`agents`/`skills`/`excludeDynamicSections`），2.1.108 不认识 | 生产冒烟通过（按协议惯例忽略未知字段） | 升级 CLI 前重新冒烟 |
| `CanUseToolShadowedWarning`（`allowed_tools` 与 `can_use_tool` 并存，预期设计） | 每进程一次日志噪音 | 可选静默 |
| CLI 2.1.108 相对陈旧，上游修复无法获得 | 已接受 | 已向上游提交 issue：[claude-agent-sdk-python#1151](https://github.com/anthropics/claude-agent-sdk-python/issues/1151)（`sandbox.seccomp.applyPath` 被内嵌转换器忽略），跟踪其解决后可评估再升级 |
| Linux wheel 无 `_bundled`（实证），`cli_path` 兜底分支在该环境不可用 | 已知 | npm CLI 由 Dockerfile 构建断言保障 |
| 升级 CLI 时 vendor 补丁需同步移植 | 流程风险 | 补丁逻辑在 Dockerfile 内，随版本号原子切换 |

## 5. 版本管理规约（建议固化）

1. **配对即原子**：SDK 与 CLI 版本必须成对变更、成对验证、成对记录（Dockerfile `CLAUDE_CODE_VERSION` + requirements `claude-agent-sdk` 同一 commit 内修改）；
2. **升级检查清单**（每次动任一版本）：
   - can_use_tool 序列化核对（对照 CLI `permissionToolOutputSchema`）；
   - hook 输出契约核对（真实 SDK 类型的形状断言测试）；
   - CLI 二进制来源核对（`cli_path` 解析结果 + 构建断言）；
   - 沙箱冒烟（Docker 内沙箱命令 + 网络确认卡端到端）；
3. **构建期防线**：`claude --version` 断言（已落地）；
4. **观测性缺口**：backend 启动日志输出 resolved cli_path + CLI 版本（待实施，一行改动）。

## 6. 验证记录

| 日期 | 验证 | 结果 |
|---|---|---|
| 2026-07-26 | SDK 0.2.128 序列化源码核对 | 与 CLI schema 对齐 |
| 2026-07-26 | 全量后端测试 | 453-458 passed, 0 failed（随机制增删波动） |
| 2026-07-26 | 2.1.220 二进制 strings 取证（macOS + Linux） | settings seccomp 路线证伪 |
| 2026-07-29 | **路线 A 配对生产验证**（沙箱命令 + 网络确认卡 + 文件写入） | ✅ 功能完善 |
