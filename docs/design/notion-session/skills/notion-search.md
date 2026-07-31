# Notion Search

> 通过 ntn api 搜索 Notion 工作空间中的内容。

## 使用方式

通过 Bash 执行 `ntn api` 命令，CLI 自动处理 Authorization 和 Notion-Version 请求头。

### 按关键词搜索

```bash
ntn api v1/search --data '{"query":"<关键词>","page_size":10}'
```

### 搜索所有 Data source

```bash
ntn api v1/search --data '{"filter":{"property":"object","value":"data_source"},"page_size":100}'
```

### 搜索所有 Page

```bash
ntn api v1/search --data '{"filter":{"property":"object","value":"page"},"page_size":100}'
```

### 排序搜索结果

```bash
ntn api v1/search --data '{"query":"<关键词>","sort":{"direction":"descending","timestamp":"last_edited_time"},"page_size":20}'
```

### 分页搜索

```bash
# 第一次请求
ntn api v1/search --data '{"query":"<关键词>","page_size":10}'

# 后续页面（使用上一次返回的 next_cursor）
ntn api v1/search --data '{"query":"<关键词>","page_size":10,"start_cursor":"<next_cursor>"}'
```

## 返回结果说明

| 字段 | 说明 |
|------|------|
| `results` | 搜索结果数组，每项包含 `object`（"page" 或 "data_source"）、`id`、`properties` 等 |
| `has_more` | 是否有更多结果 |
| `next_cursor` | 下一页游标，用于分页 |

## 使用场景

用户问到以下问题时，调用此 skill：

- "帮我在 Notion 里搜索 XXX"
- "查找 Notion 中关于 XXX 的页面"
- "我的 Notion 里有没有关于 XXX 的内容"
- "列出所有 Notion 数据库"

## 注意事项

- `ntn api` 自动添加 Authorization 和 Notion-Version 请求头，无需手动设置
- `NOTION_HOME` 环境变量已由工作空间配置
- 搜索范围限于连接器已授权的页面和数据库
- 搜索 API 仅支持标题匹配，不支持正文全文搜索
- 返回结果最大 `page_size` 为 100
- 如果需要查看页面完整内容，请结合 `notion-page-read` skill 使用
