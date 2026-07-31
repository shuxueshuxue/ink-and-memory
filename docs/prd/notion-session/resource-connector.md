# 资源连接器 — 前端 PRD

Status: Draft  
Updated: 2026-07-09
Scope: 产品设计 — 资源连接器前端功能定义、页面交互设计

> [Input] `docs/prd/Chat 工作区入口页.md`,
>      `docs/prd/notion-session/连接器具体配置页面结构草图.md`,
>      `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
> [Output] 资源连接器前端 PRD：功能定义、页面交互设计、交互流程、状态定义
> [Pos] resource-connector-prd in `docs/prd/notion-session`
> [Sync] 2026-07-04: 从 `docs/design/notion-session/resource-connector-prd.md` 拆分，前端 PRD 独立管理
> [Sync] 2026-07-07: Chat 入口页成为主落点，历史对话与连接器工作台下沉到输入框下方，嵌入式资源视图负责连接器管理。
> [Sync] 2026-07-08: 入口描述曾短暂偏离 Chat 主工作区，本稿已回收为 Chat `WorkspaceTabBar` 主入口，并撤销仅摘要化的连接器路径表述。
> [Sync] 2026-07-08: Notion 详情页统一采用 Settings 内 `ConnectorNotionDetailPage` 结构与 `资源连接器 > Notion Connector` 面包屑；详情层级、状态词汇、骨架屏说明与两份最新草图重新对齐。
> [Sync] 2026-07-08: 根据最新反馈修正入口边界：Chat `ResourceConnectorTabPanel` 只做摘要和跳转，点击「选择连接器」或连接器状态面板中的「管理」进入 Settings 的「资源链接」区；Notion 详情页由 Settings 内 `ConnectorNotionDetailPage` 承载，保留现有认证 / 资源选择流程。
> [Sync] 2026-07-08: 详情页业务模型收敛为“同一平台只能认证一个账号”；`ConnectorNotionDetailPage` 不再嵌入集合型 `ResourceConnectorPage`，也不展示新建 / 刷新 / 连接器列表等多实例入口。
> [Sync] 2026-07-08: ResourceScopeSection 合并 Databases 与 Standalone Pages 为统一资源列表，搜索框与保存按钮同一工具行，默认每页 10 条；保存资源后“已挂载来源”必须立即显示所选来源；底部授权 / 同步状态卡移除。
> [Sync] 2026-07-08: Chat `ResourceConnectorTabPanel` 已连接态收紧为非按钮状态面板：展示平台、授权状态、同步状态、已链接资源数量和来源摘要；仅小型「管理」入口跳转 Settings。landing 内容区与输入框同宽，历史 tab 移除冗余外框。
> [Sync] 2026-07-08: 修复资源选择持久化契约：后端 connector 响应必须带 persisted `sources`，前端保存时提交完整资源元数据，刷新后 Settings 已挂载来源与 Chat 已链接资源从同一 DB 状态恢复；Notion People 系统数据源从 discovery 结果过滤。
> [Sync] 2026-07-09: Notion 详情页上方信息栏收紧为无边框紧凑区，授权状态、同步状态、已链接资源数量、最近同步和受限提示统一放入该信息栏；信息栏下方保留轻量“策略设计”占位但暂不实现策略配置。
> [Sync] 2026-07-09: Chat `ResourceConnectorTabPanel` 根内容区减少线框，连接器状态信息块使用虚线边界但无卡片底色 / 阴影；空态和已链接资源行由轻表面和留白承载，只有明确操作控件保留弱边界。
> [Sync] 2026-07-09: Settings `ConnectorNotionDetailPage` 使用单一虚线纸边界；内部资源范围和已挂载来源都是无卡片列表行，不再使用按钮卡片、实线面板或投影表达层级。
> [Sync] 2026-07-09: `ResourceOptionRow` 与 `MountedSourcesSection` 的页数元信息只在 `pageCount > 0` 时显示；`0 pages` 视为空统计，不占用资源行右侧状态区域。

---

## 目录

1. [产品定位](#1-产品定位)
2. [功能定义](#2-功能定义)
3. [页面结构设计](#3-页面结构设计)
4. [交互流程设计](#4-交互流程设计)
5. [状态定义](#5-状态定义)
6. [任务解决方案设计稿](#6-任务解决方案设计稿2026-07-08)
7. [不实现清单](#7-不实现清单)
8. [API 端点汇总](#8-api-端点汇总)

---

## 1. 产品定位

### 1.1 是什么

**资源连接器**（Resource Connector）在 Chat 工作区中是一级摘要视图，在 Settings 中是完整管理视图。用户进入 Chat Dashboard 后，先看到居中的 `ChatInputDock`，其下方通过 `WorkspaceTabBar` 在 `聊天历史` 与 `资源连接器` 之间切换；点击「选择连接器」或连接器状态面板中的「管理」后进入 Settings 的「资源链接」区，再通过 Notion「管理」进入 `ConnectorNotionDetailPage` 完成认证、来源选择与同步管理。

> 本期只落地 Notion Connector 的完整详情页；飞书与本地 CLI 执行器仍保留为入口级占位，不展开完整配置流。
> 同一平台只允许认证一个账号；Notion 详情页是单账号资源配置页，不是连接器集合管理台。

### 1.2 核心价值

- 在 Chat 中让用户感知“可供对话使用的资源”，但把认证、资源选择和同步集中到 Settings，避免 Chat 工作台承担复杂设置。
- 让用户先在 Chat 内看到资源连接器入口，再按需跳转到 Settings 的 `ConnectorNotionDetailPage` 进行细配置。
- 为 Agent 提供结构化外部背景信息，并将其同步为统一的 `.notion/` canonical snapshot 读取入口。

### 1.3 类比理解

| 类比对象 | 对应关系 |
|---------|---------|
| ChatGPT Projects 聊天主页面 | `ChatInputDock` + `WorkspaceTabBar` + `MainContentArea` |
| ChatGPT Projects 来源入口 | Chat 内 `ResourceConnectorTabPanel` |
| Slack / Google Drive 连接器详情 | Settings 内的 `ConnectorNotionDetailPage` |
| 数据源选择 / 索引配置 | `ResourceScopeSection` |

---

## 2. 功能定义

### 2.1 核心功能

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 连接器主入口 | 用户在 Chat 页面通过 `WorkspaceTabBar` 进入 `资源连接器` 视图 | P0 |
| 连接外部平台 | 在 Notion Connector 详情页发起 OAuth / CLI 认证 | P0 |
| 选择资源 | 用户勾选可访问的 Database 与 Standalone Page | P0 |
| 查看来源状态 | 在 Chat 的连接器 Tab 查看摘要；在 Settings Notion 详情页查看当前账号来源 | P0 |
| 发起对话 | 在 Chat 中继续提问，Agent 自动感知已连接资源 | P0 |
| 刷新同步 | 在详情页或后续行内操作中触发同步 | P1 |
| 上传工作空间文件 | 后续迭代，不在本轮详情页实现 | 后续迭代 |
| 选择 Decks | 后续迭代，不在本轮详情页实现 | 后续迭代 |

### 2.2 组件与页面范围

```txt
ChatDashboardPage
  ├── ChatTopHeader
  ├── ChatInputDock
  ├── WorkspaceTabBar
  │     ├── HistoryTab
  │     └── ResourceConnectorTab
  └── MainContentArea
        ├── HistoryTabPanel
        └── ResourceConnectorTabPanel
              ├── ConnectorToolbar
              ├── ConnectorEmptyState / ConnectorList
              └── ConnectorStatusPanel / SelectConnectorButton → Settings ConnectorSettingsSection

