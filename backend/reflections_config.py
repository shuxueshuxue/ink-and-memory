# [Input] None — static configuration module, no runtime dependencies.
# [Output] Provide REFLECTIONS_SECTION_CONFIGS for reflections analysis router and DB seeding.
# [Pos] reflections-config node in backend
# [Sync] 2026-06-06: initial implementation — three Reflections section procedural memory
#                    configs (echoes / traits / patterns) with Polanyi-inspired prompts.
"""Reflections section procedural memory workspace configurations.

Each section in the Reflections page (Recurring Themes / Character Traits /
Behavioral Patterns) has its own procedural memory config.  These configs
are used to initialise a dedicated workspace memory/ directory before running
a claude-agent analysis turn.

Design principle — Polanyi's tacit knowledge:
  Explicit rules in these prompts provide the scaffolding (what to look for,
  how to structure output).  Practical judgment about which signals matter,
  when a pattern is strong enough, and what deserves a note cannot be fully
  articulated.  The agent is expected to exercise that tacit boundary sense
  rather than mechanically applying every rule.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# ---------------------------------------------------------------------------
# Shared output contract across all three sections
# ---------------------------------------------------------------------------

_OUTPUT_CONTRACT = """
## Output Contract

Respond with a single JSON array only.  No preamble, no explanation, no markdown fences.
Each element represents one discovered insight:

```
[
  {
    "title": "Concise name (3–6 words)",
    "description": "2–4 sentences that honestly capture what was found",
    "related_session_ids": ["session-id-1", "session-id-2"],
    "evidence": "A short direct quote or paraphrase from the notes",
    "confidence": "high | medium | low"
  }
]
```

Rules:
- Return 3–6 elements.  Quality over volume.
- If the evidence is genuinely thin, set confidence to "low" and say so.
- Do not fabricate sessions that were not in the provided notes.
- Some real patterns resist clean articulation — capture them anyway with
  honest uncertainty rather than forcing false precision.
"""

# ---------------------------------------------------------------------------
# Recurring Themes (Echoes)
# ---------------------------------------------------------------------------

_ECHOES_WORKFLOW = """\
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

Recurring Themes are often felt before they can be named.  A pattern that
appears only twice may matter more than one appearing ten times if the
emotional charge is significant.  Trust that judgment rather than counting.
""" + _OUTPUT_CONTRACT

_ECHOES_QUERY = """\
# Memory Query — Recurring Themes

Scan the notes for signals that qualify as an "echo" — a theme, feeling,
or preoccupation that returns across different sessions:

1. Emotional resonance — the same worry, longing, or joy resurfacing.
2. Recurring metaphors or images — the writer keeps reaching for the same imagery.
3. Unresolved tensions — questions or conflicts the writer returns to without closure.
4. Seasonal or circumstantial loops — themes tied to recurring life contexts.
5. Quiet undercurrents — things rarely stated directly but always present.

Prefer patterns that span at least two sessions.  A single intense mention
may still qualify if the emotional weight suggests it will recur.
"""

_ECHOES_DISTILLER = """\
# Memory Distiller — Recurring Themes

Extract each echo with these fields:

- Title: the shortest phrase that names the theme honestly.
- Description: 2–4 sentences that describe the pattern without over-explaining it.
  Some themes are easier to point at than to define — that is acceptable.
- Related sessions: list the session IDs where this echo appears.
- Evidence: the clearest quote or paraphrase that anchors the pattern.
- Confidence: high / medium / low.

Distillation rules:
- Capture what is there, not what would make a tidy story.
- If two echoes feel related, name the relationship rather than merging them.
- Resist forcing an echo into a category.  Name it on its own terms.
"""

_ECHOES_ANSWER = """\
# Answer Format — Recurring Themes

Output the JSON array from the Output Contract.
Do not add interpretation beyond what the notes support.
Do not soften genuine recurring pain into something neutral.
Do not exaggerate a faint pattern into a defining theme.
The honesty of the analysis is more valuable than its polish.

Language requirement:
- Write all user-facing `title`, `description`, and `evidence` values in the
  current frontend UI language provided by the Reflections task context.
