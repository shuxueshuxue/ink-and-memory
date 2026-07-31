# Plugin 远程指令交互方案设计稿

> 调研对象:`/Users/dmeck/project/claude-code-sourcemap/restored-src`(Claude Code sourcemap 还原源码,只读分析)
> 问题:`/plugin install superpowers@claude-plugins-official` 在 SDK 中通过什么方式交互?能否远程指令交互?
> 姊妹篇:`docs/design/mcp-remote-interaction.md`(MCP 侧,结论可对照)
> 日期:2026-07-31

---

## 1. 核心结论(300 字以内)

`/plugin` 是 `local-jsx` 型斜杠命令(`src/commands/plugin/index.tsx:2-10`,别名 `plugins`/`marketplace`),在 SDK/print 非交互模式下被 `processSlashCommand.tsx:612-621` 短路为**静默空操作**——SDK 中发送 `/plugin install ...` 文本不会有任何效果。SDK↔CLI 的 control 协议中**不存在任何 plugin install/uninstall/marketplace 子类型**,唯一相关的是 `reload_plugins`(重扫并物化"已声明"的插件)。但插件体系是**意图驱动**的:合规的远程路径是把意图写进 settings(`enabledPlugins` + `extraKnownMarketplaces`),由 headless 会话启动时的 reconciler 自动完成 marketplace 克隆与插件安装(`installPluginsForHeadless`),或用可脚本化的 `claude plugin install` argv 子命令。真正的安装网络行为是 git clone / HTTPS 下载 / GCS 镜像,**无 Anthropic API 中介、无授权校验**,与 `registerMcpAddCommand`(纯本地写配置)不同,但同样**不经过任何远程指令通道**。

---

## 2. 架构证据

### 2.1 双入口、单一安装核心

| 层 | 入口 | 注册点 | 汇合点 |
|---|---|---|---|
| REPL 斜杠命令 | `/plugin install x@y`(TUI) | `src/commands/plugin/index.tsx`(local-jsx)→ `parseArgs.ts:17` `parsePluginArgs()` → `PluginSettings.tsx:636` 视图分发 → `BrowseMarketplace.tsx:371` | `installResolvedPlugin()` `src/utils/plugins/pluginInstallationHelpers.ts:348` |
| CLI argv 子命令 | `claude plugin install x@y` | `src/main.tsx:4209` → `pluginInstallHandler` `src/cli/handlers/plugins.ts:668` → `installPluginOp()` `src/services/plugins/pluginOperations.ts:321` | 同上 |

`name@marketplace` 语法解析:`parsePluginIdentifier()`(`src/utils/plugins/pluginIdentifier.ts:51`,按第一个 `@` 切分)。

### 2.2 `/plugin install superpowers@claude-plugins-official` 端到端流程

| # | 步骤 | 符号/文件 | 本地/网络 |
|---|---|---|---|
| 1 | 查目录:`getPluginById('superpowers@claude-plugins-official')` 读 `known_marketplaces.json` + marketplace 缓存清单 | `marketplaceManager.ts:2238/2188` | **本地**(缓存命中;未命中则 install 直接失败,不代抓) |
| 2 | 策略门:`isPluginBlockedByPolicy`(managed-settings) | `pluginPolicy.ts:17` | 本地 |
| 3 | 依赖闭包解析 | `dependencyResolver.ts` | 本地(读缓存目录) |
| 4 | **先写意图**:`enabledPlugins["superpowers@claude-plugins-official"]=true` 写入 user/project/local settings.json | `pluginOperations.ts:305-320`(settings-first 注释) | 本地 |
| 5 | 物化:`cachePlugin(source)` | `pluginLoader.ts:911`;github → git clone(`:662`,SSH 默认);url → clone(`:645`);git-subdir → 稀疏克隆(`:718`);npm → `npm install`(`:492`);string → 本地拷贝;pip → 抛"未支持" | **网络**(git/HTTPS)/本地 |
| 6 | 版本化缓存 → `~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/` | `calculatePluginVersion`、`getVersionedCachePath` | 本地 |
| 7 | 登记 `installed_plugins.json`(V2 schema) | `addInstalledPlugin` | 本地 |
| 8 | 清缓存 + 遥测 `tengu_plugin_installed` | `clearAllCaches()` | 本地 + 遥测外发 |

