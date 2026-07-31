// [Input] User-authored text message part from the chat message stream/history.
// [Output] Right-aligned user chat bubble with GFM Markdown rendering and a bottom-right copy action.
// [Pos] user-message-part component node in frontend/src/components/chat
// [Sync] 2026-06-02: created to render user prompt text as Markdown in ChatMessageList.
// [Sync] 2026-07-20: Markdown rendering delegated to shared ChatMarkdown so user messages
//                    render ```mermaid blocks through the same chain as assistant messages.
// [Sync] 2026-07-26: add bottom-right copy button under the bubble via shared useCopy hook
//                    and shared IconCopy/IconCheck, matching the assistant action style.
import { memo } from 'react';
import { useCopy } from '../../hooks/useCopy';
import { IconCheck, IconCopy } from './Icons';
import ChatMarkdown from './ChatMarkdown';

interface UserMessagePartProps {
  text: string;
}

export default memo(function UserMessagePart({ text }: UserMessagePartProps) {
  const { copied, copy } = useCopy();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '0.25rem' }}>
      <div
        style={{
          maxWidth: '85%',
          minWidth: 0,
          overflowWrap: 'anywhere',
          borderRadius: '18px',
          padding: '0.9rem 1rem',
          background: 'var(--color-bg-paper)',
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
        }}
      >
        <div className="prose prose-chat" style={{ color: 'var(--color-text-primary)', fontSize: '0.92rem', lineHeight: 1.7 }}>
          <ChatMarkdown text={text} />
        </div>
      </div>
      <button
        type="button"
        title="Copy"
        onClick={() => copy(text)}
        style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '1.9rem', height: '1.9rem', borderRadius: '0.5rem', border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}
      >
        {copied ? <IconCheck style={{ width: '0.95rem', height: '0.95rem' }} /> : <IconCopy style={{ width: '0.95rem', height: '0.95rem' }} />}
      </button>
    </div>
  );
});
