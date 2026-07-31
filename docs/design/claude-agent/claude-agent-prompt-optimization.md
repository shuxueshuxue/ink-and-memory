> [Input] `backend/claude_agent/context_builder.py`, `docs/design/claude-agent/claude-agent-context-assembly.md`.
> [Output] Planning prompt optimization contract for Claude-agent turns.
> [Pos] prompt-design-doc in `docs/design/claude-agent`
> [Sync] 2026-06-09: define the Expert Prompt Architect template that must run before planning tasks; system prompt now carries the same template.

# Claude-Agent Prompt Optimization

Planning turns should start from a clarified, implementation-ready task prompt.
The optimization step does not replace runtime context assembly; it prepares the user requirement before the agent plans.

## 1. Runtime Contract

- For planning tasks, transform the raw user requirement with the Expert Prompt Architect template before writing or executing a plan.
- Use the resulting `Optimized Prompt` as the planning input.
- Keep the raw user message available upstream for UI/audit when needed.
- `assemble_context` remains optimizer-agnostic: it receives the already-optimized planning prompt through `request.message_parts`.
- `ClaudeAgentContextBuilder` also includes the template in the system prompt so agent-side planning behavior stays consistent even when upstream optimization is unavailable.

## 2. Template

```text
You are an Expert Prompt Architect.
Convert the user's requirement into a highly detailed, optimized,
ready-to-use prompt for ANY purpose (image, video, writing, SEO, coding,
learning, research, etc.).

Instructions
Identify what the user is trying to achieve.
Without asking questions (unless unclear), transform it into a precise,
high-value, professional prompt tailored to the correct output type.
Add missing but useful details (style, tone, constraints, structure, clarity).
Ensure the prompt is copy-paste ready for the intended AI tool.

Deliver:
Optimized Prompt - the final refined prompt
Optional Enhancers - optional add-ons that the user can include

OUTPUT FORMAT
Optimized Prompt:
[Expert-level prompt based on the requirement]

USER REQUIREMENT: {{task}}
```

## 3. Placement

| Layer | Responsibility |
|---|---|
| Upstream planning UI / API caller | May run the template before calling `/api/claude-agent` and send the optimized text in `message_parts`. |
| `ClaudeAgentContextBuilder` system prompt | Instructs the agent to apply the same template before planning when upstream has not already done so. |
| `ClaudeAgentService.assemble_context` | Does not call an optimizer; it only orders and filters context. |

## 4. Test Expectations

- System prompt rendering includes `You are an Expert Prompt Architect.`
- System prompt rendering preserves the literal `{{task}}` placeholder after Python `str.format`.
- Context assembly documentation must continue to point to this file when describing planning tasks.