**官方 marketplace 自动安装**:REPL 启动时 `checkAndInstallOfficialMarketplace()`(`officialMarketplaceStartupCheck.ts:147`)—— 优先 GCS 镜像 `https://downloads.claude.ai/claude-code-releases/plugins/claude-plugins-official/latest`(`officialMarketplaceGcs.ts:47`,匿名 GET),失败回退 git clone(GrowthBook 旗标 `tengu_plugin_official_mkt_git_fallback` 门控)。官方源硬编码:`OFFICIAL_MARKETPLACE_SOURCE = {source:'github', repo:'anthropics/claude-plugins-official'}`(`officialMarketplace.ts:15-25`)。

### 2.3 磁盘布局与启动加载

```
~/.claude/plugins/
  known_marketplaces.json                  # marketplace 注册表
  marketplaces/<name>/                     # 克隆的 marketplace(.claude-plugin/marketplace.json)
  cache/<marketplace>/<plugin>/<version>/  # 版本化插件缓存
  installed_plugins.json                   # 安装登记(V2)
  data/<plugin-id>/                        # 跨升级持久数据
```

意图层:`enabledPlugins: {"name@marketplace": true}` 与 `extraKnownMarketplaces` 在 `~/.claude/settings.json` / `.claude/settings.json` / `.claude/settings.local.json`;managed 策略可强制 `strictKnownMarketplaces`。启动加载(`getCommands` → `getPluginCommands` → `loadAllPluginsCacheOnly`)**全部 cache-only,无网络**;插件命令以 `pluginName:command` 命名空间注入命令表,skills/agents/hooks/MCP 分别经 `loadPluginSkills/Agents/Hooks`、`mcpPluginIntegration` 注入。

## 3. 关键判定

### 3.1 与 `registerMcpAddCommand` 的对照

- 相同点:两者都是 Commander argv 注册(`claude plugin install` @ `main.tsx:4148-4262`),**进程启动期挂载,运行期无远程触发通道**;管理写都是本地文件。
- 不同点:plugin install 的物化步骤**有真实网络行为**(git clone / axios GET / GCS 镜像),而 `mcp add` 纯本地。
- **两者都不能被远程指令直接交互**:control 协议无 plugin install 子类型(全集见 `controlSchemas.ts:552-575`,仅 `reload_plugins` 相关);桥白名单 `BRIDGE_SAFE_COMMANDS` 不含 plugin,`local-jsx` 一律拒绝;`handleServerControlRequest` 只认 5 个子类型。

### 3.2 SDK 侧可编程面(证据)

| 通道 | 能力 | 能否装插件 |
|---|---|---|
| `reload_plugins` control(`print.ts:3065-3132`) | 重扫 + 物化**已声明且 marketplace 已缓存**的插件;返回 `{commands, agents, plugins, mcpServers, error_count}`;远程模式下先回拉用户 settings | 间接:需意图先行 |
| `apply_flag_settings`(内存 flag-settings 层) | 可推 `enabledPlugins`/`extraKnownMarketplaces` 键,但**不触发安装**,需配合后续 `reload_plugins` | 组合技 |
| `--settings` / settings 文件 + headless 启动 reconcile | `installPluginsForHeadless()`(`headlessPluginInstall.ts:43`)在 print/SDK 会话启动时跑 `reconcileMarketplaces()`,物化全部已声明意图;`CLAUDE_CODE_SYNC_PLUGIN_INSTALL=true` 可同步阻塞至首条 query 前 | **是(主路径)** |
| `--plugin-dir <path>` / SDK `plugins:[{type:'local',path}]` | 会话级 inline 插件(`name@inline`) | 仅本地路径、会话级 |
| `claude plugin marketplace add / install / uninstall / enable / disable / update / list --json / validate` | 完整脚本化生命周期,`process.exit(0)` 可组合 | **是(最直接)** |
| `initialize` 请求 / stdin 消息 / 桥通道 | 无任何 plugin 字段或子类型 | 否 |

**未在还原源码中找到**:任何 Anthropic API 中介的插件分发、授权/license 校验;`/plugin list` 斜杠子命令(仅 CLI 有);npm 型 marketplace 源与 pip 型插件源(schema 存在但抛"未实现")。

---

## 4. 交互方案设计

### 4.1 目标

为本产品 agent 运行时提供编程式插件管理:声明意图 → 自动物化 → 会话激活 → 可观测。约束:不改 Claude Code 二进制;不用 TUI;企业策略不可绕过。

### 4.2 方案选型