SettingsView
  ├── ConnectorSettingsSection
  └── ConnectorNotionDetailPage
        ├── TopNavigation
        ├── ConnectorHeader
        ├── StrategyDesignPlaceholder
        ├── ResourceScopeSection
        └── MountedSourcesSection
```

---

## 3. 页面结构设计

### 3.1 Chat 主入口布局

`资源连接器` 的主入口直接位于 Chat 页面，而不是独立设置页。

```txt
┌──────────────────────────────────────────────────────────────────────────────┐
│ ChatTopHeader                                                                │
│ [Icon] Chat Dashboard                                           [分享] [更多] │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                    ┌──────────────────────────────────────┐                  │
│                    │ ChatInputDock                        │                  │
│                    │ [+] Ask anything...        [附件][模型][头像] │                  │
│                    └──────────────────────────────────────┘                  │
│                                                                              │
│                    ┌──────────────┐ ┌──────────────┐                         │
│                    │ 聊天历史      │ │ 资源连接器    │                         │
│                    └──────────────┘ └──────────────┘                         │
│                                                                              │
│                    MainContentArea                                           │
│                    ├─ HistoryTabPanel（默认）                                │
│                    └─ ResourceConnectorTabPanel（切换后）                    │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Chat 内 `ResourceConnectorTabPanel`

