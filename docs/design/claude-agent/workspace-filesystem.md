> **迁移来源**: Pawkeyland docs/app/design/workspace-filesystem.md — 路径已适配 Ink & Memory。
> **Ink & Memory 适配说明**: skills 同步已由 `workspace_file_sync.py` 引入；
> `sync_skills_symlinks()` 会先导入 `.claude/skills/` 的真实写入，再维护
> `workspace/skills/` 到 `.claude/skills/` 的发现软链接。
> **[Sync] 2026-06-06**: Memory Workspace 不再由 `init_workspace()` 或 `ClaudeAgentService.assemble_context()` 初始化；`/memory/` 仅通过 `POST /api/workspace/memory-init` 文件接口从 `voices.memory_workspace_config` 写入。详见 [`../memory/memory-workspace-design.md`](../memory/memory-workspace-design.md)。
> **[Sync] 2026-06-16**: `.claude/skills/` 真实文件/目录会在下次 workspace
> 同步时导入 `workspace/skills/`，支持 Agent 直接创建或替换 skill。
> **[Sync] 2026-06-22**: Workspace Mode 收束：`system_config.workspace_enabled=false`
> 时，Claude Agent chat 不再初始化 thread workspace、不传 `cwd`、不注入
> workspace/memory context；附件路径也不触发 workspace file sync。

# 工作空间文件系统设计方案

