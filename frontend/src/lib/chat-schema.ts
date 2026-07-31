// [Input] Consume AI SDK message and usage types for chat request/metadata contracts.
// [Output] Define frontend chat transport request body, attachment, model, tool, and metadata types.
// [Pos] chat-schema type node in frontend/src/lib
// [Sync] 2026-05-25: remove frontend customer-context request fields from the chat schema.
import type { LanguageModelUsage, UIMessage } from 'ai';

export type ChatAttachment = {
  type: 'file' | 'source-url';
  url: string;
  storageKey?: string;
  mediaType?: string;
  filename?: string;
  size?: number;
  workspacePath?: string;
  savedAt?: string;
  hash?: string;
};

export type ChatModel = { provider: string; model: string };
export const DEFAULT_CHAT_MODEL: ChatModel = {
  provider: 'anthropic',
  model: 'claude-sonnet-4-20250514',
};

export type ToolChoice = 'auto' | 'none' | 'manual';

export type ChatApiSchemaRequestBody = {
  id: string;
  resume?: boolean;
  message: UIMessage;
  chatModel?: ChatModel;
  toolChoice?: ToolChoice;
  attachments?: ChatAttachment[];
  systemPrompt?: string;
  allowedMcpServers?: Record<string, unknown>;
  allowedAppDefaultToolkit?: string[];
  /** Current EditorState snapshot — enables .editor/ virtual index redirect in the agent runner. */
  editor_state?: Record<string, unknown>;
};

export type ChatMetadata = {
  usage?: LanguageModelUsage;
  chatModel?: ChatModel;
  toolChoice?: ToolChoice;
  toolCount?: number;
  agentId?: string;
  workspacePath?: string;
  workspaceSessionId?: string;
};

/** Voice / deck info displayed in the Chat view and forwarded to the backend as voice context. */
export interface ActiveChatVoice {
  name: string;
  systemPrompt: string;
  icon: string;
  color: string;
}