当用户切换到 `资源连接器` Tab：

```txt
ResourceConnectorTabPanel
├── ConnectorToolbar
│   ├── FilterDropdown
│   └── SortDropdown
├── ConnectorContentArea
│   ├── ConnectorEmptyState
│   │   ├── ConnectorTypeIcons（远程资源 / 本地资源 / 更多）
│   │   ├── EmptyTitle：暂无资源连接器
│   │   ├── EmptyDescription：连接 Notion / 飞书 / CLI 后可在对话中使用资源
│   │   └── SelectConnectorButton
│   └── ConnectorList
│       └── ConnectorStatusPanel（平台 / 授权 / 同步 / 已链接资源 / 最近同步 / 来源摘要）
└── ConnectorStatusPanel 管理入口 / SelectConnectorButton click
    └── Navigate → Settings / ConnectorSettingsSection
```

> `ConnectorToolbar` 即使在空状态下也保留位置；加载时显示骨架占位，空态时显示真实筛选 / 排序控件。
> 已连接态中，连接器信息面板不是整卡按钮。面板正文必须优先表达平台状态和已链接资源；跳转 Settings 只能由明确的「管理」小按钮承担。

### 3.3 Settings 内 `ConnectorNotionDetailPage` 详情页

用户从 Chat 进入 Settings 的「资源链接」区，或在 Settings 里点击 Notion「管理」后进入独立详情页：

```txt
页面外层：1px 虚线纸边界，无卡片底色 / 阴影
  ← 资源连接器 > Notion Connector

  ConnectorHeader
│ [Notion图标] Notion Resource Connector              [连接/重新连接 Notion] [关闭连接] │
              授权 / 同步 / 已链接资源 / 最近同步 / 当前限制说明
              无外框，紧凑信息栏

  StrategyDesignPlaceholder
    策略设计暂不实现，只保留位置说明

  ResourceScopeSection
    资源范围                              [搜索资源] [保存资源] [刷新同步]
    未认证：禁用态 + 轻表面说明
    已认证：统一轻列表行（Data source / Page），每页 10 条

  MountedSourcesSection
    当前 Notion 账号已挂载来源和同步状态，轻列表行展示
```

### 3.4 组件表

| 区域 | 组件 | 说明 |
|------|------|------|
| Chat 主切换条 | `WorkspaceTabBar` | Chat 级唯一主切换，固定只有 `HistoryTab` / `ResourceConnectorTab` 两项 |
| Chat 历史内容 | `HistoryTabPanel` | 默认承载空聊天态、历史列表、会话切换后的消息流 |
| Chat 连接器内容 | `ResourceConnectorTabPanel` | 承载筛选排序、空态、连接器列表与错误提示 |
| 连接器详情页 | `ConnectorNotionDetailPage` | Settings 内点击 Notion「管理」后进入的独立配置页 |
| 顶部导航 | `TopNavigation` | 固定使用 `← 资源连接器 > Notion Connector` |
| 连接器头部 | `ConnectorHeader` | 紧凑无边框信息栏：图标 / 名称 / 状态 badge / 连接或关闭动作 / 授权状态 / 同步状态 / 来源数量 / 最近同步 / 受限提示 |
| 策略占位 | `StrategyDesignPlaceholder` | 保留“策略设计”信息位置，但暂不实现表单、开关或策略配置 |
| 资源范围 | `ResourceScopeSection` | 未认证时禁用说明；已认证时展示统一资源列表，支持搜索、每页 10 条分页和选择；页数只在 `pageCount > 0` 时显示 |
| 来源列表 | `MountedSourcesSection` | 只展示当前 Notion 账号已挂载来源，使用无卡片列表行，不提供连接器列表或多实例切换；空页数不显示 |

