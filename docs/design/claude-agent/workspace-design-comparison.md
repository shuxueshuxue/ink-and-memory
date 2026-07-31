> **迁移来源**: Pawkeyland docs/app/design/workspace-design-comparison.md — 路径已适配。

# 工作空间设计对比方案

> **对比基准**：`glide-the/claude-agent-next-kit`（TypeScript/Next.js）vs Pawkeyland（Python/FastAPI）

---

## 1. 技术栈与架构差异

| 维度 | 参考项目（claude-agent-next-kit） | Pawkeyland |
|------|----------------------------------|------------|
| 语言 | TypeScript（Node.js 20+） | Python 3.12 |
| 框架 | Next.js 15 App Router | FastAPI + server.py |
| Agent SDK | `@anthropic-ai/claude-agent-sdk`（npm） | `claude-agent-sdk`（pip） |
| 工作空间模块 | `app/lib/workspace.ts`（已实现） | `backend/libs/claude_agent_kit/server/workspace.py`（已实现） |
| 文件管理 API | `app/api/workspace/files/route.ts`（已实现） | `backend/routers/workspace.py`（已实现） |
| 会话上下文 | 无宠物上下文 | `ClaudeAgentContextBuilder` 注入宠物状态 |
| 部署环境 | Docker / Vercel | Python 服务器进程 |

---

## 2. 工作空间初始化对比

### 参考项目（TypeScript）

```typescript
// app/lib/workspace.ts
export function initWorkspace(sessionId?: string): string {
  const workspaceRoot = getWorkspaceRoot(); // process.env.AGENT_CWD
  const workspaceId = sessionId || randomUUID();
  const workspacePath = join(workspaceRoot, workspaceId);

  mkdirSync(join(workspacePath, "files"), { recursive: true });
  mkdirSync(join(workspacePath, "logs"), { recursive: true });
  mkdirSync(join(workspacePath, "skills"), { recursive: true });

  // Copy .claude/ from project root
  const claudeDir = join(process.cwd(), ".claude");
  if (existsSync(claudeDir)) cpSync(claudeDir, join(workspacePath, ".claude"), { recursive: true });

  // Copy .mcp.json from project root
  const mcpJson = join(process.cwd(), ".mcp.json");
  if (existsSync(mcpJson)) copyFileSync(mcpJson, join(workspacePath, ".mcp.json"));

  syncSkillsSymlinks(workspacePath);
  return workspacePath;
}
```

### Ink & Memory（Python，已实现）

```python
# backend/libs/claude_agent_kit/server/workspace.py
def init_workspace(session_id: str | None = None) -> str:
    workspace_root = get_workspace_root()  # os.environ.get("AGENT_CWD")
    workspace_id = session_id or str(uuid.uuid4())
    workspace_path = os.path.join(workspace_root, workspace_id)

    for subdir in ["files", "logs", "skills"]:
        os.makedirs(os.path.join(workspace_path, subdir), exist_ok=True)

    # Sync .claude/ template (excluding skills/ — managed by symlink mechanism)
    sync_claude_project_template(
        os.path.join(os.getcwd(), ".claude"),
        os.path.join(workspace_path, ".claude")
    )

    # Seed workspace/skills/ from project .claude/skills/ (skip existing entries)
    _seed_workspace_skills(os.getcwd(), workspace_path)

    # Copy .mcp.json from project root
    mcp_json = os.path.join(os.getcwd(), ".mcp.json")
    target_mcp_json = os.path.join(workspace_path, ".mcp.json")
    if os.path.exists(mcp_json) and not os.path.exists(target_mcp_json):
        shutil.copy2(mcp_json, target_mcp_json)

    sync_skills_symlinks(workspace_path)
    return workspace_path
```

**差异**：
- TypeScript 版直接将整个 `.claude/` 复制进工作空间（含 `skills/`），导致内置 skills 通过文件复制而非软链接暴露给 Agent。
- Pawkeyland 版拆分为两步：① `sync_claude_project_template` 同步除 `skills/` 外的配置文件；② `_seed_workspace_skills` 将 `.claude/skills/` 种子复制到 `workspace/skills/`，由软链接机制统一管理。这样既保持幂等性（现有条目不覆盖），又让所有 skills（内置 + 用户安装）走同一套软链接路径。

---

## 3. Skills 软链接同步对比

### 参考项目（TypeScript）

```typescript
export function syncSkillsSymlinks(workspacePath: string): void {
  const claudeSkillsDir = join(workspacePath, ".claude", "skills");
  const workspaceSkillsDir = join(workspacePath, "skills");
  mkdirSync(claudeSkillsDir, { recursive: true });

  const entries = readdirSync(workspaceSkillsDir, { withFileTypes: true });
  for (const entry of entries) {
    if (entry.name.startsWith(".")) continue;
    const sourcePath = join(workspaceSkillsDir, entry.name);
    const symlinkPath = join(claudeSkillsDir, entry.name);
    // ... check existing symlink, remove if needed, create new
    symlinkSync(sourcePath, symlinkPath);
  }
  cleanStaleSkillSymlinks(claudeSkillsDir, workspaceSkillsDir);
}
```

