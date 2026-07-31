> [Input] `backend/reflections_config.py`, `backend/routers/reflections.py`,
>         `frontend/src/api/voiceApi.ts`, `frontend/src/components/AnalysisView.tsx`,
>         `docs/design/memory/memory-workspace-design.md`
> [Output] Reflections 页面分区记忆系统工作空间配置的完整 PRD：分区定义、配置文件内容、初始化流程、Agent 执行协议、输出格式、前端交互设计。
> [Pos] reflections-analysis-prd node in `docs/design/memory`
> [Sync] 2026-06-06: 初版 PRD，补全三分区配置内容、sessions_context 格式、结果获取方式、工作空间结构、扩展性设计。
> [Sync] 2026-06-07: 更新 §11 前端 AnalysisView 设计——恢复暖纸张主题（Georgia + CSS 设计 tokens），新增 PaperStack 报告视图，保留一键「Generate Reflections」按钮，更新卡片字段（ReflectionResult 统一类型，confidence 替代 strength/frequency），补充历史报告按日期合并策略。
> [Sync] 2026-06-26: 更新 §11 前端业务交互——一键 Generate New Analysis 默认不弹窗，按钮下方显示后端任务进度且执行中禁止重复点击；如果当天已点击过或已有当天报告，再次点击必须弹窗确认是否重新分析并选择可分析日记；保留分区独立分析；分析完成后使用 ReflectionBlogPage wrapper 展示结果；ReflectionBlogPage 保持固定分栏 + 详情区 + 底部播放器布局，仅优化视觉与交互反馈；echoes / traits / patterns 输出均遵循当前前端语言。

# Reflections 页面分区记忆系统工作空间配置 PRD

---

## 1. 产品定位

Reflections 页面是 Ink & Memory 的自我认知功能入口。它通过分析用户的写作/日记记录，提供三类结构化洞察：

- **回响 Echoes**（Recurring Themes）：跨会话反复出现的情感主题与思想回响
- **性格特质 Traits**（Character Traits）：从行为与语言中推断的稳定性格倾向
- **行为模式 Patterns**（Behavioral Patterns）：写作节奏、生活规律与应对方式的规律

**当前改造目标**：用 Memory Workspace（程序性记忆工作空间）驱动每个分区的分析流程。  
每个分区拥有独立的工作空间配置文件集合，Agent 读取这些文件后按分区规则执行分析，输出结构化结果（含关联笔记 ID 与置信度）。

---

## 2. 三个分区定义

| 分区 Key | EN 显示名 | ZH 显示名 | 分析目标 | 信号侧重 |
|---|---|---|---|---|
| `echoes` | Recurring Themes | 回响 | 发现跨会话反复出现的情感主题与思想回响 | 情感共鸣、意象重复、未解张力 |
| `traits` | Character Traits | 性格特质 | 从行为与语言中推断稳定的性格倾向 | 反应方式、决策模式、自我语气 |
| `patterns` | Behavioral Patterns | 行为模式 | 识别写作节奏、生活规律与应对方式 | 时间规律、触发条件、回避行为 |

---

## 3. 分区记忆工作空间结构

每次分析在 `{AGENT_CWD}/{thread_id}/` 下创建以下目录：

```text
{thread_id}/
└── memory/
    ├── WORKFLOW.md                   ← 分区分析工作流决策树
    ├── MEMORY_QUERY_PROMPT.md        ← 该分区的信号识别规则
    ├── MEMORY_Distiller_PROMPT.md    ← 从信号到结构化洞察的提取规则
    ├── MEMORY_ANSWER_PROMPT.md       ← 输出格式规范
    ├── DEFAULT_UPDATE_MEMORY_PROMPT.md ← 状态更新规则
    └── procedural/
        └── analysis_state.json       ← 分析状态（section, completed, results_count）
```

五个 Markdown 文件由 `reflections_config.py` 中对应分区的 `prompt_files` 字段提供。  
每次分析创建新 thread（一次性会话），分析完成后工作空间保留（供调试），不主动删除。

---

## 4. 分区配置文件详细内容

配置存储于 `backend/reflections_config.py`，数据结构为：

```python
REFLECTIONS_SECTION_CONFIGS: dict[str, dict] = {
    "echoes": {
        "section": "echoes",
        "display_name": "Recurring Themes",
        "display_name_zh": "回响",
        "workspace_type": "procedural",
        "enabled": True,
        "prompt_files": {
            "WORKFLOW.md": ...,
            "MEMORY_QUERY_PROMPT.md": ...,
            "MEMORY_Distiller_PROMPT.md": ...,
            "MEMORY_ANSWER_PROMPT.md": ...,
            "DEFAULT_UPDATE_MEMORY_PROMPT.md": ...,
        }
    },
    "traits": { ... },
    "patterns": { ... },
}
```

### 4.1 共享输出契约（三分区通用，追加到 WORKFLOW.md 末尾）

所有分区的 WORKFLOW.md 末尾附加以下共享输出契约：

```
## Output Contract

Respond with a single JSON array only. No preamble, no explanation, no markdown fences.
Each element represents one discovered insight:

[
  {
    "title": "Concise name (3–6 words)",
    "description": "2–4 sentences that honestly capture what was found",
    "related_session_ids": ["session-id-1", "session-id-2"],
    "evidence": "A short direct quote or paraphrase from the notes",
    "confidence": "high | medium | low"
  }
]

Rules:
- Return 3–6 elements. Quality over volume.
- If the evidence is genuinely thin, set confidence to "low" and say so.
- Do not fabricate sessions that were not in the provided notes.
- Some real patterns resist clean articulation — capture them anyway with
  honest uncertainty rather than forcing false precision.
```