---

## 4. 交互流程设计

### 4.1 进入资源连接器

```txt
用户进入 Chat Dashboard
    │
    ├─ 默认选中 HistoryTab
    │   └─ MainContentArea 显示 EmptyChatState 或历史 / 当前会话
    │
    └─ 点击 ResourceConnectorTab
        ├─ 先显示 ConnectorToolbar
        ├─ 无连接器 → ConnectorEmptyState
        └─ 有连接器 → ConnectorList
```

### 4.2 创建 / 进入 Notion Connector

```txt
用户位于 ResourceConnectorTabPanel
    │
    ├─ 点击「选择连接器」
    │   └─ 打开 Settings，并滚动 / 聚焦到 ConnectorSettingsSection
    │
    ├─ 点击 Notion Connector 状态面板中的「管理」
    │   └─ 同样打开 Settings 的 ConnectorSettingsSection
    │
    └─ 在 Settings 点击 Notion「管理」
        └─ 页面级导航到 ConnectorNotionDetailPage，顶部显示：← 资源连接器 > Notion Connector
```

### 4.3 认证与资源选择

```txt
用户进入 ConnectorNotionDetailPage
    │
    ├─ 未认证
    │   ├─ ConnectorHeader 信息栏可查看
    │   ├─ ResourceScopeSection 禁用并显示「请先完成 Notion 授权」
    │   └─ ConnectorHeader 信息栏解释当前限制原因
    │
    ├─ 点击认证入口
    │   ├─ POST /api/connectors/:id/auth/login
    │   ├─ 展示验证码 / 打开浏览器确认
    │   └─ POST /api/connectors/:id/auth/poll
    │
    └─ 已认证
        ├─ 展示 database 列表
        ├─ 点击数据库 → 展开 page tree
        ├─ 勾选页面 / 数据库
        └─ POST /api/connectors/:id/resources/select → POST /api/connectors/:id/sync
```

### 4.4 关闭连接

```txt
用户点击 ConnectorHeader 中的「关闭连接」
    │
    ├─ 弹出二次确认
    │   ├─ 说明关闭后将停止对话中调用该连接器
    │   └─ 说明已选来源保留但不可继续同步
    │
    ├─ 确认关闭
    │   ├─ 状态改为「已关闭」
    │   ├─ ResourceScopeSection 改为禁用态
    │   └─ ConnectorHeader 信息栏显示关闭原因与恢复入口
    │
    └─ 取消关闭 → 保持原状态
```

### 4.5 发起对话

```txt
用户回到 ChatInputDock 输入消息
    │
    ├─ 前端创建 / 继续 chat_thread
    ├─ Agent attach 当前 connector 的 canonical snapshot
    └─ 对话可读取 `.notion/` 内对应资源
```

---

## 5. 状态定义

### 5.1 Chat 工作区状态

| 状态 | 说明 | 前端展示 |
|------|------|---------|
| `empty_chat` | 默认历史视图且没有任何对话内容 | `HistoryTabPanel` 显示空聊天态；输入框保持主视觉 |
| `active_chat` | 已有当前会话消息 | `ChatMessageList` 放大，输入区保留在底部 |
| `connector_empty` | 切到 `ResourceConnectorTab` 且无连接器 | 轻表面空态 + 远程资源 / 本地资源 / 更多图标 + CTA |
| `connector_connected` | 至少已有一个连接器 | 虚线边界、无卡片化状态信息块列表 + 筛选 / 排序工具栏 |
| `connector_error` | 连接器读取失败或状态异常 | 在 `ResourceConnectorTabPanel` 内显示错误卡和重试入口 |

### 5.2 连接器详情状态词汇

