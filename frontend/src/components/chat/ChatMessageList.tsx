// [Input] UIMessage[] from useChat; ToolMessagePart, AssistMessagePart, UserMessagePart, FileMessagePart sub-components; toolInputSummary helpers.
// [Output] Scrollable chat message list with tool, text, reasoning, and file part rendering.
// [Pos] chat-message-list component node in frontend/src/components/chat
// [Sync] 2026-05-27: add threadId prop; propagate to ToolMessagePart; render AskUserQuestion tool parts directly (not collapsed) so the question form is immediately visible.
// [Sync] 2026-05-27: add toolChoice prop; render non-completed tool parts in manual mode directly with isManualToolInvocation=true so Approve/Cancel UI is shown.
// [Sync] 2026-05-29: import isEditorWriteTool; render editor write tool parts directly (not collapsed) with isManualToolInvocation=true so specialized approval UI shows immediately.
// [Sync] 2026-05-29: render completed editor write tool parts as EditorWriteCompletedCard instead of Terminal card.
// [Sync] 2026-05-29: add onEditorWriteConfirmed prop; forward to ToolMessagePart for editor write tools.
// [Sync] 2026-05-29: let the message list fill the available chat page width.
// [Sync] 2026-05-29: fix history-replay regression — history-loaded DynamicToolUIPart may lack toolName field causing getToolName() to return 'invocation'; add resolveToolName() with direct field fallback and hoist editor write completed check above Terminal block, decoupled from outputText.
// [Sync] 2026-05-30: fix reasoning SSE display — auto-expand reasoning when state==='streaming'; show spin loader + blinking cursor during stream; border dims when done; hide manual expand toggle while streaming.
// [Sync] 2026-05-30: reasoning blocks default to expanded (isExpandedActual ?? true) so thinking content stays visible after streaming ends; user can click to collapse; toggle flips isExpandedActual.
// [Sync] 2026-06-02: delegate user text bubbles to UserMessagePart so user prompts render through the shared GFM Markdown path.
// [Sync] 2026-06-06: render toolMetadata.approvalRequested tool parts directly with approval UI so auto-mode backend confirmations are visible.
// [Sync] 2026-06-13: render built-in Write tool input-streaming/input-complete states
//                    as a terminal-style file write preview.
// [Sync] 2026-06-14: collapse long built-in Write file previews by default while
//                    keeping full-content copy and an inline expand/collapse control.
// [Sync] 2026-06-14: forward editor write toolCallId for event-driven Writing view reload de-duplication.
// [Sync] 2026-07-19: show per-tool task summaries — the Terminal card header displays input.description and prefers input.command for the $ line; collapsed tool rows append the description/target so running tools are recognizable (shared helpers from toolInputSummary.ts).
// [Sync] 2026-07-20: pending tool confirmations no longer render inline Approve/Cancel or
//                    AskUserQuestion forms — those moved to ToolConfirmationDock above AIInputDock.
//                    Pending parts now render as collapsed rows with an amber 「待确认」 badge;
//                    shared classifiers moved to toolConfirmation.ts (design §8).
// [Sync] 2026-07-20: i18n — pending confirmation badge copy resolves through the
//                    chat.toolConfirmation namespace (en + zh) via useTranslation.
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { getToolName, isToolUIPart, type DynamicToolUIPart, type FileUIPart, type ToolUIPart, type UIMessage } from 'ai';
import type { UseChatHelpers } from '@ai-sdk/react';
import FileMessagePart from './FileMessagePart';
import AssistMessagePart from './AssistMessagePart';
import UserMessagePart from './UserMessagePart';
import ToolMessagePart from './ToolMessagePart';
import { EditorWriteCompletedCard, type EditorWriteOutput } from './EditorWriteApprovalUI';
import { isEditorWriteTool } from './editorWriteTools';
import { resolvePendingToolConfirmation, resolveToolName } from './toolConfirmation';
import { parsePartialInputJson, resolveToolInputSummary, summarizeToolInvocation } from './toolInputSummary';

interface ChatMessageListProps {
  messages: UIMessage[];
  threadId: string;
  isLoading: boolean;
  error?: Error | null;
  addToolResult: (args: { tool: string; toolCallId: string; output: unknown }) => void;
  shouldShowLoadingIndicator?: boolean;
  readonly?: boolean;
  toolChoice?: string;
  setMessages?: UseChatHelpers<UIMessage>['setMessages'];
  sendMessage?: UseChatHelpers<UIMessage>['sendMessage'];
  /** Forwarded to ToolMessagePart for editor write tools — triggers Writing view reload. */
  onEditorWriteConfirmed?: (toolCallId: string) => void;
}