### 4.2 回响（echoes）分区配置

#### WORKFLOW.md

```markdown
# Reflections — Recurring Themes (Echoes) Workflow

Memory workspace type: procedural (Reflections analysis).

You are performing a Recurring Themes analysis for the Ink & Memory Reflections page.
You will receive a block of journal/writing notes with their session IDs and dates.

## Analysis Workflow

1. Read the session notes carefully — read for resonance, not just keywords.
2. Read MEMORY_QUERY_PROMPT.md to understand what constitutes an "echo".
3. Surface recurring emotional themes, thought patterns, or preoccupations
   that appear across multiple sessions.
4. Read MEMORY_Distiller_PROMPT.md to extract each echo with care.
5. Read MEMORY_ANSWER_PROMPT.md for the required output format.
6. Output the result JSON and nothing else.

## Tacit Boundary

Recurring Themes are often felt before they can be named. A pattern that
appears only twice may matter more than one appearing ten times if the
emotional charge is significant. Trust that judgment rather than counting.

[+ Output Contract appended]
```

#### MEMORY_QUERY_PROMPT.md

```markdown
# Memory Query — Recurring Themes

Scan the notes for signals that qualify as an "echo" — a theme, feeling,
or preoccupation that returns across different sessions:

1. Emotional resonance — the same worry, longing, or joy resurfacing.
2. Recurring metaphors or images — the writer keeps reaching for the same imagery.
3. Unresolved tensions — questions or conflicts the writer returns to without closure.
4. Seasonal or circumstantial loops — themes tied to recurring life contexts.
5. Quiet undercurrents — things rarely stated directly but always present.

Prefer patterns that span at least two sessions. A single intense mention
may still qualify if the emotional weight suggests it will recur.
```

#### MEMORY_Distiller_PROMPT.md

```markdown
# Memory Distiller — Recurring Themes

Extract each echo with these fields:
- Title: the shortest phrase that names the theme honestly.
- Description: 2–4 sentences. Some themes are easier to point at than define — that is acceptable.
- Related sessions: session IDs where this echo appears.
- Evidence: the clearest quote or paraphrase anchoring the pattern.
- Confidence: high / medium / low.

Rules:
- Capture what is there, not what would make a tidy story.
- If two echoes feel related, name the relationship rather than merging them.
- Resist forcing an echo into a category. Name it on its own terms.
```

#### MEMORY_ANSWER_PROMPT.md

```markdown
# Answer Format — Recurring Themes

Output the JSON array from the Output Contract.
Do not add interpretation beyond what the notes support.
Do not soften genuine recurring pain into something neutral.
Do not exaggerate a faint pattern into a defining theme.
The honesty of the analysis is more valuable than its polish.
```

#### DEFAULT_UPDATE_MEMORY_PROMPT.md

```markdown
# Update Rules — Recurring Themes Analysis

This is a single-turn analysis session. Choose NO_CHANGE for procedural state.
Only ADD an analysis result entry to the output JSON.
Do not DELETE or UPDATE existing entries in this session.
```

---

### 4.3 性格特质（traits）分区配置

#### WORKFLOW.md

```markdown
# Reflections — Character Traits Workflow

Memory workspace type: procedural (Reflections analysis).

## Analysis Workflow

1. Read the session notes — look for how the person acts, not only what they say.
2. Read MEMORY_QUERY_PROMPT.md for trait identification signals.
3. Identify stable dispositions revealed through choices, reactions, and language.
4. Read MEMORY_Distiller_PROMPT.md to extract each trait with evidence.
5. Read MEMORY_ANSWER_PROMPT.md for the required output format.
6. Output the result JSON and nothing else.

## Tacit Boundary

Character traits are inferred, not declared. The writer rarely says "I am curious" —
they show curiosity through what they notice, what they pursue, what they regret skipping.
Read between the lines, and remain honest about the limits of what can be known
from a finite set of notes.

[+ Output Contract appended]
```

#### MEMORY_QUERY_PROMPT.md

```markdown
# Memory Query — Character Traits

Look for stable dispositions — how the person habitually responds to situations:

1. Curiosity vs. comfort — does the writer seek novelty or depth in familiar things?
2. Openness vs. guardedness — how much do they share, hedge, or hold back?
3. Persistence vs. flexibility — how do they handle obstacles or changed plans?
4. Self-criticism vs. self-compassion — what is the default tone toward themselves?
5. Relational orientation — do they write toward others or primarily inward?
6. Response to uncertainty — how do they carry things they cannot resolve?

Signal strength increases when the same disposition appears across
different contexts (work, relationships, creative practice, body).
```

#### MEMORY_Distiller_PROMPT.md

```markdown
# Memory Distiller — Character Traits

For each trait:
- Title: a plain-language trait name (not a clinical label).
- Description: describe the trait as it appears in this person's writing.
  Use their language and situations as grounding.
- Related sessions: session IDs that show the trait most clearly.
- Evidence: a quote or paraphrase that demonstrates the trait in action.
- Confidence: high / medium / low.

Rules:
- A trait must be demonstrated, not just mentioned by the writer.
- Traits that conflict with each other are usually more accurate than a single coherent portrait. Name both.
- Low-confidence traits are valuable when named honestly.
```

---

### 4.4 行为模式（patterns）分区配置

