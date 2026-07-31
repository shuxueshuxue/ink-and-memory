# 工作空间文件系统 — 业务说明文档

> **迁移来源**: `glide-the/claude-agent-next-kit → docs/design/workspace-filesystem.md`
> **适配说明**: 从 Next.js / TypeScript 迁移到 Python / FastAPI 架构。
> **[Sync] 2026-06-13**: Workspace Mode 现在会在每个 thread 的
> `.claude/settings.json` 写入 Claude Code `sandbox` 配置；Bash 目录隔离由
> Claude Code 原生 sandbox 执行，PreToolUse 不解析复杂 shell 语法。
> **[Sync] 2026-06-14**: Docker 部署由后端自动检测 Linux 容器环境并写入
> Claude Code `enableWeakerNestedSandbox`，解决容器内 bubblewrap nested
> sandbox 启动问题；无需用户配置额外 env。
> **[Sync] 2026-06-16**: Workspace sandbox 不再 deny 整个 `.claude/`；
> `.claude/skills/` 保持可创建/替换 skill，denyWrite 仅保护 settings/hooks/editor index。
> **[Sync] 2026-06-16**: Skills 同步在重建软链接前会导入
> `.claude/skills/` 下的真实文件/目录，使 Agent 直接创建的 skill 回写到
> `workspace/skills/`。
> **[Sync] 2026-06-21**: `.claude/settings.json` sandbox block now also
> carries Settings-backed `sandbox.network` policy for Bash subprocess egress.

## 1. 概述

每一次 AI 对话（conversation）都拥有独立的工作空间目录，实现用户文件上传、Agent 文件读写、Skills 管理的完全隔离。工作空间由 `backend/libs/claude_agent_kit/server/workspace.py` 统一管理。

---

## 2. 目录结构

```
{AGENT_CWD}/
  └── {sessionId}/                   ← 每个对话的隔离工作空间
      ├── .claude/                   ← 从项目根 .claude/ 复制（包含 settings、commands）
      │   └── skills/                ← Claude Code 发现目录；软链接到 skills/，真实写入会导入
      ├── .mcp.json                  ← MCP 服务器配置（从项目根复制）
      ├── files/                     ← 用户文件区
      │   ├── report.pdf             ← 用户上传的文件
      │   └── analysis.xlsx          ← Agent 生成的文件
      ├── logs/                      ← 执行日志区
      │   └── agent-run-2026-05-25.log
      └── skills/                    ← 对话级 Skills 区
          ├── custom-research.md     ← 用户/Agent 创建的 skill
          └── sales-analysis.md      ← 对话专属 skill
```

---

## 3. 各目录职责

### 3.1 `files/` — 用户文件区

| 属性 | 说明 |
|------|------|
| **用途** | 存放用户上传的文件和 Agent 生成的产出物 |
| **写入者** | 用户（通过 FileSidebar 上传）、Agent（在执行过程中生成） |
| **读取者** | Agent（作为上下文输入）、用户（通过 FileSidebar 下载/预览） |
| **API** | `GET/POST/DELETE/PATCH /api/workspace/files` |
| **生命周期** | 随对话存在；对话删除时可选清理 |

Claude Agent 运行在 `tool_choice=auto` 时，Runner 的 PreToolUse 策略会对内置
`Read` / `Write` / `Edit` / `MultiEdit` 工具做路径解析校验：只有目标路径位于
当前工作空间 `{workspace}/files/` 下，才返回显式 `permissionDecision:"allow"`。
这使 Agent 可以生成普通工作区产物，同时不授予源码、`.editor/` 或其他工作区内部目录的写权限。
`tool_choice=auto` 下，明确低敏工具（例如 `Read` outside `files/`、`Glob`、`Grep`、`LS`、`WebSearch`、会话查询、memory/necklace 查询、`Skill`、`switch_editor`）也会收到显式 allow；执行/写入/交互工具进入前端确认侧路。
`tool_choice=manual` 时仍由前端工具确认流审批。

### 3.2 `logs/` — 日志区

| 属性 | 说明 |
|------|------|
| **用途** | 存放 Agent 执行日志、调试信息 |
| **写入者** | Agent runner（streaming 输出日志） |
| **读取者** | 开发者调试、运维排查 |
| **生命周期** | 随对话存在 |

