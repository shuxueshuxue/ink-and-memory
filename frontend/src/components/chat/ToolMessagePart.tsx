// [Input] EditorWriteApprovalUI, Icons, toolConfirmation helpers; part shape from @ai-sdk/react DynamicToolUIPart/ToolUIPart.
// [Output] Collapsed tool detail card (header + expandable input/output), plus the inline
//          EditorWriteApproval UI for mcp__editor__ write tools. Generic approvals and
//          AskUserQuestion prompts are NOT rendered here — they live in ToolConfirmationDock
//          floating above AIInputDock.
// [Pos] tool-message-part component node in frontend/src/components/chat
// [Sync] 2026-05-27: add threadId prop; fix confirmToolCall body to send thread_id+tool_call_id (snake_case) matching ToolConfirmRequestBody; accept ok|success response flag.
// [Sync] 2026-05-29: integrate EditorWriteApprovalUI for mcp__editor__ write tools; detect by isEditorWriteTool().
// [Sync] 2026-06-12: use centralized API_BASE for cross-origin tool confirmation requests.
// [Sync] 2026-06-14: pass toolCallId to onEditorWriteConfirmed for event-driven reload de-duplication.
// [Sync] 2026-07-08: use semantic error/on-action color tokens in generic tool cards for dark mode.
// [Sync] 2026-07-19: show task summary (input.description/target) and shell command lines in the generic tool card header so approvals and collapsed cards explain what the tool is doing.
// [Sync] 2026-07-20: remove inline Approve/Cancel + AskUserQuestion rendering and the
//        isManualToolInvocation prop — pending confirmations moved to ToolConfirmationDock;
//        confirmToolCall moved to toolConfirmation.ts (design: claude-agent-tool-confirmation-flow.md §8).
// [Sync] 2026-07-20: i18n — editor write status rows and the default reject reason resolve
//        through the chat.editorWrite namespace (en + zh) via useTranslation.
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { getToolName, type DynamicToolUIPart, type ToolUIPart } from 'ai';
import EditorWriteApprovalUI from './EditorWriteApprovalUI';
import { isEditorWriteTool } from './editorWriteTools';
import { confirmToolCall } from './toolConfirmation';
import { isShellTool, resolveToolInputSummary, summarizeToolInvocation } from './toolInputSummary';
import { IconCheck, IconChevronDown, IconChevronUp, IconLoader, IconX } from './Icons';

type AnyToolUIPart = ToolUIPart | DynamicToolUIPart;

function IconTool() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: '0.95rem', height: '0.95rem' }}>
      <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
    </svg>
  );
}

function IconAlert() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: '0.95rem', height: '0.95rem' }}>
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

interface ToolMessagePartProps {
  part: AnyToolUIPart;
  threadId: string;
  isLast?: boolean;
  isLoading?: boolean;
  addToolResult?: (params: { tool: string; toolCallId: string; output: unknown }) => void;
  /** Called after an editor write tool is successfully confirmed so the Writing view can reload. */
  onEditorWriteConfirmed?: (toolCallId: string) => void;
}

