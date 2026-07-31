# Notion Search 参考

> 通过 ntn api 搜索 Notion 工作空间中的内容。

## 目录

1. [按关键词搜索](#按关键词搜索)
2. [按类型筛选](#按类型筛选)
3. [排序](#排序)
4. [分页](#分页)
5. [返回结果说明](#返回结果说明)

---

## 按关键词搜索

```bash
ntn api v1/search --data '{"query":"<关键词>","page_size":10}'
```

## 按类型筛选

### 搜索所有 Database

```bash
ntn api v1/search --data '{"filter":{"property":"object","value":"database"},"page_size":100}'
```

### 搜索所有 Page

```bash
ntn api v1/search --data '{"filter":{"property":"object","value":"page"},"page_size":100}'
```

## 排序

```bash
ntn api v1/search --data '{"query":"<关键词>","sort":{"direction":"descending","timestamp":"last_edited_time"},"page_size":20}'
```

## 分页

```bash
# 第一次请求
ntn api v1/search --data '{"query":"<关键词>","page_size":10}'

# 后续页面（使用上一次返回的 next_cursor）
ntn api v1/search --data '{"query":"<关键词>","page_size":10,"start_cursor":"<next_cursor>"}'
```

## 返回结果说明

| 字段 | 说明 |
|------|------|
| `results` | 搜索结果数组，每项包含 `object`（"page" 或 "database"）、`id`、`properties` 等 |
| `has_more` | 是否有更多结果 |
| `next_cursor` | 下一页游标，用于分页 |

## 使用限制

- 搜索范围限于连接器已授权的页面和数据库
- 搜索 API 仅支持标题匹配，不支持正文全文搜索
- 返回结果最大 `page_size` 为 100
- 如需查看页面完整内容，结合 `references/notion-page-read.md` 使用