### 3.3 `skills/` — 对话级 Skills 区

| 属性 | 说明 |
|------|------|
| **用途** | 存放对话专属的 Claude Code skills 文件 |
| **写入者** | 用户手动放置、Agent 在对话中动态生成 |
| **读取者** | Claude SDK（通过 `{workspace}/.claude/skills/` 软链接间接读取） |
| **同步机制** | `sync_skills_symlinks()` 先导入 `.claude/skills/` 真实写入，再自动创建软链接到工作空间 `.claude/skills/` |
| **命名约定** | 软链接名称与源文件/文件夹同名（工作空间隔离，无需前缀） |
| **支持类型** | 文件和文件夹均可软链接 |
| **生命周期** | 随对话存在；过期链接自动清理 |

### 3.4 `.claude/` — Claude 配置区

从项目根目录的 `.claude/` 同步，包含 `settings.json`、`index.json`、`commands/` 等。
每次 `init_workspace` 调用时刷新（`skills/` 子目录除外，由软链接机制维护）。

`init_workspace()` 会在复制模板后合并当前 thread 专属的
`sandbox` 配置到 `{workspace}/.claude/settings.json`。当 Settings 的
`workspace_enabled=true` 时，Claude Code Bash sandbox 被启用：

- `sandbox.enabled=true`
- `sandbox.failIfUnavailable=true`
- `sandbox.enableWeakerNestedSandbox=true`（仅后端检测到 Linux 容器运行时）
- `sandbox.autoAllowBashIfSandboxed=true`
- `sandbox.allowUnsandboxedCommands=false`
- `sandbox.network` 根据 Settings「沙箱网络」写入
  `allowedDomains: []` + `deniedDomains: ["*"]`、`allowedDomains: [...]`
  或在 open 模式下省略整个 `sandbox.network`；关闭态还由 runner PreToolUse 拒绝网络工具
- `sandbox.filesystem.denyRead=["/"]`，再通过 `allowRead` 重新开放当前
  workspace 与必要只读运行时依赖
- `sandbox.filesystem.allowRead/allowWrite` 包含当前 `{AGENT_CWD}/{sessionId}`
- `sandbox.filesystem.denyWrite` 保护 `.claude/settings*.json`、`.claude/hooks/`、
  `.editor/`、`.mcp.json` 等内部配置；不覆盖 `.claude/skills/`

这层只约束 Bash 及其子进程。内置 `Read` / `Write` / `Edit` / `Grep`
等非 Bash 工具仍由 Claude Agent 的 PreToolUse 权限策略和前端确认流控制。
因此，`Write/Edit` 直接操作 `.claude/skills/` 时仍需按产品权限策略通过确认；
通过后，Bash sandbox 不会再阻断该目录的创建或替换操作。下一次
`sync_skills_symlinks()` 会把 `.claude/skills/` 中的真实文件/目录移动回
`workspace/skills/`，再把 `.claude/skills/` 恢复为发现用软链接。

### 3.5 `.mcp.json` — MCP 配置

从项目根目录复制的 MCP 服务器配置文件，首次初始化时复制，后续不再覆盖。

---

## 4. Skills 软链接机制

### 4.1 背景

Claude SDK 被调用时设置 `cwd = workspace_path`，因此它从
`{workspace_path}/.claude/skills/` 读取 skills。

每个对话工作空间在初始化时已从项目根同步 `.claude/` 到 `{workspace}/.claude/`，
因此只需将 skills 链接到**工作空间内部**的 `.claude/skills/` 即可。

### 4.2 方案

在每个工作空间创建 `skills/` 目录（用户友好的顶层位置）。同步时先检查
`.claude/skills/`：如果 Agent 在 Claude Code canonical 目录直接创建了真实文件或
目录，则先移动到 `workspace/skills/`；随后通过 `sync_skills_symlinks()` 将
`skills/` 中的**文件和文件夹**软链接到同一工作空间的 `.claude/skills/`。

```
工作空间:   {workspace}/skills/research.md
                          ↓ symlink
Claude读取:  {workspace}/.claude/skills/research.md

工作空间:   {workspace}/skills/analysis-tools/
                          ↓ symlink
Claude读取:  {workspace}/.claude/skills/analysis-tools/

Agent直接写入: {workspace}/.claude/skills/new-skill/
                           ↓ import on sync
工作空间:      {workspace}/skills/new-skill/
                           ↓ symlink rebuilt
Claude读取:     {workspace}/.claude/skills/new-skill/
```

