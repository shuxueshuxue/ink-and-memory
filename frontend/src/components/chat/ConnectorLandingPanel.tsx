// [Input] Connector API client and a callback that opens Settings' resource-link connector section.
// [Output] Chat `ResourceConnectorTab` content — a soft-surface `ConnectorEmptyState`
//          (三枚资源类型图标 + 标题 + 描述 + CTA), skeleton loading,
//          and non-button connector status panels with linked resource previews. Only explicit
//          management actions navigate to Settings' resource-link section; Chat never owns the
//          Notion configuration flow. Toolbar actions live beside `WorkspaceTabBar` in ChatView.
// [Pos] chat connector landing panel (ResourceConnectorTabPanel) in frontend/src/components/chat
// [Sync] 2026-07-08: initial Chat-to-Settings connector landing panel for the resource-link migration.
// [Sync] 2026-07-08: replace text-only loading state with a skeleton-screen placeholder, aligning
//                    with 《链接器概念的交互设计稿》 Chat 入口页「无资源链接」骨架屏 default state.
// [Sync] 2026-07-08: rebuild into `ResourceConnectorTabPanel` per docs/prd/notion-session/resource-connector.md
//                    §3.2 — add `ConnectorToolbar` (filter/sort), 三图标 empty state with「选择连接器」
//                    CTA.
// [Sync] 2026-07-08: route connector CTA/card selection back to Settings resource-link management,
//                    matching 《链接器概念的交互设计稿》 Chat 入口页.
// [Sync] 2026-07-08: replace light-only card/empty-state fills with semantic theme tokens so the Chat
//                    resource connector tab renders correctly under dark mode.
// [Sync] 2026-07-08: convert connector entries from full-card buttons to status panels with linked
//                    resource previews and an explicit 管理 action.
// [Sync] 2026-07-09: move scrolling into the linked-resource list and compress connector metadata
//                    into compact chips so the status panel itself stays stable.
// [Sync] 2026-07-09: remove the local filter/sort toolbar; ChatView renders active-tab actions
//                    at the same hierarchy as the WorkspaceTabBar.
// [Sync] 2026-07-09: render linked resources with scroll pagination so long source lists load
//                    page-by-page inside the resource list viewport.
// [Sync] 2026-07-09: listen for Settings resource saves and reload connector summaries so Chat
//                    status panels reflect newly mounted sources.
// [Sync] 2026-07-09: reduce Chat connector card styling; ConnectorStatusPanel keeps a dashed
//                    boundary but removes card fill/shadow while inner rows use soft hierarchy.
// [Sync] 2026-07-20: i18n — status/auth/sync labels, stat chips, empty state, and pagination
//                    hints resolve through the chat.connector namespace (en + zh) via useTranslation.
import { useCallback, useEffect, useState, type UIEvent } from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import {
  listConnectors,
  RESOURCE_CONNECTORS_CHANGED_EVENT,
  type ConnectorSource,
  type ResourceConnector,
} from '../../api/resourceConnectorApi';
import {
  IconChevronRight,
  IconClock,
  IconDatabase,
  IconFile,
  IconFolder,
  IconGrid,
} from './Icons';
import { SkeletonList } from './Skeleton';

interface ConnectorLandingPanelProps {
  /** Opens Settings and focuses the resource-link connector section. */
  onOpenConnector?: (connector: ResourceConnector | null) => void;
}

const LINKED_SOURCE_PAGE_SIZE = 6;
const CONNECTOR_SOFT_SURFACE = 'color-mix(in srgb, var(--color-bg-surface) 78%, transparent)';
const CONNECTOR_ROW_SURFACE = 'color-mix(in srgb, var(--color-bg-hover) 76%, var(--color-bg-surface))';
const CONNECTOR_CHIP_SURFACE = 'color-mix(in srgb, var(--color-bg-surface) 72%, transparent)';
const CONNECTOR_ROW_DIVIDER = '0 1px 0 color-mix(in srgb, var(--color-border-paper) 40%, transparent)';
const CONNECTOR_CONTROL_BORDER = '1px solid color-mix(in srgb, var(--color-border-paper) 58%, transparent)';

