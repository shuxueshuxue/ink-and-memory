
# 1. Chat Dashboard 默认空状态结构草图

> [Sync] 2026-07-08: 资源连接器 Tab 只承载轻量摘要、空态、列表和跳转入口；点击「选择连接器」或连接器状态面板中的「管理」进入 Settings「资源链接」，再由 Settings 内 `ConnectorNotionDetailPage` 完成 Notion 单账号认证、统一资源列表搜索 / 分页 / 保存和已挂载来源展示。
> [Sync] 2026-07-08: Chat 入口比例以《链接器概念的交互设计稿》为准：输入框、`WorkspaceTabBar`、下方主内容区保持同宽居中；历史内容不显示额外窗体边框；资源连接器已连接态展示状态信息与已链接资源摘要，不再把整张连接器信息做成按钮。
> [Sync] 2026-07-08: Chat 资源连接器已连接态必须读取 connector persisted `sources`，与 Settings「已挂载来源」共用同一份后端状态；刷新页面后仍显示已链接资源，Notion People 系统数据源不出现在 Chat 摘要中。
> [Sync] 2026-07-09: `ConnectorLandingPanel` 根内容区减少线框，连接器状态信息块改为虚线边界但无卡片底色 / 阴影，空态、状态 chip 与已链接资源行改为轻表面。

对应图片 1：默认没有聊天内容时的首屏。

```txt
┌──────────────────────────────────────────────────────────────────────────────┐
│ App Header                                                                    │
│ ┌──────┐  Chat / 当前模块名称                                      [分享] [更多] │
│ │Icon  │  Chat Dashboard                                                     │
│ └──────┘                                                                      │
└──────────────────────────────────────────────────────────────────────────────┘


                    ┌──────────────────────────────────────────────┐
                    │ Input Dock                                    │
                    │ ┌───┐  输入框 / 创建新会话提示                 │
                    │ │ + │  例如：Ask anything...                  │
                    │ └───┘                              [附件] [模型] [头像] │
                    └──────────────────────────────────────────────┘


                    ┌──────────────┐ ┌──────────────┐
                    │ 聊天历史      │ │ 资源连接器    │
                    └──────────────┘ └──────────────┘


                    ┌──────────────────────────────────────────────┐
                    │                                              │
                    │                                              │
                    │                    Empty Chat State           │
                    │                    ┌────────┐                │
                    │                    │ 图标   │                │
                    │                    └────────┘                │
                    │                    标题文案                  │
                    │                    描述文案                  │
                    │                                              │
                    │                                              │
                    └──────────────────────────────────────────────┘
```

---

# 2. 页面模块拆解

```txt
ChatDashboardPage
├── ChatTopHeader
│   ├── ModuleIcon
│   ├── ModuleTitle
│   ├── ModuleDescription
│   ├── ShareButton
│   └── MoreButton
│
├── ChatInputDock
│   ├── AddButton
│   ├── TextInput
│   ├── AttachmentEntry
│   ├── ModelOrToolEntry
│   └── UserAvatar / SubmitEntry
│
├── WorkspaceTabBar
│   ├── HistoryTab
│   └── ResourceConnectorTab
│
└── MainContentArea
    └── EmptyChatState
        ├── EmptyIcon
        ├── EmptyTitle
        └── EmptyDescription
```

---

# 3. 图片 1 的功能含义

```txt
页面状态：Chat 默认无内容状态

用户可以做的事：
1. 从中间 Input Dock 创建新会话
2. 点击 + 添加附件或资源
3. 通过下方 Tab 切换：
   - 聊天历史
   - 资源连接器
4. 通过右上角分享 / 更多进入辅助操作
```

这里的主视觉重心是 **输入框**。
空状态卡片只是承接“当前还没有对话内容”，不要抢输入框的权重。

---

# 4. 切换到资源连接器后的空状态结构草图

对应图片 2：资源连接器 Tab 下，没有任何资源链接时的状态。

```txt
┌──────────────────────────────────────────────────────────────────────────────┐
│ App Header                                                                    │
│ ┌──────┐  Chat / 当前模块名称                                      [分享] [更多] │
│ │Icon  │  Chat Dashboard                                                     │
│ └──────┘                                                                      │
└──────────────────────────────────────────────────────────────────────────────┘


                    ┌──────────────────────────────────────────────┐
                    │ Input Dock                                    │
                    │ ┌───┐  输入框                                  │
                    │ │ + │  仍然允许创建新对话                       │
                    │ └───┘                         [附件] [工具] [头像] │
                    └──────────────────────────────────────────────┘


                    ┌──────────────┐ ┌──────────────┐      ┌────────┐ ┌────────┐
                    │ 聊天历史      │ │ 资源连接器    │      │ 筛选 ▾ │ │ 排序 ▾ │
                    └──────────────┘ └──────────────┘      └────────┘ └────────┘


                    ┌ - - - - - - - - - - - - - - - - - - - - - - ┐
                    │                                             │
                    │                                             │
                    │                 Resource Empty State         │
                    │                                             │
                    │                ┌────┐ ┌────┐ ┌────┐         │
                    │                │远程│ │本地│ │更多│         │
                    │                └────┘ └────┘ └────┘         │
                    │                                             │
                    │                标题：暂无资源连接器           │
                    │                描述：连接 Notion / 飞书 / CLI │
                    │                     后可在对话中使用资源       │
                    │                                             │
                    │                [前往设置 / 选择连接器]         │
                    │                                             │
                    │                                             │
                    └ - - - - - - - - - - - - - - - - - - - - - - ┘
```