| 状态词 | 触发条件 | 详情页表现 |
|--------|----------|------------|
| `未认证` | 尚未完成认证 | `ResourceScopeSection` 禁用；`ConnectorHeader` 信息栏解释需先授权 |
| `认证中` | 已发起认证，等待用户确认或轮询 | 显示验证码、浏览器确认提示与轮询反馈 |
| `已连接` | 认证成功且可读取当前连接器配置 | `ConnectorHeader` 信息栏显示正常态 |
| `同步中` | 已选择资源并触发同步 | 状态 badge 与资源列表行显示 loading |
| `同步失败` | 同步任务失败 | 保留已有资源展示并提供重试 |
| `已关闭` | 用户确认关闭连接 | 保留历史资源记录但禁用操作，提示不可在对话中调用 |

### 5.3 资源同步状态

| 状态 | 说明 | 前端展示 |
|------|------|---------|
| `pending` | 已选择资源，等待 sync 开始 | 列表行显示 `待同步` |
| `syncing` | 正在同步中 | skeleton / spinner + 状态文案 |
| `synced` | 同步完成 | 显示最近同步时间、页面数 |
| `stale` | 当前快照过旧 | 提示 `刷新同步` |
| `error` | 同步失败 | 显示错误提示 + 重试按钮 |
| `missing` | 当前 snapshot 未包含该资源 | 显示 `暂不可用` + 重新同步入口 |

---

## 6. 任务解决方案设计稿（2026-07-08）

### 6.1 入口与路由

| 项 | 方案 |
|---|---|
| 问题 | Chat 的「选择连接器」和连接器状态面板不应进入 Chat 内配置页。 |
| 处理 | Chat 只触发 App 层 Settings 导航，并通过 `focusNonce` 聚焦 `ConnectorSettingsSection`。 |
| 判断 | 符合目标：Chat 入口页保持轻量，复杂连接器配置回到 Settings。 |
| 避免过度设计 | 不新增路由库、不新增 URL query/anchor 体系；沿用现有 App 视图状态。 |

### 6.2 Notion 具体配置页

| 项 | 方案 |
|---|---|
| 问题 | `ConnectorNotionDetailPage` 只有简单面包屑和嵌入页，缺少草图里的头部、概览、策略占位、资源区和状态解释。 |
| 处理 | 在 Settings 内重建单账号页面骨架：`TopNavigation`、紧凑 `ConnectorHeader` 信息栏、`StrategyDesignPlaceholder`、`ResourceScopeSection`、`MountedSourcesSection`；页面外层使用单一虚线纸边界，内部保留无卡片列表行；直接复用现有 connector API helpers 承载认证、资源选择、同步和删除流程。 |
| 判断 | 符合目标：保留认证整体流程，同时移除多连接器集合心智。 |
| 避免过度设计 | 不新增后端模型、不新增路由系统、不做多平台抽象，只在 Notion 详情页收敛单平台单账号交互。 |

### 6.2.1 信息栏压缩与策略占位

| 项 | 方案 |
|---|---|
| 问题 | 独立账号状态卡和提示卡占用过多页面比例，授权、同步、已链接资源数量分散，资源范围配置被推到更低位置。 |
| 处理 | `ConnectorHeader` 改为无边框紧凑信息栏，集中展示授权状态、同步状态、已链接资源数量、最近同步和当前限制提示；原账号状态大卡片移除。 |
| 判断 | 符合目标：状态信息仍可见，但不再压缩资源范围配置的首屏空间。 |
| 避免过度设计 | “策略设计”只保留轻量占位，不新增策略表单、开关、存储字段或后端接口。 |

### 6.3 单平台单账号约束

| 项 | 方案 |
|---|---|
| 问题 | Notion 详情页嵌入集合型 `ResourceConnectorPage` 后，会暴露「新建连接器」「刷新列表」「连接器列表」和多个 connector 选择，违背“同一平台只能认证一个账号”。 |
| 处理 | `ConnectorNotionDetailPage` 自己加载当前用户最新的 Notion connector；无 connector 时点击「连接 Notion」隐式创建唯一 connector 并立即进入认证；有 connector 时只允许重新连接、保存资源、刷新同步或关闭连接。 |
| 判断 | 符合目标：页面任务从“管理连接器集合”变成“管理 Notion 这个平台账号的资源范围”。 |
| 避免过度设计 | 不批量迁移历史重复 connector，不引入账号切换器；前端只展示最新 Notion connector，本地 fallback 创建时替换同平台旧记录。 |