> **来源对比**：参考 `glide-the/claude-agent-next-kit → app/lib/workspace.ts`（TypeScript/Node.js）迁移适配为 Python 设计。
> **当前状态**：核心工作空间管理、Skills 软链接、项目内置 Skills 种子复制、压缩包提取与 `ClaudeAgentRunRequest.cwd` 接入已实现；本文保留设计约束与后续扩展说明。
> **Thread Session 集成**：`cwd` 在 Thread Session 模式下作为 `AgentRunState` 的 intrinsic 享元字段，按 `thread_id` 按需缓存。`Service.assemble_context` 先读取 `system_config.workspace_enabled`：开启时调用 `get_or_create_workspace(thread_id)` 后写回 `state.cwd`；关闭时跳过 workspace 初始化、清空 `state.cwd`，并以 `AgentRunOptions.cwd=None` 运行。该流程只维护 workspace 骨架和 `.claude/.editor` 文件，不初始化 `/memory/`。详见 [claude-agent-thread-session-patterns.md §4.3](./claude-agent-thread-session-patterns.md#43-享元体agentrunstate)。

---

## 1. 背景与对比

### 1.1 参考项目实现（claude-agent-next-kit，TypeScript）

参考项目在 `app/lib/workspace.ts` 中实现了完整的工作空间管理：

| 能力 | 实现 |
|------|------|
| 工作空间初始化 | `initWorkspace(sessionId)` — 创建 `files/`, `logs/`, `skills/` 子目录；复制 `.claude/` 和 `.mcp.json` |
| Skills 软链接同步 | `syncSkillsSymlinks(workspacePath)` — 将 `skills/` 条目软链接到 `.claude/skills/` |
| 获取或创建 | `getOrCreateWorkspace(sessionId)` — 幂等；每次访问均重新同步 skills |
| 文件操作 | `writeWorkspaceFile()`, `deleteWorkspaceFile()`, `moveWorkspaceFile()` — 操作后自动同步 skills |
| 压缩包提取 | `extractArchiveInSkills()` — 支持 `.zip`, `.tar.gz`, `.tgz`, `.tar`, `.skill` 格式 |
| 文件管理 API | `GET/POST/DELETE/PATCH /api/workspace/files` — Next.js API Route |
| 工作空间根目录 | `AGENT_CWD` 环境变量（默认 `/tmp/claude-agent-workspaces`） |
| 隔离维度 | `conversationId`（一次对话 = 一个工作空间） |

### 1.2 当前 Pawkeyland 实现状态

| 能力 | 状态 |
|------|------|
| `ClaudeAgentRunRequest.cwd` 参数 | ✅ 已实现（`backend/claude_agent/service.py`，由 Phase 1 `assemble_context` 在三层享元短路中使用） |
| `AgentRunOptions.cwd` 传入 ClaudeAgentRunner | ✅ 已实现（`backend/claude_agent/agent_runner.py`） |
| 工作空间初始化管理器 | ✅ 已实现（`backend/libs/claude_agent_kit/server/workspace.py`） |
| 项目内置 Skills 种子复制 | ✅ 已实现（`_seed_workspace_skills()`：首次 init 时将 `.claude/skills/` 复制到 `workspace/skills/`，现有条目跳过） |
| Skills 目录软链接 | ✅ 已实现（`backend/libs/claude_agent_kit/server/workspace_file_sync.py`；同步前导入 `.claude/skills/` 真实写入） |
| 工作空间文件管理 API | ✅ 已实现（`api/workspace/files.py`） |
| 压缩包 Skills 提取 | ✅ 已实现（`extract_archive_in_skills()`） |

---

## 2. 规划的工作空间目录结构

```
{AGENT_CWD}/                              ← 工作空间根（环境变量配置）
  └── {user_id}__{pet_id}/               ← 每对 (user, pet) 的隔离目录 = Claude SDK cwd
      ├── .claude/                        ← 从项目根同步模板文件（Claude Agent 配置）
      │   └── skills/                     ← Skills 软链接目标（Claude 自动发现）
      │       ├── my-skill.md             → symlink → skills/my-skill.md
      │       └── research-tools/         → symlink → skills/research-tools/
      ├── .mcp.json                       ← 从项目根复制（MCP 服务配置）
      ├── files/                          ← 用户上传 + Agent 生成文件
      ├── logs/                           ← Agent 执行日志
      └── skills/                         ← 对话级 Skills；首次 init 时从项目 .claude/skills/ 种子复制，之后用户/Agent 可自由修改；.claude/skills/ 真实写入也会导入这里
            ├── pet-context-assembly/       ← 项目内置 Skill（从 .claude/skills/ 种子复制而来）
            ├── my-skill.md
            └── research-tools/
                └── web-search.md
```

### 2.1 隔离维度（对比参考项目）

| 维度 | 参考项目（TypeScript） | Pawkeyland（Python） |
|------|----------------------|---------------------|
| 主隔离键 | `conversationId`（前端生成的对话 ID） | workspace_key = `"{user_id}__{pet_id}"`（由服务层派生，不再依赖调用方传入 conversation_id） |
| 孠物维度扩展 | 无 | ✅ **已实现**：每对 (user_id, pet_id) 共用同一工作空间 |
| 工作空间根 | `AGENT_CWD` 环境变量 | `AGENT_CWD` 环境变量（保持一致） |

---

## 3. 规划的 Python 模块结构

```
backend/claude_agent/
└── workspace.py                 ← 新增工作空间管理模块
    ├── WORKSPACE_DIRS            # 常量: files, logs, skills
    ├── get_workspace_root()      # 读取 AGENT_CWD 或 /tmp/claude-agent-workspaces
    ├── init_workspace(session_id) → str
    ├── get_or_create_workspace(session_id) → str
    ├── sync_skills_symlinks(workspace_path)
    ├── write_workspace_file(workspace_path, file_path, content) → str
    ├── delete_workspace_file(workspace_path, file_path) → bool
    ├── move_workspace_file(workspace_path, from_path, to_path) → bool
    ├── list_workspace_files(workspace_path, sub_path) → list[WorkspaceFileInfo]
    └── extract_archive_in_skills(workspace_path, archive_rel_path) → None (async)
```

### 3.1 TypeScript → Python 关键映射

| TypeScript（workspace.ts） | Python（workspace.py） | 说明 |
|---------------------------|----------------------|------|
| `mkdirSync(path, { recursive: true })` | `os.makedirs(path, exist_ok=True)` | 递归创建目录 |
| `existsSync(path)` | `os.path.exists(path)` | 路径存在检查 |
| `cpSync(src, dest, { recursive: true })` | `shutil.copytree(src, dest, dirs_exist_ok=True)` | 目录递归同步 |
| `copyFileSync(src, dest)` | `shutil.copy2(src, dest)` | 单文件复制 |
| `symlinkSync(src, dest)` | `os.symlink(src, dest)` | 创建软链接 |
| `lstatSync(path)` | `os.lstat(path)` | 不跟随软链接的 stat |
| `readlinkSync(path)` | `os.readlink(path)` | 读取软链接目标 |
| `unlinkSync(path)` | `os.unlink(path)` | 删除文件/链接 |
| `rmSync(path, { recursive: true })` | `shutil.rmtree(path)` | 递归删除目录 |
| `renameSync(from, to)` | `os.rename(from_path, to_path)` | 重命名/移动 |
| `readdirSync(dir, { withFileTypes: true })` | `os.scandir(dir)` | 目录遍历（带类型） |
| `resolve(path)` | `os.path.realpath(path)` | 规范化绝对路径 |
| `relative(base, target)` | `os.path.relpath(target, base)` | 相对路径（用于路径穿越检查） |
| `process.env.AGENT_CWD` | `os.environ.get("AGENT_CWD")` | 环境变量读取 |
| `tmpdir()` | `tempfile.gettempdir()` | 系统临时目录 |
| `randomUUID()` | `str(uuid.uuid4())` | UUID 生成 |
| `void extractArchiveInSkills(...)` | `asyncio.create_task(extract_archive_in_skills(...))` | 后台异步解压 |

---

## 4. 核心函数设计

### 4.1 `get_workspace_root() → str`

```python
def get_workspace_root() -> str:
    env_cwd = os.environ.get("AGENT_CWD")
    if env_cwd:
        return os.path.abspath(env_cwd)
    return os.path.join(tempfile.gettempdir(), "claude-agent-workspaces")
```

### 4.2 `init_workspace(session_id) → str`

```python
def init_workspace(session_id: str | None = None) -> str:
    workspace_root = get_workspace_root()
    workspace_id = session_id or str(uuid.uuid4())
    workspace_path = os.path.join(workspace_root, workspace_id)

    # 创建三个标准子目录
    for subdir in [WORKSPACE_DIRS.FILES, WORKSPACE_DIRS.LOGS, WORKSPACE_DIRS.SKILLS]:
        os.makedirs(os.path.join(workspace_path, subdir), exist_ok=True)

    # 从项目根同步 .claude/ 模板文件（排除 skills/，该目录由软链接机制维护）
    project_root = os.getcwd()
    claude_dir = os.path.join(project_root, ".claude")
    target_claude_dir = os.path.join(workspace_path, ".claude")
    sync_claude_project_template(claude_dir, target_claude_dir)

    # 种子复制：将项目 .claude/skills/ 中的内置 Skills 复制到 workspace/skills/
    # 已存在的条目跳过，保留用户/Agent 在运行时安装的 Skills
    _seed_workspace_skills(project_root, workspace_path)

    # 从项目根复制 .mcp.json（MCP 服务端配置）
    mcp_json = os.path.join(project_root, ".mcp.json")
    target_mcp_json = os.path.join(workspace_path, ".mcp.json")
    if os.path.exists(mcp_json) and not os.path.exists(target_mcp_json):
        shutil.copy2(mcp_json, target_mcp_json)

    # 同步 Skills 软链接（包含刚种子复制的内置 Skills）
    sync_skills_symlinks(workspace_path)
    return workspace_path
```

### 4.3 `sync_skills_symlinks(workspace_path)`

Skills 软链接机制（详见 [workspace-skills-flow.md](../workspace/workspace-skills-flow.md)）：

- 扫描 `{workspace}/.claude/skills/`，将非点开头的真实文件/目录导入
  `{workspace}/skills/`
- 扫描 `{workspace}/skills/` 目录中所有非点开头条目
- 为每个条目在 `{workspace}/.claude/skills/` 创建指向原路径的软链接
- 若软链接已存在且目标相同，跳过；否则先删再建
- 调用 `_clean_stale_skill_symlinks()` 清理失效链接

### 4.4 路径穿越防护

```python
def _ensure_workspace_safe_path(workspace_path: str, file_path: str) -> str:
    full_path = os.path.join(workspace_path, file_path)
    resolved_path = os.path.realpath(full_path)
    resolved_workspace = os.path.realpath(workspace_path)
    rel = os.path.relpath(resolved_path, resolved_workspace)
    if rel.startswith(".."):
        raise WorkspaceFileAccessError("PATH_TRAVERSAL", "路径穿越不被允许", 400)
    return full_path
```

---

## 5. 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `AGENT_CWD` | `/tmp/claude-agent-workspaces` | 工作空间根目录；生产环境建议设为持久化路径 |

```bash
# 生产环境示例
AGENT_CWD=/data/pawkeyland-workspaces
```

---

## 6. 与 ClaudeAgentService / ClaudeAgentThreadFactory 的集成边界

工作空间骨架在 `ClaudeAgentService.assemble_context()` 内部按 Settings Workspace Mode 按需创建，并作为 Thread Session 享元的 intrinsic 字段被 `AgentRunState` 缓存。该阶段只解析 `cwd`，不初始化 `/memory/`：

```python
# backend/claude_agent/service.py — Phase 1 (Context Assembly)
from libs.claude_agent_kit.server.workspace import get_or_create_workspace

async def assemble_context(self, request, *, state, queue, runner=None):
    system_config = database.get_system_config(user_id)
    workspace_enabled = bool(system_config.get("workspace_enabled", True))

    if workspace_enabled:
        cwd = str(get_or_create_workspace(
            state.session_id,
            sandbox_enabled=True,
            sandbox_network_mode=sandbox_network_mode,
            sandbox_network_allowed_domains=sandbox_network_allowed_domains,
        ))
        state.with_cwd(cwd)
    else:
        cwd = ""
        state.with_cwd("")

    opts = AgentRunOptions(
        thread_id=existing_claude_session_id,
        user_message=user_message_content,
        cwd=cwd or None,
        system_prompt=state.system_prompt,
        # ...
    )
```

> **生产 HTTP 路径**：通过 `ClaudeAgentThreadFactory.run_streaming(request)` 进入；Factory 持有 `AgentRunStatePool`。只有 `workspace_enabled=true` 时，`get_or_create_workspace` 才会被触发并写回 `state.cwd`；关闭时对话保持可用但没有 `<workspace_context>`、`<memory_context>` 或 thread workspace。
>
> **Memory 路径**：调用方在发送首轮 Agent 消息前显式调用 `POST /api/workspace/memory-init`。该文件接口读取 `voices.memory_workspace_config` 并写入 `{cwd}/memory/`。`/api/claude-agent/threads` 和 `assemble_context()` 都不承担 Memory 初始化职责。

---

## 7. 宠物行为记录扩展（未来规划）

在基础工作空间之上，宠物行为记录场景规划扩展路径隔离：

```
{AGENT_CWD}/
  └── {user_id}/
      └── {pet_id}/
          └── {user_id}__{pet_id}/    ← 等价于当前 workspace_path
              ├── files/
              ├── logs/
              └── skills/
```

- 按 `user_id + pet_id` 维度持久化宠物历史行为日志
- 与硬件状态数据（`PetHardwareStatus`）配合，形成可回溯的行为时间线
- `pet_behavior_log.jsonl` 落地到 `logs/` 目录
