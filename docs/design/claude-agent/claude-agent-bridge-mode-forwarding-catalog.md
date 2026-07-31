# Bridge 模式（Remote Control）远端转发操作编目

> 状态：源码分析参考文档
> 分析对象：`/Users/dmeck/project/claude-code-sourcemap/restored-src`（Claude Code sourcemap 恢复源码）
> 关联文档：`claude-agent-sandbox-network-sdk-gap.md`（§6.2 Bridge 概念澄清）
> 日期：2026-07-23

---

## 0. 总览

Bridge 模式（Remote Control）把本地交互式 CLI 会话桥接到 claude.ai，远端 Web/移动用户可查看并控制会话。源码中并存两代协议：

| 代际 | 注册/会话 | 传输 |
|---|---|---|
| v1（env-based） | Environments API 注册 + work poll/ack | Session-Ingress WS 读 + 批量 POST 写（`HybridTransport`） |
| v2（env-less） | `POST /v1/code/sessions` + `/bridge` 换 worker JWT | SSE 读（`…/worker/events/stream`）+ CCRClient 写（`/worker/*`） |

REPL 路径按 GrowthBook `tengu_bridge_repl_v2` 选代（`src/bridge/initReplBridge.ts:397-452`）。两条路径统一产出 `ReplBridgeHandle`（`replBridge.ts:70-81`）：`writeMessages / writeSdkMessages / sendControlRequest / sendControlResponse / sendControlCancelRequest / sendResult / teardown`；入站解析、回声去重、控制处理共享于 `src/bridge/bridgeMessaging.ts`。

**进出方向总原则**：remote→local 只有三种东西——user 消息、control_request、control_response；local→remote 只有——SDKMessage 事件、control_request/response/cancel、keep_alive、result。**远端从不下发模型内容**。

---

## 1. 权限/审批类转发（can_use_tool 族）

### 1.1 通用工具权限（local→remote）

- **触发**：任何工具权限判定为 `behavior:'ask'`（`interactiveHandler.ts:244-253`）。**全部工具都转发**（源码注释 `interactiveHandler.ts:239-243`：CCR 通用 allow/deny 弹窗可处理任意工具）。因此 **ExitPlanMode/计划审批、AskUserQuestion 也在转发之列**；**MCP elicitation 不转发**（本地 `ElicitationDialog` 独立流程，无 bridge 接线）。
- **发送**：`useReplBridge.tsx:541-558` → `sendControlRequest`（v1 `replBridge.ts:1779-1791`；v2 `remoteBridgeCore.ts:824-839`，并 `reportState('requires_action')` 让 claude.ai 显示"等待输入"）。
- **报文**：`{type:'control_request', request_id, session_id, request:{subtype:'can_use_tool', tool_name, input, tool_use_id, description, permission_suggestions?, blocked_path?}}`。
- **竞争与裁决**：本地 UI、hooks、bash 分类器、channel relay、远端五方竞争，`claim()` 先者胜（`interactiveHandler.ts:70`）。远端应答以 `control_response` 入站（`bridgeMessaging.ts:143-147`）→ 按 `request_id` 路由（`useReplBridge.tsx:372-386`）→ allow ⇒ `buildAllow(updatedInput ?? displayInput)` + `persistPermissions(updatedPermissions)`；deny ⇒ `cancelAndAbort(message)`。
- **远端→本地应答报文**：`{behavior:'allow'|'deny', updatedInput?, updatedPermissions?, message?}`（`bridgePermissionCallbacks.ts:3-8`）。
- **取消**：本地先裁决时，CLI 对同一 `request_id` 发 `control_response` + `control_cancel_request`（`useReplBridge.tsx:560-575`；v2 附带 `reportState('running')`），Web 弹窗撤销。客户端侧无超时；服务端仅对**未应答的 server→client** 控制请求断 WS（~10-14s，`bridgeMessaging.ts:150,236-238`）。

### 1.2 沙箱网络审批（local→remote）

- 触发：`REPL.tsx:2251-2309`（"Allow network connection to {host}?"）。
- 发送：`REPL.tsx:2274-2276`，`tool_name = SANDBOX_NETWORK_ACCESS_TOOL_NAME`，`input = {host}`，`tool_use_id` 为随机 UUID。
- 生命周期：与本地 `sandboxPermissionRequestQueue` 弹窗竞争；远端响应**一次性解决同 host 全部挂起请求**（`REPL.tsx:2282-2285`）；本地先裁决经 `sandboxBridgeCleanupRef` 调 `cancelRequest`（`REPL.tsx:2300-2306`）。Swarm worker 不走此路（走 leader mailbox，`REPL.tsx:2233-2247`）。

