// [Input] Consume chat icon components and parent callbacks for expand/collapse and thread selection.
// [Output] Render theme-adaptive collapsible left rail; collapsed state shows only the expand trigger; expanded state shows inline thread list.
// [Pos] vertical-navigation component node in frontend/src/components/dashboard
// [Sync] 2026-05-25: remove Settings button from the chat/dashboard vertical nav.
// [Sync] 2026-05-29: keep foldable rail behavior while restoring theme colors and the original icon set.
// [Sync] 2026-05-29: expanded state becomes a full ChatGPT-style sidebar with new-chat button, search input, and inline thread list.
// [Sync] 2026-05-29: action buttons (new chat, files, history) moved to ChatView top-right floating bar; sidebar is now pure navigation/history panel.
import { useState } from 'react';
import { IconChevronLeft, IconGrid, IconTrash } from '../chat/Icons';

interface ThreadItem {
  id: string;
  title: string | null;
  updated_at: string;
}

interface VerticalNavProps {
  onExpandedChange?: (expanded: boolean) => void;
  onToggleFileSidebar?: () => void;
  threads?: ThreadItem[];
  activeThreadId?: string | null;
  onSelectThread?: (id: string) => void;
  onDeleteThread?: (id: string, e: React.MouseEvent) => void;
}


export default function VerticalNav({
  onExpandedChange,
  threads = [],
  activeThreadId = null,
  onSelectThread,
  onDeleteThread,
}: VerticalNavProps) {
  const [expanded, setExpanded] = useState(false);
  const railWidth = expanded ? '16rem' : '4rem';
  const updateExpanded = (next: boolean) => {
    setExpanded(next);
    onExpandedChange?.(next);
  };

  return (
    <aside style={{ width: railWidth, flexShrink: 0, display: 'flex', flexDirection: 'column', alignItems: 'stretch', padding: expanded ? '0.85rem 0.65rem' : '1.25rem 0.75rem', borderRight: '1px solid var(--color-border-paper)', background: 'var(--color-bg-app)', color: 'var(--color-text-primary)', transition: 'width 0.22s ease, padding 0.22s ease', boxSizing: 'border-box', overflow: 'hidden' }}>

      {/* Header row – expand / collapse trigger */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: expanded ? 'space-between' : 'center', height: '2.5rem', marginBottom: expanded ? '0.75rem' : '1.4rem', minWidth: 0, flexShrink: 0 }}>
        <button
          type="button"
          title={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          aria-label={expanded ? 'Collapse sidebar' : 'Expand sidebar'}
          onClick={() => updateExpanded(!expanded)}
          style={{ border: 'none', background: 'var(--color-action-link)', color: 'var(--color-text-on-action)', cursor: 'pointer', display: 'grid', placeItems: 'center', width: '2.2rem', height: '2.2rem', borderRadius: '12px', flexShrink: 0 }}
        >
          <IconGrid style={{ width: '1rem', height: '1rem' }} />
        </button>
        {expanded ? <span style={{ flex: 1 }} /> : null}
        {expanded ? (
          <button
            type="button"
            title="Collapse sidebar"
            aria-label="Collapse sidebar"
            onClick={() => updateExpanded(false)}
            style={{ border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', color: 'var(--color-text-secondary)', cursor: 'pointer', display: 'grid', placeItems: 'center', width: '2rem', height: '2rem', borderRadius: '0.65rem', flexShrink: 0 }}
          >
            <IconChevronLeft style={{ width: '1rem', height: '1rem' }} />
          </button>
        ) : null}
      </div>

      {expanded ? (
        /* Expanded: inline thread list */
        <div style={{ flex: 1, overflowY: 'auto' }}>
          {threads.length === 0 ? (
            <div style={{ padding: '0.55rem 0.4rem', color: 'var(--color-text-muted)', fontSize: '0.75rem' }}>暂无对话</div>
          ) : null}
          {threads.map((thread) => {
            const isActive = thread.id === activeThreadId;
            return (
              <div
                key={thread.id}
                onClick={() => onSelectThread?.(thread.id)}
                style={{ padding: '0.42rem 0.5rem', borderRadius: '0.65rem', cursor: 'pointer', background: isActive ? 'var(--color-bg-paper)' : 'transparent', border: isActive ? '1px solid var(--color-border-paper)' : '1px solid transparent', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.35rem', marginBottom: '0.1rem', transition: 'background 0.12s ease' }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && onSelectThread?.(thread.id)}
              >
                <span style={{ fontSize: '0.78rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1, color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)' }}>
                  {thread.title ?? '新对话'}
                </span>
                {isActive ? <span style={{ width: '0.38rem', height: '0.38rem', borderRadius: '999px', background: 'var(--color-action-link)', flexShrink: 0 }} aria-hidden="true" /> : null}
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); onDeleteThread?.(thread.id, e); }}
                  title="删除"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-text-muted)', display: 'grid', placeItems: 'center', width: '1.35rem', height: '1.35rem', borderRadius: '0.35rem', flexShrink: 0, padding: 0, opacity: 0.7 }}
                >
                  <IconTrash style={{ width: '0.75rem', height: '0.75rem' }} />
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        /* Collapsed: just the expand trigger (already in header); flex spacer below */
        <div style={{ flex: 1 }} />
      )}
    </aside>
  );
}