type ToolStatus = 'executing' | 'completed' | 'error';

const TOOL_COMPLETED_STATES = new Set(['output-available', 'output-error']);
const REASONING_PREVIEW_LENGTH = 80;
const WRITE_PREVIEW_COLLAPSE_CHAR_LIMIT = 1800;
const WRITE_PREVIEW_COLLAPSE_LINE_LIMIT = 24;
const WRITE_PREVIEW_COLLAPSED_MAX_HEIGHT = `${WRITE_PREVIEW_COLLAPSE_LINE_LIMIT * 1.65}em`;
const WRITE_PREVIEW_DEFAULT_MAX_HEIGHT = '24rem';
const WRITE_PREVIEW_EXPANDED_MAX_HEIGHT = '36rem';

function getToolStatus(part: ToolUIPart | DynamicToolUIPart, isLoading: boolean): ToolStatus {
  if (part.state === 'output-error') return 'error';
  if (TOOL_COMPLETED_STATES.has(part.state ?? '')) return 'completed';
  return isLoading ? 'executing' : 'completed';
}

function getToolOutputText(part: ToolUIPart | DynamicToolUIPart): string | null {
  if ('output' in part && part.output != null) return typeof part.output === 'string' ? part.output : JSON.stringify(part.output, null, 2);
  if ('error' in part && part.error != null) return typeof part.error === 'string' ? part.error : JSON.stringify(part.error, null, 2);
  return null;
}

function parseTerminalOutput(raw: string): { command: string | null; output: string; exitCode: string | null } {
  const lines = raw.split('\n');
  let command: string | null = null;
  let exitCode: string | null = null;
  const outputLines: string[] = [];

  lines.forEach((line) => {
    const commandMatch = line.match(/^\$\s+(.+)/);
    const exitMatch = line.match(/^Exit code:\s*(\d+)/i);
    if (commandMatch && !command) command = commandMatch[1];
    else if (exitMatch) exitCode = exitMatch[1];
    else outputLines.push(line);
  });

  return { command, output: outputLines.join('\n').trim(), exitCode };
}

function IconCopy() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: '1rem', height: '1rem' }}>
      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </svg>
  );
}

const BUILTIN_WRITE_TOOL_NAMES = new Set(['write']);

function isBuiltInWriteTool(toolName: string): boolean {
  return BUILTIN_WRITE_TOOL_NAMES.has(toolName.toLowerCase());
}

function readToolInput(part: ToolUIPart | DynamicToolUIPart): unknown {
  return 'input' in part ? part.input : undefined;
}

function resolveWriteInput(input: unknown): { filePath: string; content: string; partialJson: string } {
  const partial = parsePartialInputJson(input);
  const value =
    input && typeof input === 'object' && !Array.isArray(input)
      ? { ...partial, ...(input as Record<string, unknown>) }
      : partial;
  return {
    filePath: typeof value.file_path === 'string' ? value.file_path : '',
    content: typeof value.content === 'string' ? value.content : '',
    partialJson: typeof value._partialInputJson === 'string' ? value._partialInputJson : '',
  };
}

