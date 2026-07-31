> [Input] Claude Code sandbox docs, restored Claude Code `sandbox-adapter.ts`,
> `backend/libs/claude_agent_kit/server/workspace.py`,
> `backend/claude_agent/service.py`, Settings `workspace_enabled`, Settings
> sandbox network policy.
> [Output] Design for Settings-controlled per-thread Claude Code Bash sandbox.
> [Pos] workspace-sandbox-design-doc in `docs/design/claude-agent`
> [Sync] 2026-06-13: initial design and implementation contract.
> [Sync] 2026-06-14: add runtime dependency read allowlist and clarify that
> built-in file/search tool `input-available` is not proof of execution.
> [Sync] 2026-06-14: document Docker nested sandbox mode for Remote SSH
> deployments.
> [Sync] 2026-06-14: remove user-facing nested sandbox env switch; backend
> auto-detects Linux containers.
> [Sync] 2026-06-16: keep `.claude/skills/` writable; sandbox denyWrite
> protects config/hook internals instead of the whole `.claude/` tree.
> [Sync] 2026-06-17: document Docker Compose runtime privileges required by
> bubblewrap mount namespace setup.
> [Sync] 2026-06-17: include standard Linux `sbin` directories in the runtime
> read allowlist to avoid bubblewrap `/newroot/sbin` tmpfs mount failures.
> [Sync] 2026-06-16: direct real writes under `.claude/skills/` are imported
> into `workspace/skills/` on the next workspace sync before symlinks rebuild.
> [Sync] 2026-06-21: add Settings-backed `sandbox.network` policy.
> [Sync] 2026-06-22: Workspace Mode is now the workspace lifecycle gate:
> when `workspace_enabled=false`, Claude Agent chat does not initialize a
> thread workspace, does not pass `cwd`, and the frontend hides workspace file
> sidebars/entry points.
> [Sync] 2026-06-22: Settings hides Sandbox Network and user environment
> variable controls while Workspace Mode is disabled because both depend on the
> workspace runtime path.
> [Sync] 2026-06-25: `sandbox_network_mode="open"` omits `sandbox.network`
> instead of writing unsupported `allowedDomains:["*"]`.
> [Sync] 2026-07-26: filesystem write policy revision (§2.1) — default-allow
> Claude Code's sandbox TMPDIR (`$CLAUDE_TMPDIR` / `/tmp/claude*` — both
> `/tmp/claude` and `/tmp/claude-{uid}` conventions are allowed) to kill
> the `zsh: operation not permitted: .../cwd-*` noise, and add the
> `sandbox_fs_allowed_write_paths` Settings key for user extra writable
> absolute paths; denyWrite precedence documented.
> [Sync] 2026-07-26: apply-seccomp passthrough revision — bundled-CLI shadowing
> recurrence story documented; `sandbox.seccomp.applyPath` settings override
> (2.1.220 single-binary layout) emitted when
> `INK_AGENT_SANDBOX_SECCOMP_APPLY_PATH` names an existing shim.
> [Sync] 2026-07-26: Route A — settings seccomp override proven DEAD in
> production (2.1.220 embedded converter hardcodes `seccomp: jCu()`, 0
> settings-reader string hits; shim never invoked); mechanism removed,
> reverted to the 2.1.108 vendor passthrough patch + `claude --version`
> build assertion; seccomp section rewritten with the evidence chain.

# Claude-Agent Workspace Sandbox

## 1. Decision

Use Claude Code's built-in `.claude/settings.json` `sandbox` field as the
kernel-level boundary for Bash. Do not implement thread-directory isolation in
`agent_runner.py::_pre_tool_use_hook`.

Reasoning:

- Claude Code already converts `settings.sandbox` into sandbox-runtime config
  and enforces it with OS primitives: macOS Seatbelt, Linux/WSL bubblewrap.
- Sandbox enforcement applies to Bash and all child processes, including complex
  shell syntax that is brittle to parse correctly in a Python hook.