export function ToolMessagePart({ part, threadId, isLast, isLoading, addToolResult, onEditorWriteConfirmed }: ToolMessagePartProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [confirmationStatus, setConfirmationStatus] = useState<'idle' | 'confirming' | 'confirmed' | 'rejected'>('idle');
  const toolCallId = part.toolCallId;
  const toolName = getToolName(part);
  const input = 'input' in part ? part.input : undefined;
  const output = 'output' in part ? part.output : undefined;
  const state = part.state;
  const title = 'title' in part ? (part as { title?: string }).title : undefined;
  const providerExecuted = 'providerExecuted' in part ? (part as { providerExecuted?: boolean }).providerExecuted : undefined;
  const partType = part.type;

  const isCompleted = useMemo(() => state === 'output-available' || state === 'output-error', [state]);
  const isExecuting = useMemo(() => !isCompleted && Boolean(isLast && isLoading), [isCompleted, isLast, isLoading]);
  const isError = useMemo(() => state === 'output-error', [state]);
  const isEditorWrite = useMemo(() => isEditorWriteTool(toolName), [toolName]);
  const shouldShowEditorWriteUI = useMemo(() => isEditorWrite && !isCompleted && (state === 'input-available' || state === 'approval-requested' || !state || state === 'input-streaming'), [isEditorWrite, isCompleted, state]);
  // One-line "what is this tool doing" summary for the card header: task
  // description when the model provides one, otherwise the command/target.
  const toolSummaryText = useMemo(() => summarizeToolInvocation(toolName, input), [toolName, input]);
  const toolCommandText = useMemo(() => (isShellTool(toolName) ? resolveToolInputSummary(input).command : ''), [toolName, input]);

  const inputDisplay = useMemo(() => {
    try { return JSON.stringify(input, null, 2); } catch { return String(input); }
  }, [input]);
  const outputDisplay = useMemo(() => {
    if (output == null) return null;
    try { return JSON.stringify(output, null, 2); } catch { return String(output); }
  }, [output]);

  const handleEditorWriteApprove = useCallback(async () => {
    if (confirmationStatus !== 'idle') return;
    setConfirmationStatus('confirming');
    try {
      const result = await confirmToolCall(threadId, toolCallId, true);
      if (result.ok ?? result.success) {
        addToolResult?.({ tool: toolName, toolCallId, output: { approved: true } });
        setConfirmationStatus('confirmed');
        onEditorWriteConfirmed?.(toolCallId);
        return;
      }
    } catch {
      // fall through
    }
    setConfirmationStatus('idle');
  }, [addToolResult, confirmationStatus, onEditorWriteConfirmed, threadId, toolCallId, toolName]);

  const handleEditorWriteReject = useCallback(async (reason?: string) => {
    if (confirmationStatus !== 'idle') return;
    setConfirmationStatus('confirming');
    try {
      const result = await confirmToolCall(threadId, toolCallId, false, reason || t('chat.editorWrite.userRejected'));
      if (result.ok ?? result.success) {
        addToolResult?.({ tool: toolName, toolCallId, output: { approved: false } });
        setConfirmationStatus('rejected');
        return;
      }
    } catch {
      // fall through
    }
    setConfirmationStatus('idle');
  }, [addToolResult, confirmationStatus, threadId, toolCallId, toolName, t]);

  // Editor write tools (write_segment, delete_segment, insert_widget, reply_to_comment)
  // are always-confirm tools; render the specialized approval UI directly.
  if (shouldShowEditorWriteUI) {
    return (
      <div style={{ width: '100%' }}>
        {confirmationStatus === 'idle' && input !== undefined ? (
          <EditorWriteApprovalUI
            toolName={toolName}
            toolCallId={toolCallId}
            input={input as Record<string, unknown>}
            isProcessing={false}
            onApprove={() => void handleEditorWriteApprove()}
            onReject={(reason) => void handleEditorWriteReject(reason)}
          />
        ) : confirmationStatus === 'idle' ? (
          <div style={{ borderRadius: '14px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', padding: '1.25rem', color: 'var(--color-text-muted)', fontSize: '0.85rem', textAlign: 'center' }}>
            <IconLoader style={{ width: '1rem', height: '1rem', display: 'inline-block', marginRight: '0.5rem' }} />
            {t('chat.editorWrite.loading')}
          </div>
        ) : confirmationStatus === 'confirming' ? (
          <StatusRow tone="warning" label={t('chat.editorWrite.processing')} />
        ) : confirmationStatus === 'confirmed' ? (
          <StatusRow tone="success" label={t('chat.editorWrite.accepted')} icon={<IconCheck style={{ width: '1rem', height: '1rem' }} />} />
        ) : (
          <StatusRow tone="danger" label={t('chat.editorWrite.rejected')} icon={<IconX style={{ width: '1rem', height: '1rem' }} />} />
        )}
      </div>
    );
  }

  return (
    <div style={{ width: '100%' }}>
      <div style={{ display: 'flex', flexDirection: 'column', borderRadius: '12px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
        <div onClick={() => setExpanded((value) => !value)} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '0.75rem 0.9rem', cursor: 'pointer' }}>
          <div style={{ display: 'grid', placeItems: 'center', width: '1.9rem', height: '1.9rem', borderRadius: '10px', background: 'var(--color-bg-surface)', color: isError ? '#d9534f' : isExecuting ? 'var(--color-action-link)' : 'var(--color-text-secondary)' }}>
            {isExecuting ? <IconLoader style={{ width: '0.95rem', height: '0.95rem' }} /> : isError ? <IconAlert /> : <IconTool />}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{title || toolName}</div>
            {toolSummaryText ? (
              <div style={{ marginTop: '0.15rem', fontSize: '0.78rem', color: 'var(--color-text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{toolSummaryText}</div>
            ) : null}
            {toolCommandText && toolCommandText !== toolSummaryText ? (
              <div style={{ marginTop: '0.15rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.72rem', color: 'var(--color-text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>$ {toolCommandText}</div>
            ) : null}
            <div style={{ marginTop: '0.15rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{partType}{providerExecuted !== undefined ? ` • ${providerExecuted ? 'provider' : 'local'} execution` : ''}</div>
          </div>
          <div style={{ color: 'var(--color-text-muted)' }}>{expanded ? <IconChevronUp style={{ width: '1rem', height: '1rem' }} /> : <IconChevronDown style={{ width: '1rem', height: '1rem' }} />}</div>
        </div>

        {expanded ? (
          <div style={{ padding: '0 0.9rem 0.9rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            <section style={{ borderRadius: '10px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-surface)', padding: '0.85rem' }}>
              <h5 style={{ margin: '0 0 0.5rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Tool info</h5>
              <div style={{ display: 'grid', gap: '0.3rem', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                <div>Type: {partType}</div>
                <div>Tool: {toolName}</div>
                <div>Call ID: <code>{toolCallId}</code></div>
                <div>Status: {state || 'pending'}</div>
                {title ? <div>Title: {title}</div> : null}
              </div>
            </section>
            <section style={{ borderRadius: '10px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-surface)', padding: '0.85rem' }}>
              <h5 style={{ margin: '0 0 0.5rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>Input</h5>
              <pre style={{ margin: 0, fontSize: '0.76rem', whiteSpace: 'pre-wrap', overflowX: 'auto', color: 'var(--color-text-secondary)' }}>{inputDisplay}</pre>
            </section>
            {outputDisplay ? (
              <section style={{ borderRadius: '10px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-surface)', padding: '0.85rem' }}>
                <h5 style={{ margin: '0 0 0.5rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{isError ? 'Error' : 'Output'}</h5>
                <pre style={{ margin: 0, fontSize: '0.76rem', whiteSpace: 'pre-wrap', overflowX: 'auto', color: isError ? 'var(--color-state-error)' : 'var(--color-text-secondary)' }}>{outputDisplay}</pre>
              </section>
            ) : null}
          </div>
        ) : null}

        {isExecuting ? <StatusRow tone="warning" label="Executing…" /> : null}
      </div>
    </div>
  );
}

function StatusRow({ tone, label, icon }: { tone: 'warning' | 'success' | 'danger'; label: string; icon?: ReactNode }) {
  const color = tone === 'success' ? '#22c55e' : tone === 'danger' ? '#d9534f' : 'var(--color-action-link)';
  return <div style={{ padding: '0 0.9rem 0.9rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', color, fontSize: '0.85rem' }}>{icon || <IconLoader style={{ width: '1rem', height: '1rem' }} />}{label}</div>;
}

export default ToolMessagePart;
