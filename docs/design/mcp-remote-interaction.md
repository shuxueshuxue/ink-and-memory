# MCP 远程指令交互方案设计稿

> 调研对象:`/Users/dmeck/project/claude-code-sourcemap/restored-src`(Claude Code sourcemap 还原源码,只读分析)
> 问题:SDK 中 command 指令(如 `/mcp`)通过什么方式交互?`registerMcpAddCommand` 能否被远程指令交互?
> 日期:2026-07-26

---

## 1. 核心结论(300 字以内)

Claude Code 源码中存在**两套完全不相交的"命令"体系**:`registerMcpAddCommand`(`src/commands/mcp/addCommand.ts:33`)注册的是 **Commander.js 的 argv 子命令** `claude mcp add`,由 `src/main.tsx:3912` 挂载,只做本地配置文件写入(`.mcp.json` / `~/.claude.json`),本身不经过任何网络通道,**不能被远程指令直接交互**。交互式 `/mcp` 是另一条线:`local-jsx` 类型的斜杠命令(`src/commands/mcp/index.ts`),在 SDK/print 非交互模式下被 `processSlashCommand.tsx:615` 短路为**静默空操作**。SDK 与 CLI 之间走 **stdio NDJSON + control 协议**(`control_request`/`control_response`),该协议**确实暴露了远程 MCP 管理能力**:`mcp_set_servers`、`mcp_status`、`mcp_toggle`、`mcp_reconnect`、`mcp_authenticate`、`mcp_clear_auth`。因此远程交互的合规入口是 **SDK control 协议(运行时、dynamic scope、不落盘)** 与 **CLI 子命令/配置文件(持久化)**,而非 `registerMcpAddCommand` 本身。

---

## 2. 架构证据:两套命令层

| 层 | 输入形态 | 框架 | 注册点 | 网络行为 |
|---|---|---|---|---|
| CLI 子命令 | `claude mcp add ...`(argv) | Commander.js(`@commander-js/extra-typings`) | `src/main.tsx:3890+`,`registerMcpAddCommand(mcp)` @ 3912 | 仅本地写配置,无网络 I/O |
| REPL 斜杠命令 | `/mcp`(TUI 输入) | 自定义 `Command` 闭包联合类型 | `src/commands.ts` `COMMANDS()` @ 258 | 无远程命令类型 |

**斜杠命令类型联合**(`src/types/command.ts:205`):`prompt` | `local` | `local-jsx`,**没有 remote 变体**。

- `prompt`:展开为 prompt 发给模型;
- `local`:`call(args, context)` 返回文本,可用 `supportsNonInteractive` 支持无头模式;
- `local-jsx`:返回 Ink/React 节点渲染 TUI 模态 —— `/mcp` 即此类型。

**分发链**:REPL 提交 → `handlePromptSubmit.ts:476` → `processUserInputBase()`(`processUserInput.ts:281`)→ `processSlashCommand()`(`processSlashCommand.tsx:309`)→ `parseSlashCommand()`(`slashCommandParsing.ts:25`)→ 按 `command.type` 分派。SDK 输入同样经此漏斗(`QueryEngine.ts:416`,`querySource: 'sdk'`)。

## 3. 关键判定

### 3.1 `registerMcpAddCommand` 做了什么

`src/commands/mcp/addCommand.ts:33`,签名 `registerMcpAddCommand(mcp: Command): void`(此 `Command` 是 Commander 类型)。注册 `add <name> <commandOrUrl> [args...]`,支持 `-s/--scope`(local|user|project)、`-t/--transport`(stdio|sse|http)、`-e/--env`、`-H/--header`、OAuth 相关选项。action 执行路径:

1. 校验 scope/transport(`src/services/mcp/utils.ts:301,313`);
2. 埋点 `tengu_mcp_add`;
3. 构造 `serverConfig`(stdio / sse / http);
4. `addMcpConfig()`(`src/services/mcp/config.ts:625`):名校验 → 企业策略(`isMcpServerDenied` 等)→ Zod 校验 → **只写本地文件**:
   - project → cwd 的 `.mcp.json`(原子写,config.ts:88)
   - user → `~/.claude.json`
   - local → `~/.claude.json` 的 per-project 段
5. 可选 `saveMcpClientSecret`(keychain)。

**`mcp add` 本身无任何网络交互**;配置的服务器在后续连接时才走 HTTP/SSE/stdio。

### 3.2 为什么不能"远程调用 `registerMcpAddCommand`"