- `PreToolUse` remains a product permission layer. It should decide whether a
  tool call needs frontend approval; it should not try to emulate an OS sandbox.

The target boundary is:

```text
{AGENT_CWD}/{thread_id}
```

`AGENT_CWD` is the shared parent workspace root. The sandbox allowlist is the
resolved per-thread workspace path, not the parent root.

## 2. Product Switch

Settings → AI 模型配置 → 工作区模式 controls:

- whether workspace file/sidebar context is active for the conversation;
- whether Claude Agent chat initializes a per-thread workspace and passes `cwd`
  to Claude Code; and
- whether each initialized thread workspace writes an enabled Claude Code Bash
  sandbox block.

When Workspace Mode is enabled, Settings → AI 模型配置 → 沙箱网络 controls the
sandbox network policy written into the same thread-local `sandbox` block.
When Workspace Mode is disabled, Settings hides Sandbox Network because no
thread workspace or sandbox settings file is initialized for chat turns.

The user environment-variable controls are also shown only while Workspace Mode
is enabled. They are part of the same workspace-runtime surface used by Skills,
MCP tools, and Claude Code subprocess configuration.

When `system_config.workspace_enabled=true`, workspace initialization writes:

```json
{
  "sandbox": {
    "enabled": true,
    "failIfUnavailable": true,
    "autoAllowBashIfSandboxed": true,
    "allowUnsandboxedCommands": false,
    "filesystem": {
      "denyRead": ["/"],
      "allowRead": [
        "{AGENT_CWD}/{thread_id}",
        "<runtime dependency read paths>"
      ],
      "allowWrite": [
        "{AGENT_CWD}/{thread_id}",
        "<Claude sandbox TMPDIR: $CLAUDE_TMPDIR or /tmp/claude[{-uid}]>",
        "<user extra paths: system_config.sandbox_fs_allowed_write_paths>"
      ],
      "denyWrite": [
        "{AGENT_CWD}/{thread_id}/.claude/settings.json",
        "{AGENT_CWD}/{thread_id}/.claude/settings.local.json",
        "{AGENT_CWD}/{thread_id}/.claude/hooks",
        "{AGENT_CWD}/{thread_id}/.claude/.clawhub",
        "{AGENT_CWD}/{thread_id}/.claude/worktrees",
        "{AGENT_CWD}/{thread_id}/.editor",
        "{AGENT_CWD}/{thread_id}/.mcp.json"
      ]
    },
    "network": {
      "allowedDomains": []
    }
  }
}
```

When `workspace_enabled=false`, Claude Agent chat does not initialize the
thread workspace, does not write `.claude/settings.json`, does not pass
`AgentRunOptions.cwd`, and does not inject `<workspace_context>` or
`<memory_context>` into the user message. The route-level attachment path also
skips workspace file sync so file uploads cannot create a workspace as a side
effect. Existing workspaces on disk are left untouched; they are simply not used
while the setting is off.

`enableWeakerNestedSandbox` is emitted automatically when the backend detects
that it is running inside a Linux container. Docker Compose and Remote SSH
Docker deployments do not require a user-facing env switch for this. Claude
Code's Linux sandbox uses bubblewrap, and unprivileged containers may not allow
bubblewrap to mount a fresh `/proc`; the weaker nested mode is acceptable only
because the outer Docker container is the primary isolation boundary. Local
non-container deployments do not write this key.

**apply-seccomp passthrough (Route A, 2026-07-26).** Docker images need the
apply-seccomp passthrough to survive the nested-userns
`/proc/self/setgroups` failure (inherent to bwrap nested userns without
caps; `kernel.apparmor_restrict_unprivileged_userns=0` is NOT the blocker).
The Dockerfile patches the npm CLI's `vendor/seccomp/apply-seccomp` file in
place (2.1.108 layout) with `#!/bin/sh` + `exec "$@"`, and the backend pins
`cli_path` to that patched npm CLI via
`sdk_env.apply_cli_path_to_options()` (see `claude-sdk-env-design.md` §5.5A)
so the SDK's bundled CLI cannot shadow it. A build-time `claude --version`
assertion guards against silent platform-binary misses.