### 1.3 Headless/SDK 的权限转发

SDK 消费方经控制请求 `remote_control {enabled:true}` 启用（`src/cli/print.ts:3892-4005`）：`structuredIO.setOnControlRequestSent` → `handle.sendControlRequest`，`setOnControlRequestResolved` → `sendControlCancelRequest`；入站 `control_response` 经 `structuredIO.injectControlResponse` 回注 stdin 循环（`print.ts:3931-3936`）。**即 headless 下 SDK client 与 Web client 在同一 `can_use_tool` 请求上竞争**——这是 Ink & Memory 方案 A（升级 SDK + 桥接）可复用的官方机制。

### 1.4 Spawn 模式（`claude remote-control` 守护进程）

被 spawn 的子进程（`--print --sdk-url … --replay-user-messages`，`sessionRunner.ts:287-304`）持有自己的传输，`can_use_tool` 直接 child↔server；父进程仅在子进程 stdout 上观察并记录日志（`bridgeMain.ts:2586-2590`，"not auto-approving"）。配套 API：`BridgeApiClient.sendPermissionResponseEvent`（`bridgeApi.ts:419-450`）。

---

## 2. 消息/会话同步

### 2.1 会话历史与实时消息（local→remote）

- **过滤**（`bridgeMessaging.ts:77-88`）：仅 `user`、`assistant`（非 virtual）、`system`+`local_command` 过桥；工具结果/进度/虚拟消息不过桥。compact 摘要与合成中断消息属于 user 类型，会转发。
- **初始冲刷**：首次连接时按上限（`tengu_bridge_initial_history_cap`，默认 200）转 SDKMessage 批量发送（v1 `replBridge.ts:1241-1313`；v2 `remoteBridgeCore.ts:624-656`）。
- **实时流**：`useReplBridge.tsx:685-713` 按索引 diff `messages` → `writeMessages`。去重：`initialMessageUUIDs`、`recentPostedUUIDs`（容量 2000）、`FlushGate`（历史 POST 期间排队）。
- **回合结束**：`onQuery` finally 中 `sendBridgeResult()`（`REPL.tsx:2932-2934`）→ 合成 `SDKResultSuccess`（usage 置零，`bridgeMessaging.ts:399-416`）——通知移动端停止 spinner；teardown 时供服务端归档。
- **system/init**：连接后推送**脱敏版**（model、permissionMode、bridge 安全命令、agents、skills；tools/mcpClients/plugins 清空防泄漏集成与路径），GB 开关 `tengu_bridge_system_init`（`useReplBridge.tsx:291-326`）。
- **keep_alive**：默认 120s 一跳（`replBridge.ts:1534-1548`）。

### 2.2 入站用户输入（remote→local）

- **到达**：ingress WS/SSE → `handleIngressMessage`（`bridgeMessaging.ts:132-208`）：回声丢弃（`recentPostedUUIDs`）、重投丢弃（`recentInboundUUIDs`）、老 iOS `requestId` 键名兼容；仅 `type:'user'` 转发。
- **内容**：字符串或 ContentBlock[]（图片块 camelCase 归一化，`inboundMessages.ts:52-80`）。
- **附件**：`file_attachments:[{file_uuid,file_name}]` → `GET /api/oauth/files/{uuid}/content`（OAuth Bearer，30s 超时）下载到 `~/.claude/uploads/{sessionId}/{uuid8}-{name}`，并以 `@"path"` 引用前缀注入（`inboundAttachments.ts:81-175`），best-effort。
- **注入**：`enqueue({mode:'prompt', uuid, skipSlashCommands:true, bridgeOrigin:true})`（`useReplBridge.tsx:204-215`）。`bridgeOrigin` 仅放行白名单斜杠命令：prompt 型（skills）+ `BRIDGE_SAFE_COMMANDS` = {compact, clear, cost, summary, releaseNotes, files}；`local-jsx` 一律拒绝并提示"isn't available over Remote Control"（`commands.ts:649-674`）。

### 2.3 远端控制请求（remote→local control_request）

由 `handleServerControlRequest` 处理（`bridgeMessaging.ts:243-391`）：