function WriteToolTerminalCard({
  part,
  partKey,
  isLoading,
  isLastMessage,
  onCopy,
  copiedPartId,
  isContentExpanded,
  onToggleContent,
}: {
  part: ToolUIPart | DynamicToolUIPart;
  partKey: string;
  isLoading: boolean;
  isLastMessage: boolean;
  onCopy: (id: string, text: string) => void;
  copiedPartId: string | null;
  isContentExpanded: boolean;
  onToggleContent: () => void;
}) {
  const input = readToolInput(part);
  const outputText = getToolOutputText(part);
  const { filePath, content, partialJson } = resolveWriteInput(input);
  const status = getToolStatus(part, isLoading);
  const isStreamingInput = part.state === 'input-streaming';
  const isExecuting = status === 'executing' || (isLastMessage && isLoading && !TOOL_COMPLETED_STATES.has(part.state ?? ''));
  const isError = status === 'error';
  const isWritten = part.state === 'output-available';
  const displayContent = content || (partialJson ? 'Receiving file content…' : '');
  const contentLineCount = displayContent ? displayContent.split('\n').length : 0;
  const shouldCollapseContent =
    Boolean(displayContent) &&
    (displayContent.length > WRITE_PREVIEW_COLLAPSE_CHAR_LIMIT ||
      contentLineCount > WRITE_PREVIEW_COLLAPSE_LINE_LIMIT);
  const contentMaxHeight =
    shouldCollapseContent
      ? isContentExpanded
        ? WRITE_PREVIEW_EXPANDED_MAX_HEIGHT
        : WRITE_PREVIEW_COLLAPSED_MAX_HEIGHT
      : WRITE_PREVIEW_DEFAULT_MAX_HEIGHT;
  const contentOverflow = shouldCollapseContent && !isContentExpanded ? 'hidden' : 'auto';
  const contentSummary = contentLineCount > 1 ? `${contentLineCount} lines` : `${displayContent.length} chars`;
  const copyText = [filePath ? `$ write ${filePath}` : '$ write', displayContent, outputText || ''].filter(Boolean).join('\n\n');
  const statusLabel = isError ? 'Write failed' : isWritten ? 'Written' : isStreamingInput ? 'Receiving input' : isExecuting ? 'Writing' : 'Ready';

  return (
    <div style={{ overflow: 'hidden', borderRadius: '12px', background: 'var(--color-code-bg)', color: 'var(--color-code-text)' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', padding: '0.65rem 1rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
        <span>‹ Write</span>
        <span style={{ marginLeft: 'auto', color: isError ? 'var(--color-state-error)' : isWritten ? 'var(--color-state-success)' : 'var(--color-action-link)' }}>{statusLabel}</span>
        <button type="button" onClick={() => onCopy(partKey, copyText)} title="Copy" style={{ border: 'none', background: 'transparent', color: copiedPartId === partKey ? 'var(--color-state-success)' : 'var(--color-code-text)', cursor: 'pointer' }}>{copiedPartId === partKey ? 'Copied!' : <IconCopy />}</button>
      </div>
      <div style={{ padding: '0 1rem 0.9rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.8rem', lineHeight: 1.65 }}>
        <p style={{ margin: '0 0 0.45rem' }}><span style={{ color: 'var(--color-action-link)' }}>$</span> <span>write {filePath || 'pending-path'}</span></p>
        <div style={{ position: 'relative' }}>
          <pre style={{ margin: 0, whiteSpace: 'pre-wrap', maxHeight: contentMaxHeight, overflow: contentOverflow, color: 'var(--color-code-text)' }}>{displayContent}{isExecuting ? <span style={{ opacity: 0.5 }}>▌</span> : null}</pre>
          {shouldCollapseContent && !isContentExpanded ? (
            <div aria-hidden="true" style={{ position: 'absolute', left: 0, right: 0, bottom: 0, height: '2.5rem', pointerEvents: 'none', background: 'linear-gradient(to bottom, transparent, var(--color-code-bg))' }} />
          ) : null}
        </div>
        {shouldCollapseContent ? (
          <button
            type="button"
            onClick={onToggleContent}
            style={{
              marginTop: '0.65rem',
              border: '1px solid rgba(255,255,255,0.14)',
              borderRadius: '8px',
              background: 'rgba(255,255,255,0.04)',
              color: 'var(--color-code-text)',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: '0.75rem',
              padding: '0.35rem 0.55rem',
            }}
          >
            {isContentExpanded ? 'Collapse file preview' : `Show full file (${contentSummary})`}
          </button>
        ) : null}
      </div>
      {outputText ? (
        <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', padding: '0.55rem 1rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.75rem', color: isError ? 'var(--color-state-error)' : 'var(--color-state-success)', whiteSpace: 'pre-wrap' }}>{outputText}</div>
      ) : null}
    </div>
  );
}

export default function ChatMessageList({ messages, threadId, isLoading, error, addToolResult, shouldShowLoadingIndicator = false, readonly = false, toolChoice, setMessages, sendMessage, onEditorWriteConfirmed }: ChatMessageListProps) {
  const { t } = useTranslation();
  const [expandedParts, setExpandedParts] = useState<Record<string, boolean>>({});
  const [copiedPartId, setCopiedPartId] = useState<string | null>(null);

  const handleCopy = async (id: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedPartId(id);
      window.setTimeout(() => setCopiedPartId((current) => (current === id ? null : current)), 1800);
    } catch {
      setCopiedPartId(null);
    }
  };

  return (
    <div style={{ width: '100%', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {messages.map((message, index) => {
        const isLastMessage = index === messages.length - 1;
        return (
          <div key={message.id} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {message.parts?.map((part, partIndex) => {
              const partKey = `${message.id}-${partIndex}`;
              const isExpanded = expandedParts[partKey] ?? false;
              // For reasoning parts: default expanded (see isExpandedActual below).
              // toggleExpanded flips from the *actual* state that was used to render.
              const toggleExpanded = () => setExpandedParts((current) => ({ ...current, [partKey]: !isExpanded }));

              if (part.type === 'reasoning') {
                const reasoningPart = part as { text?: string; state?: 'streaming' | 'done' };
                const reasoningText = reasoningPart.text ?? '';
                const isStreaming = reasoningPart.state === 'streaming';
                // Reasoning defaults to expanded so users always see thinking content.
                // Use ?? true so first render is expanded; user can click to collapse.
                const isExpandedActual = expandedParts[partKey] ?? true;
                const showContent = isExpandedActual || isStreaming;
                const toggleReasoningExpanded = () =>
                  setExpandedParts((current) => ({ ...current, [partKey]: !isExpandedActual }));
                return (
                  <div key={partKey} style={{ paddingLeft: '0.85rem', borderLeft: `2px solid ${isStreaming ? 'var(--color-action-link)' : 'var(--color-border-paper)'}`, transition: 'border-color 0.3s' }}>
                    <button
                      type="button"
                      onClick={isStreaming ? undefined : toggleReasoningExpanded}
                      style={{
                        width: '100%',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.5rem',
                        border: 'none',
                        background: 'transparent',
                        padding: 0,
                        color: 'var(--color-text-muted)',
                        fontSize: '0.85rem',
                        fontStyle: 'italic',
                        cursor: isStreaming ? 'default' : 'pointer',
                      }}
                    >
                      {isStreaming ? (
                        <span style={{
                          width: '0.65rem', height: '0.65rem', borderRadius: '999px',
                          border: '2px solid var(--color-action-link)', borderTopColor: 'transparent',
                          display: 'inline-block', flexShrink: 0,
                          animation: 'spin 0.8s linear infinite',
                        }} />
                      ) : null}
                      <span style={{ flex: 1, textAlign: 'left', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {reasoningText.slice(0, REASONING_PREVIEW_LENGTH) || 'Thinking…'}
                      </span>
                      {!isStreaming ? <span>{isExpandedActual ? '‹' : '›'}</span> : null}
                    </button>
                    {showContent ? (
                      <div style={{ marginTop: '0.5rem', whiteSpace: 'pre-wrap', fontSize: '0.85rem', lineHeight: 1.7, color: 'var(--color-text-secondary)' }}>
                        {reasoningText}
                        {isStreaming ? (
                          <span style={{
                            display: 'inline-block', width: '2px', height: '0.85em',
                            background: 'var(--color-text-muted)', marginLeft: '1px',
                            verticalAlign: 'text-bottom', animation: 'pulse 1s ease-in-out infinite',
                          }} />
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                );
              }

              if (part.type === 'step-start') return null;

              if (part.type === 'text' && part.text) {
                const isUser = message.role === 'user';
                if (isUser) {
                  return <UserMessagePart key={partKey} text={part.text} />;
                }

                const isLastPart = partIndex === (message.parts?.length ?? 0) - 1;
                const previousMessage = index > 0 ? messages[index - 1] : undefined;
                return (
                  <div key={partKey} style={{ width: '100%' }}>
                    <AssistMessagePart
                      part={part}
                      isLast={isLastMessage && isLastPart}
                      isLoading={isLoading}
                      message={message}
                      prevMessage={previousMessage}
                      showActions={isLastMessage ? isLastPart && !isLoading : isLastPart}
                      readonly={readonly}
                      setMessages={setMessages}
                      sendMessage={sendMessage}
                    />
                  </div>
                );
              }

              if (isToolUIPart(part)) {
                const toolPart = part as ToolUIPart | DynamicToolUIPart;
                const toolStatus = getToolStatus(toolPart, isLoading);
                const isCompleted = toolStatus !== 'executing';
                const isError = toolStatus === 'error';
                const outputText = getToolOutputText(toolPart);
                const title = 'title' in toolPart ? (toolPart as { title?: string }).title : undefined;
                const toolName = resolveToolName(toolPart);
                const displayTitle = title || toolName || getToolName(toolPart);
                const isBuiltInWrite = isBuiltInWriteTool(toolName);

                // Editor write tools always render as EditorWriteCompletedCard when
                // completed — this check is independent of outputText so that history-
                // replay parts (which may lack output after DB serialization) still get
                // the correct UI instead of falling through to the Terminal block.
                if (isCompleted && isEditorWriteTool(toolName)) {
                  const rawInput = 'input' in toolPart ? (toolPart as { input?: unknown }).input : undefined;
                  const rawOutput = 'output' in toolPart ? (toolPart as { output?: unknown }).output : undefined;
                  return (
                    <div key={partKey}>
                      <EditorWriteCompletedCard
                        toolName={toolName}
                        input={(rawInput ?? {}) as Record<string, unknown>}
                        output={(rawOutput ?? {}) as EditorWriteOutput}
                      />
                    </div>
                  );
                }

                if (isCompleted && isBuiltInWrite) {
                  return (
                    <div key={partKey}>
                      <WriteToolTerminalCard
                        part={toolPart}
                        partKey={partKey}
                        isLoading={isLoading}
                        isLastMessage={isLastMessage}
                        onCopy={(id, text) => void handleCopy(id, text)}
                        copiedPartId={copiedPartId}
                        isContentExpanded={isExpanded}
                        onToggleContent={toggleExpanded}
                      />
                    </div>
                  );
                }

                if (isCompleted && outputText) {
                  const { command, output, exitCode } = parseTerminalOutput(outputText);
                  const exitCodeNumber = exitCode != null ? Number(exitCode) : null;
                  const terminalToolInput = readToolInput(toolPart);
                  const terminalSummary = summarizeToolInvocation(toolName, terminalToolInput);
                  // Prefer the command from the tool input itself — the output text
                  // only carries a `$ command` echo for some backends, so relying on
                  // parseTerminalOutput alone leaves the card showing only results.
                  const displayCommand = resolveToolInputSummary(terminalToolInput).command || command;
                  return (
                    <div key={partKey} style={{ overflow: 'hidden', borderRadius: '12px', background: 'var(--color-code-bg)', color: 'var(--color-code-text)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', padding: '0.65rem 1rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
                        <span style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'baseline', gap: '0.55rem' }}>
                          <span style={{ flexShrink: 0 }}>‹ Terminal</span>
                          {terminalSummary ? <span style={{ minWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: 'var(--color-code-text)' }}>{terminalSummary}</span> : null}
                        </span>
                        <button type="button" onClick={() => void handleCopy(partKey, outputText)} title="Copy" style={{ flexShrink: 0, border: 'none', background: 'transparent', color: copiedPartId === partKey ? 'var(--color-state-success)' : 'var(--color-code-text)', cursor: 'pointer' }}>{copiedPartId === partKey ? 'Copied!' : <IconCopy />}</button>
                      </div>
                      <div style={{ padding: '0 1rem 0.9rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.8rem', lineHeight: 1.65 }}>
                        {displayCommand ? <p style={{ margin: '0 0 0.45rem' }}><span style={{ color: 'var(--color-action-link)' }}>$</span> <span>{displayCommand}</span></p> : null}
                        <pre style={{ margin: 0, whiteSpace: 'pre-wrap', maxHeight: '20rem', overflow: 'auto', color: 'var(--color-code-text)' }}>{output || outputText}</pre>
                      </div>
                      {exitCodeNumber != null ? <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', padding: '0.55rem 1rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.75rem', color: exitCodeNumber === 0 ? 'var(--color-state-success)' : 'var(--color-state-error)' }}>Exit code: {exitCode}</div> : null}
                      {isError && exitCodeNumber == null ? <div style={{ borderTop: '1px solid rgba(255,255,255,0.1)', padding: '0.55rem 1rem', fontSize: '0.75rem', color: 'var(--color-state-error)' }}>Error</div> : null}
                    </div>
                  );
                }

                // Pending confirmations (AskUserQuestion forms, manual-mode and
                // backend-requested approvals) are NOT rendered inline anymore —
                // they surface in the ToolConfirmationDock floating above the input
                // area. Here they fall through to the collapsed row with a 「待确认」
                // badge (see pendingConfirmationKind below).

                // Editor write tools (write_segment, delete_segment, insert_widget,
                // reply_to_comment) are always-confirm tools — render directly so
                // the specialized approval UI shows immediately.
                const needsEditorWriteApproval = isEditorWriteTool(toolName) && !isCompleted;
                if (needsEditorWriteApproval) {
                  return (
                    <div key={partKey}>
                      <ToolMessagePart part={toolPart} threadId={threadId} isLast={isLastMessage} isLoading={isLoading} addToolResult={addToolResult} onEditorWriteConfirmed={onEditorWriteConfirmed} />
                    </div>
                  );
                }

                if (isBuiltInWrite && !isCompleted) {
                  return (
                    <div key={partKey}>
                      <WriteToolTerminalCard
                        part={toolPart}
                        partKey={partKey}
                        isLoading={isLoading}
                        isLastMessage={isLastMessage}
                        onCopy={(id, text) => void handleCopy(id, text)}
                        copiedPartId={copiedPartId}
                        isContentExpanded={isExpanded}
                        onToggleContent={toggleExpanded}
                      />
                    </div>
                  );
                }

                const toolRowSummary = summarizeToolInvocation(toolName, readToolInput(toolPart));
                const pendingConfirmationKind = resolvePendingToolConfirmation(toolPart, toolChoice);
                return (
                  <div key={partKey} style={{ paddingLeft: '0.85rem', borderLeft: `2px solid ${pendingConfirmationKind ? '#f59e0b' : 'var(--color-action-link)'}` }}>
                    <button type="button" onClick={toggleExpanded} style={{ width: '100%', display: 'flex', alignItems: 'center', gap: '0.55rem', border: 'none', background: 'transparent', padding: 0, color: 'var(--color-text-secondary)', fontSize: '0.88rem', cursor: 'pointer' }}>
                      {pendingConfirmationKind ? (
                        <span style={{ width: '0.55rem', height: '0.55rem', borderRadius: '999px', background: '#f59e0b', display: 'inline-block', flexShrink: 0 }} />
                      ) : toolStatus === 'executing' ? <span style={{ width: '0.7rem', height: '0.7rem', borderRadius: '999px', border: '2px solid var(--color-action-link)', borderTopColor: 'transparent', display: 'inline-block' }} /> : null}
                      <span style={{ flex: 1, textAlign: 'left', fontStyle: 'italic', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{displayTitle}{toolRowSummary ? ` — ${toolRowSummary}` : ''}</span>
                      {pendingConfirmationKind ? (
                        <span style={{ flexShrink: 0, borderRadius: '999px', padding: '0.1rem 0.5rem', fontSize: '0.72rem', fontWeight: 600, fontStyle: 'normal', color: '#b45309', background: 'color-mix(in srgb, #f59e0b 16%, transparent)' }}>
                          {pendingConfirmationKind === 'askuser' ? t('chat.toolConfirmation.pendingAnswer') : t('chat.toolConfirmation.pendingConfirm')}
                        </span>
                      ) : null}
                      <span style={{ color: 'var(--color-text-muted)' }}>{isExpanded ? '‹' : '›'}</span>
                    </button>
                    {isExpanded ? <div style={{ marginTop: '0.6rem' }}><ToolMessagePart part={toolPart} threadId={threadId} isLast={isLastMessage} isLoading={isLoading} addToolResult={addToolResult} /></div> : null}
                  </div>
                );
              }

              if (part.type === 'file') {
                const isUser = message.role === 'user';
                return <div key={partKey} style={{ display: 'flex', justifyContent: isUser ? 'flex-end' : 'flex-start' }}><div style={{ maxWidth: '80%' }}><FileMessagePart part={part as FileUIPart} isUserMessage={isUser} /></div></div>;
              }

              return null;
            })}
          </div>
        );
      })}

      {shouldShowLoadingIndicator ? <div style={{ alignSelf: 'flex-start', borderRadius: '12px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', padding: '0.8rem 0.95rem', color: 'var(--color-text-secondary)', fontSize: '0.85rem' }}>Thinking…</div> : null}
      {error ? <div style={{ alignSelf: 'flex-start', maxWidth: '80%', borderRadius: '18px', padding: '0.8rem 0.95rem', background: 'color-mix(in srgb, var(--color-state-error) 10%, transparent)', color: 'var(--color-state-error)', fontSize: '0.85rem' }}>Error: {error.message}</div> : null}
    </div>
  );
}
