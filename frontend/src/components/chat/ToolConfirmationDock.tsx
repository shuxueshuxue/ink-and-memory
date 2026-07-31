// [Input] PendingToolConfirmation descriptor from ChatPanel; confirmToolCall from toolConfirmation;
//         AskUserQuestionUI (unframed variant) for askuser questions; toolInputSummary helpers.
// [Output] Floating confirmation panel rendered above AIInputDock: generic tool approvals show
//          拒绝/同意, AskUserQuestion prompts show the option form with 取消/提交, and sandbox
//          network requests show the network-variant card (host + policy mode + 拒绝/同意).
// [Pos] tool-confirmation-dock component node in frontend/src/components/chat
// [Sync] 2026-07-20: created — tool confirmations moved out of the message list into this
//        floating dock (design: claude-agent-tool-confirmation-flow.md §8).
// [Sync] 2026-07-20: cap panel height at min(46vh, 24rem) with internal scroll and mount the
//        AskUserQuestion form in compact density so the dock never fills the chat viewport.
// [Sync] 2026-07-20: the dock now RENDERS IN PLACE OF AIInputDock (input dock hidden while a
//        confirmation is pending) instead of floating above it — the panel occupies the
//        composer slot in normal flow.
// [Sync] 2026-07-20: i18n — titles, status badges, button labels, and rejection reasons now
//        resolve through the chat.toolConfirmation namespace (en + zh) via useTranslation.
// [Sync] 2026-07-23: SandboxPermissionRequest — render a network-variant confirmation card
//        (target host + sandbox policy mode, binary 拒绝/同意, no "remember" in this iteration)
//        when kind==='sandbox-network'; generic card unchanged when the discriminator is absent
//        (design: claude-agent-sandbox-network-permission-tool.md §5A).
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import AskUserQuestionUI, { type AskUserQuestionInput } from './AskUserQuestionUI';
import { confirmToolCall, type PendingToolConfirmation } from './toolConfirmation';
import { isShellTool, resolveToolInputSummary, summarizeToolInvocation } from './toolInputSummary';
import { IconCheck, IconLoader, IconX } from './Icons';

type DockStatus = 'idle' | 'confirming' | 'confirmed' | 'rejected';

interface ToolConfirmationDockProps {
  confirmation: PendingToolConfirmation;
  threadId: string;
  addToolResult?: (params: { tool: string; toolCallId: string; output: unknown }) => void;
}

function KbdHint({ label }: { label: string }) {
  return (
    <span style={{ marginLeft: '0.4rem', fontSize: '0.68rem', opacity: 0.55, fontWeight: 500, letterSpacing: '0.02em' }}>{label}</span>
  );
}