- 它是进程启动期的 argv 解析挂载点,注册行为发生在 CLI 启动时,运行期没有暴露任何触发它的协议通道;
- 命令层联合类型无 remote 变体;远程桥(Remote Control / CCR)对斜杠命令有 `isBridgeSafeCommand` 白名单(`commands.ts:651`),`local-jsx` **一律拒绝**;
- `handleServerControlRequest`(`bridge/bridgeMessaging.ts:243-390`)只处理 `initialize`/`set_model`/`set_max_thinking_tokens`/`set_permission_mode`/`interrupt`,**没有任何 MCP 子类型**。

### 3.3 SDK 侧的交互方式(可远程的部分)

传输层:`StructuredIO`(`src/cli/structuredIO.ts:135`)—— stdin/stdout 上的 **NDJSON**;`--sdk-url` 时换成 `RemoteIO`(WebSocket/SSE,`src/cli/remoteIO.ts:35`),**协议不变,载体不同**。

消息模型(`src/entrypoints/sdk/controlSchemas.ts:642-663`):

- 入:`SDKUserMessage` | `control_request` | `control_response` | `keep_alive` | `update_environment_variables`
- 出:`SDKMessage`(user/assistant/result/system/stream_event)| `control_request` | `control_response` | `control_cancel_request` | `keep_alive`

MCP 相关 control 子类型(`print.ts` 分发链 2831-4025):

| control 子类型 | 能力 | 持久化 |
|---|---|---|
| `mcp_status` | 列出服务器及状态(`buildMcpServerStatuses`,print.ts:1620+) | — |
| `mcp_set_servers` | 动态增/删/换服务器(stdio/sse/http/sdk 型),返回 `{added, removed, errors}`,企业策略仍强制 | **否**(scope=`dynamic`,仅内存) |
| `mcp_toggle` | 启用/禁用(调用 `setMcpServerEnabled`) | 是(写 `~/.claude.json`) |
| `mcp_reconnect` | 重连指定服务器 | — |
| `mcp_authenticate` / `mcp_clear_auth` / `mcp_oauth_callback_url` | OAuth 流程 | 凭证入 keychain |
| `initialize.sdkMcpServers` | 会话级 SDK 型(in-process)服务器 | 否 |

非交互模式下 `/mcp` 是**静默空操作**:`processSlashCommand.tsx:615-622` 对 `local-jsx` 且 `isNonInteractiveSession` 直接 `resolve({messages: [], shouldQuery: false})`,其 React `useEffect` 逻辑从不渲染。

---

## 4. 交互方案设计

### 4.1 目标

在不改动 Claude Code 二进制的前提下,为本产品(ink-and-memory 的 agent 运行时)提供**编程式 MCP 管理**能力,覆盖:查看状态、动态挂载/卸载、启停、重连、OAuth、持久化增删。

### 4.2 方案选型(三条合规路径)

| 路径 | 机制 | 适用场景 | 持久化 | 限制 |
|---|---|---|---|---|
| **A. SDK control 协议** | 持有 `query()` 会话传输,发 `control_request` | 会话内运行时调整、状态观测 | `mcp_toggle` 落盘;`mcp_set_servers` 不落盘 | 需活跃 SDK 会话;企业策略仍生效 |
| **B. CLI 子命令** | 子进程调用 `claude mcp add/add-json/remove/list/get` | 跨会话持久化配置管理 | 是 | 每次起进程;`list/get` 会真实连接服务器做健康检查 |
| **C. 配置文件直写** | 原子写 `.mcp.json` / `~/.claude.json` | 离线批量编排、IaC 化 | 是 | 需自行做 Zod 等价校验与并发互斥;project scope 有 approval 门 |

**推荐:A 为主(运行时),B 为备(持久化),C 仅用于编排场景。**

### 4.3 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                  本产品 Agent Runtime                    │
│  ┌──────────────────┐      ┌─────────────────────────┐  │
│  │ McpAdminService  │─────▶│  A. SDK Control Channel │  │
│  │  (统一门面)       │      │  query() + control_request│ │
│  └───────┬──────────┘      │  mcp_status/set_servers/ │  │
│          │                 │  toggle/reconnect/auth   │  │
│          │                 └───────────┬─────────────┘  │
│          │                             │ stdio NDJSON   │
│          │                 ┌───────────▼─────────────┐  │
│          │                 │  claude CLI (print 模式) │  │
│          │                 └─────────────────────────┘  │
│          │                 ┌─────────────────────────┐  │
│          └────────────────▶│  B. CliMcpAdmin (子进程) │  │
│                            │  claude mcp add/remove… │  │
│                            └───────────┬─────────────┘  │
│                                        ▼                │
│                            .mcp.json / ~/.claude.json   │
└─────────────────────────────────────────────────────────┘
```

### 4.4 接口设计(门面)

```ts
interface McpAdminService {
  /** 路径 A:需活跃 SDK 会话;dynamic scope,不落盘 */
  listStatus(session: SdkSession): Promise<McpServerStatus[]>;        // mcp_status
  setServers(session: SdkSession, servers: McpServersMap)
    : Promise<{ added: string[]; removed: string[]; errors: Record<string, Error> }>; // mcp_set_servers
  toggle(session: SdkSession, name: string, enabled: boolean): Promise<void>; // mcp_toggle(落盘)
  reconnect(session: SdkSession, name: string): Promise<void>;        // mcp_reconnect
  authenticate(session: SdkSession, name: string): Promise<string>;   // mcp_authenticate → OAuth URL