- Keep JSON keys and enum values (`confidence`, section names) in English.
- If the task context does not provide a language, default to English.
"""

_ECHOES_UPDATE = """\
# Update Rules — Recurring Themes Analysis

This is a single-turn analysis session.  Choose NO_CHANGE for procedural state.
Only ADD an analysis result entry to the output JSON.
Do not DELETE or UPDATE existing entries in this session.
"""

# ---------------------------------------------------------------------------
# Character Traits
# ---------------------------------------------------------------------------

_TRAITS_WORKFLOW = """\
# Reflections — Character Traits Workflow

Memory workspace type: procedural (Reflections analysis).

You are performing a Character Traits analysis for the Ink & Memory Reflections page.
You will receive a block of journal/writing notes with their session IDs and dates.

## Analysis Workflow

1. Read the session notes — look for how the person acts, not only what they say.
2. Read MEMORY_QUERY_PROMPT.md for trait identification signals.
3. Identify stable dispositions revealed through choices, reactions, and language.
4. Read MEMORY_Distiller_PROMPT.md to extract each trait with evidence.
5. Read MEMORY_ANSWER_PROMPT.md for the required output format.
6. Output the result JSON and nothing else.

## Tacit Boundary

Character traits are inferred, not declared.  The writer rarely says
"I am curious" — they show curiosity through what they notice, what they pursue,
what they regret skipping.  Read between the lines, and remain honest about
the limits of what can be known from a finite set of notes.
""" + _OUTPUT_CONTRACT

_TRAITS_QUERY = """\
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
"""

_TRAITS_DISTILLER = """\
# Memory Distiller — Character Traits

For each trait, extract:

- Title: a plain-language trait name (not a clinical label).
- Description: describe the trait as it appears in this person's writing,
  not in the abstract.  Use their language and situations as grounding.
- Related sessions: session IDs that show the trait most clearly.
- Evidence: a quote or paraphrase that demonstrates the trait in action.
- Confidence: high / medium / low.

Rules:
- A trait must be demonstrated, not just mentioned by the writer.
- Traits that conflict with each other are usually more accurate than
  a single coherent portrait.  Name both.
- Low-confidence traits are valuable when named honestly — they prompt
  the writer to reflect rather than accept.
"""

_TRAITS_ANSWER = """\
# Answer Format — Character Traits

Output the JSON array from the Output Contract.
Present traits as observations grounded in the notes, not judgments.
The goal is a mirror the writer can use — honest, specific, and open to revision.

Language requirement:
- Write all user-facing `title`, `description`, and `evidence` values in the
  current frontend UI language provided by the Reflections task context.
- Keep JSON keys and enum values (`confidence`, section names) in English.
- If the task context does not provide a language, default to English.
"""

_TRAITS_UPDATE = """\
# Update Rules — Character Traits Analysis

Single-turn analysis session.  Choose NO_CHANGE for procedural state.
Only ADD trait entries to the output JSON.
"""

# ---------------------------------------------------------------------------
# Behavioral Patterns
# ---------------------------------------------------------------------------

_PATTERNS_WORKFLOW = """\
# Reflections — Behavioral Patterns Workflow

Memory workspace type: procedural (Reflections analysis).

You are performing a Behavioral Patterns analysis for the Ink & Memory Reflections page.
You will receive a block of journal/writing notes with their session IDs and dates.

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
rather than impose structure to make the data tidier.  If a pattern is genuinely
irregular, say so rather than finding a false regularity.
""" + _OUTPUT_CONTRACT

_PATTERNS_QUERY = """\
# Memory Query — Behavioral Patterns

Look for temporal and conditional regularities in behaviour:

1. Writing rhythm — when does the writer write?  Under what conditions?
2. Avoidance patterns — topics or tasks repeatedly deferred.
3. Stress responses — how does the writer's output change under pressure?
4. Creative cycles — periods of generativity followed by silence, or vice versa.
5. Relational patterns — recurring dynamics in how the writer describes interactions.
6. Completion loops — does the writer tend to finish, abandon, or transform projects?

Note frequency and context, not just presence.  A pattern that appears every
two months is still a pattern.
"""

_PATTERNS_DISTILLER = """\
# Memory Distiller — Behavioral Patterns