History of the dead alternative (do not retry): after the 0.2.128 migration
we bumped the npm CLI to 2.1.220 (bundled-line parity) and, because 2.1.220
packages the CLI as a single binary with no on-disk vendor file, tried a
settings-driven override (`sandbox.seccomp.applyPath` + a passthrough shim
via `INK_AGENT_SANDBOX_SECCOMP_APPLY_PATH`). Production evidence proved the
settings route dead: the Linux 2.1.220 binary contains **0** occurrences of
the `sandbox?.seccomp` settings reader (vs **16** of `/proc/self/fd/` — the
embedded executor), the macOS bundled converter hardcodes
`seccomp: jCu()` instead of reading `e.sandbox?.*` like sibling fields, and
shim logging confirmed the CLI never invoked the shim. Reverted to Route A;
the settings-seccomp mechanism was removed entirely.

Docker-enabled settings therefore add this sibling key to the same `sandbox`
object:

```json
{
  "sandbox": {
    "enableWeakerNestedSandbox": true
  }
}
```

Docker Compose deployments also need container runtime support for bubblewrap.
The backend service grants `SYS_ADMIN` and disables Docker's seccomp/AppArmor
profiles for that container. Without those privileges, bubblewrap can fail
before executing the command with errors such as
`bwrap: Failed to make / slave: Permission denied`.

The runtime read allowlist must also include existing standard system executable
directories, including `/bin`, `/usr/bin`, `/sbin`, `/usr/sbin`,
`/usr/local/bin`, and `/usr/local/sbin`. For top-level system directories that
may be symlinks in container images, such as `/sbin -> /usr/sbin`, the backend
keeps both the literal alias and the canonical target. These are not product
data roots; they are required so bubblewrap can construct the sandbox root
filesystem and so commands can resolve normal system binaries. If `/sbin` is
hidden by the root deny policy, bubblewrap can fail during rootfs setup with
`bwrap: Can't mount tmpfs on /newroot/sbin: No such file or directory`.

Sandbox network settings are derived from `system_config.sandbox_network_mode`
and `system_config.sandbox_network_allowed_domains`:

| Mode | Written network setting | Meaning |
|---|---|---|
| `disabled` | `allowedDomains: []` + `deniedDomains: ["*"]` | Request no outbound network from Bash sandbox subprocesses; runner PreToolUse also denies network tools. |
| `allowlist` | `allowedDomains: [...]` | Pre-allow configured domains; non-listed domains still follow Claude Code or managed policy. |
| `open` | omit `sandbox.network` | Request unrestricted/default sandbox-runtime egress without passing an unsupported bare `*` allowlist domain; still subject to deployment and managed policy. |

This network policy covers Bash and child processes such as `curl`, `git`, and
package managers. In `disabled` mode, `agent_runner.py` also rejects
`WebFetch`, `WebSearch`, and common Bash network commands before full-access or
low-sensitivity allow decisions. It does not install missing binaries.

### 2.1 Filesystem write policy **[2026-07-26]**

`filesystem.allowWrite` is an ordered allow list; per sandbox-runtime
semantics `denyWrite` always wins over `allowWrite`, so the workspace-internal
deny entries above still take precedence even when a configured extra write
path overlaps them.

1. **`{AGENT_CWD}/{thread_id}`** — the thread workspace (product data root).
2. **Claude sandbox TMPDIR (default-allowed)** — `$CLAUDE_TMPDIR` or
   `/tmp/claude*`. Root cause of the sandboxed-Bash
   `zsh: operation not permitted: /tmp/claude*/cwd-*` noise: Claude Code's
   sandbox sets `TMPDIR` for sandboxed commands to this directory and its
   shell hook writes `cwd-*` files there, but the previous workspace-only
   `allowWrite` denied those writes. The default convention differs by CLI
   version — sandbox-runtime uses `$CLAUDE_TMPDIR || /tmp/claude` (no uid;
   observed in production), other builds use `/tmp/claude-{uid}` (restored
   `filesystem.ts:331-346`) — so **both** `/tmp/claude` and
   `/tmp/claude-{uid}` are allowed defensively. This is the CLI's own runtime
   scratch area (evidence: bundled CLI `CLAUDE_TMPDIR` / `cwd-` strings;
   restored-source analysis `claude-task-tools-source-analysis.md`), not
   user data, so it is always appended when the sandbox is enabled. When
   `sandbox_enabled=false` the `allowWrite` shape is unchanged (workspace
   only).