#### WORKFLOW.md

```markdown
# Reflections — Behavioral Patterns Workflow

Memory workspace type: procedural (Reflections analysis).

## Analysis Workflow

1. Read the session notes — attend to what the person does, at what intervals, under what conditions.
2. Read MEMORY_QUERY_PROMPT.md for behavioral pattern signals.
3. Surface regularities in behaviour, writing rhythm, stress response, and creative cycles.
4. Read MEMORY_Distiller_PROMPT.md to extract each pattern with timing and triggers.
5. Read MEMORY_ANSWER_PROMPT.md for the required output format.
6. Output the result JSON and nothing else.

## Tacit Boundary

Behavioral patterns often follow rhythms the person has not consciously named.
The analysis should reveal structure that the writer can recognise as true
rather than impose structure to make the data tidier. If a pattern is genuinely
irregular, say so rather than finding a false regularity.

[+ Output Contract appended]
```

#### MEMORY_QUERY_PROMPT.md

```markdown
# Memory Query — Behavioral Patterns

Look for temporal and conditional regularities in behaviour:

1. Writing rhythm — when does the writer write? Under what conditions?
2. Avoidance patterns — topics or tasks repeatedly deferred.
3. Stress responses — how does the writer's output change under pressure?
4. Creative cycles — periods of generativity followed by silence, or vice versa.
5. Relational patterns — recurring dynamics in how the writer describes interactions.
6. Completion loops — does the writer tend to finish, abandon, or transform projects?

Note frequency and context, not just presence. A pattern that appears every
two months is still a pattern.
```

---

## 5. sessions_context 格式

后端在调用 claude-agent 前，将本次允许分析的会话格式化为轻量 `sessions_context`。为避免全部笔记正文塞进 `POST /api/claude-agent` SSE 请求导致上下文过长，`sessions_context` **只包含真实存在的 session ID、日期、标题和 labels，不包含正文 / first_line / excerpt / text**。Agent 必须按需通过 `mcp__user__get_sessions_range` 根据日期、labels 和返回的 `sessionId` 获取笔记内容，再进行分析。

```
<sessions_context>
Full note bodies are intentionally omitted to keep this request small.
Use only these real session IDs in related_session_ids.
Before writing final insights, fetch needed note content by session ID with mcp__user__get_sessions_range using the listed date and labels, then match the returned sessionId.
{"sessionId":"session-id-1","date":"2026-01-15","title":"标题","labels":["情绪","工作"]}
{"sessionId":"session-id-2","date":"2026-01-20","title":"今天感觉有些疲惫","labels":["身体","日常"]}
{"sessionId":"session-id-3","date":"2026-02-03","title":"新项目启动了","labels":["工作","创作"]}
</sessions_context>
```

**格式规则**：
- 每条 session 使用一行 JSON，`sessionId` 必须来自本次 DB 查询结果，Agent 只能引用这些真实 ID 到 `related_session_ids`。
- `date` 为 `YYYY-MM-DD`，用于调用 `mcp__user__get_sessions_range(start_date=date, end_date=date, labels=...)` 缩小检索范围。
- `title` 截取前 120 字符，只作为定位线索，不替代正文证据。
- `labels` 为用户标记的分类标签（可为空），用于按需检索正文。
- 禁止在 `sessions_context` 和 `memory/sessions_context.json` 中写入正文、excerpt、first_line 或 full text。

完整用户消息结构：

```
<sessions_context>
{"sessionId":"session-id-1","date":"2026-01-15","title":"...","labels":["..."]}
{"sessionId":"session-id-2","date":"2026-01-20","title":"...","labels":[]}
</sessions_context>

Your memory workspace contains procedural analysis guidance.
Start by reading memory/WORKFLOW.md to understand the analysis procedure.
The sessions_context lists only allowed session IDs and labels, not full note bodies. Fetch the note content you need by session ID before final analysis.
Then output ONLY a JSON array — no other text.
```

---

## 6. 分析流程（完整时序）

