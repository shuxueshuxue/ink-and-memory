// [Input] Assistant text message part from the chat message stream/history.
// [Output] Assistant message body with GFM Markdown (Mermaid diagrams included) plus message actions.
// [Pos] assistant-message-part component node in frontend/src/components/chat
// [Sync] 2026-07-20: Markdown rendering delegated to shared ChatMarkdown, which routes ```mermaid
//                    blocks to MermaidBlock and unwraps their <pre> wrapper (fixes the
//                    "[<pre /> in Markdown ...]" invalid-nesting error).
// [Sync] 2026-07-26: local IconCopy replaced by the shared Icons.tsx export so user and
//                    assistant bubbles reuse one copy affordance.
import { memo, useCallback, useMemo, useState, type ReactNode } from 'react';
import type { UIMessage } from 'ai';
import type { UseChatHelpers } from '@ai-sdk/react';
import { useCopy } from '../../hooks/useCopy';
import type { ChatMetadata } from '../../lib/chat-schema';
import { IconCheck, IconCopy, IconLoader, IconTrash } from './Icons';
import ChatMarkdown from './ChatMarkdown';

interface AssistMessagePartProps {
  part: { type: 'text'; text: string };
  isLast?: boolean;
  isLoading?: boolean;
  message: UIMessage;
  prevMessage?: UIMessage;
  showActions: boolean;
  isError?: boolean;
  readonly?: boolean;
  setMessages?: UseChatHelpers<UIMessage>['setMessages'];
  sendMessage?: UseChatHelpers<UIMessage>['sendMessage'];
}

function IconRefresh() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: '0.95rem', height: '0.95rem' }}>
      <polyline points="23 4 23 10 17 10" />
      <polyline points="1 20 1 14 7 14" />
      <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15" />
    </svg>
  );
}

function IconEllipsis() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" style={{ width: '0.95rem', height: '0.95rem' }}>
      <circle cx="12" cy="12" r="1" />
      <circle cx="19" cy="12" r="1" />
      <circle cx="5" cy="12" r="1" />
    </svg>
  );
}