3. **User extra writable paths** — `system_config.sandbox_fs_allowed_write_paths`
   (new Settings field 「沙箱文件写入」). Sanitized to absolute paths only
   (trailing slashes stripped, deduped, capped at 32 entries / 512 chars),
   appended after the two entries above. Mirrors the
   `sandbox_network_allowed_domains` plumbing:
   `system_config.py` sanitizer → `service.py` /
   `routers/workspace.py` Settings read → `get_or_create_workspace` →
   `_workspace_sandbox_config`.

## 3. Access Semantics

Claude Code sandbox filesystem paths use normal path semantics:

| Prefix | Meaning |
|---|---|
| `/path` | absolute filesystem path |
| `~/path` | home-relative path |
| `./path` or `path` | relative to the settings file's project root |

Because each Claude SDK process runs with `cwd={AGENT_CWD}/{thread_id}` and the
SDK runtime is forced to project settings, the thread's
`{cwd}/.claude/settings.json` is the project settings source for sandboxing.

Read policy is deny-then-allow: deny the filesystem root, then re-allow the
current thread workspace plus a minimal read-only runtime dependency allowlist.
Write policy is allow-only: write access is granted to the current thread
workspace and common sandbox temp locations added by Claude Code itself. We
additionally deny writes to workspace-local config, hook, and editor-index files
that should not be mutated by Bash.

`{workspace}/.claude/skills/` is intentionally **not** in `denyWrite`. Claude
Code discovers skills from this canonical directory, and the workspace sync
mechanism maintains symlinks from `{workspace}/skills/*` into
`{workspace}/.claude/skills/*`. Bash must be able to create, update, and
replace entries there after a tool call has passed the product permission
layer. On the next workspace sync, real files/directories written directly under
`.claude/skills/` are moved into `{workspace}/skills/`, then the canonical
`.claude/skills/` entry is rebuilt as a symlink.

The runtime dependency allowlist is generated by
`workspace.py::_sandbox_runtime_read_allow_paths()` and contains only existing
paths. It covers interpreter/tool roots, system libraries, OpenSSL config, and
temp directories required for commands such as `python --version`,
`node --version`, `rg`, `git`, or compiler probes to start inside the OS
sandbox. It deliberately does **not** include the project root or business data
directories outside the thread workspace.

Deployment-specific runtime roots can be appended with
`INK_AGENT_SANDBOX_EXTRA_ALLOW_READ`, using `os.pathsep` separators (`:` on
Unix-like systems). This is intended for interpreter/package-manager locations,
not for adding product source or user data.

## 4. Interaction Flow

```mermaid
sequenceDiagram
    participant UI as Settings
    participant API as /api/system-config
    participant Service as ClaudeAgentService
    participant Workspace as workspace.py
    participant CC as Claude Code
    participant OS as OS sandbox

    UI->>API: PUT {workspace_enabled, sandbox_network_*}
    API->>API: save system_config
    Service->>API: get_system_config(user_id)
    alt workspace_enabled=true
        Service->>Workspace: get_or_create_workspace(thread_id, sandbox_enabled=true, sandbox_network_*)
        Workspace->>Workspace: write {cwd}/.claude/settings.json sandbox block
        Service->>CC: ClaudeAgentOptions(cwd={AGENT_CWD}/{thread_id})
        CC->>CC: load project sandbox settings
        CC->>OS: run Bash inside sandbox
        OS-->>CC: allow only configured filesystem access
    else workspace_enabled=false
        Service->>Service: skip get_or_create_workspace; clear cached cwd
        Service->>CC: ClaudeAgentOptions(cwd=None)
    end
```

