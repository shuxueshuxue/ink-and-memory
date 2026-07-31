## ✨ 总体视觉风格（Aesthetic Style）

> [Sync] 2026-07-08: 组件命名回收到 Chat `WorkspaceTabBar` + Settings `ConnectorNotionDetailPage` 体系；保留纸张审美、色板与微交互定义，Chat 不再承载完整配置下钻。
> [Sync] 2026-07-08: Settings 详情页改为单平台单账号资源配置页，不再使用 `ResourceConnectorPage` 的集合型新建、刷新、列表布局。
> [Sync] 2026-07-08: ResourceScopeSection 合并 data_source / page 为统一资源列表，操作行包含搜索、保存、刷新；每页显示 10 条；保存后 MountedSourcesSection 立即显示所选来源；底部授权状态卡移除。
> [Sync] 2026-07-08: `MountedSourcesSection` 与 Chat `ConnectorStatusPanel` 均读取 persisted connector `sources`；刷新后状态不丢失，Notion People 系统 data source 在 discovery 层过滤，不进入统一资源列表。
> [Sync] 2026-07-09: ConnectorNotionDetailPage 的上半部分改为紧凑无边框信息栏，授权 / 同步 / 已链接资源 / 最近同步 / 提示说明全部收敛其中；策略设计只保留轻量占位。
> [Sync] 2026-07-09: ConnectorNotionDetailPage 全页减少线框设计；结构区块、资源行、已挂载来源、空态与状态标签改用轻纸面色块和留白，只有搜索、翻页等控件保留弱边界。
> [Sync] 2026-07-09: Chat `ConnectorLandingPanel` 同步减少卡片化；根内容区无外框，`ConnectorStatusPanel` 使用虚线边界但无卡片底色 / 阴影，已链接资源行、chip 和空态改用轻表面，只有「管理」等明确控件保留弱边界。
> [Sync] 2026-07-09: Settings `ConnectorNotionDetailPage` 使用单一虚线纸边界；内部 `ResourceOptionRow` 与已挂载来源改为无卡片列表行，用轻纸面列表容器和细分隔线表达层级，资源选中态只在右侧显示对勾。
> [Sync] 2026-07-09: 资源行和已挂载来源只在 `pageCount > 0` 时显示页数；`0 pages` 属于空统计，不进入右侧元信息区。

| 维度 | 设计定义 |
| --- | --- |
| 风格关键词 | 暖纸张、手写感、安静工具台、资料贴签、低饱和编辑台 |
| 视觉气质 | 像一本被轻轻摊开的研究手账：留白充足、边界柔和、信息层级克制，强调“整理资源后再开始思考”的安静秩序。 |
| 光影策略 | Settings 详情页只保留页面级虚线纸边界；内部使用留白、轻纸面列表、细分隔线和必要控件边界，资源选中不加深色背景，避免卡片阴影和重描边打断阅读节奏。 |
| 排版策略 | 标题采用 **Noto Serif SC** 增加书卷感，正文与操作采用 **Noto Sans SC**，形成“文档感 + 工具感”的双重语气。 |
| 色彩策略 | Light 模式以米白、奶油、暖灰、墨棕为主；Dark 模式保留暖感，转为深炭褐、烟灰、柔米白，避免冰冷蓝黑。 |
| 交互策略 | 所有反馈都控制在轻量级：悬停上浮 1~2px、纸面层次增强、按钮产生柔和墨色涟漪，强调“可操作但不喧哗”。 |

---

## 🧩 UI 组件结构（Component Structure）

| 模块 | 名称 | 作用 | 关键视觉表现 |
| --- | --- | --- | --- |
| RC-A | `WorkspaceTabBar` | Chat 工作区主切换，固定承载 `HistoryTab` / `ResourceConnectorTab` | 胶囊 tab、位于居中 Input Dock 下方、切换时不改变头部结构 |
| RC-B | `ResourceConnectorTabPanel` | Chat 内连接器内容区，承载 `ConnectorToolbar`、空态和列表 | 轻表面空态、筛选 / 排序工具栏、虚线边界但无卡片化的状态信息块 |
| RC-C | `ConnectorNotionDetailPage` | Settings 内连接器详情 / 配置页的整体页面壳 | 顶部面包屑 `← 资源连接器 > Notion Connector`、单一虚线纸边界、内部无卡片分区 |
| RC-D | `TopNavigation` + `ConnectorHeader` + `StrategyDesignPlaceholder` | 详情页上半部分：导航、无边框紧凑信息栏、策略占位 | Notion 图标、状态胶囊、连接 / 关闭真实操作、授权 / 同步 / 已链接资源 / 最近同步 chip |
| RC-E | `ResourceScopeSection` + `MountedSourcesSection` | 详情页下半部分：资源范围与已挂载来源 | 轻纸面列表容器、统一资源行、弱边界搜索框、分页、来源行无卡片 |

