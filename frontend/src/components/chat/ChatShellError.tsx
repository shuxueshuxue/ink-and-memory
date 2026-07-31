// [Input] Chat shell error details, landing-tab state, and recovery callbacks.
// [Output] Render a warm-paper shell-level fallback with retry/reload actions and preserved Chat entry tabs.
// [Pos] chat-shell-error component node in frontend/src/components/chat
// [Sync] 2026-07-07: add a recoverable shell fallback so ChatViewContent failures do not white-screen the page.
// [Sync] 2026-07-08: replace light-only fallback gradients with semantic theme surfaces for dark mode.
// [Sync] 2026-07-20: i18n — landing tab labels resolve through the chat.shellError namespace (en + zh).
import { useTranslation } from 'react-i18next';
import { IconClock, IconDatabase, IconX } from './Icons';

export type ChatLandingTab = 'history' | 'connector';

interface ChatShellErrorProps {
  error: Error | null;
  landingTab: ChatLandingTab;
  onSelectLandingTab: (tab: ChatLandingTab) => void;
  onRetry: () => void;
  onReload: () => void;
  isMobile?: boolean;
}

function LandingTabButton({
  active,
  label,
  icon,
  onClick,
}: {
  active: boolean;
  label: string;
  icon: 'history' | 'connector';
  onClick: () => void;
}) {
  const Icon = icon === 'history' ? IconClock : IconDatabase;
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.45rem',
        padding: '0.62rem 0.95rem',
        borderRadius: '999px',
        border: `1px solid ${active ? 'var(--color-border-focus)' : 'var(--color-border-paper)'}`,
        background: active ? 'var(--color-bg-surface)' : 'transparent',
        color: 'var(--color-text-primary)',
        cursor: 'pointer',
        fontSize: '0.84rem',
        fontWeight: 700,
        boxShadow: active ? '0 10px 24px var(--color-shadow-soft)' : 'none',
      }}
    >
      <Icon style={{ width: '0.9rem', height: '0.9rem' }} />
      {label}
    </button>
  );
}

export default function ChatShellError({
  error,
  landingTab,
  onSelectLandingTab,
  onRetry,
  onReload,
  isMobile = false,
}: ChatShellErrorProps) {
  const { t } = useTranslation();
  return (
    <div
      style={{
        minHeight: '100%',
        display: 'grid',
        placeItems: 'center',
        padding: isMobile ? '1rem' : '1.5rem',
        background: 'var(--color-bg-app)',
        color: 'var(--color-text-primary)',
      }}
    >
      <div
        style={{
          width: 'min(52rem, 100%)',
          border: '1px solid var(--color-border-paper)',
          borderRadius: '28px',
          background: 'var(--color-bg-surface)',
          boxShadow: '0 24px 60px var(--color-shadow-medium)',
          padding: isMobile ? '1rem' : '1.25rem 1.25rem 1.15rem',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            justifyContent: 'space-between',
            gap: '1rem',
            flexWrap: 'wrap',
          }}
        >
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', flexWrap: 'wrap' }}>
              <span
                style={{
                  width: '2rem',
                  height: '2rem',
                  borderRadius: '999px',
                  display: 'inline-flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  background: 'color-mix(in srgb, var(--color-state-error) 14%, var(--color-bg-paper))',
                  color: 'var(--color-state-error)',
                  flexShrink: 0,
                }}
              >
                <IconX style={{ width: '1rem', height: '1rem' }} />
              </span>
              <div>
                <h1 style={{ margin: 0, fontSize: isMobile ? '1.2rem' : '1.35rem', fontWeight: 700 }}>
                  Chat shell temporarily unavailable
                </h1>
                <p style={{ margin: '0.3rem 0 0', fontSize: '0.86rem', lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
                  The shell hit a render error. The input entry, quick actions, and connector tab can be restored without leaving the page.
                </p>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={onRetry}
              style={{
                border: 'none',
                borderRadius: '999px',
                padding: '0.68rem 0.95rem',
                background: 'var(--color-text-primary)',
                color: 'var(--color-text-on-action)',
                cursor: 'pointer',
                fontSize: '0.86rem',
                fontWeight: 700,
              }}
            >
              Retry shell
            </button>
            <button
              type="button"
              onClick={onReload}
              style={{
                border: '1px solid var(--color-border-paper)',
                borderRadius: '999px',
                padding: '0.68rem 0.95rem',
                background: 'var(--color-bg-paper)',
                color: 'var(--color-text-secondary)',
                cursor: 'pointer',
                fontSize: '0.86rem',
                fontWeight: 600,
              }}
            >
              Reload shell
            </button>
          </div>
        </div>

        <div
          style={{
            marginTop: '1rem',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.55rem',
            flexWrap: 'wrap',
          }}
        >
          <LandingTabButton
            active={landingTab === 'history'}
            label={t('chat.shellError.history')}
            icon="history"
            onClick={() => {
              onSelectLandingTab('history');
            }}
          />
          <LandingTabButton
            active={landingTab === 'connector'}
            label={t('chat.shellError.connector')}
            icon="connector"
            onClick={() => {
              onSelectLandingTab('connector');
            }}
          />
        </div>

        <div
          style={{
            marginTop: '1rem',
            borderRadius: '20px',
            border: '1px solid color-mix(in srgb, var(--color-state-error) 20%, transparent)',
            background: 'color-mix(in srgb, var(--color-state-error) 6%, var(--color-bg-paper))',
            padding: '0.95rem 1rem',
          }}
        >
          <div style={{ fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>
            Recoverable error
          </div>
          <p style={{ margin: '0.45rem 0 0', fontSize: '0.86rem', lineHeight: 1.65, color: 'var(--color-text-primary)' }}>
            {error?.message || 'The Chat view failed to render. Use the buttons above to retry the current shell or reload the page.'}
          </p>
        </div>
      </div>
    </div>
  );
}