```
用户点击某分区的「分析」按钮
        │
        ▼
Step 1. POST /api/claude-agent/threads
        → 获得 thread_id（一次性会话，分析完成后不再复用）
        │
        ▼
Step 2. POST /api/reflections/memory-init
        body: { threadId, section: "echoes" | "traits" | "patterns" }
        → 后端从 reflections_config 读取分区 5 个文件
        → 写入 {AGENT_CWD}/{thread_id}/memory/
        → 创建 memory/procedural/analysis_state.json
        → 返回 { initialised: true, section, memoryPath }
        ★ 非致命：初始化失败时 Agent 无 memory_context，仍可继续分析
        │
        ▼
Step 3. POST /api/claude-agent (SSE)
        ┌── 使用 Step 2 返回的 memoryPath 和 section 构造 system_prompt ──┐
        │  "You are performing a "{section_display}" analysis for         │
        │   the Ink & Memory Reflections page.                            │
        │   The procedural memory workspace has been initialised at:      │
        │   {memoryPath}                                                  │
        │   Follow memory/WORKFLOW.md for the analysis procedure.         │
        │   Output ONLY a JSON array as your final response."             │
        └─────────────────────────────────────────────────────────────────┘
        body:
          id: thread_id
          resume: false
          system_prompt: 上方构造的分区标识 + memoryPath 字符串
                         ↳ 引擎注入为 <voice_context>，在用户消息前给 Agent 定向
          message.parts[0].text: <sessions_context> + 读 WORKFLOW.md 指令
          tool_choice: "auto"      ← 允许 Agent 用文件读取工具
          max_turns: 1000             ← 允许多轮（读文件 → 分析 → 输出）
        ★ memoryPath 来自 Step 2 响应；若 Step 2 失败则 system_prompt 注明
          "No memory workspace was initialised"，Agent 使用内嵌指令继续。
        │
        ▼
Step 4. claude-agent 引擎执行（多轮，由 WORKFLOW.md 驱动）
        a. <memory_context> 注入 → Agent 知道 memory/ 路径
        b. Agent 读取 memory/WORKFLOW.md（工具调用）
        c. Agent 读取 memory/MEMORY_QUERY_PROMPT.md
        d. Agent 读取 memory/MEMORY_Distiller_PROMPT.md
        e. Agent 输出结构化 JSON array
        │
        ▼
Step 5. 前端 drain SSE stream 直到 finish 事件
        → text-delta 仅转发给 onDelta（UI 进度展示），不累积为解析来源
        → 原因：SSE 混合输出 reasoning（思维链）和 text，直接拼接会污染 JSON
        │
        ▼
Step 6. GET /api/claude-agent/threads/{thread_id}/messages
        → 取最后一条 assistant 消息
        → 过滤 parts：只保留 type="text"，跳过 type="reasoning"
        → 拼接得到干净的 JSON 字符串
        │
        ▼
Step 7. 前端解析 JSON → ReflectionResult[]
        → extractReflectionResults(text)：剥离 markdown fence，定位 [...] 区间
        │
        ▼
Step 8. POST /api/reports
        body: { report_type: "reflections_echoes", report_data: results }
        │
        ▼
Step 9. AnalysisView 对应分区展示多个卡片
        每张卡片：title / description / confidence 颜色点 / 关联笔记数量
        点击卡片 → 关联笔记视图（related_session_ids 精确匹配 + 关键词兜底）
```

---

## 7. 前端配置修改设计

### 7.1 功能定位

每个分区的 memory workspace 配置文件（WORKFLOW.md 等 5 个文件）默认来自 `reflections_config.py`（静态代码）。  
用户可以在 Reflections 页面的配置面板中修改任意文件的内容，修改后保存到数据库，下次分析时优先使用用户配置。

### 7.2 数据存储

新增数据库表：

```sql
CREATE TABLE reflections_section_configs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  section TEXT NOT NULL CHECK(section IN ('echoes', 'traits', 'patterns')),
  prompt_files TEXT NOT NULL DEFAULT '{}',  -- JSON: { "WORKFLOW.md": "...", ... }
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, section),
  FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
```

**有效配置优先级**（memory-init 时合并）：

```
用户自定义（DB）  覆盖  静态默认（reflections_config.py）
```

支持部分覆盖——用户只需修改关心的文件，其余文件仍使用静态默认。

### 7.3 API 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/reflections/config/{section}` | 读取有效配置（用户自定义 merge 静态默认）|
| `PUT` | `/api/reflections/config/{section}` | 保存用户自定义 prompt_files（可部分） |
| `DELETE` | `/api/reflections/config/{section}` | 重置为静态默认（删除 DB 行） |

`GET` 响应结构：

```json
{
  "section": "echoes",
  "display_name": "Recurring Themes",
  "display_name_zh": "回响",
  "usedCustomConfig": true,
  "prompt_files": {
    "WORKFLOW.md": "用户修改后的内容...",
    "MEMORY_QUERY_PROMPT.md": "静态默认内容...",
    "MEMORY_Distiller_PROMPT.md": "...",
    "MEMORY_ANSWER_PROMPT.md": "...",
    "DEFAULT_UPDATE_MEMORY_PROMPT.md": "..."
  }
}
```

`PUT` 请求结构（支持只传部分文件）：

```json
{
  "prompt_files": {
    "WORKFLOW.md": "用户修改后的 WORKFLOW 内容..."
  }
}
```

### 7.4 生效时机

配置修改后，下次点击「分析」按钮时：

1. `POST /api/reflections/memory-init` 调用 `_effective_prompt_files(user_id, section)`
2. 该函数先查 DB 用户配置，再 merge 静态默认
3. 写入 workspace memory/ 目录
4. Agent 读取写入后的文件执行分析

**`memory-init` 响应新增字段** `usedCustomConfig: boolean`，前端可据此显示配置状态标记。

### 7.5 前端配置 UI 设计（AnalysisView）

每个分区 Section 组件支持展开配置面板：

```
[回响 Recurring Themes]                  [分析] [⚙ 配置]
─────────────────────────────────────────────────────────
▼ 配置面板（点击 ⚙ 展开）
  文件: [WORKFLOW.md ▾]
  ┌────────────────────────────────────────────────┐
  │ # Reflections — Recurring Themes (Echoes) ...  │
  │ ...                                            │
  └────────────────────────────────────────────────┘
  [保存修改]  [重置为默认]
  ★ 已使用自定义配置（usedCustomConfig=true 时显示）
```

前端调用链：
- 打开面板时 → `getReflectionsSectionConfig(section)` 加载当前有效配置
- 保存时 → `saveReflectionsSectionConfig(section, editedFiles)`
- 重置时 → `resetReflectionsSectionConfig(section)`

### 7.6 文件名白名单

只有以下 5 个文件名被接受，未知文件名在路由层静默丢弃：

```
WORKFLOW.md
MEMORY_QUERY_PROMPT.md
MEMORY_Distiller_PROMPT.md
MEMORY_ANSWER_PROMPT.md
DEFAULT_UPDATE_MEMORY_PROMPT.md
```