---

# 5. 资源连接器 Tab 页面模块拆解

```txt
ChatConnectorTabView
├── ChatTopHeader
│   ├── ModuleIcon
│   ├── ModuleTitle
│   ├── ModuleDescription
│   ├── ShareButton
│   └── MoreButton
│
├── ChatInputDock
│   ├── AddButton
│   ├── TextInput
│   ├── AttachmentEntry
│   ├── ToolEntry
│   └── UserAvatar
│
├── WorkspaceTabBar
│   ├── HistoryTab
│   └── ResourceConnectorTab(active)
│
├── ConnectorToolbar
│   ├── FilterDropdown
│   └── SortDropdown
│
└── ConnectorContentArea
    └── EmptyConnectorState
        ├── ConnectorTypeIcons
        │   ├── RemoteResourceIcon
        │   ├── LocalResourceIcon
        │   └── AddConnectorIcon
        ├── EmptyTitle
        ├── EmptyDescription
        └── GoToConnectorSettingsButton
```

---

# 6. 核心交互规则

## 默认 Chat 状态

```txt
进入 Chat Dashboard
→ 显示 Chat 模块头部
→ 显示中间 Input Dock
→ 下方默认选中「聊天历史」
→ 主内容区展示空聊天状态
```

## 有对话内容时

```txt
用户发送第一条消息
→ 主内容区从 EmptyChatState 切换为 ChatMessageList
→ 中间输入框视觉权重降低
→ 对话内容区域放大
→ Input Dock 固定在底部或保持主输入位置
```

## 切换到资源连接器

```txt
点击「资源连接器」Tab
→ 主内容区切换为 ConnectorContentArea
→ 如果没有任何资源连接
   → 显示轻表面空状态
   → 展示远程资源 / 本地资源 / 添加资源图标
   → 展示「前往设置 / 选择连接器」按钮
→ 如果已有资源连接
   → 展示平台连接器状态信息和已链接资源摘要
   → 已链接资源来自 connector.sources，不读取前端临时选择态
   → 点击小型「管理」入口进入 Settings「资源链接」
   → 不在 Chat 内展示 Notion 认证、资源范围、已挂载来源或关闭连接操作
```

## 进入 Notion 具体配置

```txt
点击「选择连接器」或连接器状态面板中的「管理」
→ App 视图切换到 Settings
→ 聚焦「资源链接」区
→ 用户点击 Notion「管理」
→ 进入 ConnectorNotionDetailPage
→ 保留 Notion 认证流程
→ 资源范围使用统一 data_source / page 列表
→ 搜索框与「保存资源」同在操作行
→ 默认每页 10 条，支持上一页 / 下一页
→ 保存后「已挂载来源」立即显示所选来源
```

---

# 7. 资源连接器空状态文案建议

```txt
标题：
暂无资源连接器

描述：
连接 Notion、飞书或本地 CLI 执行器后，你可以在对话中直接调用这些资源。

主按钮：
选择连接器

次级说明：
远程资源用于读取外部知识库，本地资源用于连接当前系统 CLI 执行器。
```

---

# 8. 页面状态枚举

```txt
ChatDashboardState
├── empty_chat
│   └── 默认无对话内容
│
├── active_chat
│   └── 有消息内容，聊天区放大
│
├── connector_empty
│   └── 切到资源连接器，但没有任何资源
│
├── connector_connected
│   └── 已有 Notion / 飞书 / CLI 等资源，展示授权 / 同步 / 来源摘要，不使用整卡按钮
│
└── connector_error
    └── 资源认证失效、同步失败、连接不可用
```

---

# 9. 本次问题任务解决方案设计稿

## 9.1 Chat 页面比例不一致

| 项 | 方案 |
|---|---|
| 问题现象 | 下方主内容区横向铺满 shell，与居中输入框和 tab 的比例不一致。 |
| 目标行为 | 默认入口保持“居中输入框 → 同宽 tab → 同宽主内容区”的结构，符合设计稿骨架。 |
| 涉及组件 | `ChatView.tsx` landing 分支中的 `MainContentArea`。 |
| UI 调整 | 给 landing 主内容区设置与输入框一致的最大宽度并居中。 |
| 不做什么 | 不改 active chat 消息流，不重做全局 shell。 |
| 验收标准 | 历史与资源连接器 tab 内容在桌面端不再比输入框宽一大截，移动端仍占满可用宽度。 |

