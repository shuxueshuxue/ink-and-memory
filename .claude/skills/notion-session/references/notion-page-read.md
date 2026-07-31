# Notion Page Read 参考

> 读取指定 Notion 页面的完整内容。

## 目录

1. [快速阅读（推荐）](#快速阅读推荐)
2. [获取页面元信息](#获取页面元信息)
3. [获取 Block 结构](#获取-block-结构)
4. [获取指定属性](#获取指定属性)
5. [返回结果说明](#返回结果说明)
6. [工作流建议](#工作流建议)

---

## 快速阅读（推荐）

优先使用 Markdown 端点，最简洁的可读内容：

```bash
ntn api v1/pages/<page_id>/markdown
```

返回：`{"markdown": "页面内容的 Markdown 文本"}`

## 获取页面元信息

获取页面属性（标题、状态、日期等）：

```bash
ntn api v1/pages/<page_id>
```

## 获取 Block 结构

当需要精确控制或 Markdown 端点不满足时：

```bash
# 获取一级子 Block
ntn api v1/blocks/<page_id>/children

# 递归获取嵌套内容（对 has_children=true 的 block）
ntn api v1/blocks/<child_block_id>/children
```

## 获取指定属性

```bash
ntn api v1/pages/<page_id>/properties/<property_id>
```

## 返回结果说明

### `/v1/pages/<page_id>` 返回

| 字段 | 说明 |
|------|------|
| `id` | 页面 UUID |
| `parent` | 父对象（database 或 page） |
| `properties` | 页面属性键值对（标题、状态、日期等） |
| `created_time` | 创建时间 |
| `last_edited_time` | 最后编辑时间 |

### `/v1/blocks/<page_id>/children` 返回

| 字段 | 说明 |
|------|------|
| `results` | Block 数组，每项包含 `type`、`id`、对应类型的内容字段 |
| `has_more` | 是否有更多 Block |
| `next_cursor` | 分页游标 |

## 工作流建议

1. **先用 `.notion/index.json` 或搜索定位页面 ID**
2. **用 `/v1/pages/<page_id>/markdown` 快速获取可读内容**
3. **如需属性信息，再用 `/v1/pages/<page_id>` 获取元数据**
4. **如需精细 Block 操作，用 `/v1/blocks/<page_id>/children`**

## 使用限制

- Block children 接口有分页限制（默认 100 条），超过需使用 `start_cursor` 分页
- 嵌套 Block（如 toggle、callout）需要递归获取子 Block
- 页面 ID 可从 `.notion/index.json`、`.notion/databases/<db_id>.json` 或搜索结果中获取
