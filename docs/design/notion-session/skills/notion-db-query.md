# Notion Database Query

> 查询指定 Notion Database 下的页面（Row Page）。

## 使用方式

通过 Bash 执行 `ntn api` 命令，CLI 自动处理 Authorization 和 Notion-Version 请求头。

### 查询 Database 下所有页面

```bash
ntn api v1/databases/<database_id>/query --data '{}'
```

### 带筛选条件查询

```bash
# 按 Status 属性筛选（select 类型）
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "property": "Status",
    "select": {
      "equals": "In Progress"
    }
  }
}'

# 按日期筛选
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "property": "Due",
    "date": {
      "on_or_before": "2026-06-30"
    }
  }
}'

# 按标题包含关键词筛选
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "property": "Name",
    "title": {
      "contains": "重构"
    }
  }
}'
```

### 复合筛选（AND / OR）

```bash
# AND 条件
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "and": [
      {"property": "Status", "select": {"equals": "In Progress"}},
      {"property": "Due", "date": {"on_or_before": "2026-06-30"}}
    ]
  }
}'

# OR 条件
ntn api v1/databases/<database_id>/query --data '{
  "filter": {
    "or": [
      {"property": "Status", "select": {"equals": "In Progress"}},
      {"property": "Status", "select": {"equals": "Not Started"}}
    ]
  }
}'
```

### 排序查询结果

```bash
ntn api v1/databases/<database_id>/query --data '{
  "sorts": [
    {"property": "Due", "direction": "ascending"},
    {"timestamp": "last_edited_time", "direction": "descending"}
  ]
}'
```

### 分页查询

```bash
# 限制返回数量
ntn api v1/databases/<database_id>/query --data '{"page_size": 10}'

# 翻页（使用上一次返回的 next_cursor）
ntn api v1/databases/<database_id>/query --data '{"page_size": 10, "start_cursor": "<next_cursor>"}'
```

### 获取 Database Schema（属性定义）

```bash
ntn api v1/databases/<database_id>
```

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

## 常用属性筛选类型

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

## 使用场景

用户问到以下问题时，调用此 skill：

- "查看 Notion 代办清单里的未完成项"
- "帮我筛选数据库中状态为进行中的任务"
- "Notion 里这个月截止的任务有哪些"
- "查询阅读笔记数据库中的所有条目"
- "获取 Database 的属性结构"

## 工作流建议

1. **先查看 `.notion/databases.json` 或 `.notion/connector.json` 获取已同步的 Database ID 和标题**
2. **用 `/v1/databases/<database_id>` 获取属性 Schema，了解可筛选的字段**
3. **根据用户需求构建 filter 条件查询**
4. **如需查看某条记录的完整内容，结合 `notion-page-read` skill 使用**

## 注意事项

- `ntn api` 自动添加 Authorization 和 Notion-Version 请求头，无需手动设置
- `NOTION_HOME` 环境变量已由工作空间配置
- 单次查询最大 `page_size` 为 100，超过需分页
- filter 中的 `property` 值必须与 Database Schema 中的属性名完全匹配（区分大小写）
- Database ID 可从 `.notion/connector.json` 或 `.notion/databases.json` 中获取
- 查询结果中的 `properties` 包含该条记录的所有属性值