export const AssistMessagePart = memo(function AssistMessagePart({
  part,
  isLast,
  showActions,
  message,
  prevMessage,
  isError,
  setMessages,
  readonly,
  sendMessage,
  isLoading: isStreamLoading,
}: AssistMessagePartProps) {
  const { copied, copy } = useCopy();
  const [isRetrying, setIsRetrying] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const metadata = message.metadata as ChatMetadata | undefined;

  const handleRetry = useCallback(async () => {
    if (!setMessages || !sendMessage || !prevMessage) {
      return;
    }
    setIsRetrying(true);
    try {
      setMessages((messages) => {
        const index = messages.findIndex((entry) => entry.id === message.id);
        return index >= 0 ? messages.slice(0, index) : messages;
      });
      await sendMessage(prevMessage);
    } finally {
      setIsRetrying(false);
    }
  }, [message.id, prevMessage, sendMessage, setMessages]);

  const handleDelete = useCallback(() => {
    if (!setMessages || readonly) {
      return;
    }
    const confirmed = window.confirm('Delete this message?');
    if (!confirmed) {
      return;
    }
    setIsDeleting(true);
    setMessages((messages) => messages.filter((entry) => entry.id !== message.id));
    setIsDeleting(false);
  }, [message.id, readonly, setMessages]);

  const metadataSummary = useMemo(() => {
    if (!metadata) {
      return null;
    }
    const parts: string[] = [];
    if (metadata.chatModel) {
      parts.push(`${metadata.chatModel.provider} / ${metadata.chatModel.model}`);
    }
    if (metadata.usage) {
      const { inputTokens, outputTokens, totalTokens } = metadata.usage;
      if (inputTokens != null) parts.push(`Input: ${inputTokens.toLocaleString()}`);
      if (outputTokens != null) parts.push(`Output: ${outputTokens.toLocaleString()}`);
      const total = totalTokens ?? ((inputTokens ?? 0) + (outputTokens ?? 0));
      if (total > 0) parts.push(`Total: ${total.toLocaleString()}`);
    }
    if (metadata.toolCount) {
      parts.push(`${metadata.toolCount} tools`);
    }
    return parts.length ? parts : null;
  }, [metadata]);

  const stepsCount = useMemo(
    () => message.parts.filter((entry) => entry.type !== 'step-start').length,
    [message.parts],
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', opacity: isError ? 0.6 : 1, minHeight: isLast && isStreamLoading ? '2rem' : undefined }}>
      <div style={{ color: 'var(--color-text-primary)', fontSize: '0.95rem', lineHeight: 1.75 }}>
        <div className="prose prose-chat">
          <ChatMarkdown text={part.text} />
        </div>
      </div>

      {showActions ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <ActionButton title="Copy" onClick={() => copy(part.text)}>
            {copied ? <IconCheck style={{ width: '0.95rem', height: '0.95rem' }} /> : <IconCopy style={{ width: '0.95rem', height: '0.95rem' }} />}
          </ActionButton>
          {!readonly && prevMessage && sendMessage ? (
            <ActionButton title="Regenerate" onClick={() => void handleRetry()} disabled={isRetrying || isStreamLoading}>
              {isRetrying ? <IconLoader style={{ width: '0.95rem', height: '0.95rem' }} /> : <IconRefresh />}
            </ActionButton>
          ) : null}
          {!readonly ? (
            <ActionButton title="Delete" onClick={handleDelete} disabled={isDeleting}>
              {isDeleting ? <IconLoader style={{ width: '0.95rem', height: '0.95rem' }} /> : <IconTrash style={{ width: '0.95rem', height: '0.95rem' }} />}
            </ActionButton>
          ) : null}
          {metadataSummary ? (
            <MetadataTooltip metadata={metadata!} metadataSummary={metadataSummary} stepsCount={stepsCount} />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}, (prev, next) => prev.part.text === next.part.text && prev.isError === next.isError && prev.isLast === next.isLast && prev.showActions === next.showActions && prev.isLoading === next.isLoading && prev.message.id === next.message.id && prev.readonly === next.readonly);

function ActionButton({ title, onClick, disabled, children }: { title: string; onClick: () => void; disabled?: boolean; children: ReactNode }) {
  return (
    <button type="button" title={title} onClick={onClick} disabled={disabled} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '1.9rem', height: '1.9rem', borderRadius: '0.5rem', border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.45 : 1 }}>
      {children}
    </button>
  );
}

function MetadataTooltip({ metadata, metadataSummary, stepsCount }: { metadata: ChatMetadata; metadataSummary: string[]; stepsCount: number }) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <div style={{ position: 'relative', marginLeft: 'auto' }}>
      <button type="button" title="Details" onMouseEnter={() => setIsOpen(true)} onMouseLeave={() => setIsOpen(false)} onClick={() => setIsOpen((value) => !value)} style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '1.9rem', height: '1.9rem', borderRadius: '0.5rem', border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}>
        <IconEllipsis />
      </button>
      {isOpen ? (
        <div onMouseEnter={() => setIsOpen(true)} onMouseLeave={() => setIsOpen(false)} style={{ position: 'absolute', right: 0, bottom: 'calc(100% + 0.5rem)', zIndex: 10, width: '18rem', borderRadius: '0.75rem', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', padding: '1rem', boxShadow: '0 4px 12px rgba(0,0,0,0.12)' }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
            {metadata.chatModel ? (
              <div>
                <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '0.35rem' }}>Model</div>
                <div style={{ fontSize: '0.85rem', color: 'var(--color-text-secondary)' }}>{metadata.chatModel.provider}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>{metadata.chatModel.model}</div>
              </div>
            ) : null}
            {metadata.usage ? (
              <div>
                <div style={{ fontSize: '0.74rem', fontWeight: 700, color: 'var(--color-text-primary)', marginBottom: '0.35rem' }}>Token usage · {stepsCount} steps</div>
                <div style={{ display: 'grid', gap: '0.35rem' }}>
                  <TokenRow label="Input" value={metadata.usage.inputTokens} />
                  <TokenRow label="Output" value={metadata.usage.outputTokens} />
                  <TokenRow label="Total" value={metadata.usage.totalTokens ?? ((metadata.usage.inputTokens ?? 0) + (metadata.usage.outputTokens ?? 0))} highlight />
                </div>
              </div>
            ) : null}
            <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>{metadataSummary.join(' · ')}</div>
          </div>
        </div>
      ) : null}
    </div>
  );
}

function TokenRow({ label, value, highlight }: { label: string; value?: number; highlight?: boolean }) {
  if (!value) {
    return null;
  }
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', borderRadius: '0.5rem', padding: '0.4rem 0.55rem', background: highlight ? 'rgba(74,144,226,0.12)' : 'var(--color-bg-surface)' }}>
      <span style={{ fontSize: '0.75rem', color: highlight ? 'var(--color-action-link)' : 'var(--color-text-muted)' }}>{label}</span>
      <span style={{ fontSize: '0.75rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', color: highlight ? 'var(--color-action-link)' : 'var(--color-text-primary)', fontWeight: 600 }}>{value.toLocaleString()}</span>
    </div>
  );
}

export default AssistMessagePart;