---

## 8. Agent 执行协议

### 7.1 工具权限

| 参数 | 值 | 说明 |
|---|---|---|
| `tool_choice` | `"auto"` | 允许 Agent 使用文件读取工具（Read）读取 WORKFLOW.md 等文件 |
| `max_turns` | `1000` | 避免按需检索笔记和多轮读取 memory 文件时被旧的 5 轮限制截断 |
| `resume` | `false` | 一次性分析，不恢复历史对话 |

### 7.2 memory_context 注入

当 `{AGENT_CWD}/{thread_id}/memory/` 目录存在时，`context_builder.py` 的 `build_user_message()` 自动注入：

```xml
<memory_context>
Memory workspace (type: procedural only): /path/to/thread_id/memory
This is a procedural memory workspace, not a short-term chat cache or long-term summary store.

Memory prompt files (read for instructions):
  memory/WORKFLOW.md  - available
  memory/MEMORY_QUERY_PROMPT.md  - available
  memory/MEMORY_Distiller_PROMPT.md  - available
  memory/MEMORY_ANSWER_PROMPT.md  - available
  memory/DEFAULT_UPDATE_MEMORY_PROMPT.md  - available

Procedural state files: analysis_state.json
  Located in memory/procedural/  (read only when relevant)
</memory_context>
```

引擎系统提示不嵌入记忆操作指令；分区规则完全由 WORKFLOW.md 提供。

### 7.3 结果获取：为何使用 messages API

SSE 流包含两种事件类型的 delta：

| 事件类型 | 内容 | 用于解析 |
|---|---|---|
| `reasoning-delta` | Agent 的思维链（thinking） | 不能用 |
| `text-delta` | Agent 的最终文字输出 | 应该用 |

直接拼接 `text-delta` 可能混入 reasoning 内容（两者交错输出）。  
正确做法：drain SSE 直到 `finish` → 调用 messages API → 取 `parts[type="text"]`。

messages API 响应结构：

```json
{
  "messages": [
    {
      "role": "assistant",
      "parts": [
        { "type": "reasoning", "text": "思维链内容（跳过）" },
        { "type": "text",      "text": "[ { \"title\": ... } ]" }
      ]
    }
  ]
}
```

---

## 8. 输出格式 Contract

Agent 输出纯 JSON array，无 markdown 包装：

```json
[
  {
    "title": "3-6 词的简洁名称",
    "description": "2-4 句描述，诚实捕捉发现",
    "related_session_ids": ["session-id-1", "session-id-2"],
    "evidence": "来自笔记的直接引用或 paraphrase",
    "confidence": "high | medium | low"
  }
]
```

**字段约束**：

| 字段 | 约束 |
|---|---|
| `title` | 3–6 词，平实语言，不用临床术语 |
| `description` | 2–4 句，描述发现本身，不过度诠释 |
| `related_session_ids` | 只引用 sessions_context 中真实存在的 session ID（方括号内的 UUID） |
| `evidence` | 直接引用或 paraphrase；无确切引用时留空字符串，不捏造 |
| `confidence` | `"low"` 不是失败，是诚实；比强制高置信更有价值（Polanyi 原则） |

**数量约束**：每次分析返回 3–6 个结果，质量优先于数量。

---

## 9. 数据模型

### 9.1 前端 TypeScript

```typescript
// 统一的分析结果类型（三个分区共用）
export interface ReflectionResult {
  title: string;
  description: string;
  related_session_ids: string[];  // agent 精确引用的 session ID
  evidence: string;
  confidence: 'high' | 'medium' | 'low';
}

// 分区配置类型（GET /api/reflections/config/{section} 响应）
export interface ReflectionSectionConfig {
  section: string;
  display_name: string;
  display_name_zh: string;
  usedCustomConfig: boolean;  // true 时表示用户有自定义配置
  prompt_files: Record<string, string>;  // filename → content
}

// AnalysisView 的分区状态
interface SectionState {
  results: ReflectionResult[];
  loading: boolean;       // 分析中
  streaming: string;      // 实时流式输出片段（仅用于 UI 进度）
  error: string;          // 错误信息
}
```

### 9.2 后端存储

使用现有 `analysis_reports` 表（无需新建）：

| 字段 | 值 |
|---|---|
| `report_type` | `"reflections_echoes"` / `"reflections_traits"` / `"reflections_patterns"` |
| `report_data` | `{ [section]: ReflectionResult[], stats: {...} }` JSON |
| `all_notes_text` | sessions_context 前 2000 字符（可选，供调试） |

历史报告在页面加载时按 section 分别取最新一条恢复展示。

---

## 10. API 接口

### 10.1 Memory 初始化

```
POST /api/reflections/memory-init
Authorization: Bearer <token>
Content-Type: application/json

Request:
{
  "threadId": "uuid-string",
  "section": "echoes" | "traits" | "patterns"
}

Response 200:
{
  "initialised": true,
  "section": "echoes",
  "threadId": "uuid-string",
  "memoryPath": "/agent-workspaces/uuid-string/memory",
  "usedCustomConfig": false
}

Error 400: section 不合法 / threadId 为空
Error 404: thread 不存在（需先 POST /api/claude-agent/threads）
```

### 10.2 分析调用

复用现有 `POST /api/claude-agent`，关键参数：