| subtype | 效果 | 应答 |
|---|---|---|
| `initialize` | 回最小能力集 `{commands:[], output_style, models:[], account:{}, pid}` | success（outbound-only 也必须应答，否则服务端断 WS） |
| `interrupt` | `abortController.abort()`（本地 Esc 等价） | success |
| `set_model` | 主循环模型覆盖 | success |
| `set_max_thinking_tokens` | thinking 开关 | success |
| `set_permission_mode` | 策略门控：禁 bypassPermissions/未启用时拒绝，否则 `transitionPermissionMode` + 重查队列中权限提示 | success 或带原因的 **error** |
| unknown | — | error "REPL bridge does not handle…" |

**outbound-only 模式**：除 `initialize` 外全部应答 error "This session is outbound-only…"（`bridgeMessaging.ts:231-283`）。

---

## 3. 会话生命周期

### 3.1 v1 序列（`initBridgeCore`，`replBridge.ts:260-1839`）

1. 注册环境 `POST /v1/environments/bridge`（OAuth + `environments-2025-11-01` beta，按需 `X-Trusted-Device-Token`）→ `{environment_id, environment_secret}`；
2. 建会话 `POST /v1/sessions`（`source:'remote-control'`），标题派生：`/remote-control <name>` → `/rename` → 最近用户消息 → `remote-control-{slug}`，第 1/3 轮用 Haiku 重派生并 PATCH；
3. 崩溃恢复指针 `bridge-pointer.json`（4h TTL）；
4. work poll 循环：`GET …/work/poll`（environment_secret 鉴权，2s 找活 / 10min 满载），work item `type:'session'` → ack（JWT）→ 连接传输；`healthcheck` 仅 ack；
5. 传输连接：v1 `wss://…/session_ingress/ws/{sessionId}`（OAuth）；v2 注册 worker + SSE；首次连接冲刷历史；
6. 重连：WS 非正常关闭/ poll 404 → 策略1 同会话重注册（URL 不变）；策略2 归档重建。上限 3 次环境重建，poll 退避 2s→60s，15min 放弃；
7. Teardown：result → stopWork(force) → archive → 关连接 → `DELETE` 环境 → 清指针。Perpetual（KAIROS）仅本地拆除。

### 3.2 v2 序列（`initEnvLessBridgeCore`，`remoteBridgeCore.ts:140-887`）

`POST /v1/code/sessions` → `cse_*` id → `POST …/bridge` 换 `{worker_jwt, expires_in, worker_epoch}`（每次调用 epoch +1）→ SSE 读 + CCRClient 写（批量 ≤100）→ 心跳 `PUT …/worker`（默认 20s，服务端 TTL 60s）→ 每帧 `reportDelivery('received'+'processed')` 防幻影重投。JWT 到期前 5min 主动刷新（携带 SSE seq-num 重建传输）；401 触发同等恢复；epoch 失配 409 → 关闭码 4090 → failed。

### 3.3 入口与门控

- URL：连接页 `{claudeAiBase}/code?bridge={environmentId}`；会话页 `{base}/code/{compatSessionId}`；`/remote-control` 对话框与 footer pill 提供 QR。
- 启用路径：`/remote-control [name]`、`--remote-control/--rc`、`remoteControlAtStartup` 配置（旧键 `replBridgeEnabled` 已迁移）、ConfigTool、KAIROS 自动启用、SDK `remote_control` 控制请求。
- 门控：构建旗标 `feature('BRIDGE_MODE')`；`isClaudeAISubscriber()` + GB `tengu_ccr_bridge`；组织策略 `allow_remote_control`；全 scope token + org UUID；各路径最低版本。

### 3.4 Outbound-only / CCR mirror

`feature('CCR_MIRROR')` / 环境 `CLAUDE_CODE_CCR_MIRROR` / GB `tengu_ccr_mirror` 触发（`bridgeEnabled.ts:197-202`）：v2 传输**跳过 SSE 读流**，打 `['ccr-mirror']` 标签，无权限回调、无会话 URL、入站控制一律 error。**纯 local→remote 事件镜像**，让会话在 claude.ai 可见但不可控。

---

## 4. 文件/产物类转发

