# Notion Database Query 参考

> 查询指定 Notion Database 下的页面（Row Page）。

## 目录

1. [基本查询](#基本查询)
2. [筛选条件](#筛选条件)
3. [复合筛选](#复合筛选)
4. [排序](#排序)
5. [分页](#分页)
6. [获取 Schema](#获取-schema)
7. [属性筛选类型参考](#属性筛选类型参考)
8. [返回结果说明](#返回结果说明)

---

## 基本查询

```bash
ntn api v1/databases/<database_id>/query --data '{}'
```

## 筛选条件

### 按 Status 属性筛选（select 类型）

```bash
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "property": "Status",
    "select": {
      "equals": "In Progress"
    }
  }
}'
```

### 按日期筛选

```bash
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "property": "Due",
    "date": {
      "on_or_before": "2026-06-30"
    }
  }
}'
```

### 按标题包含关键词筛选

```bash
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "property": "Name",
    "title": {
      "contains": "重构"
    }
  }
}'
```

## 复合筛选

### AND 条件

```bash
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "and": [
      {"property": "Status", "select": {"equals": "In Progress"}},
      {"property": "Due", "date": {"on_or_before": "2026-06-30"}}
    ]
  }
}'
```

### OR 条件

```bash
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "or": [
      {"property": "Status", "select": {"equals": "In Progress"}},
      {"property": "Status", "select": {"equals": "Not Started"}}
    ]
  }
}'
```

## 排序

```bash
ntn api v1/databases/<database_id>/query --data '{
  "sorts": [
    {"property": "Due", "direction": "ascending"},
    {"timestamp": "last_edited_time", "direction": "descending"}
  ]
}'
```

## 分页

```bash
# 限制返回数量
ntn api v1/databases/<database_id>/query --data '{"page_size": 10}'

# 翻页（使用上一次返回的 next_cursor）
ntn api v1/databases/<database_id>/query --data '{"page_size": 10, "start_cursor": "<next_cursor>"}'
```

## 获取 Schema

查看 Database 的属性定义，了解可筛选的字段：

```bash
ntn api v1/databases/<database_id>
```

## 属性筛选类型参考

| 属性类型 | 筛选关键字 | 支持的条件 |
|---------|-----------|-----------|
| `title` | `title` | `equals`, `contains`, `starts_with`, `ends_with`, `is_empty`, `is_not_empty` |
| `rich_text` | `rich_text` | 同上 |
| `number` | `number` | `equals`, `greater_than`, `less_than`, `greater_than_or_equal_to`, `less_than_or_equal_to` |
| `select` | `select` | `equals`, `does_not_equal`, `is_empty`, `is_not_empty` |
| `multi_select` | `multi_select` | `contains`, `does_not_contain`, `is_empty`, `is_not_empty` |
| `date` | `date` | `equals`, `before`, `after`, `on_or_before`, `on_or_after`, `is_empty`, `is_not_empty` |
| `checkbox` | `checkbox` | `equals` (true/false) |
| `status` | `status` | `equals`, `does_not_equal` |

## 返回结果说明

### `/v1/databases/<database_id>/query` 返回

| 字段 | 说明 |
|------|------|
| `results` | Page 数组，每项包含 `id`、`properties`（属性值）、`created_time`、`last_edited_time` |
| `has_more` | 是否有更多结果 |
| `next_cursor` | 下一页游标 |

### `/v1/databases/<database_id>` 返回

| 字段 | 说明 |
|------|------|
| `id` | Database UUID |
| `title` | Database 标题 |
| `properties` | 属性 Schema 定义（字段名 → 类型配置） |

## 工作流建议

1. **先查看 `.notion/connector.json` 获取已同步的 Database ID 和标题**
2. **用 `/v1/databases/<database_id>` 获取属性 Schema，了解可筛选的字段**
3. **根据用户需求构建 filter 条件查询**
4. **如需查看某条记录的完整内容，结合 `references/notion-page-read.md` 使用**

## 使用限制

- 单次查询最大 `page_size` 为 100，超过需分页
- filter 中的 `property` 值必须与 Database Schema 中的属性名完全匹配（区分大小写）
- Database ID 可从 `.notion/connector.json` 或 `.notion/databases.json` 中获取