## 5. Relationship To Tool Permissions

Sandboxing and permissions are separate layers:

| Layer | Scope | Owner |
|---|---|---|
| `PreToolUse` permission policy | whether a tool call may run or needs frontend confirmation; also blocks built-in file/search tools outside the thread workspace | `agent_runner.py` |
| Claude Code Bash sandbox | what filesystem resources Bash and child processes can access after the tool is allowed | `.claude/settings.json` + Claude Code |

Claude Code's own documentation separates these two layers: sandboxing applies
to Bash and subprocesses, while Read/Edit permission rules are the layer for
built-in file tools such as `Read`, `Grep`, and `Glob`. Therefore this design
uses both mechanisms:

- Bash and child processes are OS-confined by the thread-local sandbox.
- Built-in file/search tools are hard-denied by `_pre_tool_use_hook` when their
  resolved path is outside `{AGENT_CWD}/{thread_id}`. This directly addresses
  observations like `Grep(path=backend/libs)` or `Read(backend/libs/utils/.folder.md)`
  succeeding: those are not Bash subprocesses, so the Bash sandbox alone cannot
  be the enforcement point.

This design intentionally does not add a `_pre_tool_use_hook` shell parser for
Bash. Complex commands are allowed to reach Claude Code's Bash permission and
sandbox path, where the OS-level sandbox enforces the boundary.

Existing PreToolUse behavior remains with one stricter boundary:

- `.editor/` virtual-index `Read` redirects to a safe temporary snapshot.
- Built-in file/search tools (`Read`, `Grep`, `Glob`, `LS`, `NotebookRead`,
  `Write`, `Edit`, `MultiEdit`) are denied if the resolved path is outside the
  current thread workspace.
- Workspace `files/` built-in file tools can receive explicit allow in auto
  mode after path validation.
- Low-sensitivity non-filesystem query tools, `Skill`, and `switch_editor` can
  be auto-allowed.
- High-sensitivity execution/write/interactive tools still go through frontend
  confirmation unless Settings full-access approval is enabled; full-access does
  not bypass the hard workspace-boundary denial.

The frontend may still show `tool-input-available` for a built-in file/search
tool before the final PreToolUse decision is visible. For example,
`Grep(path=/Users/.../ink-and-memory/backend)` being shown as input only means
Claude proposed that call. It is not evidence that the tool executed. The
backend must return a PreToolUse `permissionDecision:"deny"` before Claude Code
performs the search.

## 6. Implementation Points