| 流 | 方向 | 位置 |
|---|---|---|
| Web 附件 `file_uuid` → 下载到 `~/.claude/uploads/` + `@path` 注入 | remote→local | `inboundAttachments.ts` |
| 入站图片块（base64，键名归一化） | remote→local | `inboundMessages.ts:52-80` |
| BriefTool（SendUserMessage/SendUserFile）附件上传 `POST /api/oauth/file_upload`（≤30MB，multipart）→ `file_uuid` 供 Web 预览 | local→remote | `tools/BriefTool/upload.ts:92-173`，门控 `replBridgeEnabled` 或 env `CLAUDE_CODE_BRIEF_UPLOAD`（`attachments.ts:88-108`） |
| `bridge:` 协议 Claude 间对等消息（SendMessageTool 校验 bridge 活跃后 `postInterClaudeMessage`） | local→remote(对等) | `SendMessageTool.ts:633-655,741-759`；`peerSessions.js` 为 feature-gated 模块，恢复源码树中缺失 |

---

## 5. 队列/离线/可靠性清单

- **出站批处理**：v1 `SerialBatchEventUploader`（串行 POST + 退避重试，连续失败 50 次 ≈20min 上限）；v2 CCRClient 批量 ≤100 + 关闭前 flush。
- **入站重放控制**：SSE `from_sequence_num` 高水位跨传输重建与进程重启延续；`recentInboundUUIDs` 兜底。
- **work item 生命周期**：ack（JWT）/ 心跳（300s 租约）/ stop（force=false 重排队，true 终止）/ 5s 未 ack 被 reclaim。
- **冲刷顺序**：`FlushGate` 在历史 POST 期间排队实时写入，跨传输替换保留。
- **失败熔断**：初始化连续失败 3 次自动禁用；失败提示 10s 自动消散；跨进程死 token 退避（`bridgeOauthDeadFailCount≥3`）。
- **认证模型**：注册/会话管理 = claude.ai OAuth（401 单重试刷新）；poll = environment_secret；ack/心跳/事件 = session-ingress JWT（v2 强制 worker 角色）；v1 传输刻意用 OAuth（自刷新），v2 用 JWT（服务端重派或 `/bridge` 重唤刷新）；可信设备令牌（ELEVATED 级）；`SAFE_ID_PATTERN` 防路径注入；work secret 严格版本校验。

---

## 6. TTY/REPL 与 headless/SDK 能力对照

| 能力 | TTY REPL | headless `print.ts` | daemon/SDK |
|---|---|---|---|
| `useReplBridge` / AppState 桥接标志 | ✓ | 自有 `bridgeHandle` | 父进程直连 `initBridgeCore` |
| 权限竞争转发 | ✓ | ✓（structuredIO 钩子） | daemon 自处理 |
| 沙箱网络审批转发 | ✓ | ✗ | ✗ |
| BriefTool 上传 | ✓ | 仅 env `CLAUDE_CODE_BRIEF_UPLOAD` | 同左 |
| 初始历史冲刷 | ✓ | ✓ | ✗ |
| v2 env-less 路径 | ✓（GB 旗标） | 注释称 env-based 专用 | ✗ |
| 入站输入注入 | `enqueue(bridgeOrigin)` | `enqueue` + `run()` | `inboundPrompts()` 生成器 |
| `system/init` 推送 | ✓ | ✗ | ✗ |

> **源码缺失声明**：`src/bridge/peerSessions.js`、`src/bridge/webhookSanitizer.js`、`src/assistant/daemonBridge.ts` 为 feature-gated 模块，未包含在 sourcemap 恢复树中，其内部转发无法从源码编目。

---

## 7. 对 Ink & Memory 的映射启示

| Bridge 机制 | Ink & Memory 对应物 | 差距/可借鉴点 |
|---|---|---|
| `can_use_tool` 五方竞争 + claim 先者胜 | `ToolConfirmationStore` 单一 Future | 竞争解决、cancel 撤销远端弹窗的配对协议可直接对标 |
| 沙箱网络审批同 host 批量解决 | 每次独立弹窗 | 值得引入：同 host 并发请求合并裁决 |
| `set_permission_mode` 远端策略门控 | 无远端模式切换 | 若做 Web 端模式切换，需复刻策略门控（禁 bypassPermissions 等） |
| 斜杠命令 `BRIDGE_SAFE_COMMANDS` 白名单 | 无 | Web 注入输入时的命令白名单范式 |
| `system/init` 脱敏（清空 tools/mcpClients/plugins） | 无 | 任何对外同步的元数据必须过脱敏层 |
| outbound-only mirror | 无 | "只读镜像"是低权限查看端的最小实现 |
| headless `remote_control` 控制请求（print.ts:3892） | 方案 A 桥接点 | SDK 升级后可直接复用官方竞争机制，无需自研协议 |