```json
{
  "id": "<thread_id>",
  "resume": false,
  "system_prompt": "You are performing a \"Recurring Themes (回响)\" analysis for the Ink & Memory Reflections page.\nThe procedural memory workspace has been initialised at: /agent-workspaces/<thread_id>/memory\nFollow memory/WORKFLOW.md for the analysis procedure.\nOutput ONLY a JSON array as your final response.",
  "message": {
    "id": "reflections-echoes-<timestamp>",
    "role": "user",
    "parts": [{
      "type": "text",
      "text": "<sessions_context>\n{\"sessionId\":\"id-1\",\"date\":\"2026-01-15\",\"title\":\"...\",\"labels\":[\"...\"]}\n...\n</sessions_context>\n\nStart by reading memory/WORKFLOW.md to understand the analysis procedure for this section.\nFetch note bodies by session ID with mcp__user__get_sessions_range before final analysis.\nThen output ONLY a JSON array — no other text."
    }]
  },
  "tool_choice": "auto",
  "max_turns": 1000
}
```

`system_prompt` 字段由前端在 Step 2 完成后动态构造，包含：
- 分区中英文名（`section_display`）
- Step 2 返回的 `memoryPath`（若 Step 2 失败则注明无 workspace）
- 输出格式约束（JSON only）

引擎将 `system_prompt` 注入为 `<voice_context>` 块，出现在用户消息中，让 Agent 在读取 WORKFLOW.md 之前就知道当前任务的定向。
```

### 10.3 结果获取

```
GET /api/claude-agent/threads/{thread_id}/messages
Authorization: Bearer <token>

Response: messages 数组，取最后 role="assistant" 的消息
          过滤 parts[type="text"]，跳过 parts[type="reasoning"]
```

### 10.4 结果存储

```
POST /api/reports
{ "report_type": "reflections_echoes", "report_data": [...], "all_notes_text": "..." }
```

---

### 11.x Generate New Analysis 问题整理与当天重复生成保护

本次问题分为两类：

1. 点击 `Generate New Analysis` 后，页面不应直接跳转到已有结果，而必须先启动后端 Reflections-agent 异步任务并显示进度。
2. 如果用户当天已经点击过 `Generate New Analysis`，再次点击时必须弹窗确认是否重新分析，并选择可分析日记。

正确时序：`create task(auto_start=false) → SSE 订阅/短暂 fallback grace timer → start task → EventBus 进度 → task completed → fetch results → ReflectionBlogPage wrapper`。

当天重复点击判断由两部分组成：

- `localStorage[REFLECTIONS_ANALYSIS_CLICKED_DATE]` 等于当前本地日期，表示今天已经点击过；
- Past Reflections 中存在当前本地日期报告，表示今天已经有分析结果。

弹窗只服务于重复分析确认，不替代分析结果页。用户至少选择一条有正文内容的日记后才能确认；确认后前端将所选 `sessionIds` 写入 task request，后端只用这些 sessions 组装分析上下文。

## 11. 前端 AnalysisView 设计

### 11.1 视图层级

AnalysisView 包含两个视图，通过 `viewMode` state 切换：

```
viewMode = 'dashboard'  →  仪表盘视图（入口）
viewMode = 'report'     →  PaperStack 报告视图（分析完成后自动跳转）
```

### 11.2 仪表盘视图（dashboard）

**主题**：暖纸张 / 复古日记风格
- 背景：`linear-gradient(var(--color-bg-app) → var(--color-bg-paper))`（米色渐变，随系统亮/暗模式自动适配）
- 字体：`Georgia, serif`（标题）+ 系统 sans-serif（元数据、按钮）
- 装饰：DecorativeInkSpots 背景光晕

**布局结构**：

```
仪表盘头部（标题 + 副标题）
├── VintageStatLabel × 3（Days / Entries / Words）
├── 历史报告网格（最近 3 条，点击进入报告视图）
│   └── 报告卡片：日期 + LATEST 徽章 + 分区数量标签
├── 一键「Generate Reflections」按钮（stamp 风格，同时触发三分区）
│   └── 分析完成后自动切换 viewMode → 'report'
├── SectionControlsRow（分区控制行）
│   ├── echoes 分区：[⚙] + [Analyze] + 流式进度
│   ├── traits 分区：[⚙] + [Analyze] + 流式进度
│   └── patterns 分区：[⚙] + [Analyze] + 流式进度
├── 全局错误提示（汇总三分区错误，仅在非加载中时显示）
├── Empty State（无数据时：📖 + 提示文字）
└── 「View Reflections →」按钮（有数据时显示，切换到报告视图）
```

**触发方式对比**：

| 维度 | 一键按钮 | 分区独立按钮（SectionControlsRow）|
|---|---|---|
| 触发范围 | 后端 Reflections-agent 单个 task 默认执行三分区 | 单分区独立 task |
| 完成后跳转 | 是（将三分区结果包装为 `ReflectionBlogPage` report） | 是（将单分区结果包装为 `ReflectionBlogPage` report） |
| 流式进度 | 按钮下方显示 `Live editorial analysis` 进度面板；仅当天重复分析前弹窗确认 | 分区卡片内显示当前 section 事件 |
| 适用场景 | 首次全量生成 | 按需刷新单分区 |
| 重复点击 | `anyLoading` 时按钮 disabled，禁止重复提交 | 当前分区 loading 时按钮 disabled |
| 输出语言 | 任务创建时携带当前前端 `i18n.language`，后端归一化为 `en` / `zh` | 同左，三个 section 的 answer prompt 都使用该语言限定 |

**加载状态（分区独立）**：

```
一键按钮：
├── [Generate New Analysis] 按钮（loading 时 disabled）
├── 按钮下方进度面板（taskStatus）
│   ├── Live editorial analysis eyebrow
│   ├── 当前 SSE 事件状态
│   └── 细线扫光动效
└── 首次分析不弹窗；当天重复分析先显示确认与日记选择弹窗