## 9.2 聊天历史窗体多余边框

| 项 | 方案 |
|---|---|
| 问题现象 | 历史列表外层出现额外边框和头部分割线，形成重复窗体。 |
| 目标行为 | 历史 tab 使用轻量列表容器，保留搜索、骨架、空态和滚动，但不加外层边框。 |
| 涉及组件 | `ChatView.tsx` 的 `HistoryTabPanel`。 |
| UI 调整 | 移除历史 tab 外层 border / header border，使用透明或纸面背景承接内容。 |
| 不做什么 | 不移除列表项 hover / active 反馈，不移除历史搜索弹窗。 |
| 验收标准 | 入口页历史区域没有多余外框，仍能选择 / 删除 / 搜索历史对话。 |

## 9.3 资源连接器窗体内容是按钮

| 项 | 方案 |
|---|---|
| 问题现象 | 已连接连接器使用整卡 `<button>`，主要文案是“点击管理”，没有突出平台状态和已链接资源。 |
| 目标行为 | 已连接态显示平台状态面板：平台名称、授权状态、同步状态、已链接资源数量、最近同步、来源摘要。 |
| 涉及组件 | `ConnectorLandingPanel.tsx`。 |
| UI 调整 | 将整卡按钮改为非按钮状态面板，仅保留小型「管理」按钮调用现有 Settings 跳转。 |
| 不做什么 | 不在 Chat 内新增认证、资源选择、同步刷新、筛选排序真实逻辑或多实例入口。 |
| 验收标准 | 连接器区域看起来是状态信息和资源摘要，不是按钮列表；空态 CTA 仍可进入 Settings。 |

## 9.3.1 资源连接器线框面板过重

| 项 | 方案 |
|---|---|
| 问题现象 | `ConnectorLandingPanel` 根 section、连接器状态面板、已链接资源行和空态同时使用外框 / 虚线框 / 阴影卡片，形成重复窗体感。 |
| 目标行为 | Chat 连接器 Tab 像历史 Tab 一样轻量承接内容：状态信息块用虚线边界标识范围，但不使用卡片底色或阴影，内部层级依靠轻表面和留白，只有「管理」等明确控件保留弱边界。 |
| 涉及组件 | `ConnectorLandingPanel.tsx`。 |
| UI 调整 | 移除根内容区外框；状态信息块改为虚线边界并移除卡片背景和阴影；状态 chip、资源行、空态和三枚图标使用轻表面样式。 |
| 不做什么 | 不改变筛选 / 排序位置，不新增 Chat 内同步、保存或连接器配置流程。 |
| 验收标准 | 资源连接器区域不再呈现多层线框面板，但仍能清晰识别平台状态、已链接资源和「管理」入口。 |

## 9.4 已链接资源未读取持久化来源

| 项 | 方案 |
|---|---|
| 问题现象 | Settings 中选择并保存的 Notion 资源刷新后消失，Chat 资源连接器面板也不显示已链接资源。 |
| 目标行为 | Settings 的「已挂载来源」与 Chat 的「已链接资源」都从后端 connector `sources` 恢复，刷新页面后保持一致。 |
| 涉及组件 | `ConnectorNotionDetailPage.tsx`、`ConnectorLandingPanel.tsx`、`resourceConnectorApi.ts`。 |
| 数据约束 | `GET /api/connectors` 与 `GET /api/connectors/:id` 返回 persisted `sources`；source id 使用 Notion 外部 id（`database_id` / `page_id` / `external_id`）对齐 discovery 结果。 |
| 不做什么 | 不新增 Chat 内资源管理状态，不把已链接资源复制成第二份前端缓存。 |
| 验收标准 | 保存资源后刷新 Settings 仍显示已挂载来源；切到 Chat 资源连接器 Tab 能看到同一批已链接资源。 |

## 9.5 People 系统数据源过滤

| 项 | 方案 |
|---|---|
| 问题现象 | Notion search 返回 Workspace People 系统 data source，被误显示为可挂载资源。 |
| 目标行为 | People 等系统用户数据源在后端 discovery 层过滤，不进入 Settings 资源范围，也不会出现在 Chat 已链接资源摘要。 |
| 涉及组件 | Notion discovery / `ConnectorNotionDetailPage` 资源列表 / `ConnectorLandingPanel` 摘要展示。 |
| 过滤边界 | 只过滤具有 People 系统库特征的 data source：标题为 People 且包含 people 属性、Person 字段或 Membership Type 角色字段；不按标题单独误伤普通数据库。 |
| 不做什么 | 不在前端维护黑名单，不新增用户可配置过滤规则。 |
| 验收标准 | 资源范围列表和 Chat 已链接资源中都看不到 Notion People 系统库。 |

## 9.6 目标符合性判断

以上方案都只修正当前偏差：比例、边框、信息表达、持久化回显和系统资源过滤。没有新增 Chat 内资源管理流程、没有扩展多平台管理模型、没有把 Settings 详情页搬回 Chat，因此不属于过度设计。