| 路径 | 机制 | 适用 | 持久化 | 确定性 |
|---|---|---|---|---|
| **A. 意图 + headless reconcile(推荐主路径)** | 写 settings(`enabledPlugins`/`extraKnownMarketplaces`)或 `--settings` 注入 → 起 print/SDK 会话自动安装;`CLAUDE_CODE_SYNC_PLUGIN_INSTALL=true` 保序 | 自动化、CI、远程会话 | 是 | 高(可同步阻塞) |
| **B. CLI argv 子命令** | 子进程 `claude plugin marketplace add` + `claude plugin install --scope` | 运维侧显式生命周期管理 | 是 | 高 |
| **C. 活跃会话组合技** | `apply_flag_settings`(推意图)→ `reload_plugins`(物化+激活) | 长驻 SDK 会话内热启用 | 内存层(不落盘) | 中:marketplace 必须已物化,新 marketplace 需先走 A/B |
| **D. `--plugin-dir` / SDK plugins 选项** | 本地路径 inline 加载 | 开发调试、会话级试验 | 否 | 高 |

**推荐:A 为主(声明式),B 为备(命令式),C 仅作热刷新,D 用于本地开发。**

### 4.3 架构设计

```
┌────────────────────────────────────────────────────────────┐
│                    本产品 Agent Runtime                     │
│  ┌──────────────────┐   ┌───────────────────────────────┐  │
│  │ PluginAdminService│   │ A. IntentWriter               │  │
│  │  (统一门面)        │──▶│  合并写 enabledPlugins /       │  │
│  └───────┬──────────┘   │  extraKnownMarketplaces        │  │
│          │              │  → settings.json / --settings  │  │
│          │              └──────────────┬────────────────┘  │
│          │                             │ spawn             │
│          │              ┌──────────────▼────────────────┐  │
│          │              │ claude -p / SDK 会话启动        │  │
│          │              │ installPluginsForHeadless()    │  │
│          │              │  reconcileMarketplaces()       │  │
│          │              │  (SYNC_PLUGIN_INSTALL=true)    │  │
│          │              └──────────────┬────────────────┘  │
│          │                             │ git clone / GCS    │
│          │                             ▼                    │
│          │                   ~/.claude/plugins/…           │
│          │              ┌───────────────────────────────┐  │
│          ├─────────────▶│ B. CliPluginAdmin (子进程)     │  │
│          │              │ claude plugin marketplace add  │  │
│          │              │ claude plugin install x@y -s … │  │
│          │              └───────────────────────────────┘  │
│          │              ┌───────────────────────────────┐  │
│          └─────────────▶│ C. LiveSessionActivator        │  │
│                         │ apply_flag_settings →          │  │
│                         │ reload_plugins → 校验响应       │  │
│                         └───────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 4.4 接口设计(门面)

```ts
interface PluginAdminService {
  /** 路径 A:声明式。写意图并保证下一次会话启动时物化完成 */
  declareAndInstall(target: PluginRef /* "superpowers@claude-plugins-official" */,
                    scope: 'user'|'project'|'local',
                    opts?: { syncTimeoutMs?: number }): Promise<InstallReceipt>;
  declareMarketplace(name: string, source: MarketplaceSource,
                     scope: Scope): Promise<void>;

  /** 路径 B:命令式。立即子进程执行,适合运维动作 */
  installNow(target: PluginRef, scope: Scope): Promise<void>;          // claude plugin install
  uninstallNow(target: PluginRef, opts?: { keepData?: boolean }): Promise<void>;
  listInstalled(scope?: Scope): Promise<InstalledPlugin[]>;            // claude plugin list --json

  /** 路径 C:活跃会话热激活(前置:marketplace 已物化) */
  activateInSession(session: SdkSession, targets: PluginRef[])
    : Promise<{ plugins: PluginInfo[]; mcpServers: string[]; errorCount: number }>; // apply_flag_settings + reload_plugins

  /** 路径 D:会话级本地插件 */
  withLocalPluginDir(path: string): SpawnOption; // --plugin-dir
}
```

时序(路径 A,主路径):

```
Runtime                 本地状态                    claude -p(SDK 会话)
  │ 写 enabledPlugins + extraKnownMarketplaces
  │────────────────────▶│ settings.json
  │ spawn: claude -p --output-format stream-json …
  │   env: CLAUDE_CODE_SYNC_PLUGIN_INSTALL=true
  │────────────────────────────────────────────────▶│
  │                                                   │ installPluginsForHeadless()
  │                                                   │  ├─ reconcileMarketplaces()
  │                                                   │  │   → clone/GCS 新 marketplace
  │                                                   │  └─ cachePlugin() → 版本化缓存
  │ system/init {plugins:[{name,path,source}], …}     │  (首条 query 前完成)
  │◀──────────────────────────────────────────────────│
  │ 校验 init.plugins 包含目标 → InstallReceipt