分区控制行每个分区：
├── [Analyze] 按钮（loading 时显示 ◌，disabled）
├── [⚙] 齿轮按钮（打开 SectionConfigModal）
├── 流式进度面板（loading && streamingText）
│   └── 当前 SSE 事件状态 + ▌
└── 读取中提示（loading && !streamingText）
    └── "Waiting for backend Reflections task…"（斜体，灰色）
```

### 11.3 PaperStack 报告视图（report）

**主题**：三维堆叠纸张动效，暖白纸背景
- 纸张背景：`linear-gradient(var(--color-bg-surface-solid) → var(--color-bg-paper))`
- 纸张阴影：多层 box-shadow 模拟真实纸张厚度
- 纸面纹理：细密网格叠加层（opacity: 0.7）
- 水彩光晕：右上角模糊圆形装饰

**交互**：
- 纸张切换：左右箭头 + 小圆点导航（最多三张：echoes / traits / patterns）
- 激活纸张：全不透明，前置（z-index 10），正角度
- 非激活纸张：opacity 0.4，偏移 ±10px，微旋转 ±0.5°

**每张纸的结构**：

```
纸张 Header
├── 图标 + 分区名（Georgia 斜体）+ 副标题（uppercase）
└── 控制区（仅登录用户）
    ├── [⚙] 齿轮按钮 → 打开 SectionConfigModal
    ├── [Re-analyze] 按钮 → 触发该分区单独分析
    └── 分析中：显示流式进度或"Reading memory workspace…"

纸张 Body
└── ResultCard × n（echoes / traits / patterns 统一格式）
```

**结果卡片（ResultCard，三分区统一 ReflectionResult 类型）**：

| 字段 | 展示位置 | 视觉处理 |
|---|---|---|
| `title` | 卡片标题 | Georgia 斜体，17px，`var(--color-text-primary)` |
| `description` | 卡片正文（echoes / patterns） | 系统字体，13px，`var(--color-text-body)`，line-height 1.75 |
| `evidence` | 卡片正文（traits）| 同上，作为主要描述替代 description |
| `confidence` | traits：5 格进度条；patterns：Confidence 标签 | 进度条：`var(--color-text-muted)` 渐变；标签：圆角 pill |

> **注**：`ReflectionResult` 为三分区统一类型（替代旧的 `Echo/Trait/Pattern` 分离类型），confidence 替代 traits 的 `strength`（1–5）和 patterns 的 `frequency` 字段。

### 11.4 ReflectionBlogPage 固定布局播放器阅读页

Past Reflections 卡片点击后进入 `ReflectionBlogPage`。页面必须保留原有整体结构，不允许把页面改成全屏单列杂志长页，也不允许删除底部播放器：

```text
ReflectionBlogPage
├── Sticky Nav：返回 Past Reflections
├── Main Content（固定高度、overflow hidden）
│   ├── Split Area
│   │   ├── Left Hero：日期封面、完整日期、days / entries / words
│   │   └── Right Panel：Section Tabs + title-only list
│   └── Detail Area（选中条目后展开）
│       ├── Detail Header：分区、当前位置、关闭按钮
│       ├── Description / Evidence
│       └── Related Notes 占位
└── Bottom Player Bar（选中条目后固定在底部）
    ├── 当前条目信息
    ├── 上一条 / 圆点队列 / 下一条
    └── X / N 计数
```

完成态入口与语言：
- 前端创建 Reflections task 时传递当前 `i18n.language`；后端写入 `input_snapshot.language`，并在 echoes / traits / patterns 的 `MEMORY_ANSWER_PROMPT.md` 都追加运行时语言限定。
- `_ECHOES_ANSWER`、`_TRAITS_ANSWER`、`_PATTERNS_ANSWER` 都要求 `title` / `description` / `evidence` 按当前前端语言输出，JSON keys 和 enum values 保持英文。
- `handleAnalyzeAll` 完成后不再自动进入旧 PaperStack report 视图，而是将 echoes / traits / patterns 包装为 `AnalysisReport` 并设置 `selectedReport` + `viewMode='blog'`。
- `handleAnalyzeSection` 对应 analyzeEchoes / analyzeTraits / analyzePatterns 的分区 wrapper：单分区 task 完成后只填充当前 section，其余 section 为空，并进入同一个 `ReflectionBlogPage`。
- Dashboard 的 `View Reflections` 按钮也使用当前内存中的结果包装为 `ReflectionBlogPage` report，避免旧弹窗视觉不一致。

设计原则：
- 保持“左侧封面 + 右侧列表 + 下方详情 + 底部播放器”的既有布局，避免破坏用户已熟悉的操作路径。
- 视觉优化应服务于可读性和状态识别：封面更像数字杂志，选中项更像正在播放的 track。
- 底部 Player Bar 是核心交互能力，负责在当前 section 内切换上一条/下一条和圆点跳转。
- Related Notes 暂时保持占位，不做后端匹配，避免过度设计。
- 不新增分析完成后的自动弹窗，不增加复杂动效，不引入外部 UI 依赖；当天重复分析确认弹窗是唯一例外。

### 11.5 历史报告恢复策略

`reloadSavedReports`（`useCallback`）从 DB 加载最多 `MAX_SAVED_REPORTS`（10）条记录：

1. 每条 DB 记录可能只包含一个分区（分区独立保存时）
2. 按**日历日**分组，同一天的多条记录合并为一张历史报告 pill
3. 恢复当前展示的各分区内容时，从全部行中分别取**最新含该分区**的一条

```
DB rows（individual）
    │ 按 toDateString() 分组
    ▼