function formatLastInteraction(connector: ResourceConnector | null, t: TFunction): string {
  const value = connector?.lastSyncedAt ?? connector?.updatedAt ?? connector?.createdAt;
  if (!value) return t('chat.connector.noInteraction');

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function getConnectorStatusLabel(connector: ResourceConnector | null, t: TFunction): string {
  if (!connector) return t('chat.connector.status.notConnected');
  if (connector.status === 'authenticated' || connector.status === 'synced' || connector.auth.status === 'authenticated') {
    return t('chat.connector.status.healthy');
  }
  if (connector.status === 'authenticating' || connector.auth.status === 'authenticating') {
    return t('chat.connector.status.authenticating');
  }
  if (connector.status === 'expired' || connector.auth.status === 'expired') {
    return t('chat.connector.status.expired');
  }
  if (connector.status === 'error' || connector.auth.status === 'error') {
    return t('chat.connector.status.error');
  }
  return t('chat.connector.status.notConnected');
}

function getPlatformLabel(connector: ResourceConnector): string {
  return connector.platform === 'notion' ? 'Notion' : connector.platform;
}

function getAuthorizationStatusLabel(connector: ResourceConnector, t: TFunction): string {
  switch (connector.auth.status) {
    case 'authenticated':
      return t('chat.connector.auth.authenticated');
    case 'authenticating':
      return t('chat.connector.auth.authenticating');
    case 'expired':
      return t('chat.connector.auth.expired');
    case 'error':
      return t('chat.connector.auth.error');
    default:
      return t('chat.connector.auth.unauthorized');
  }
}

function getSyncStatusLabel(connector: ResourceConnector, t: TFunction): string {
  switch (connector.status) {
    case 'syncing':
      return t('chat.connector.sync.syncing');
    case 'synced':
    case 'authenticated':
      return t('chat.connector.sync.synced');
    case 'authenticating':
      return t('chat.connector.sync.waitingAuth');
    case 'expired':
      return t('chat.connector.sync.reauthNeeded');
    case 'error':
      return t('chat.connector.sync.error');
    default:
      return connector.sources.length > 0 ? t('chat.connector.sync.mounted') : t('chat.connector.sync.notSynced');
  }
}

function getSourceTypeLabel(type: ConnectorSource['type']): string {
  return type === 'notion_database' ? 'Database' : 'Page';
}

function getSourceStatusLabel(status: ConnectorSource['status'], t: TFunction): string {
  switch (status) {
    case 'syncing':
      return t('chat.connector.sync.syncing');
    case 'synced':
      return t('chat.connector.sync.synced');
    case 'error':
      return t('chat.connector.status.error');
    default:
      return t('chat.connector.sync.pendingSync');
  }
}

function ConnectorStatusPanel({ connector, onOpen }: { connector: ResourceConnector; onOpen: () => void }) {
  const { t } = useTranslation();
  const [visibleSourceCount, setVisibleSourceCount] = useState(LINKED_SOURCE_PAGE_SIZE);
  const healthy = connector.status === 'authenticated'
    || connector.status === 'synced'
    || connector.auth.status === 'authenticated';
  const statusLabel = getConnectorStatusLabel(connector, t);
  const lastInteraction = formatLastInteraction(connector, t);
  const metaItems = [
    [t('chat.connector.statAuth'), getAuthorizationStatusLabel(connector, t)],
    [t('chat.connector.statSync'), getSyncStatusLabel(connector, t)],
    [t('chat.connector.statResources'), t('chat.connector.resourceCount', { count: connector.sources.length })],
  ];
  const visibleSources = connector.sources.slice(0, visibleSourceCount);
  const hasMoreSources = visibleSourceCount < connector.sources.length;

  useEffect(() => {
    setVisibleSourceCount(LINKED_SOURCE_PAGE_SIZE);
  }, [connector.id, connector.sources.length]);

  const handleSourceListScroll = useCallback((event: UIEvent<HTMLDivElement>) => {
    if (!hasMoreSources) return;
    const target = event.currentTarget;
    const nearBottom = target.scrollTop + target.clientHeight >= target.scrollHeight - 20;
    if (!nearBottom) return;
    setVisibleSourceCount((current) => Math.min(current + LINKED_SOURCE_PAGE_SIZE, connector.sources.length));
  }, [connector.sources.length, hasMoreSources]);

  return (
    <article
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.65rem',
        border: '1px dashed color-mix(in srgb, var(--color-border-paper) 72%, transparent)',
        borderRadius: '0.65rem',
        background: 'transparent',
        padding: '0.68rem 0.72rem',
        boxShadow: 'none',
        textAlign: 'left',
        width: '100%',
        boxSizing: 'border-box',
      }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '2.25rem minmax(0, 1fr) auto', alignItems: 'start', gap: '0.7rem' }}>
        <div
          style={{
            width: '2.25rem',
            height: '2.25rem',
            borderRadius: '0.75rem',
            border: 'none',
            background: CONNECTOR_ROW_SURFACE,
            color: 'var(--color-text-primary)',
            display: 'grid',
            placeItems: 'center',
            flexShrink: 0,
          }}
        >
          <IconDatabase style={{ width: '1rem', height: '1rem' }} />
        </div>

        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.42rem', flexWrap: 'wrap' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
              {getPlatformLabel(connector)}
            </h3>
            <span
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.3rem',
                padding: '0.22rem 0.48rem',
                borderRadius: '999px',
                border: 'none',
                background: healthy ? 'color-mix(in srgb, var(--color-state-success) 16%, var(--color-bg-paper))' : 'var(--color-bg-hover)',
                color: healthy ? 'var(--color-state-success)' : 'var(--color-text-secondary)',
                fontSize: '0.68rem',
                fontWeight: 700,
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: '0.4rem',
                  height: '0.4rem',
                  borderRadius: '999px',
                  background: healthy ? 'var(--color-state-success)' : 'var(--color-text-muted)',
                }}
              />
              {statusLabel}
            </span>
          </div>
          <p style={{ margin: '0.24rem 0 0', fontSize: '0.76rem', lineHeight: 1.4, color: 'var(--color-text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {connector.name}
          </p>
          <div style={{ marginTop: '0.36rem', display: 'flex', alignItems: 'center', gap: '0.36rem', flexWrap: 'wrap' }}>
            {metaItems.map(([label, value]) => (
              <span
                key={label}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.24rem',
                  minWidth: 0,
                  maxWidth: '100%',
                  border: 'none',
                  borderRadius: '999px',
                  background: CONNECTOR_CHIP_SURFACE,
                  padding: '0.2rem 0.44rem',
                  color: 'var(--color-text-secondary)',
                  fontSize: '0.68rem',
                  fontWeight: 700,
                }}
              >
                <span style={{ color: 'var(--color-text-muted)', fontWeight: 600 }}>{label}</span>
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</span>
              </span>
            ))}
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.28rem', color: 'var(--color-text-muted)', fontSize: '0.7rem', minWidth: 0 }}>
              <IconClock style={{ width: '0.76rem', height: '0.76rem', flexShrink: 0 }} />
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t('chat.connector.lastInteraction', { time: lastInteraction })}</span>
            </span>
          </div>
        </div>

        <button
          type="button"
          onClick={onOpen}
          style={{
            justifySelf: 'end',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            border: CONNECTOR_CONTROL_BORDER,
            borderRadius: '999px',
            padding: '0.36rem 0.58rem',
            background: CONNECTOR_CHIP_SURFACE,
            color: 'var(--color-text-primary)',
            cursor: 'pointer',
            fontSize: '0.72rem',
            fontWeight: 700,
            whiteSpace: 'nowrap',
          }}
        >
          {t('chat.connector.manage')}
          <IconChevronRight style={{ width: '0.78rem', height: '0.78rem', color: 'var(--color-text-muted)' }} />
        </button>
      </div>

      <div style={{ display: 'grid', gap: '0.38rem', minHeight: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.6rem' }}>
          <div style={{ fontSize: '0.72rem', color: 'var(--color-text-muted)', fontWeight: 700 }}>{t('chat.connector.linkedResources')}</div>
          <div style={{ fontSize: '0.68rem', color: 'var(--color-text-muted)', fontWeight: 600 }}>{t('chat.connector.resourceCount', { count: connector.sources.length })}</div>
        </div>
        <div
          onScroll={handleSourceListScroll}
          style={{
            display: 'grid',
            gap: '0.36rem',
            maxHeight: '11rem',
            overflowY: connector.sources.length > 0 ? 'auto' : 'visible',
            paddingRight: connector.sources.length > 3 ? '0.18rem' : 0,
            scrollbarGutter: connector.sources.length > 3 ? 'stable' : 'auto',
          }}
        >
          {connector.sources.length > 0 ? visibleSources.map((source) => {
            const SourceIcon = source.type === 'notion_page' ? IconFile : IconDatabase;
            return (
              <div key={source.id} style={{ display: 'grid', gridTemplateColumns: '1.42rem minmax(0, 1fr) auto', alignItems: 'center', gap: '0.5rem', border: 'none', borderRadius: '0.62rem', background: CONNECTOR_ROW_SURFACE, padding: '0.42rem 0.5rem', boxShadow: CONNECTOR_ROW_DIVIDER }}>
                <span style={{ width: '1.42rem', height: '1.42rem', borderRadius: '0.44rem', display: 'grid', placeItems: 'center', color: 'var(--color-text-secondary)', background: CONNECTOR_CHIP_SURFACE }}>
                  <SourceIcon style={{ width: '0.76rem', height: '0.76rem' }} />
                </span>
                <span style={{ minWidth: 0 }}>
                  <span style={{ display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.76rem', color: 'var(--color-text-primary)', fontWeight: 650 }}>{source.title}</span>
                  <span style={{ display: 'block', marginTop: '0.08rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.66rem', color: 'var(--color-text-muted)' }}>
                    {getSourceTypeLabel(source.type)} · {getSourceStatusLabel(source.status, t)}
                    {typeof source.pageCount === 'number' ? ` · ${source.pageCount} pages` : ''}
                  </span>
                </span>
                <span style={{ fontSize: '0.66rem', color: 'var(--color-text-muted)', whiteSpace: 'nowrap' }}>
                  {formatLastInteraction({ ...connector, lastSyncedAt: source.syncedAt ?? source.updatedAt }, t)}
                </span>
              </div>
            );
          }) : (
            <div style={{ border: 'none', borderRadius: '0.68rem', background: CONNECTOR_ROW_SURFACE, padding: '0.55rem 0.62rem', color: 'var(--color-text-muted)', fontSize: '0.74rem' }}>
              {t('chat.connector.noLinkedResources')}
            </div>
          )}
          {connector.sources.length > 0 ? (
            <div style={{ padding: '0.2rem 0.1rem 0.05rem', color: 'var(--color-text-muted)', fontSize: '0.66rem', textAlign: 'center' }}>
              {hasMoreSources
                ? t('chat.connector.showingProgress', { shown: visibleSources.length, total: connector.sources.length })
                : t('chat.connector.showingAll', { count: connector.sources.length })}
            </div>
          ) : null}
        </div>
      </div>
    </article>
  );
}

function ConnectorEmptyState({ onSelectConnector }: { onSelectConnector: () => void }) {
  const { t } = useTranslation();
  return (
    <div
      style={{
        border: 'none',
        borderRadius: '1rem',
        background: CONNECTOR_SOFT_SURFACE,
        padding: '1.6rem 1.2rem',
        textAlign: 'center',
        boxShadow: '0 10px 24px color-mix(in srgb, var(--color-shadow-soft) 68%, transparent)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.6rem' }}>
        <span style={{ width: '2.2rem', height: '2.2rem', borderRadius: '0.7rem', border: 'none', background: CONNECTOR_ROW_SURFACE, display: 'grid', placeItems: 'center', color: 'var(--color-text-secondary)' }}>
          <IconDatabase style={{ width: '1rem', height: '1rem' }} />
        </span>
        <span style={{ width: '2.2rem', height: '2.2rem', borderRadius: '0.7rem', border: 'none', background: CONNECTOR_ROW_SURFACE, display: 'grid', placeItems: 'center', color: 'var(--color-text-secondary)' }}>
          <IconFolder style={{ width: '1rem', height: '1rem' }} />
        </span>
        <span style={{ width: '2.2rem', height: '2.2rem', borderRadius: '0.7rem', border: 'none', background: CONNECTOR_ROW_SURFACE, display: 'grid', placeItems: 'center', color: 'var(--color-text-secondary)' }}>
          <IconGrid style={{ width: '1rem', height: '1rem' }} />
        </span>
      </div>
      <h3 style={{ margin: '0.9rem 0 0', fontSize: '0.96rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
        {t('chat.connector.emptyTitle')}
      </h3>
      <p style={{ margin: '0.4rem auto 0', maxWidth: '28rem', fontSize: '0.82rem', lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
        {t('chat.connector.emptyDescription')}
      </p>
      <button
        type="button"
        onClick={onSelectConnector}
        style={{
          marginTop: '1.1rem',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.45rem',
          border: 'none',
          borderRadius: '999px',
          padding: '0.68rem 1rem',
          background: 'var(--color-action-link)',
          color: 'var(--color-text-on-action)',
          fontSize: '0.84rem',
          fontWeight: 700,
          cursor: 'pointer',
        }}
      >
        {t('chat.connector.selectConnector')}
        <IconChevronRight style={{ width: '0.9rem', height: '0.9rem' }} />
      </button>
    </div>
  );
}

export default function ConnectorLandingPanel({ onOpenConnector }: ConnectorLandingPanelProps) {
  const { t } = useTranslation();
  const [connectors, setConnectors] = useState<ResourceConnector[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadNonce, setReloadNonce] = useState(0);

  useEffect(() => {
    let active = true;

    void (async () => {
      setLoading(true);
      setError(null);

      try {
        const items = await listConnectors();
        if (active) {
          setConnectors(items);
        }
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : t('chat.connector.loadFailed'));
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [reloadNonce, t]);

  useEffect(() => {
    const handleConnectorsChanged = () => {
      setReloadNonce((value) => value + 1);
    };
    window.addEventListener(RESOURCE_CONNECTORS_CHANGED_EVENT, handleConnectorsChanged);
    return () => {
      window.removeEventListener(RESOURCE_CONNECTORS_CHANGED_EVENT, handleConnectorsChanged);
    };
  }, []);

  const handleSelectConnector = useCallback((connector: ResourceConnector | null) => {
    onOpenConnector?.(connector);
  }, [onOpenConnector]);

  const hasConnectors = connectors.length > 0;

  return (
    <section
      style={{
        flex: 1,
        minHeight: 0,
        minWidth: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: '0.75rem',
        border: 'none',
        borderRadius: '1.15rem',
        background: 'transparent',
        boxShadow: 'none',
        overflow: 'hidden',
        padding: '0.2rem 0 0',
      }}
    >
      <div style={{ flex: 1, minHeight: 0, overflowY: 'auto', display: 'grid', gap: '0.8rem' }}>
        {loading ? <SkeletonList rows={2} /> : null}

        {!loading && hasConnectors ? connectors.map((connector) => (
          <ConnectorStatusPanel key={connector.id} connector={connector} onOpen={() => handleSelectConnector(connector)} />
        )) : null}

        {!loading && !hasConnectors ? (
          <ConnectorEmptyState onSelectConnector={() => handleSelectConnector(null)} />
        ) : null}

        {error ? (
          <div style={{ fontSize: '0.78rem', color: 'var(--color-state-error)' }}>
            {error}
          </div>
        ) : null}
      </div>
    </section>
  );
}
