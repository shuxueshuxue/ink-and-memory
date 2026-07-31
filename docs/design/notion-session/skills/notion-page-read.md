# Notion Page Read

> 读取指定 Notion 页面的完整内容。

## 使用方式

通过 Bash 执行 `ntn api` 命令，CLI 自动处理 Authorization 和 Notion-Version 请求头。

### 获取页面元信息（属性）

```bash
ntn api v1/pages/<page_id>
```

### 获取页面内容（Markdown 格式）

```bash
ntn api v1/pages/<page_id>/markdown
```

### 获取页面内容（Block 结构）

```bash
ntn api v1/blocks/<page_id>/children
```

### 获取嵌套 Block 的子内容

```bash
ntn api v1/blocks/<block_id>/children
```

### 获取页面指定属性

```bash
ntn api v1/pages/<page_id>/properties/<property_id>
```

## 推荐用法

### 快速阅读页面

优先使用 Markdown 端点获取可读内容：

```bash
# 1. 获取 Markdown 格式的页面内容（最简洁）
ntn api v1/pages/<page_id>/markdown
```

### 获取页面结构化属性

```bash
# 2. 获取页面属性（标题、状态、日期等）
ntn api v1/pages/<page_id>
```

### 获取完整 Block 树

当需要精确控制或 Markdown 端点不满足时：

```bash
# 3. 获取一级子 Block
ntn api v1/blocks/<page_id>/children

# 4. 递归获取嵌套内容（对 has_children=true 的 block）
ntn api v1/blocks/<child_block_id>/children
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

### `/v1/pages/<page_id>/markdown` 返回

| 字段 | 说明 |
|------|------|
| `markdown` | 页面内容的 Markdown 文本 |

### `/v1/blocks/<page_id>/children` 返回

| 字段 | 说明 |
|------|------|
| `results` | Block 数组，每项包含 `type`、`id`、对应类型的内容字段 |
| `has_more` | 是否有更多 Block |
| `next_cursor` | 分页游标 |

## 使用场景

用户问到以下问题时，调用此 skill：

- "帮我看看这个 Notion 页面的内容"
- "读取 Notion 里的 XXX 文档"
- "把这个页面的内容给我看看"
- "获取页面 <page_id> 的详细内容"

## 工作流建议

1. **先用 `.notion/index.json` 或 `notion-search` 定位页面 ID**
2. **用 `/v1/pages/<page_id>/markdown` 快速获取可读内容**
3. **如需属性信息，再用 `/v1/pages/<page_id>` 获取元数据**
4. **如需精细 Block 操作，用 `/v1/blocks/<page_id>/children`**

## 注意事项

- `ntn api` 自动添加 Authorization 和 Notion-Version 请求头，无需手动设置
- `NOTION_HOME` 环境变量已由工作空间配置
- Block children 接口有分页限制（默认 100 条），超过需使用 `start_cursor` 分页
- 嵌套 Block（如 toggle、callout）需要递归获取子 Block
- Markdown 端点是最快获取可读内容的方式，优先使用
- 页面 ID 可从 `.notion/index.json`、`.notion/databases/<db_id>.json` 或搜索结果中获取
