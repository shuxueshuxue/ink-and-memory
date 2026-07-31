# [Input] None.
# [Output] Provide default_memory_workspace_config for database voice partition seeding.
# [Pos] procedural-memory-default-config node in backend
# [Sync] 2026-06-06: initial implementation - default procedural Memory workspace
#                    prompt files for voices.memory_workspace_config backfill/seed.
"""Default procedural Memory workspace configuration.

This module is a database seeding/backfill source only.  Runtime workspace
initialisation must read prompt file contents from the partition row
(``voices.memory_workspace_config``), not from project ``.claude/memory/`` files.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


DEFAULT_MEMORY_PROMPT_FILES: dict[str, str] = {
    "WORKFLOW.md": """# Procedural Memory Workflow

Memory workspace type: procedural.

Use these files as operating rules for memory work. Short-term memory and
long-term memory are conceptual collaborators, but this workspace is not a chat
window cache and is not a summary bucket. It stores procedural rules, prompt
resources, and structured state files that guide how memory work is performed.

## Decision Tree

1. Memory retrieval
   - Read `memory/MEMORY_QUERY_PROMPT.md`.
   - Decide whether the current turn warrants memory lookup.
   - Retrieve only relevant procedural state from the current workspace.

2. Memory distillation
   - Read `memory/MEMORY_Distiller_PROMPT.md`.
   - Distill the current exchange into a concise memory note when warranted.
   - Include event summary, emotional tone, key people/entities, and follow-up tasks.

3. Output to the current directory
   - Keep working outputs under the current thread workspace.
   - Prefer `memory/procedural/` for structured state updates.
   - Do not write memory artifacts outside the workspace.

4. Memory-informed answer
   - Read `memory/MEMORY_ANSWER_PROMPT.md`.
   - Use relevant memory as context, not as a script.
   - Do not expose raw private memory records unless the user asks.

5. Memory update decision
   - Read `memory/DEFAULT_UPDATE_MEMORY_PROMPT.md`.
   - Choose exactly one operation: ADD, UPDATE, DELETE, or NO_CHANGE.

## Judgment Boundary

Polanyi's tacit knowledge reminder applies here: some useful judgment is known
in practice before it can be fully verbalized. Use the explicit rules above,
but do not force an update merely because a rule can be matched. Preserve
context, proportion, and user intent.
""",
    "MEMORY_QUERY_PROMPT.md": """# Memory Query Prompt

You are retrieving procedural memory for the current conversation. Classify
candidate memories into these seven categories and return only items that
materially help the current turn.

## Seven Retrieval Categories

1. User habits
   - Writing routines, app usage patterns, communication style, language habits.

2. Emotional and mental state
   - Recent emotional shifts, recurring triggers, stress signals, coping patterns.

3. Personally important events
   - Milestones, anniversaries, relationship changes, meaningful recent events.

4. Preferences and interests
   - Topics, tone, depth, creative interests, activities, media, learning goals.

5. Relationships and trust
   - Important people, relationship context, trust boundaries, expected support.

6. Work and stress
   - Active projects, pressure sources, career goals, achievements, challenges.

7. Companionship behavior instructions
   - Explicit instructions about how the assistant should accompany, support,
     avoid topics, set boundaries, or adjust interaction style.

## Retrieval Rules

- Prefer relevance over volume.
- Retrieve no more than five highly relevant memories.
- Summarize sensitive material instead of exposing raw details.
- If nothing clearly applies, return an empty result rather than guessing.

## Output Shape

```json
{
  "retrieved_memories": [
    {
      "category": "user_habits",
      "relevance_score": 0.9,
      "content": "Concise memory summary",
      "source": "memory/procedural/<file>",
      "last_updated": "YYYY-MM-DD"
    }
  ],
  "query_summary": "Short explanation of what was or was not retrieved"
}
```
""",
    "MEMORY_Distiller_PROMPT.md": """# Memory Distiller Prompt

You are distilling the current exchange into procedural memory candidates. Your
goal is not to summarize the whole conversation. Extract only durable signals
that could improve future assistance.

## Extract

- Event summary: what happened or what changed.
- Emotional tone: the user's affect, intensity, and uncertainty.
- Key people/entities: names, projects, places, organizations, artifacts.
- Follow-up tasks: commitments, reminders, unresolved questions, next actions.

## Distillation Rules

- Keep entries concise and evidence-based.
- Preserve ambiguity when the user is uncertain.
- Do not infer private facts beyond what the user provided.
- Prefer structured fields over prose when updating state files.
- If the signal is too weak, recommend NO_CHANGE.

## Output Shape

```json
{
  "event_summary": "",
  "emotional_tone": "",
  "key_entities": [],
  "follow_up_tasks": [],
  "confidence": "low|medium|high",
  "recommended_update": "ADD|UPDATE|DELETE|NO_CHANGE"
}
```
""",
    "MEMORY_ANSWER_PROMPT.md": """# Memory Answer Prompt

Use retrieved procedural memory to answer with continuity and tact.

## Response Rules

- Let memory inform the answer without making the response feel archival.
- Mention remembered context only when it is useful and natural.
- Avoid saying "I remember" for every memory use.
- Do not reveal raw memory records unless the user asks to inspect them.
- Respect changed context: older memories can be stale.
- If memory conflicts with the current message, trust the current message and
  treat the old memory as a candidate for update.

## Style

Be specific, grounded, and proportionate. Some judgment cannot be fully
formalized; use the prompts as rails, and use practical discernment for timing,
tone, and whether memory should stay silent.
""",
    "DEFAULT_UPDATE_MEMORY_PROMPT.md": """# Default Update Memory Prompt

Choose one operation for each memory candidate.

## Operations

### ADD
Use when the user provides a new durable preference, important event, explicit
assistant instruction, relationship fact, work/stress context, or follow-up task.

### UPDATE
Use when an existing memory is still valid but needs correction, refinement,
fresh timestamping, or confidence adjustment.

### DELETE
Use when the user asks to remove a memory, revokes consent, or a memory is
clearly false, harmful, or obsolete.

### NO_CHANGE
Use when the exchange is casual, temporary, already represented, too ambiguous,
or not useful for future assistance.

## Update Rules

- Prefer NO_CHANGE when uncertain.
- Do not store sensitive details without clear utility.
- Store summaries, not transcripts.
- Keep state files in the current `memory/procedural/` directory.
- Never update memory to manipulate, judge, or pathologize the user.

## Output Shape

```json
{
  "operation": "ADD|UPDATE|DELETE|NO_CHANGE",
  "target": "memory/procedural/<file>",
  "reason": "Concise reason",
  "content": {}
}
```
""",
}


DEFAULT_MEMORY_WORKSPACE_CONFIG: dict[str, Any] = {
    "enabled": True,
    "workspace_type": "procedural",
    "prompt_files": DEFAULT_MEMORY_PROMPT_FILES,
    "procedural_state_files": {
        "user_preferences.json": True,
        "important_events.json": True,
        "timeline.json": True,
    },
}


def default_memory_workspace_config() -> dict[str, Any]:
    """Return a fresh copy of the default partition Memory config."""

    return deepcopy(DEFAULT_MEMORY_WORKSPACE_CONFIG)