### 4.3 隔离机制

每个对话工作空间是完全独立的目录，无需 sessionId 前缀区分：

```
会话 A:  chat_abc123/skills/analysis.md  → chat_abc123/.claude/skills/analysis.md
会话 B:  chat_def456/skills/analysis.md  → chat_def456/.claude/skills/analysis.md
```

### 4.4 生命周期管理

| 事件 | 行为 |
|------|------|
| 工作空间初始化 | 扫描 `skills/` 并创建软链接 |
| Skill 文件新增 | 下次 `sync_skills_symlinks()` 调用时自动链接（写入 skills/ 自动触发） |
| `.claude/skills/` 真实文件/目录新增或替换 | 下次 `sync_skills_symlinks()` 调用时先导入 `workspace/skills/`，同名条目以 `.claude/skills/` 的真实写入为最新版本，再重建软链接 |
| Skill 文件删除 | `_clean_stale_skill_symlinks()` 自动清理失效链接（删除 skills/ 自动触发） |
| 对话删除 | 工作空间目录被删除后，源文件消失，下次同步时清理链接 |

### 4.5 Python API

```python
# workspace.py 主要导出
init_workspace(session_id)           # 创建工作空间（自动调用 sync_skills_symlinks）
get_or_create_workspace(session_id)  # 获取或创建工作空间（幂等）
list_workspace_files(workspace, sub) # 列出目录内容
list_workspace_file_tree(workspace, sub)  # 递归树列表
read_workspace_file_content(workspace, path)  # 读取文件内容
write_workspace_file(workspace, path, content)  # 写入文件（bytes）
delete_workspace_file(workspace, path)  # 删除文件/目录
move_workspace_file(workspace, from_, to)  # 移动/重命名

# workspace_file_sync.py 主要导出
sync_skills_symlinks(workspace_path)  # 手动触发 skills 同步
save_buffer_to_workspace_files(workspace, filename, mime, content)  # 保存上传文件

# 常量
WORKSPACE_SUBDIRS = ("files", "logs", "skills")
```

---

## 5. 安全保障

### 路径遍历防护

所有文件操作函数均包含路径安全校验（`_resolve_workspace_safe_path`）：

```python
candidate = (workspace_path / rel_path).resolve()
candidate.relative_to(workspace_path.resolve())  # raises ValueError on escape
```

### 软链接安全

- 软链接只指向同一工作空间 `skills/` 目录内的文件和文件夹
- `.claude/skills/` 中非点开头的真实文件/目录会先移动进 `skills/`，避免直接创建的 skill 被下一次软链接重建隐藏或删除
- 同名真实写入以 `.claude/skills/` 为最新版本，用于支持 Agent 直接替换 canonical skill 文件
- 链接目标始终在工作空间 `.claude/skills/` 内，不触碰项目根或用户级 `~/.claude/`
- 跳过 dotfiles/dotfolders（`.` 开头的条目）
- 支持文件和文件夹两种类型的软链接

### 压缩包安全（WSK-04）

`extract_archive_in_skills` 在提取前验证每个条目：

- 拒绝绝对路径条目
- 拒绝 `..` 路径穿越
- 拒绝 TAR 软链接/硬链接条目
- 先提取到临时目录，成功后原子重命名（失败不污染原始内容）

---

## 6. 环境配置

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `AGENT_CWD` | `{tmpdir}/ink-agent-workspaces` | 工作空间根目录 |

**生产环境建议**：设为持久化磁盘路径（如 `/data/workspaces`），避免 tmpdir 被系统清理。

---

## 7. 改动影响范围

| 文件 | 内容 |
|------|------|
| `backend/libs/claude_agent_kit/server/workspace.py` | 核心工作空间管理 + 文件操作 API |
| `backend/libs/claude_agent_kit/server/workspace_file_sync.py` | Skills 软链接同步 + 文件同步工具 |
| `backend/routers/workspace.py` | FastAPI 路由：`GET/POST/DELETE/PATCH /api/workspace/files`、`GET /api/workspace/files/download` |
| `backend/server.py` | 注册 `workspace_router` |
| `docs/design/workspace/` | 本设计文档目录 |