> Chat 中的 `ResourceConnectorTabPanel` 负责“看见连接器、筛选连接器、跳转设置”；复杂配置全部进入 Settings 内的 `ConnectorNotionDetailPage`。
> Chat 已连接态的 `ConnectorStatusPanel` 只展示 persisted `sources` 的数量和最多数条来源摘要；它不读取 Settings 详情页的临时选择态，也不承担保存 / 删除来源。
> Notion 详情页不出现集合级的创建按钮、刷新列表按钮或连接器列表；无账号时「连接 Notion」隐式创建唯一 connector。
> 授权 / 同步解释不再放到底部独立卡片，也不再单独占用账号状态大卡；统一收敛到顶部 `ConnectorHeader` 信息栏。
> 「保存资源」不是静默动作：保存完成后，`MountedSourcesSection` 必须立刻从空态切换为来源列表行，展示标题、类型、同步状态和最近更新时间。
> 页面刷新后的 `MountedSourcesSection` 必须由 connector `sources` 恢复，而不是依赖 optimistic sources；如果 discovery 返回 Notion People 系统 data source，后端过滤后前端不渲染该行。

---

## 🎨 CSS Variables 色彩系统

```css
:root {
  --paper-bg: #f6f0e6;
  --paper-panel: rgba(255, 250, 242, 0.9);
  --paper-card: #fffaf2;
  --paper-card-strong: #f2e8d8;
  --paper-border: rgba(114, 92, 72, 0.18);
  --paper-border-strong: rgba(114, 92, 72, 0.32);
  --paper-text: #3f3429;
  --paper-text-soft: #7a6a59;
  --paper-accent: #5f4a36;
  --paper-accent-soft: #d9c6ad;
  --paper-success: #7e9468;
  --paper-warning: #c78855;
  --paper-danger: #a86652;
  --paper-shadow: 0 18px 40px rgba(106, 83, 58, 0.08);
}

html[data-theme='dark'] {
  --paper-bg: #1d1916;
  --paper-panel: rgba(43, 37, 33, 0.92);
  --paper-card: #2a241f;
  --paper-card-strong: #342d27;
  --paper-border: rgba(222, 206, 186, 0.12);
  --paper-border-strong: rgba(222, 206, 186, 0.26);
  --paper-text: #f3e8d8;
  --paper-text-soft: #b7a894;
  --paper-accent: #ead8bd;
  --paper-accent-soft: #544739;
  --paper-success: #9db487;
  --paper-warning: #e2a674;
  --paper-danger: #cd8b78;
  --paper-shadow: 0 20px 48px rgba(0, 0, 0, 0.28);
}
```

---

## 🎞 微交互定义（Micro-interactions）

| 交互对象 | 触发方式 | 反馈定义 |
| --- | --- | --- |
| 顶栏按钮 | Hover / Focus | 背景由透明过渡为纸卡底色，阴影或纸面层次略增强，整体上浮 1px。 |
| 输入框容器 | Focus within | 外圈出现暖棕色柔和 ring，阴影略加深，强化“可以开始提问”的入口感。 |
| `WorkspaceTabBar` | Switch | 活跃 tab 背景加深并切换 `MainContentArea`；输入区与头部不抖动。 |
| 空状态按钮 | Hover | 轻微上浮并出现更深纸影，箭头图标向右移动 2px。 |
| 连接器状态面板 | Hover | 仅小型「管理」入口强化可点击反馈；面板正文保持信息展示属性，不做整卡按钮。 |
| 统一资源行 | Select | 勾选切换只改变右侧对勾和已选择数量；People 系统 data source 不生成资源行，资源行不做深色背景或卡片按钮；页数只在大于 0 时显示。 |
| 警告状态卡 | Toggle | 开关切换时保持文案区稳定，仅切换状态色与开关位置。 |
| 深色模式 | Toggle | 页面变量切换并带 220ms 颜色过渡，不闪屏。 |

---

## ✅ 说明
- 页面支持 **Light / Dark** 模式切换，并统一服务于 Chat 内 `WorkspaceTabBar` 与 Settings 内 `ConnectorNotionDetailPage`。
- `ResourceConnectorTabPanel` 要求默认保留筛选 / 排序工具栏位置；空态与加载态都不能挤掉该布局锚点。
- 已连接态使用非按钮状态面板，正文展示平台、授权 / 同步状态、已链接资源数量和来源摘要；只有明确的「管理」入口跳转 Settings。
- `ConnectorNotionDetailPage` 必须复用同一纸面视觉语言，外层为单一虚线纸边界，组件层级固定为 `TopNavigation` → `ConnectorHeader` → `StrategyDesignPlaceholder` → `ResourceScopeSection` → `MountedSourcesSection`。
- 资源连接器入口在 Chat 工作区呈现为轻量摘要；完整配置归属于 Settings「资源链接」，详情页是 Settings 内管理层。
- 统一资源列表只展示用户可挂载的 data_source / page；Workspace People 等系统用户数据源属于不可挂载系统资源，应在进入 UI 前过滤。
- 已挂载来源和 Chat 已链接资源是同一份 persisted connector `sources` 的两种视图：Settings 展示完整列表，Chat 展示摘要。
