# [Input] None — stub placeholder.
# [Output] Provide expand_memory_recall_query stub to libs/claude_agent_kit/server/memory_tool.py.
# [Pos] utility node in backend/libs/utils
# [Sync] 2026-05-23: moved from backend/prompts/policy_loader.py.
#                    Pawkeyland's mem0 query expansion — not implemented in Ink & Memory.
#                    Kept as stub so memory_tool.py import doesn't fail at module load.


def expand_memory_recall_query(*args, **kwargs):
    raise NotImplementedError("policy_loader is not available in Ink & Memory.")