For each pattern, extract:

- Title: a short phrase that captures the pattern's rhythm or shape.
- Description: describe when it occurs, how it manifests, and what seems to trigger it.
  Include approximate frequency if the notes support it.
- Related sessions: session IDs that show the pattern most clearly.
- Evidence: a quote or paraphrase that anchors the pattern.
- Confidence: high / medium / low.

Rules:
- Describe patterns behaviourally (what happens), not psychologically (why).
- If a pattern has exceptions, note them — exceptions often contain the
  information that makes the pattern meaningful.
- Resist over-pathologising.  Most patterns serve a function; name the function
  when you can see it.
"""

_PATTERNS_ANSWER = """\
# Answer Format — Behavioral Patterns

Output the JSON array from the Output Contract.
Present patterns as observable regularities the writer can verify.
The goal is to make implicit rhythms visible so the writer can choose
to continue, interrupt, or reframe them.

Language requirement:
- Write all user-facing `title`, `description`, and `evidence` values in the
  current frontend UI language provided by the Reflections task context.
- Keep JSON keys and enum values (`confidence`, section names) in English.
- If the task context does not provide a language, default to English.
"""

_PATTERNS_UPDATE = """\
# Update Rules — Behavioral Patterns Analysis

Single-turn analysis session.  Choose NO_CHANGE for procedural state.
Only ADD pattern entries to the output JSON.
"""

# ---------------------------------------------------------------------------
# Public section configs
# ---------------------------------------------------------------------------

REFLECTIONS_SECTION_CONFIGS: dict[str, dict[str, Any]] = {
    "echoes": {
        "section": "echoes",
        "display_name": "Recurring Themes",
        "display_name_zh": "回响",
        "workspace_type": "procedural",
        "enabled": True,
        "prompt_files": {
            "WORKFLOW.md": _ECHOES_WORKFLOW,
            "MEMORY_QUERY_PROMPT.md": _ECHOES_QUERY,
            "MEMORY_Distiller_PROMPT.md": _ECHOES_DISTILLER,
            "MEMORY_ANSWER_PROMPT.md": _ECHOES_ANSWER,
            "DEFAULT_UPDATE_MEMORY_PROMPT.md": _ECHOES_UPDATE,
        },
    },
    "traits": {
        "section": "traits",
        "display_name": "Character Traits",
        "display_name_zh": "性格特质",
        "workspace_type": "procedural",
        "enabled": True,
        "prompt_files": {
            "WORKFLOW.md": _TRAITS_WORKFLOW,
            "MEMORY_QUERY_PROMPT.md": _TRAITS_QUERY,
            "MEMORY_Distiller_PROMPT.md": _TRAITS_DISTILLER,
            "MEMORY_ANSWER_PROMPT.md": _TRAITS_ANSWER,
            "DEFAULT_UPDATE_MEMORY_PROMPT.md": _TRAITS_UPDATE,
        },
    },
    "patterns": {
        "section": "patterns",
        "display_name": "Behavioral Patterns",
        "display_name_zh": "行为模式",
        "workspace_type": "procedural",
        "enabled": True,
        "prompt_files": {
            "WORKFLOW.md": _PATTERNS_WORKFLOW,
            "MEMORY_QUERY_PROMPT.md": _PATTERNS_QUERY,
            "MEMORY_Distiller_PROMPT.md": _PATTERNS_DISTILLER,
            "MEMORY_ANSWER_PROMPT.md": _PATTERNS_ANSWER,
            "DEFAULT_UPDATE_MEMORY_PROMPT.md": _PATTERNS_UPDATE,
        },
    },
}

_VALID_SECTIONS = frozenset(REFLECTIONS_SECTION_CONFIGS)


def get_section_config(section: str) -> dict[str, Any]:
    """Return a fresh copy of the config for *section*.

    Raises ``KeyError`` for unknown sections.
    """
    return deepcopy(REFLECTIONS_SECTION_CONFIGS[section])


def list_sections() -> list[str]:
    """Return the ordered list of valid section keys."""
    return ["echoes", "traits", "patterns"]