export default function ToolConfirmationDock({ confirmation, threadId, addToolResult }: ToolConfirmationDockProps) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<DockStatus>('idle');
  const { kind, toolCallId, toolName, input } = confirmation;

  const summaryText = useMemo(() => summarizeToolInvocation(toolName, input), [toolName, input]);
  const commandText = useMemo(() => (isShellTool(toolName) ? resolveToolInputSummary(input).command : ''), [toolName, input]);
  const detailText = useMemo(() => {
    if (commandText) return commandText;
    if (input == null) return '';
    try {
      const json = JSON.stringify(input);
      return json.length > 240 ? `${json.slice(0, 240)}…` : json;
    } catch {
      return String(input);
    }
  }, [commandText, input]);

  const runConfirm = useCallback(async (approved: boolean, reason?: string, answers?: Record<string, unknown>) => {
    if (status !== 'idle') return;
    setStatus('confirming');
    try {
      const result = await confirmToolCall(threadId, toolCallId, approved, reason, answers);
      if (result.ok ?? result.success) {
        addToolResult?.({
          tool: toolName,
          toolCallId,
          output: answers ?? (approved ? { approved: true } : { approved: false, cancelled: true }),
        });
        setStatus(approved ? 'confirmed' : 'rejected');
        return;
      }
    } catch {
      // fall through — restore the panel so the user can retry
    }
    setStatus('idle');
  }, [addToolResult, status, threadId, toolCallId, toolName]);

  const handleApprove = useCallback(() => void runConfirm(true), [runConfirm]);
  const handleReject = useCallback(() => void runConfirm(false, t('chat.toolConfirmation.userRejectedTool')), [runConfirm, t]);
  const handleAskUserSubmit = useCallback((answers: Record<string, unknown>) => void runConfirm(true, undefined, answers), [runConfirm]);
  const handleAskUserCancel = useCallback(() => void runConfirm(false, t('chat.toolConfirmation.userCancelledAnswer')), [runConfirm, t]);

  // Keyboard shortcuts for the confirm variants (generic + sandbox network):
  // Esc = 拒绝, ⌘/Ctrl+⏎ = 同意.
  // The askuser variant keeps its own shortcuts inside AskUserQuestionUI.
  useEffect(() => {
    if (kind === 'askuser' || status !== 'idle') return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
        event.preventDefault();
        handleApprove();
      } else if (event.key === 'Escape') {
        event.preventDefault();
        handleReject();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleApprove, handleReject, kind, status]);

  const isAskUser = kind === 'askuser';
  const isSandboxNetwork = kind === 'sandbox-network';
  const networkRequest = confirmation.networkRequest ?? null;
  const networkPolicyModeText = networkRequest?.policyMode === 'allowlist'
    ? t('chat.toolConfirmation.networkPolicyAllowlist')
    : networkRequest?.policyMode === 'open'
      ? t('chat.toolConfirmation.networkPolicyOpen')
      : networkRequest?.policyMode || t('chat.toolConfirmation.unknownTool');
  const title = isAskUser
    ? t('chat.toolConfirmation.askUserTitle')
    : isSandboxNetwork
      ? t('chat.toolConfirmation.networkConfirmTitle', { tool: toolName || t('chat.toolConfirmation.unknownTool') })
      : t('chat.toolConfirmation.confirmTitle', { tool: toolName || t('chat.toolConfirmation.unknownTool') })
        + (summaryText ? t('chat.toolConfirmation.withSummary', { summary: summaryText }) : '');

  return (
    <div
      role="alertdialog"
      aria-label={title}
      style={{
        width: '100%',
        boxSizing: 'border-box',
        borderRadius: '18px',
        border: '1px solid var(--color-border-paper)',
        background: 'var(--color-bg-paper)',
        boxShadow: '0 12px 32px var(--color-shadow-soft, rgba(0,0,0,0.12))',
        padding: '0.85rem 1rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.55rem',
        // Cap the panel height so long AskUserQuestion forms never dominate the
        // chat viewport — the content scrolls internally instead.
        maxHeight: 'min(46vh, 24rem)',
        overflowY: 'auto',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.6rem' }}>
        <span aria-hidden="true" style={{ marginTop: '0.35rem', width: '0.55rem', height: '0.55rem', borderRadius: '999px', background: '#f59e0b', flexShrink: 0 }} />
        <div style={{ flex: 1, minWidth: 0, fontSize: '0.95rem', fontWeight: 600, lineHeight: 1.5, color: 'var(--color-text-primary)', wordBreak: 'break-word' }}>
          {title}
        </div>
        <span style={{ flexShrink: 0, borderRadius: '999px', padding: '0.15rem 0.55rem', fontSize: '0.72rem', fontWeight: 600, color: '#b45309', background: 'color-mix(in srgb, #f59e0b 16%, transparent)' }}>
          {isAskUser ? t('chat.toolConfirmation.pendingAnswer') : t('chat.toolConfirmation.pendingApproval')}
        </span>
      </div>

      {status === 'idle' && isAskUser ? (
        <AskUserQuestionUI
          input={(input ?? {}) as AskUserQuestionInput}
          toolCallId={toolCallId}
          toolName={toolName}
          isProcessing={false}
          framed={false}
          showHeader={false}
          compact
          onSubmit={handleAskUserSubmit}
          onCancel={handleAskUserCancel}
        />
      ) : status === 'idle' && isSandboxNetwork ? (
        <div
          style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '0.3rem',
            fontSize: '0.85rem',
            lineHeight: 1.65,
            color: 'var(--color-text-muted)',
            wordBreak: 'break-all',
          }}
        >
          <div>
            {t('chat.toolConfirmation.networkHostLabel')}
            <span style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', color: 'var(--color-text-primary)' }}>
              {networkRequest?.host ?? t('chat.toolConfirmation.networkHostUnknown')}
            </span>
          </div>
          <div>
            {t('chat.toolConfirmation.networkPolicyLabel')}
            {networkPolicyModeText}
          </div>
          {detailText ? (
            <div
              style={{
                fontFamily: commandText ? 'ui-monospace, SFMono-Regular, Menlo, monospace' : undefined,
                display: '-webkit-box',
                WebkitBoxOrient: 'vertical',
                WebkitLineClamp: 4,
                overflow: 'hidden',
              }}
            >
              {commandText ? `${t('chat.toolConfirmation.commandPrefix')}${detailText}` : `${t('chat.toolConfirmation.paramsPrefix')}${detailText}`}
            </div>
          ) : null}
        </div>
      ) : status === 'idle' && detailText ? (
        <div
          style={{
            fontSize: '0.85rem',
            lineHeight: 1.65,
            color: 'var(--color-text-muted)',
            fontFamily: commandText ? 'ui-monospace, SFMono-Regular, Menlo, monospace' : undefined,
            wordBreak: 'break-all',
            display: '-webkit-box',
            WebkitBoxOrient: 'vertical',
            WebkitLineClamp: 4,
            overflow: 'hidden',
          }}
        >
          {commandText ? `${t('chat.toolConfirmation.commandPrefix')}${detailText}` : `${t('chat.toolConfirmation.paramsPrefix')}${detailText}`}
        </div>
      ) : null}

      {status === 'idle' && !isAskUser ? (
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.6rem' }}>
          <button
            type="button"
            onClick={handleReject}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', borderRadius: '999px', padding: '0.5rem 1.05rem', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-surface)', color: 'var(--color-text-secondary)', fontSize: '0.86rem', fontWeight: 600, cursor: 'pointer' }}
          >
            {t('chat.toolConfirmation.reject')}
            <KbdHint label="ESC" />
          </button>
          <button
            type="button"
            onClick={handleApprove}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', borderRadius: '999px', padding: '0.5rem 1.05rem', border: 'none', background: 'var(--color-action-link)', color: 'var(--color-text-on-action)', fontSize: '0.86rem', fontWeight: 600, cursor: 'pointer' }}
          >
            {t('chat.toolConfirmation.approve')}
            <KbdHint label="⌘⏎" />
          </button>
        </div>
      ) : null}

      {status === 'confirming' ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', color: 'var(--color-action-link)', fontSize: '0.85rem' }}>
          <IconLoader style={{ width: '1rem', height: '1rem' }} />
          {isAskUser ? t('chat.toolConfirmation.submitting') : t('chat.toolConfirmation.processing')}
        </div>
      ) : null}
      {status === 'confirmed' ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', color: '#22c55e', fontSize: '0.85rem' }}>
          <IconCheck style={{ width: '1rem', height: '1rem' }} />
          {isAskUser ? t('chat.toolConfirmation.answerSubmitted') : t('chat.toolConfirmation.approved')}
        </div>
      ) : null}
      {status === 'rejected' ? (
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem', color: 'var(--color-state-error)', fontSize: '0.85rem' }}>
          <IconX style={{ width: '1rem', height: '1rem' }} />
          {isAskUser ? t('chat.toolConfirmation.cancelled') : t('chat.toolConfirmation.rejected')}
        </div>
      ) : null}
    </div>
  );
}