### Pawkeyland（Python，规划）

```python
def sync_skills_symlinks(workspace_path: str) -> None:
    claude_skills_dir = os.path.join(workspace_path, ".claude", "skills")
    workspace_skills_dir = os.path.join(workspace_path, "skills")
    os.makedirs(claude_skills_dir, exist_ok=True)

    if not os.path.exists(workspace_skills_dir):
        return

    with os.scandir(workspace_skills_dir) as entries:
        for entry in entries:
            if entry.name.startswith("."):
                continue
            source_path = os.path.join(workspace_skills_dir, entry.name)
            symlink_path = os.path.join(claude_skills_dir, entry.name)
            # ... check existing symlink, remove if needed, create new
            os.symlink(source_path, symlink_path)
    _clean_stale_skill_symlinks(claude_skills_dir, workspace_skills_dir)
```

**差异**：逻辑完全等价。

---

## 4. Agent 执行入口对比

### 参考项目（TypeScript）

```typescript
// app/api/claude-agent/route.ts
const workspacePath = getOrCreateWorkspace(conversationId);
const result = await agentRunner.runStreaming(
  { threadId: conversationId, userMessage, cwd: workspacePath, ... },
  callbacks
);
```

### Pawkeyland（Python）

> Thread Session 模式下 `cwd` 已成为 `AgentRunState` 享元的 intrinsic 字段（见 [claude-agent-thread-session-patterns.md §4.3](./claude-agent-thread-session-patterns.md#43-享元体agentrunstate)），首轮调用 `get_or_create_workspace(session_id)` 后回写 `state.cwd`，TTL（默认 600 s）内续轮直接复用，避免每轮触发 workspace 模板刷新。

```python
# backend/claude_agent/service.py — Phase 1 (Context Assembly)
workspace_key = session_id = f"{request.user_id}__{request.persona_id}"

# 三层享元短路：① state 享元 → ② request.cwd 显式覆盖 → ③ 首轮 get_or_create_workspace
if state is not None and state.cwd:
    cwd = state.cwd                                    # ← 续轮 / TTL 内命中
elif request.cwd:
    cwd = str(request.cwd)                             # ← 调试覆盖
else:
    cwd = get_or_create_workspace(workspace_key)       # ← 首轮 / TTL 重建
    if state is not None:
        state.cwd = cwd                                # ← 写回享元

opts = AgentRunOptions(
    thread_id=existing_claude_session_id,              # from DB; None on first turn
    user_message=enriched_message,                     # 含宠物上下文
    cwd=cwd,
    system_prompt=state.system_prompt,                 # 同样享元短路
    ...
)
# Factory Phase 2: state.runner = state.runner or create_agent_runner()
# Factory Phase 3: await state.runner.run_streaming(opts, callbacks)
```

**关键差异**：
1. Pawkeyland 在 `cwd` 设置前还通过 `ClaudeAgentContextBuilder` 注入宠物状态上下文（character_card / virtual_character / long_term_profile / Mem0 preflight）
2. `request.cwd` 可直接指定（覆盖自动创建），支持外部工作空间路径
3. 参考项目没有 `request.cwd` 覆盖，始终通过 `getOrCreateWorkspace` 创建
4. **Thread Session 享元化（Pawkeyland 独有）**：`cwd` 在 `AgentRunStatePool` 中按 `session_id` 享元，TTL keepalive（默认 10 分钟）内续轮请求零成本复用 workspace 路径，无需重复触发 `init_workspace` 的模板同步与 skills symlink 重建。

---

## 5. 文件管理 API 对比

### 参考项目（TypeScript）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workspace/files?sessionId=xxx&path=subdir` | 列出工作空间文件 |
| POST | `/api/workspace/files` (multipart) | 上传文件到工作空间 |
| DELETE | `/api/workspace/files` | 删除文件/目录 |
| PATCH | `/api/workspace/files` | 移动/重命名文件 |

功能特性：
- 上传到 `files/` 目录时，自动调用 `saveBufferToWorkspaceFiles()`（含安全清洗、冲突重命名、Hash 计算）
- 上传到 `skills/` 目录时，支持压缩包自动解压（`.zip`, `.tar.gz`, `.tgz`, `.tar`, `.skill`）
- 响应含 `workspaceCreated` 标记和实例调试头（`x-workspace-instance-host`, `x-workspace-instance-pid`）

### Pawkeyland（Python，规划）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/workspace/files?session_id=xxx&path=subdir` | 列出工作空间文件 |
| POST | `/api/workspace/files` (multipart) | 上传文件到工作空间 |
| DELETE | `/api/workspace/files` | 删除文件/目录 |
| PATCH | `/api/workspace/files` | 移动/重命名文件 |

规划特性（与参考项目对齐）：
- FastAPI `UploadFile` 接收文件，等价于 Next.js `formData.getAll("file")`
- 同样支持 Skills 压缩包自动解压（`asyncio.create_task(extract_archive_in_skills(...))`）
- 路径穿越防护：`os.path.relpath(target, base).startswith("..")`
- MIME 类型白名单校验

**当前差异**：参考项目已全部实现，Pawkeyland 仅有 `request.cwd` 支持，文件管理 API 尚未实现。

---

## 6. 宠物场景特有扩展（Pawkeyland 独有）

Pawkeyland 在参考项目基础上扩展了宠物业务维度：

### 6.1 上下文注入（参考项目无此功能）

```python
# ClaudeAgentContextBuilder（Pawkeyland 独有）
enriched_message = context_builder.user_message(
    message=request.message,
    pet_info=request.pet_info,           # 宠物档案
    runtime=request.runtime,             # 运行时状态
    hardware_status=hardware_status,     # 实时硬件数据
    long_term_profile=request.long_term_profile,  # 长期记忆
)
```

### 6.2 工作空间隔离维度

```
# 已实现：每对 (user_id, persona_id) 共用同一工作空间
# Thread Session 享元键 session_id = workspace_key = "{user_id}__{persona_id}"
{AGENT_CWD}/{user_id}__{persona_id}/

# 规划孠物行为记录场景（多对话隔离）
{AGENT_CWD}/{user_id}/{persona_id}/{chat_id}/
```

> Thread Session 模式下 `session_id` 即 `workspace_key`：进程内享元（`AgentRunStatePool`）与磁盘上 workspace 目录、`asyncio.Lock` 完全 1:1 对齐，详见 [claude-agent-thread-session-patterns.md](./claude-agent-thread-session-patterns.md)。

---

## 7. 压缩包 Skill 格式对比

| 格式 | 参考项目（TypeScript 库） | Pawkeyland（Python 标准库） |
|------|--------------------------|---------------------------|
| `.zip` / `.skill` | `unzipper`（第三方 npm） | `zipfile`（Python 标准库） |
| `.tar.gz` / `.tgz` | `tar`（第三方 npm） | `tarfile`（Python 标准库） |
| `.tar` | `tar`（第三方 npm） | `tarfile`（Python 标准库） |

**优势**：Python 实现可以使用标准库，无需额外依赖。

---

## 8. 路径安全防护对比

| 检查项 | 参考项目（TypeScript） | Pawkeyland（Python） |
|--------|----------------------|---------------------|
| 路径穿越 | `relative(resolvedWorkspace, resolvedPath).startsWith("..")` | `os.path.relpath(target, base).startswith("..")` |
| 软链接攻击（tar 包） | `entry.type === "SymbolicLink" \|\| entry.type === "Link"` 抛错 | `tarinfo.issym() or tarinfo.islnk()` 抛错 |
| 绝对路径入口（tar） | `resolve(skillsDir, normalizedPath)` 后穿越检查 | `os.path.realpath(os.path.join(skills_dir, path))` 后穿越检查 |
| 点文件过滤 | `entry.name.startsWith(".")` 跳过 | `entry.name.startswith(".")` 跳过 |

---

## 9. 实现路线图（Pawkeyland）

| 优先级 | 任务 | 目标模块 | 状态 |
|--------|------|----------|------|
| P1 | 实现 `workspace.py` 核心模块 | `backend/libs/claude_agent_kit/server/workspace.py` | ✅ 已实现 |
| P1 | 在 `ClaudeAgentService.assemble_context` (Phase 1) 中自动调用工作空间初始化并享元缓存 | `backend/claude_agent/service.py` | ✅ 已实现 |
| P2 | 实现工作空间文件管理 API | `backend/routers/workspace.py` | ✅ 已实现 |
| P2 | Skills 压缩包自动解压 | `backend/libs/claude_agent_kit/server/workspace.py` | ✅ 已实现 |
| P3 | 宠物行为记录路径层级扩展 | `backend/libs/claude_agent_kit/server/workspace.py` | ⏳ 未来规划 |

---

## 10. 参考实现代码位置索引

| 模块 | 参考项目路径 | Pawkeyland 规划路径 |
|------|------------|-------------------|
| 工作空间管理 | `app/lib/workspace.ts` | `backend/libs/claude_agent_kit/server/workspace.py` |
| 文件管理 API | `app/api/workspace/files/route.ts` | `api/workspace/files.py` |
| 文件同步工具 | `app/lib/workspace-file-sync.ts` | `backend/libs/claude_agent_kit/server/workspace_file_sync.py`（先导入 `.claude/skills/` 真实写入，再重建发现软链接） |
| Agent 执行入口 | `app/api/claude-agent/route.ts` | `backend/claude_agent/thread_factory.py` (`ClaudeAgentThreadFactory.run_streaming`) → `backend/claude_agent/service.py` (Phase 1 / Phase 3) |
| Agent Runner | `app/lib/claude-agent-kit/server/server/agent-runner.ts` | `backend/claude_agent/agent_runner.py`（已实现，被 `state.runner` 享元缓存） |
| 上下文构建 | 无（参考项目无宠物上下文） | `backend/claude_agent/context_builder.py`（已实现，被 Phase 1 调用） |