| File | Responsibility |
|---|---|
| `backend/libs/claude_agent_kit/server/workspace.py` | Merge the per-thread `sandbox` block into `{workspace}/.claude/settings.json` on every init. |
| `backend/libs/claude_agent_kit/server/agent_runner.py` | Enforce the same thread-workspace boundary for built-in file/search tools, because the Bash sandbox does not cover `Read` / `Grep` / `Glob`. |
| `backend/claude_agent/service.py` | Read `system_config.workspace_enabled` and sandbox network policy before cwd resolution; when enabled, resolve Claude Code cwd through the server-owned `{AGENT_CWD}/{thread_id}` workspace; when disabled, skip workspace initialization, clear cached `state.cwd`, and pass `cwd=None`. |
| `backend/libs/claude_agent_kit/server/agent_runner.py` | Enforce `sandbox_network_mode="disabled"` in PreToolUse so network tools are denied even if sandbox domain wildcard semantics or fallback prompts would otherwise allow execution. |
| `backend/routers/system_config.py` | Persist and sanitize `sandbox_network_mode` / `sandbox_network_allowed_domains` / `sandbox_fs_allowed_write_paths`. |
| `backend/routers/claude_agent.py` | Initialize attachment workspaces with the same Settings-backed sandbox filesystem and network policy before file sync only when Workspace Mode is enabled; skip attachment workspace sync when disabled. |
| `backend/routers/workspace.py` | Initialize file-sidebar workspaces with the same Settings-backed sandbox filesystem and network policy so listing/upload/download does not revert `.claude/settings.json` to defaults. |
| `backend/libs/claude_agent_kit/server/sdk_env.py` | Already forces project-only setting sources, so the thread-local settings file is authoritative for Claude Code. |
| `frontend/src/components/dashboard/ModelConfigSection.tsx` | Describes Workspace Mode as enabling workspace context plus Bash sandbox and emits same-tab Workspace Mode events after toggles. |
| `frontend/src/contexts/WorkspaceContext.tsx` | Loads `workspace_enabled` from system-config and broadcasts the value to chat/file UI. |
| `frontend/src/components/chat/ChatView.tsx` | Hides and closes the workspace file sidebar entry when Workspace Mode is disabled. |
| `frontend/src/components/chat/ChatPanel.tsx` | Withholds `workspaceSessionId` from `AIInputDock` when Workspace Mode is disabled. |
| `backend/Dockerfile` | Installs Claude Code Linux sandbox dependencies (`bubblewrap`, `socat`) plus runtime tools needed by agent commands; ensures standard `sbin` directories exist for bubblewrap rootfs mounts. |
| `docker-compose.yml` | Enables Docker nested Bash sandbox mode for local Compose backend and grants the runtime privileges bubblewrap needs (`SYS_ADMIN`, unconfined seccomp/AppArmor). |
| `deploy/remote-ssh/docker-compose.yml` | Enables the same Docker nested Bash sandbox runtime privileges for Remote SSH backend. |

## 7. Non-Goals

- No custom `@anthropic-ai/sandbox-runtime` wrapper process in this phase.
- No Docker/container/VM sandbox.
- No Python parsing of arbitrary shell syntax for directory isolation.
- No custom proxy, audit UI, or managed-settings admin UI in this phase; the
  app writes Claude Code's supported `sandbox.network` settings for disabled
  and allowlist modes, omits `sandbox.network` for open mode, and uses
  PreToolUse only for the Settings disabled-network guard.
- No attempt to sandbox non-Bash built-in Claude tools through
  `settings.sandbox`; Claude Code documents sandboxing as Bash-scoped.

The standalone `anthropic-experimental/sandbox-runtime` remains a future option
if the product later wants to wrap the whole Claude Code process or individual
MCP servers. That would be a broader runtime architecture change and is not
needed for the current goal.

## 8. Validation

Required checks for this design:

- Workspace tests confirm enabled/disabled sandbox settings are written,
  non-sandbox settings are preserved, runtime dependency paths are read-allowed,
  standard Linux `sbin` runtime paths are read-allowed when present, Docker
  nested sandbox mode is auto-detected, the project root is not default
  read-allowed, disabled/allowlist network policies are emitted, and open mode
  omits `sandbox.network`.
- Service tests confirm `workspace_enabled=false` does not call
  `get_or_create_workspace`, clears cached `cwd`, and produces
  `AgentRunOptions.cwd=None`.
- Route tests confirm attachment handling with `workspace_enabled=false` does
  not initialize a workspace or call workspace file sync.
- Frontend build/type checks confirm Workspace Mode-gated file sidebar UI
  compiles.
- Python compile checks cover `workspace.py`, service and route integration.
- `bash -n .claude/hooks/protect-files-bash.sh` confirms the existing sensitive
  file hook remains syntactically valid.
- Markdown path/link checks cover this design and affected folder docs.

## 9. References

- [Claude Code: Configure the sandboxed Bash tool](https://code.claude.com/docs/en/sandboxing)
- [anthropic-experimental/sandbox-runtime](https://github.com/anthropic-experimental/sandbox-runtime)
- Claude Code restored source:
  `/Users/dmeck/project/claude-code-sourcemap/restored-src/src/utils/sandbox/sandbox-adapter.ts`
