---
name: notion-session
description: Notion 工作空间数据助手 — 搜索内容、读取页面、查询数据库，通过 ntn CLI 零配置访问已连接的 Notion 资源。当用户提到 Notion、想查看代办清单、查询数据库内容、搜索 Notion 页面、读取 Notion 文档时，务必使用此 skill。即使用户没有明确说 "Notion"，只要涉及 .notion/ 目录下的数据或 ntn 命令，也应触发此 skill。
tools: ["Bash"]
---

# Notion 工作空间数据助手

## 概述

通过 `ntn api` CLI 访问用户已连接的 Notion 资源连接器数据。CLI 自动处理 Authorization 和 Notion-Version 请求头，无需手动配置。

## 前置条件

- 工作空间已创建 Notion 资源连接器（`.notion/` 目录存在）
- `NOTION_HOME` 环境变量已配置
- `ntn` CLI 已安装且已认证

## 工作流

### 1. 了解连接器状态

进入对话时，先检查 `.notion/connector.json` 获取已连接的 Database 和 Page 信息：

```bash
cat .notion/connector.json
```

### 2. 浏览已同步数据

```bash
# 查看所有已同步页面索引
cat .notion/index.json

# 查看某个 Database 的页面清单
cat .notion/databases/<database_id>.json
```

### 3. 按需调用 Notion API

根据用户需求选择对应操作：

| 需求 | 操作 | 参考文档 |
|------|------|---------|
| 搜索内容 | `ntn api v1/search` | `references/notion-search.md` |
| 读取页面 | `ntn api v1/pages/<id>/markdown` | `references/notion-page-read.md` |
| 查询数据库 | `ntn api v1/databases/<id>/query` | `references/notion-db-query.md` |

## 核心命令速查

### 搜索

```bash
ntn api v1/search --data '{"query":"<关键词>","page_size":10}'
```

### 读取页面（Markdown 格式，推荐）

```bash
ntn api v1/pages/<page_id>/markdown
```

### 查询数据库

```bash
ntn api v1/databases/<database_id>/query --data '{}'
```

## 参考文档

当需要高级用法（筛选、排序、分页等）时，阅读对应参考文档：

- `references/notion-search.md` — 搜索 API 完整用法（关键词搜索、按类型筛选、排序、分页）
- `references/notion-page-read.md` — 页面读取完整用法（元信息、Markdown、Block 结构）
- `references/notion-db-query.md` — 数据库查询完整用法（筛选条件、复合筛选、排序、属性类型参考）

## 注意事项

- `ntn api` 自动添加 Auth 和 Version 头，无需手动设置
- 搜索 API 仅支持标题匹配，不支持正文全文搜索
- 单次查询最大 `page_size` 为 100，超过需分页
- 页面 ID 可从 `.notion/index.json`、`.notion/databases/<db_id>.json` 或搜索结果中获取
- filter 中的 `property` 值必须与 Database Schema 中的属性名完全匹配（区分大小写）