  /** 路径 B:子进程,持久化 */
  addPersistent(cfg: { name: string; scope: 'local'|'user'|'project';
                       transport: 'stdio'|'sse'|'http'; target: string;
                       args?: string[]; env?: Record<string,string>;
                       headers?: Record<string,string> }): Promise<void>;   // claude mcp add
  removePersistent(name: string, scope: Scope): Promise<void>;               // claude mcp remove
}
```

时序(路径 A 的 `mcp_set_servers`):

```
Runtime                SDK Transport                 CLI (print 模式)
  │  control_request{request_id, request:{subtype:'mcp_set_servers', servers}}
  │────────────────────────────────────────────────────────▶│
  │                                                         │ applyMcpServerChanges
  │                                                         │  ├─ type:'sdk' → 进程内占位
  │                                                         │  └─ stdio/sse/http → reconcileMcpServers 拉起
  │                                                         │ 企业策略校验(allowed/deniedMcpServers)
  │  control_response{subtype:'success', response:{added, removed, errors}}
  │◀────────────────────────────────────────────────────────│
```

### 4.5 边界与风险

1. **不要**在 SDK/headless 会话里发 `/mcp` 文本 —— `local-jsx` 会被静默吞掉,表现为"无报错但什么都没发生";调用方必须改走 `mcp_*` control 子类型。
2. `mcp_set_servers` 的结果是 `dynamic` scope,**会话结束即失效**;需要跨会话持久化时必须走路径 B 或 C。
3. `mcp_set_servers` 不绕过企业策略(`config.ts:538` 注释明确其为"第二策略绕过向量"的防护)。
4. 远程桥(claude.ai Remote Control)通道**不支持**任何 MCP control 子类型,移动/网页端不能做 MCP 管理。
5. 还原源码中 SDK 运行时侧(`sdk/runtimeTypes.ts`、`controlTypes.ts`、ProcessTransport)与 `claude server` 实现(`server/server.js` 等)**缺失**,仅 CLI 侧协议完整可见;若需验证 SDK 客户端行为,以已发布 npm 包 `@anthropic-ai/claude-code` 的 `sdk.d.ts` 为准。
6. `claude mcp list/get` 会实际连接服务器做健康检查,自动化批量调用时注意超时与并发。

---

## 5. 附录:证据文件索引

| 主题 | 文件:符号 |
|---|---|
| argv 子命令注册 | `src/commands/mcp/addCommand.ts:33` `registerMcpAddCommand`;`src/main.tsx:3912` |
| 配置写入 | `src/services/mcp/config.ts:625` `addMcpConfig`;:88 `writeMcpjsonFile`;:1553 `setMcpServerEnabled` |
| 命令类型联合 | `src/types/command.ts:205` |
| 斜杠命令注册表 | `src/commands.ts:258` `COMMANDS()`;:476 `getCommands()`;:651 `BRIDGE_SAFE_COMMANDS` |
| 分发 | `src/utils/processUserInput/processSlashCommand.tsx:309,615`;`src/utils/slashCommandParsing.ts:25` |
| `/mcp` 本体 | `src/commands/mcp/index.ts`(local-jsx);`src/commands/mcp/mcp.tsx` |
| SDK 传输 | `src/cli/structuredIO.ts:135`;`src/cli/remoteIO.ts:35` |
| control 协议 schema | `src/entrypoints/sdk/controlSchemas.ts:552-663` |
| control 分发 | `src/cli/print.ts:2831-4025`;`mcp_set_servers` @3055;`mcp_reconnect` @3133;`mcp_toggle` @3206;`mcp_authenticate` @3310;`mcp_clear_auth` @3651;动态挂载实现 @5345 `handleMcpSetServers` |
| 桥白名单 | `src/hooks/useReplBridge.tsx:204-215`;`src/bridge/bridgeMessaging.ts:243-390` |
| 未找到(标记) | `sdk/runtimeTypes.ts`、`sdk/controlTypes.ts`、`src/server/server.js`、`sessionManager.js`、`backends/dangerousBackend.js` |