```

### 4.5 边界与风险

1. **不要在 SDK/headless 会话里发 `/plugin install …` 文本** —— `local-jsx` 静默吞掉,表现为"无报错无效果";与 `/mcp` 完全同构。
2. `reload_plugins` **不会**拉取全新 marketplace(只物化已声明且清单已缓存的插件);路径 C 遇到新 marketplace 必须先走 A 或 B,否则报"not found"。
3. Install 是 **settings-first**:意图先落盘,物化失败时意图仍在 —— 重试语义安全,但观测层要区分"已声明"与"已物化"(读 `installed_plugins.json` vs settings)。
4. 网络面:github 源默认 **SSH clone**(`git@github.com:…`),CI 环境无 SSH key 时需设 `CLAUDE_CODE_REMOTE` 或改用 https url 源;官方 marketplace 优先走 GCS 匿名镜像,注意出口代理白名单(`downloads.claude.ai`)。
5. 遥测外发(`tengu_plugin_*`、`logPluginFetch`)默认开启,受隐私约束的环境按现有遥测开关统一治理。
6. 企业 managed-settings 的 `strictKnownMarketplaces`/插件阻断策略**本地强制执行**,任何路径都不可绕过;门面层应把策略拒绝映射为一等错误。
7. 还原源码中 SDK 运行时侧(`sdk/runtimeTypes.ts` 等)缺失;SDK `plugins:[{type:'local',path}]` 选项以已发布 npm 包 `@anthropic-ai/claude-code` 的 `sdk.d.ts` 为准。
8. npm 型 marketplace 源与 pip 型插件源在源码中抛"未实现",门面层不要暴露这两类 source。

---

## 5. 附录:证据文件索引

| 主题 | 文件:符号 |
|---|---|
| `/plugin` 注册 | `src/commands/plugin/index.tsx:2-10`(local-jsx,别名 plugins/marketplace) |
| 子命令解析 | `src/commands/plugin/parseArgs.ts:17` `parsePluginArgs()`;:39-42 `@` 切分 |
| `x@y` 标识解析 | `src/utils/plugins/pluginIdentifier.ts:51` `parsePluginIdentifier()` |
| 安装核心 | `src/utils/plugins/pluginInstallationHelpers.ts:348` `installResolvedPlugin()`;:506 `installPluginFromMarketplace()` |
| CLI 注册 | `src/main.tsx:4148-4262`(`install` @4209;`marketplace add` @4172) |
| CLI 服务层 | `src/cli/handlers/plugins.ts:668`;`src/services/plugins/pluginCliCommands.ts:103`;`pluginOperations.ts:321` `installPluginOp()` |
| 物化/缓存 | `src/utils/plugins/pluginLoader.ts:911` `cachePlugin`;:662/645/718/492 各 source 实现 |
| marketplace 管理 | `src/utils/plugins/marketplaceManager.ts:1782` `addMarketplaceSource`;:1433 `loadAndCacheMarketplace`;:2238 `getPluginById` |
| 官方 marketplace | `src/utils/plugins/officialMarketplace.ts:15-25`;`officialMarketplaceGcs.ts:47`;`officialMarketplaceStartupCheck.ts:147` |
| headless 自动安装 | `src/utils/plugins/headlessPluginInstall.ts:43`;`src/cli/print.ts:1704-1744,1881-1918`(`CLAUDE_CODE_SYNC_PLUGIN_INSTALL`) |
| 启动 reconcile | `src/services/plugins/reconciler.ts:114`;`PluginInstallationManager.ts:60`;`performStartupChecks.tsx:24` |
| 磁盘布局 | `src/utils/plugins/pluginDirectories.ts:53-99` |
| 意图 schema | `src/utils/settings/types.ts:559-599`(`enabledPlugins`、`extraKnownMarketplaces`) |
| SDK control | `src/entrypoints/sdk/controlSchemas.ts:405-433`(`reload_plugins`),:552-575(全集),:57-75(initialize 无 plugin 字段);`src/cli/print.ts:3065-3132` 处理器 |
| 桥拒绝 | `src/commands.ts:651-676`;`src/bridge/bridgeMessaging.ts:243-389` |
| 加载注入 | `src/commands.ts:446-466`;`src/utils/plugins/loadPluginCommands.ts:414,840`;`pluginLoader.ts:1888,3137` |
| 未找到(标记) | SDK runtime 侧(`sdk/runtimeTypes.ts`、`controlTypes.ts`)、npm marketplace 源实现、pip 插件源实现、API 中介分发 |