### 6.4 资源范围搜索与分页

| 项 | 方案 |
|---|---|
| 问题 | Databases 与 Standalone Pages 分成两个区块，和 `ntn api v1/search` 的统一搜索结果心智不一致；资源多时列表过长。 |
| 处理 | `ResourceScopeSection` 合并为统一资源列表，资源行用 `Data source` / `Page` 标签区分；操作行放置搜索框、保存资源、刷新同步；默认每页展示 10 条，提供上一页 / 下一页。 |
| 判断 | 符合目标：用户按标题搜索资源，不需要先判断资源属于 database 还是 page。 |
| 避免过度设计 | 本轮只做前端合并与本地分页，不新增后端游标接口；后端后续仍可按 `v1/search` 的 `query` / `page_size` / `start_cursor` 扩展。 |

### 6.4.1 资源行页数元信息

| 项 | 方案 |
|---|---|
| 问题 | Notion discovery 可能返回 `pageCount: 0`；如果直接渲染为 `0 pages`，会在资源行右侧形成低价值噪音，并挤压资源类型标签和右侧对勾。 |
| 处理 | `ResourceOptionRow` 与 `MountedSourcesSection` 只在 `pageCount > 0` 时显示页数；`0`、缺失或不可用 page count 都不渲染。 |
| 判断 | 符合目标：资源行右侧只展示有意义的类型、页数和选择状态，空统计不误导用户。 |
| 避免过度设计 | 不新增“无页面”标签，不改后端模型，不把 page count 作为筛选 / 排序条件。 |

### 6.5 保存后已挂载来源即时更新

| 项 | 方案 |
|---|---|
| 问题 | 点击「保存资源」后，资源选择已经提交，但 `MountedSourcesSection` 仍显示空态，用户无法确认当前 Notion 账号到底挂载了哪些来源。 |
| 处理 | 保存成功后优先使用后端返回的 connector sources；若后端返回为空或同步阶段失败，则基于当前选中的 data_source / page 选项生成本地 optimistic sources，同步更新 `MountedSourcesSection`。 |
| 判断 | 符合目标：保存动作有明确结果反馈，“已挂载来源”不再空白。 |
| 避免过度设计 | 不新增复杂 toast / job timeline / 后端轮询状态；只修复当前页面的数据回显闭环。 |

### 6.6 暗色模式

| 项 | 方案 |
|---|---|
| 问题 | Chat、Settings、Decks 局部存在硬编码浅色背景或白色文字，在暗色模式下破坏主题。 |
| 处理 | 将确定影响的浅色面替换为 `var(--color-*)` 语义 token 或 `color-mix()`；保留现有色彩系统。 |
| 判断 | 符合目标：修复主题错误，不重做视觉体系。 |
| 避免过度设计 | 不新增 token 命名空间，不重构全部 inline style。 |

### 6.7 Chat 入口比例、历史边框与连接器状态面板

| 项 | 方案 |
|---|---|
| 问题 | Chat landing 主内容区曾比输入框 / tab 更宽；历史 tab 有额外外层边框；连接器已连接态用整卡按钮或多层线框面板表达，弱化了平台状态和已链接资源。 |
| 处理 | landing 主内容区同输入框 `max-width` 居中；历史 tab 移除外层 border / header divider；连接器根内容区减少线框，状态信息块使用虚线边界但不做卡片底色 / 阴影，展示授权、同步、来源数量、最近同步和来源预览。 |
| 判断 | 符合目标：只修正 Chat 入口比例和信息表达，Settings 仍是唯一详细配置入口。 |
| 避免过度设计 | 不新增 API，不实现真实筛选排序，不在 Chat 内做认证 / 资源选择 / 同步刷新，不恢复多连接器实例入口。 |

### 6.8 已挂载资源持久化与 Chat 回显

