# 资源连接器 — ER 关系模型设计

Status: Draft  
Updated: 2026-07-04  
Scope: 设计 — 资源连接器 ER 关系模型与数据库设计

> [Input] `docs/design/notion-session/connector-interaction.md`,
>      `docs/design/notion-session/overview.md`,
>      `docs/design/claude-agent/notion-point/resource-connector-layer-design.md`
> [Output] 资源连接器 ER 模型、关系说明、关键约束、设计决策
> [Pos] resource-connector-er in `docs/design/notion-session`
> [Sync] 2026-07-04: 从 resource-connector-prd.md 拆分，ER 设计独立管理；前端 PRD 移至 `docs/prd/notion-session/`

---

## 目录

1. [ER 关系模型](#1-er-关系模型)
2. [设计决策记录](#2-设计决策记录)
3. [相关文档](#3-相关文档)

---

## 1. ER 关系模型

### 1.1 ER 图

```text
users
────────────────────────────────────────────────────────────
 PK  id              INTEGER

        │ 1
        │
        │ N

resource_connectors
────────────────────────────────────────────────────────────
 PK  id              TEXT (UUID)
 FK  user_id         INTEGER → users.id ON DELETE CASCADE
     name            TEXT NOT NULL          ← 连接器显示名称
     platform        TEXT NOT NULL          ← "notion" | "github" | ...
     auth_status     TEXT DEFAULT 'pending' ← "pending" | "authenticated" | "expired"
     config          JSON                   ← 平台配置（notion_home 等）
     last_synced_at  DATETIME NULL
     created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
     updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP
────────────────────────────────────────────────────────────
 INDEX: (user_id, updated_at DESC)

        │ 1
        │
        │ N

connector_resources
────────────────────────────────────────────────────────────
 PK  id              TEXT (UUID)
 FK  connector_id    TEXT → resource_connectors.id ON DELETE CASCADE
     resource_type   TEXT NOT NULL          ← "notion_database" | "notion_page" | "file" | "deck"
     external_id     TEXT NULL              ← 平台资源 ID（database_id / page_id）
     title           TEXT NOT NULL          ← 资源显示标题
     metadata        JSON NULL              ← 资源元信息（page_count, schema 等）
     sync_status     TEXT DEFAULT 'synced'  ← "syncing" | "synced" | "error"
     created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
────────────────────────────────────────────────────────────
 INDEX: (connector_id, resource_type)
 UNIQUE: (connector_id, resource_type, external_id)

        │ 1 (resource_type = "notion_database")
        │
        │ N

connector_resource_pages
────────────────────────────────────────────────────────────
 PK  id              TEXT (UUID)
 FK  resource_id     TEXT → connector_resources.id ON DELETE CASCADE
     page_id         TEXT NOT NULL          ← Notion Page UUID
     title           TEXT NOT NULL
     last_edited     DATETIME NULL
     properties_json JSON NULL              ← Row Page 属性值快照
     created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
────────────────────────────────────────────────────────────
 INDEX: (resource_id, last_edited DESC)

        │ 1 (resource_connectors)
        │
        │ N

connector_chat_threads
────────────────────────────────────────────────────────────
 PK  id              TEXT (UUID)
 FK  connector_id    TEXT → resource_connectors.id ON DELETE CASCADE
 FK  thread_id       TEXT → chat_thread.id         ← 复用现有 chat_thread
     created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
────────────────────────────────────────────────────────────
 INDEX: (connector_id, created_at DESC)
```

### 1.2 关系说明

```
users (1) ──→ (N) resource_connectors
                    │
                    ├── (1) ──→ (N) connector_resources
                    │                   │
                    │                   └── (1) ──→ (N) connector_resource_pages
                    │                                    (仅 notion_database 类型)
                    │
                    └── (1) ──→ (N) connector_chat_threads ──→ chat_thread
```

### 1.3 关键约束

| 约束 | 说明 |
|------|------|
| 连接器绑定单用户 | `resource_connectors.user_id` 不可共享 |
| 资源去重 | `(connector_id, resource_type, external_id)` UNIQUE |
| 级联删除 | 删除连接器 → 级联删除所有关联资源和页面索引 |
| chat_thread 复用 | 连接器内的对话复用已有的 `chat_thread` 模型，通过中间表关联 |

---

## 2. 设计决策记录

| 决策 | 选项 | 选择 | 理由 |
|------|------|------|------|
| 连接器与对话关系 | 内嵌 / 中间表 | 中间表 `connector_chat_threads` | 复用现有 `chat_thread` 模型，不侵入原有表结构 |
| 资源存储 | 平铺在连接器表 / 独立资源表 | 独立 `connector_resources` 表 | 支持多种资源类型，各类型可独立 CRUD |
| 页面索引 | JSON 字段 / 独立表 | 独立 `connector_resource_pages` 表 | Database 下可能有数百个 Row Page，JSON 字段查询性能差 |
| 文件上传 | 连接器内 / 全局文件系统 | 连接器内 + 关联全局文件系统 | 文件生命周期跟随连接器 |

---

## 3. 相关文档

- 前端 PRD：[`docs/prd/notion-session/resource-connector.md`](../../prd/notion-session/resource-connector.md)
- 交互方案设计：[`docs/design/notion-session/connector-interaction.md`](./connector-interaction.md)
- 总览设计：[`docs/design/notion-session/overview.md`](./overview.md)
