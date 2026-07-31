// [Input] MCP editor write tool names.
// [Output] Shared detector for specialized editor write approval rendering.
// [Pos] editor-write-tools utility node in frontend/src/components/chat
// [Sync] 2026-07-08: split non-component exports out of EditorWriteApprovalUI to keep Fast Refresh lint clean.

export const EDITOR_WRITE_TOOL_NAMES = new Set([
  'mcp__editor__write_segment',
  'mcp__editor__delete_segment',
  'mcp__editor__insert_widget',
  'mcp__editor__reply_to_comment',
]);

export function isEditorWriteTool(toolName: string): boolean {
  return EDITOR_WRITE_TOOL_NAMES.has(toolName.toLowerCase());
}