| 项 | 方案 |
|---|---|
| 问题 | 保存后的 `MountedSourcesSection` 依赖前端 optimistic sources；刷新页面后 connector 列表响应未带 persisted sources，导致勾选项和 Chat 已链接资源消失。 |
| 处理 | 后端 `store.get_connector/list_connectors` 为 connector 附加 `connector_resources` 作为 `sources`；前端归一化时使用 Notion `external_id/database_id/page_id` 作为 source id；保存时提交完整资源对象而非 id-only payload。 |
| 判断 | 符合目标：Settings 与 Chat 都从同一个数据库持久化状态读取资源。 |
| 避免过度设计 | 不新增独立缓存表，不新增轮询任务，不改变 Settings 详情页和 Chat 摘要的职责边界。 |

### 6.9 Notion People 系统数据过滤

| 项 | 方案 |
|---|---|
| 问题 | Notion `v1/search` 可能返回 Workspace People 系统 data source，不应该作为用户可挂载资源。 |
| 处理 | 在后端 `operations.discover_databases` 过滤具有 People 系统库特征的结果：标题为 People 且包含 `people:*` 属性、Person people 字段或 Membership Type 成员角色字段。 |
| 判断 | 符合目标：污染数据在 discovery 边界被排除，前端无需重复过滤。 |
| 避免过度设计 | 不维护可配置黑名单，不按标题 alone 过滤，避免误伤普通用户数据库。 |

---

## 7. 不实现清单

防止过度设计，以下内容**明确排除**：

| 排除项 | 原因 |
|--------|------|
| 多人协作同一连接器 | 连接器绑定单用户，后续再扩展 |
| 连接器间数据共享 | 每个连接器独立，不做跨连接器引用 |
| 来源内容预览 | 本轮只做标题、状态、层级选择 |
| 来源拖拽排序 | 先做筛选 / 排序即可 |
| 资源版本对比 | 先做覆盖式同步 |
| 连接器模板 / 克隆 | 无需求支撑 |
| Notion 写回 | 本期只读 |
| 多平台完整详情页 | 本期只做 Notion |

---

## 8. API 端点汇总

| 端点 | 方法 | 用途 |
|------|------|------|
| `/api/connectors` | GET | 获取用户的连接器列表 |
| `/api/connectors` | POST | 创建资源连接器 |
| `/api/connectors/:id` | GET | 获取连接器详情 |
| `/api/connectors/:id` | PATCH | 更新连接器名称 / 配置 |
| `/api/connectors/:id` | DELETE | 删除或关闭连接器 |
| `/api/connectors/:id/auth/login` | POST | 启动平台认证 |
| `/api/connectors/:id/auth/poll` | POST | 轮询认证状态 |
| `/api/connectors/:id/databases` | GET | 获取可访问的 Database 列表 |
| `/api/connectors/:id/pages` | GET | 获取可访问的 Standalone Page 列表 |
| `/api/connectors/:id/resources` | GET | 获取已连接资源列表 |
| `/api/connectors/:id/resources/select` | POST | 选择要同步的资源，并把完整资源元数据持久化为 connector `sources` |
| `/api/connectors/:id/resources/:rid` | DELETE | 移除某个资源 |
| `/api/connectors/:id/sync` | POST | 触发同步 |
| `/api/connectors/:id/threads` | GET | 获取连接器关联的对话列表 |

---

## 附录：设计决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 主入口位置 | Chat / 独立设置页 | Chat `WorkspaceTabBar` | 让资源选择保持在对话工作区心智内 |
| 详情页导航 | Chat 内下钻 / Settings 内管理页 | `ConnectorNotionDetailPage` | 复杂配置与 Chat 入口解耦，Settings 保持配置归属 |
| 详情页组件树 | 自定义散装模块 / 草图组件树 | 复用 `TopNavigation` / `ConnectorHeader` 信息栏 / 策略占位 / 资源范围 / 已挂载来源命名 | 与草图和后续实现保持一一对应 |
| 文件上传 | 连接器内 / 全局文件系统 | 后续迭代再定 | 本轮只聚焦远程资源连接 |

---

## 相关文档

- 交互方案设计：[`docs/design/notion-session/connector-interaction.md`](../../design/notion-session/connector-interaction.md)
- 总览设计：[`docs/design/notion-session/overview.md`](../../design/notion-session/overview.md)
- UI 设计稿：[`docs/prd/notion-session/resource-connector-ui-design.md`](./resource-connector-ui-design.md)