byDay Map（每天最多一条，合并 echoes/traits/patterns）
    │ 排序（最新在前）
    ▼
savedReports 数组（Dashboard 历史报告网格）

分区当前展示：
  echoes   ← individual.find(r => r.echoes.length > 0)   ← 最新行
  traits   ← individual.find(r => r.traits.length > 0)
  patterns ← individual.find(r => r.patterns.length > 0)
```

### 11.5 SectionConfigModal

每个分区在仪表盘控制行和 PaperStack 纸张头部各有一个 **⚙ 齿轮按钮**，点击打开 `SectionConfigModal`：

- 显示该分区当前使用的 5 个 memory workspace 提示词文件（可编辑 textarea）
- 文件保存：`PUT /api/reflections/config/{section}`
- 重置默认：`DELETE /api/reflections/config/{section}` → 重新 `GET` 展示
- 用户自定义激活时：弹窗标题区显示 `CUSTOM` 徽章（`usedCustomConfig === true`）

---

## 12. Polanyi 默会知识设计原则

每个分区 WORKFLOW.md 末尾包含 **Tacit Boundary** 节，明确说明显性规则的边界：

| 分区 | Tacit Boundary 核心表达 |
|---|---|
| `echoes` | 频率不等于重要性；强烈的两次可能比平淡的十次更值得命名 |
| `traits` | 特质是推断的，不是声明的；矛盾特质比单一统一画像更真实 |
| `patterns` | 不规律本身也是信息；不要为了整洁而强加虚假规律 |

**工程实现层面的 Polanyi 原则**：

1. 提示词给出显性框架（what to look for, output format），但不穷举所有判断
2. `confidence: "low"` 是合法且有价值的输出，不视为失败
3. Agent 的实践边界感（tacit judgment）填补规则未能覆盖的部分
4. 前端不对 `related_session_ids` 做二次验证，信任 Agent 的引用判断

---

## 13. 边界与约束

| 约束 | 说明 |
|---|---|
| Thread 生命周期 | 每次分析创建新 thread，不复用，不保留对话历史 |
| 工作空间清理 | 分析完成后 workspace 保留（供调试），不主动删除 |
| memory-init 失败 | 非致命：Agent 无 `<memory_context>` 时跳过 memory 操作，仍按嵌入指令分析 |
| sessions_context 上限 | 最多 80 条会话；每条只含 sessionId/date/title/labels，标题截取前 120 字符，不含正文 |
| JSON 输出数量 | 3–6 个结果，多余的前端不做截断 |
| 结果解析容错 | 支持剥离 markdown fence（```json ... ```），定位 `[...]` 区间 |
| 历史报告恢复 | 按分区分别取最新一条，不要求同一次分析的三分区同时存在 |

---

## 14. 扩展性设计

新增分区只需在 `reflections_config.py` 中添加一个 key：

```python
REFLECTIONS_SECTION_CONFIGS["new_section"] = {
    "section": "new_section",
    "display_name": "New Section",
    "display_name_zh": "新分区",
    "workspace_type": "procedural",
    "enabled": True,
    "prompt_files": {
        "WORKFLOW.md": "...",
        "MEMORY_QUERY_PROMPT.md": "...",
        "MEMORY_Distiller_PROMPT.md": "...",
        "MEMORY_ANSWER_PROMPT.md": "...",
        "DEFAULT_UPDATE_MEMORY_PROMPT.md": "...",
    }
}
```

后端 `POST /api/reflections/memory-init` 自动接受新 section（`_VALID_SECTIONS` 从 `list_sections()` 动态生成）。  
前端 `AnalysisView.tsx` 需手动添加分区渲染块（当前为静态布局）。

---

## 15. 代码归属

| 区域 | 归属文件 |
|---|---|
| 三分区静态默认配置（5 文件内容） | `backend/reflections_config.py` |
| 用户自定义配置 DB 表 + 查询函数 | `backend/database.py` (`reflections_section_configs` 表) |
| Memory 初始化端点（优先用户配置） | `backend/routers/reflections.py` → `POST /api/reflections/memory-init` |
| 配置读写端点 | `backend/routers/reflections.py` → `GET/PUT/DELETE /api/reflections/config/{section}` |
| 分析编排 + system_prompt 构造 + 解析 | `frontend/src/api/voiceApi.ts` → `analyzeReflectionsSection` |
| 配置读写客户端函数 | `frontend/src/api/voiceApi.ts` → `getReflectionsSectionConfig / saveReflectionsSectionConfig / resetReflectionsSectionConfig` |
| 结果展示（仪表盘 + PaperStack 报告视图 + 卡片）| `frontend/src/components/AnalysisView.tsx` |
| 配置编辑 UI（SectionConfigModal，每分区 ⚙ 齿轮按钮） | `frontend/src/components/AnalysisView.tsx` |
| memory_context 注入（引擎层，无改动） | `backend/claude_agent/context_builder.py` |
| 分析报告存储 | `backend/routers/reports.py` + `backend/database.py` |
