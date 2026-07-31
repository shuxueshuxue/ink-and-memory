// [Input] Resource connector API client, dashboard design tokens, modal shell, and shared icon set.
// [Output] Warm-paper resource connector page with create/auth/select/source flows, status cards, and a legacy embedded mode that remains available for compatibility only.
// [Pos] resource-connector-page component node in frontend/src/components/dashboard
// [Sync] 2026-07-04: initial frontend shell for Notion resource connector create/auth/resources/source states.
// [Sync] 2026-07-04: warm the connector palette to match the paper-workbench design and soften the page shell contrast.
// [Sync] 2026-07-05: keep the connector workbench compatible with a scrollable app shell so lower resource and source sections remain reachable.
// [Sync] 2026-07-07: embedded connector shell now uses a dark Chat-adjacent layout with share/more header actions and list-style source rows to match the connector landing screenshot.
// [Sync] 2026-07-07: split embedded chat fallback workbench from the real source-selection empty state and keep the shell viewport-contained.
// [Sync] 2026-07-07: remove duplicate embedded title/description/tab chrome so Chat owns the page entry and the workbench starts at source actions.
// [Sync] 2026-07-08: embedded dark mode is compatibility-only; Settings now owns the connector entry and Chat keeps only the lightweight landing panel.
// [Sync] 2026-07-08: replace text-only "正在加载连接器…" first-load states (embedded and page mode
//                    connector list) with skeleton-screen placeholders, aligning with 《链接器概念的
//                    交互设计稿》「具体配置页面」骨架屏。
// [Sync] 2026-07-08: page-mode connector workbench now uses semantic surface, shadow, and state
//                    tokens so Settings/Chat detail pages render coherently in dark mode.
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  IconArrowUp,
  IconCheck,
  IconDatabase,
  IconEdit,
  IconLoader,
  IconFile,
  IconMoreHorizontal,
  IconPlus,
  IconSettings,
  IconShare,
  IconSparkles,
  IconTrash,
} from '../chat/Icons';
import Modal from '../chat/Modal';
import { SkeletonList } from '../chat/Skeleton';
import {
  createConnector,
  deleteConnector,
  listConnectorDatabases,
  listConnectorPages,
  listConnectors,
  normalizeResourceConnectorFallback,
  pollConnectorAuth,
  refreshConnectorSources,
  selectConnectorResources,
  startConnectorAuth,
  updateConnector,
  type ConnectorAuthStatus,
  type ConnectorResourceSelection,
  type ConnectorSource,
  type ConnectorStatus,
  type NotionResourceOption,
  type ResourceConnector,
} from '../../api/resourceConnectorApi';

interface ResourceConnectorPageProps {
  isMobile?: boolean;
  embedded?: boolean;
  variant?: 'page' | 'embedded';
  mode?: 'page' | 'embedded';
}

type ConnectorSurfaceTheme = 'light' | 'dark';

type StatusTone = 'neutral' | 'success' | 'warning' | 'danger' | 'info';

const DEFAULT_CONNECTOR_NAME = 'Resource Connector';
const EMBEDDED_FALLBACK_CONNECTOR_NAME = 'Ink&Memory开发';

type EmbeddedConnectorView = 'chat' | 'sources';

interface EmbeddedConnectorViewModel {
  chatConnector: ResourceConnector;
}

function buildEmbeddedFallbackConnector(): ResourceConnector {
  const now = new Date().toISOString();
  return normalizeResourceConnectorFallback({
    id: 'embedded-fallback-connector',
    name: EMBEDDED_FALLBACK_CONNECTOR_NAME,
    platform: 'notion',
    status: 'synced',
    createdAt: now,
    updatedAt: now,
    lastSyncedAt: now,
    auth: {
      status: 'authenticated',
      message: 'Fallback connector workbench is available while connector data is unavailable.',
    },
    sources: [
      {
        id: 'embedded-fallback-roadmap',
        title: '路线图',
        type: 'notion_database',
        status: 'synced',
        updatedAt: now,
        syncedAt: now,
        pageCount: 9,
        description: 'Milestones and release planning',
      },
      {
        id: 'embedded-fallback-brand-guide',
        title: '品牌规范',
        type: 'notion_page',
        status: 'synced',
        updatedAt: now,
        syncedAt: now,
        description: 'Standalone page',
      },
    ],
  });
}

function connectorTheme(theme: ConnectorSurfaceTheme) {
  if (theme === 'dark') {
    return {
      shellSurface: 'rgba(17, 17, 17, 0.94)',
      textPrimary: 'rgba(255,255,255,0.95)',
      textSecondary: 'rgba(255,255,255,0.66)',
      border: 'rgba(255,255,255,0.12)',
      borderStrong: 'rgba(255,255,255,0.2)',
      borderFocus: 'rgba(255,255,255,0.32)',
      cardBackground: 'rgba(255,255,255,0.05)',
      cardShadow: '0 14px 34px rgba(0, 0, 0, 0.34)',
    } as const;
  }

  return {
    shellSurface: 'var(--color-bg-paper)',
    textPrimary: 'var(--color-text-primary)',
    textSecondary: 'var(--color-text-secondary)',
    border: 'var(--color-border-paper)',
    borderStrong: 'var(--color-border-focus)',
    borderFocus: 'var(--color-border-focus)',
    cardBackground: 'var(--color-bg-surface)',
    cardShadow: '0 10px 20px var(--color-shadow-soft)',
  } as const;
}

function formatDateTime(value?: string): string {
  if (!value) return '未更新';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function formatStatusLabel(
  status?: ConnectorStatus | ConnectorSource['status'] | ConnectorAuthStatus | 'idle',
): string {
  switch (status) {
    case 'authenticating':
      return '认证中';
    case 'authenticated':
      return '已认证';
    case 'syncing':
      return '同步中';
    case 'synced':
      return '已同步';
    case 'expired':
      return '已过期';
    case 'error':
      return '错误';
    case 'draft':
      return '草稿';
    default:
      return '待处理';
  }
}

function statusTone(
  status?: ConnectorStatus | ConnectorSource['status'] | ConnectorAuthStatus | 'idle',
): StatusTone {
  switch (status) {
    case 'authenticated':
    case 'synced':
      return 'success';
    case 'authenticating':
    case 'syncing':
      return 'info';
    case 'expired':
      return 'warning';
    case 'error':
      return 'danger';
    default:
      return 'neutral';
  }
}

function sourceKindLabel(type: ConnectorSource['type']): string {
  return type === 'notion_database' ? 'Database' : 'Page';
}

function buildSelectionFromSources(sources: ConnectorSource[]): ConnectorResourceSelection {
  return {
    databaseIds: sources.filter((source) => source.type === 'notion_database').map((source) => source.id),
    pageIds: sources.filter((source) => source.type === 'notion_page').map((source) => source.id),
  };
}

function mergeConnector(connectors: ResourceConnector[], nextConnector: ResourceConnector): ResourceConnector[] {
  const index = connectors.findIndex((item) => item.id === nextConnector.id);
  if (index === -1) {
    return [nextConnector, ...connectors];
  }
  const next = connectors.slice();
  next[index] = nextConnector;
  return next;
}

function ConnectorStatusPill({
  status,
  theme = 'light',
}: {
  status: ConnectorStatus | ConnectorSource['status'] | ConnectorAuthStatus | 'idle';
  theme?: ConnectorSurfaceTheme;
}) {
  const tone = statusTone(status);
  const palette = theme === 'dark'
    ? {
        neutral: {
          background: 'rgba(255,255,255,0.06)',
          color: 'rgba(255,255,255,0.74)',
          border: 'rgba(255,255,255,0.12)',
        },
        success: {
          background: 'rgba(141, 167, 112, 0.16)',
          color: '#d9efd1',
          border: 'rgba(141, 167, 112, 0.26)',
        },
        warning: {
          background: 'rgba(199, 136, 85, 0.18)',
          color: '#f0c79f',
          border: 'rgba(199, 136, 85, 0.26)',
        },
        danger: {
          background: 'rgba(168, 102, 82, 0.18)',
          color: '#f3b7a8',
          border: 'rgba(168, 102, 82, 0.28)',
        },
        info: {
          background: 'rgba(255,255,255,0.08)',
          color: 'rgba(255,255,255,0.92)',
          border: 'rgba(255,255,255,0.16)',
        },
      }[tone]
    : {
        neutral: {
          background: 'var(--color-bg-hover)',
          color: 'var(--color-text-secondary)',
          border: 'var(--color-border-paper)',
        },
        success: {
          background: 'color-mix(in srgb, var(--color-state-success) 18%, var(--color-bg-paper))',
          color: 'var(--color-state-success)',
          border: 'color-mix(in srgb, var(--color-state-success) 34%, var(--color-border-paper))',
        },
        warning: {
          background: 'color-mix(in srgb, var(--color-state-warning) 18%, var(--color-bg-paper))',
          color: 'var(--color-state-warning)',
          border: 'color-mix(in srgb, var(--color-state-warning) 34%, var(--color-border-paper))',
        },
        danger: {
          background: 'color-mix(in srgb, var(--color-state-error) 18%, var(--color-bg-paper))',
          color: 'var(--color-state-error)',
          border: 'color-mix(in srgb, var(--color-state-error) 34%, var(--color-border-paper))',
        },
        info: {
          background: 'var(--color-bg-active)',
          color: 'var(--color-text-primary)',
          border: 'var(--color-border-paper)',
        },
      }[tone];

  return (
    <span
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.35rem',
        padding: '0.32rem 0.65rem',
        borderRadius: '999px',
        border: `1px solid ${palette.border}`,
        background: palette.background,
        color: palette.color,
        fontSize: '0.72rem',
        fontWeight: 600,
        letterSpacing: '0.02em',
        whiteSpace: 'nowrap',
      }}
    >
      <span
        style={{
          width: '0.4rem',
          height: '0.4rem',
          borderRadius: '999px',
          background: palette.color,
          opacity: 0.9,
        }}
      />
      {formatStatusLabel(status)}
    </span>
  );
}

function SectionCard({
  title,
  subtitle,
  action,
  children,
  compact = false,
  theme = 'light',
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  compact?: boolean;
  theme?: ConnectorSurfaceTheme;
}) {
  const palette = connectorTheme(theme);
  return (
    <section
      style={{
        width: '100%',
        minWidth: 0,
        boxSizing: 'border-box',
        border: `1px solid ${palette.border}`,
        borderRadius: compact ? '20px' : '24px',
        background: theme === 'dark' ? palette.shellSurface : 'var(--color-bg-paper)',
        boxShadow: theme === 'dark' ? '0 18px 44px rgba(0, 0, 0, 0.34)' : '0 14px 34px var(--color-shadow-soft)',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          padding: compact ? '0.85rem 0.95rem 0.72rem' : '1rem 1.15rem 0.85rem',
          borderBottom: `1px solid ${palette.border}`,
          background: theme === 'dark'
            ? 'linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0))'
            : 'var(--color-bg-surface)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: compact ? '0.9rem' : '0.96rem', fontWeight: 700, color: palette.textPrimary }}>{title}</h3>
            {subtitle ? (
              <p style={{ margin: '0.35rem 0 0', fontSize: compact ? '0.76rem' : '0.8rem', lineHeight: 1.55, color: palette.textSecondary }}>
                {subtitle}
              </p>
            ) : null}
          </div>
          {action}
        </div>
      </div>
      <div style={{ padding: compact ? '0.85rem 0.95rem 0.95rem' : '1rem 1.15rem 1.15rem' }}>{children}</div>
    </section>
  );
}

function ConnectorListItem({
  connector,
  isActive,
  onSelect,
}: {
  connector: ResourceConnector;
  isActive: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      style={{
        width: '100%',
        border: '1px solid',
        borderColor: isActive ? 'var(--color-border-focus)' : 'var(--color-border-paper)',
        background: isActive ? 'var(--color-bg-surface-solid)' : 'var(--color-bg-surface)',
        borderRadius: '18px',
        padding: '0.9rem',
        textAlign: 'left',
        cursor: 'pointer',
        boxShadow: isActive ? '0 16px 30px var(--color-shadow-soft)' : '0 10px 24px var(--color-shadow-soft)',
        color: 'var(--color-text-primary)',
        transition: 'transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.75rem' }}>
        <div
          style={{
            width: '2.4rem',
            height: '2.4rem',
            borderRadius: '0.9rem',
            display: 'grid',
            placeItems: 'center',
            background: 'var(--color-bg-hover)',
            border: '1px solid var(--color-border-paper)',
            color: 'var(--color-text-primary)',
            flexShrink: 0,
          }}
        >
          <IconDatabase style={{ width: '1rem', height: '1rem' }} />
        </div>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
            <h4
              style={{
                margin: 0,
                fontSize: '0.95rem',
                fontWeight: 700,
                color: 'var(--color-text-primary)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {connector.name}
            </h4>
            {isActive ? <IconCheck style={{ width: '0.95rem', height: '0.95rem', flexShrink: 0 }} /> : null}
          </div>
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.77rem', color: 'var(--color-text-secondary)' }}>
            {connector.platform.toUpperCase()} · {connector.sources.length} source{connector.sources.length === 1 ? '' : 's'}
          </p>
          <div style={{ marginTop: '0.7rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
            <ConnectorStatusPill status={connector.status} />
            <span style={{ fontSize: '0.72rem', color: 'var(--color-text-secondary)' }}>{formatDateTime(connector.updatedAt)}</span>
          </div>
        </div>
      </div>
    </button>
  );
}

function ToggleRow({
  label,
  helper,
  checked,
  onToggle,
  disabled,
  meta,
  theme = 'light',
}: {
  label: string;
  helper?: string;
  checked: boolean;
  onToggle: () => void;
  disabled?: boolean;
  meta?: string;
  theme?: ConnectorSurfaceTheme;
}) {
  const palette = connectorTheme(theme);
  return (
    <button
      type="button"
      onClick={onToggle}
      disabled={disabled}
      style={{
        width: '100%',
        border: `1px solid ${palette.border}`,
        borderRadius: '18px',
        background: checked
          ? theme === 'dark'
            ? 'linear-gradient(180deg, rgba(255,255,255,0.08), rgba(255,255,255,0.05))'
            : 'var(--color-bg-surface-solid)'
          : theme === 'dark'
            ? 'rgba(255,255,255,0.03)'
            : 'var(--color-bg-surface)',
        padding: '0.9rem 0.95rem',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.66 : 1,
        textAlign: 'left',
        boxShadow: checked
          ? theme === 'dark'
            ? '0 12px 28px rgba(0,0,0,0.24)'
            : '0 12px 26px var(--color-shadow-soft)'
          : 'none',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '0.85rem' }}>
        <span
          aria-hidden="true"
          style={{
            width: '1.15rem',
            height: '1.15rem',
            marginTop: '0.15rem',
            borderRadius: '0.35rem',
            border: `1px solid ${palette.border}`,
            background: checked ? (theme === 'dark' ? 'rgba(255,255,255,0.94)' : 'var(--color-text-primary)') : 'transparent',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: theme === 'dark' ? '#090909' : 'var(--color-text-on-action)',
            flexShrink: 0,
          }}
        >
          {checked ? <IconCheck style={{ width: '0.75rem', height: '0.75rem' }} /> : null}
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.8rem' }}>
            <span style={{ fontSize: '0.92rem', fontWeight: 600, color: palette.textPrimary }}>{label}</span>
            {meta ? <span style={{ fontSize: '0.72rem', color: palette.textSecondary }}>{meta}</span> : null}
          </div>
          {helper ? (
            <p style={{ margin: '0.35rem 0 0', fontSize: '0.78rem', lineHeight: 1.5, color: palette.textSecondary }}>{helper}</p>
          ) : null}
        </div>
      </div>
    </button>
  );
}

function SourceCard({ source, theme = 'light' }: { source: ConnectorSource; theme?: ConnectorSurfaceTheme }) {
  const palette = connectorTheme(theme);
  const SourceIcon = source.type === 'notion_page' ? IconFile : IconDatabase;
  return (
    <article
      style={{
        width: '100%',
        minWidth: 0,
        boxSizing: 'border-box',
        border: `1px solid ${palette.border}`,
        borderRadius: '18px',
        background: palette.cardBackground,
        padding: '0.9rem 0.95rem',
        boxShadow: palette.cardShadow,
      }}
    >
      {theme === 'dark' ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div
            style={{
              width: '3rem',
              height: '3rem',
              borderRadius: '0.9rem',
              display: 'grid',
              placeItems: 'center',
              background: 'rgba(255,255,255,0.12)',
              border: `1px solid ${palette.border}`,
              color: palette.textPrimary,
              flexShrink: 0,
            }}
          >
            <SourceIcon style={{ width: '1rem', height: '1rem' }} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <h5
              style={{
                margin: 0,
                fontSize: '0.95rem',
                lineHeight: 1.35,
                color: palette.textPrimary,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {source.title}
            </h5>
            <p style={{ margin: '0.22rem 0 0', fontSize: '0.78rem', lineHeight: 1.45, color: palette.textSecondary }}>
              {sourceKindLabel(source.type)} · {formatDateTime(source.syncedAt || source.updatedAt)}
            </p>
            {source.description ? (
              <p style={{ margin: '0.28rem 0 0', fontSize: '0.75rem', lineHeight: 1.45, color: palette.textSecondary }}>
                {source.description}
              </p>
            ) : null}
          </div>
          <div style={{ display: 'grid', gap: '0.35rem', justifyItems: 'end', flexShrink: 0 }}>
            <ConnectorStatusPill status={source.status} theme={theme} />
            {typeof source.pageCount === 'number' ? (
              <span style={{ fontSize: '0.72rem', color: palette.textSecondary }}>{source.pageCount} pages</span>
            ) : null}
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.85rem' }}>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: palette.textSecondary }}>
                {sourceKindLabel(source.type)}
              </span>
              <ConnectorStatusPill status={source.status} theme={theme} />
            </div>
            <h5
              style={{
                margin: '0.4rem 0 0',
                fontSize: '0.94rem',
                lineHeight: 1.4,
                color: palette.textPrimary,
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {source.title}
            </h5>
            <p style={{ margin: '0.35rem 0 0', fontSize: '0.76rem', color: palette.textSecondary }}>
              {source.description || 'Source synced from Notion'}
            </p>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0 }}>
            {typeof source.pageCount === 'number' ? (
              <div style={{ fontSize: '0.78rem', fontWeight: 700, color: palette.textPrimary }}>{source.pageCount} pages</div>
            ) : null}
            <div style={{ marginTop: '0.35rem', fontSize: '0.72rem', color: palette.textSecondary }}>
              {formatDateTime(source.syncedAt || source.updatedAt)}
            </div>
          </div>
        </div>
      )}
    </article>
  );
}

function ConnectorEmptyState({
  onCreate,
  compact = false,
  theme = 'light',
}: {
  onCreate: () => void;
  compact?: boolean;
  theme?: ConnectorSurfaceTheme;
}) {
  const palette = connectorTheme(theme);
  return (
    <div
      style={{
        width: '100%',
        minWidth: 0,
        boxSizing: 'border-box',
        border: `1px dashed ${palette.border}`,
        borderRadius: compact ? '24px' : '28px',
        background: theme === 'dark'
          ? 'linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.03))'
          : 'var(--color-bg-surface)',
        padding: compact ? '1.35rem 1.15rem' : '2rem 1.5rem',
        textAlign: 'center',
        boxShadow: theme === 'dark' ? '0 18px 44px rgba(0,0,0,0.28)' : '0 18px 40px var(--color-shadow-soft)',
      }}
    >
      <div
        style={{
          width: compact ? '3.2rem' : '4rem',
          height: compact ? '3.2rem' : '4rem',
          margin: '0 auto',
          borderRadius: compact ? '1.15rem' : '1.4rem',
          display: 'grid',
          placeItems: 'center',
          background: theme === 'dark' ? 'rgba(255,255,255,0.08)' : 'var(--color-bg-hover)',
          border: `1px solid ${palette.border}`,
          color: palette.textPrimary,
        }}
      >
        <IconSparkles style={{ width: compact ? '1.1rem' : '1.35rem', height: compact ? '1.1rem' : '1.35rem' }} />
      </div>
      <h3 style={{ margin: compact ? '0.75rem 0 0' : '1rem 0 0', fontSize: compact ? '1rem' : '1.15rem', color: palette.textPrimary }}>为工作区添加 Notion 连接器</h3>
      <p style={{ margin: compact ? '0.4rem auto 0' : '0.55rem auto 0', maxWidth: '34rem', fontSize: compact ? '0.84rem' : '0.9rem', lineHeight: 1.65, color: palette.textSecondary }}>
        创建一个资源连接器，完成 Notion 认证，选择可访问的数据库和页面，然后在同一张卡片里查看来源状态与同步信息。
      </p>
      <button
        type="button"
        onClick={onCreate}
        style={{
          marginTop: compact ? '1rem' : '1.25rem',
          border: 'none',
          borderRadius: '999px',
          background: theme === 'dark' ? 'rgba(255,255,255,0.92)' : 'var(--color-text-primary)',
          color: theme === 'dark' ? '#090909' : 'var(--color-text-on-action)',
          padding: compact ? '0.72rem 1rem' : '0.8rem 1.2rem',
          fontSize: compact ? '0.86rem' : '0.92rem',
          fontWeight: 700,
          cursor: 'pointer',
          display: 'inline-flex',
          alignItems: 'center',
          gap: '0.5rem',
          boxShadow: theme === 'dark' ? '0 16px 30px rgba(0,0,0,0.28)' : '0 16px 30px var(--color-shadow-medium)',
        }}
      >
        <IconPlus style={{ width: '1rem', height: '1rem' }} />
        新建连接器
      </button>
    </div>
  );
}

export default function ResourceConnectorPage({
  isMobile = false,
  embedded,
  variant,
  mode,
}: ResourceConnectorPageProps) {
  const isEmbedded = embedded ?? (variant === 'embedded' || mode === 'embedded');
  const compact = isEmbedded;
  const [connectors, setConnectors] = useState<ResourceConnector[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedConnectorId, setSelectedConnectorId] = useState<string | null>(null);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createName, setCreateName] = useState(DEFAULT_CONNECTOR_NAME);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createSaving, setCreateSaving] = useState(false);
  const [renameDraft, setRenameDraft] = useState('');
  const [renameEditing, setRenameEditing] = useState(false);
  const [renameSaving, setRenameSaving] = useState(false);
  const [resourceLoading, setResourceLoading] = useState(false);
  const [resourceError, setResourceError] = useState<string | null>(null);
  const [databaseOptions, setDatabaseOptions] = useState<NotionResourceOption[]>([]);
  const [pageOptions, setPageOptions] = useState<NotionResourceOption[]>([]);
  const [selectedDatabaseIds, setSelectedDatabaseIds] = useState<string[]>([]);
  const [selectedPageIds, setSelectedPageIds] = useState<string[]>([]);
  const [resourceSaving, setResourceSaving] = useState(false);
  const [authLoading, setAuthLoading] = useState(false);
  const [syncLoading, setSyncLoading] = useState(false);
  const [embeddedView, setEmbeddedView] = useState<EmbeddedConnectorView>('chat');
  const [embeddedShareCopied, setEmbeddedShareCopied] = useState(false);
  const [embeddedMenuOpen, setEmbeddedMenuOpen] = useState(false);
  const embeddedFallbackConnector = useMemo(() => buildEmbeddedFallbackConnector(), []);

  const selectedConnector = useMemo(
    () => connectors.find((connector) => connector.id === selectedConnectorId) ?? null,
    [connectors, selectedConnectorId],
  );

  const embeddedViewModel = useMemo<EmbeddedConnectorViewModel>(() => {
    const chatConnector = selectedConnector ?? embeddedFallbackConnector;
    return {
      chatConnector,
    };
  }, [embeddedFallbackConnector, selectedConnector]);

  const activeSelection = useMemo<ConnectorResourceSelection>(
    () => ({
      databaseIds: selectedDatabaseIds,
      pageIds: selectedPageIds,
    }),
    [selectedDatabaseIds, selectedPageIds],
  );

  const canEditResources = selectedConnector?.auth.status === 'authenticated';

  const upsertConnector = useCallback((nextConnector: ResourceConnector) => {
    setConnectors((current) => mergeConnector(current, nextConnector));
    setSelectedConnectorId(nextConnector.id);
  }, []);

  const reloadConnectors = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listConnectors();
      setConnectors(items);
      setSelectedConnectorId((current) => {
        if (current && items.some((item) => item.id === current)) {
          return current;
        }
        return items[0]?.id ?? null;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : '连接器列表加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reloadConnectors();
  }, [reloadConnectors]);

  useEffect(() => {
    if (!selectedConnectorId) return;
    const stillPresent = connectors.some((connector) => connector.id === selectedConnectorId);
    if (!stillPresent) {
      setSelectedConnectorId(connectors[0]?.id ?? null);
    }
  }, [connectors, selectedConnectorId]);

  useEffect(() => {
    if (!selectedConnector) {
      setRenameDraft('');
      setRenameEditing(false);
      setDatabaseOptions([]);
      setPageOptions([]);
      setSelectedDatabaseIds([]);
      setSelectedPageIds([]);
      setResourceError(null);
      return;
    }

    setRenameDraft(selectedConnector.name);
    setRenameEditing(false);

    if (selectedConnector.auth.status !== 'authenticated') {
      setDatabaseOptions([]);
      setPageOptions([]);
      setSelectedDatabaseIds([]);
      setSelectedPageIds([]);
      setResourceError(null);
      setResourceLoading(false);
      return;
    }

    let active = true;
    setResourceLoading(true);
    setResourceError(null);

    void (async () => {
      try {
        const [databases, pages] = await Promise.all([
          listConnectorDatabases(selectedConnector.id),
          listConnectorPages(selectedConnector.id),
        ]);
        if (!active) return;

        setDatabaseOptions(databases);
        setPageOptions(pages);

        const selection = buildSelectionFromSources(selectedConnector.sources);
        setSelectedDatabaseIds(selection.databaseIds);
        setSelectedPageIds(selection.pageIds);
      } catch (err) {
        if (!active) return;
        setResourceError(err instanceof Error ? err.message : '资源列表加载失败');
        setDatabaseOptions([]);
        setPageOptions([]);
      } finally {
        if (active) {
          setResourceLoading(false);
        }
      }
    })();

    return () => {
      active = false;
    };
  }, [selectedConnector, selectedConnector?.id, selectedConnector?.auth.status, selectedConnector?.name, selectedConnector?.sources]);

  useEffect(() => {
    if (!selectedConnector || selectedConnector.auth.status !== 'authenticating') {
      return undefined;
    }

    let active = true;
    let intervalId: number | null = null;

    const poll = async () => {
      if (!active) return;
      try {
        const next = await pollConnectorAuth(selectedConnector.id);
        if (!active || !next) return;
        upsertConnector(next);
      } catch (err) {
        if (!active) return;
        setResourceError(err instanceof Error ? err.message : '认证轮询失败');
      }
    };

    void poll();
    intervalId = window.setInterval(() => {
      void poll();
    }, 3500);

    return () => {
      active = false;
      if (intervalId !== null) {
        window.clearInterval(intervalId);
      }
    };
  }, [selectedConnector, selectedConnector?.id, selectedConnector?.auth.status, upsertConnector]);

  const openCreateModal = useCallback(() => {
    setCreateError(null);
    setCreateName(DEFAULT_CONNECTOR_NAME);
    setCreateModalOpen(true);
  }, []);

  const handleCreateConnector = useCallback(async () => {
    const name = createName.trim() || DEFAULT_CONNECTOR_NAME;
    setCreateSaving(true);
    setCreateError(null);
    try {
      const next = await createConnector({ name, platform: 'notion' });
      upsertConnector(next);
      setCreateModalOpen(false);
      setRenameDraft(next.name);
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : '创建连接器失败');
    } finally {
      setCreateSaving(false);
    }
  }, [createName, upsertConnector]);

  const handleStartAuth = useCallback(async () => {
    if (!selectedConnector) return;
    setAuthLoading(true);
    setResourceError(null);
    try {
      const next = await startConnectorAuth(selectedConnector.id);
      if (next) {
        upsertConnector(next);
      }
    } catch (err) {
      setResourceError(err instanceof Error ? err.message : '启动认证失败');
    } finally {
      setAuthLoading(false);
    }
  }, [selectedConnector, upsertConnector]);

  const handleSyncSources = useCallback(async () => {
    if (!selectedConnector) return;
    setSyncLoading(true);
    setResourceError(null);
    try {
      const next = await refreshConnectorSources(selectedConnector.id);
      if (next) {
        upsertConnector(next);
      }
    } catch (err) {
      setResourceError(err instanceof Error ? err.message : '同步来源失败');
    } finally {
      setSyncLoading(false);
    }
  }, [selectedConnector, upsertConnector]);

  const handleSaveResources = useCallback(async () => {
    if (!selectedConnector) return;
    setResourceSaving(true);
    setResourceError(null);
    try {
      const next = await selectConnectorResources(selectedConnector.id, activeSelection);
      if (next) {
        upsertConnector(next);
        const selection = buildSelectionFromSources(next.sources);
        setSelectedDatabaseIds(selection.databaseIds);
        setSelectedPageIds(selection.pageIds);
      }
    } catch (err) {
      setResourceError(err instanceof Error ? err.message : '保存资源选择失败');
    } finally {
      setResourceSaving(false);
    }
  }, [activeSelection, selectedConnector, upsertConnector]);

  const handleSaveRename = useCallback(async () => {
    if (!selectedConnector) return;
    const nextName = renameDraft.trim() || DEFAULT_CONNECTOR_NAME;
    if (nextName === selectedConnector.name) {
      setRenameEditing(false);
      return;
    }
    setRenameSaving(true);
    setResourceError(null);
    try {
      const next = await updateConnector(selectedConnector.id, { name: nextName });
      if (next) {
        upsertConnector(next);
      }
      setRenameEditing(false);
    } catch (err) {
      setResourceError(err instanceof Error ? err.message : '重命名失败');
    } finally {
      setRenameSaving(false);
    }
  }, [renameDraft, selectedConnector, upsertConnector]);

  const handleDeleteSelected = useCallback(async () => {
    if (!selectedConnector) return;
    const ok = window.confirm(`删除 ${selectedConnector.name} ?`);
    if (!ok) return;
    setResourceError(null);
    try {
      const success = await deleteConnector(selectedConnector.id);
      if (success) {
        setConnectors((current) => current.filter((item) => item.id !== selectedConnector.id));
        setSelectedConnectorId((current) => (current === selectedConnector.id ? null : current));
      }
    } catch (err) {
      setResourceError(err instanceof Error ? err.message : '删除连接器失败');
    }
  }, [selectedConnector]);

  const sourceStats = useMemo(() => {
    const sourceCount = selectedConnector?.sources.length ?? 0;
    const databases = selectedConnector?.sources.filter((source) => source.type === 'notion_database').length ?? 0;
    const pages = sourceCount - databases;
    return { sourceCount, databases, pages };
  }, [selectedConnector?.sources]);

  const handleEmbeddedShare = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setEmbeddedShareCopied(true);
      window.setTimeout(() => setEmbeddedShareCopied(false), 1600);
    } catch {
      setEmbeddedShareCopied(false);
    }
  }, []);

  if (isEmbedded) {
    const embeddedPalette = connectorTheme('dark');
    const { chatConnector } = embeddedViewModel;
    const chatSources = chatConnector.sources;

    return (
      <>
        <div
          style={{
            minHeight: '100%',
            height: '100%',
            width: '100%',
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
            padding: isMobile ? '0.7rem' : '0.9rem',
            boxSizing: 'border-box',
            background: '#050505',
            color: embeddedPalette.textPrimary,
          }}
        >
          <div
            style={{
              width: '100%',
              minWidth: 0,
              flex: 1,
              minHeight: 0,
              display: 'flex',
              flexDirection: 'column',
              border: `1px solid ${embeddedPalette.border}`,
              borderRadius: isMobile ? '28px' : '32px',
              background: 'linear-gradient(180deg, rgba(18,18,18,0.98), rgba(8,8,8,0.96))',
              boxShadow: '0 28px 80px rgba(0,0,0,0.58)',
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                padding: isMobile ? '0.72rem 0.85rem 0.2rem' : '0.82rem 1rem 0.25rem',
                flexShrink: 0,
                boxSizing: 'border-box',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.75rem', minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem', flexWrap: 'wrap', position: 'relative' }}>
                  <button
                    type="button"
                    onClick={() => void handleEmbeddedShare()}
                    style={{
                      border: `1px solid ${embeddedPalette.border}`,
                      borderRadius: '999px',
                      padding: '0.62rem 0.9rem',
                      background: 'rgba(255,255,255,0.06)',
                      color: embeddedPalette.textPrimary,
                      cursor: 'pointer',
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '0.45rem',
                      fontSize: '0.84rem',
                      fontWeight: 600,
                    }}
                  >
                    <IconShare style={{ width: '0.92rem', height: '0.92rem' }} />
                    {embeddedShareCopied ? '已复制链接' : '分享'}
                  </button>
                  <button
                    type="button"
                    onClick={() => setEmbeddedMenuOpen((current) => !current)}
                    style={{
                      border: `1px solid ${embeddedPalette.border}`,
                      borderRadius: '999px',
                      width: '2.35rem',
                      height: '2.35rem',
                      background: embeddedMenuOpen ? 'rgba(255,255,255,0.12)' : 'rgba(255,255,255,0.06)',
                      color: embeddedPalette.textPrimary,
                      cursor: 'pointer',
                      display: 'grid',
                      placeItems: 'center',
                      flexShrink: 0,
                    }}
                    title="更多"
                  >
                    <IconMoreHorizontal style={{ width: '1rem', height: '1rem' }} />
                  </button>
                  {embeddedMenuOpen ? (
                    <>
                      <div
                        aria-hidden="true"
                        style={{ position: 'fixed', inset: 0, zIndex: 14 }}
                        onClick={() => setEmbeddedMenuOpen(false)}
                      />
                      <div
                        style={{
                          position: 'absolute',
                          top: '2.9rem',
                          right: 0,
                          zIndex: 15,
                          minWidth: '12rem',
                          padding: '0.35rem',
                          border: `1px solid ${embeddedPalette.border}`,
                          borderRadius: '0.95rem',
                          background: 'rgba(8, 8, 8, 0.96)',
                          boxShadow: '0 20px 36px rgba(0, 0, 0, 0.36)',
                          backdropFilter: 'blur(12px)',
                        }}
                      >
                        <button
                          type="button"
                          onClick={() => {
                            setEmbeddedMenuOpen(false);
                            openCreateModal();
                          }}
                          style={{
                            width: '100%',
                            border: 'none',
                            borderRadius: '0.7rem',
                            padding: '0.72rem 0.8rem',
                            background: 'transparent',
                            color: embeddedPalette.textPrimary,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '0.5rem',
                            fontSize: '0.84rem',
                            fontWeight: 600,
                            textAlign: 'left',
                          }}
                        >
                          <span>新建</span>
                          <IconPlus style={{ width: '0.9rem', height: '0.9rem', color: embeddedPalette.textSecondary }} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEmbeddedMenuOpen(false);
                            void reloadConnectors();
                          }}
                          style={{
                            width: '100%',
                            border: 'none',
                            borderRadius: '0.7rem',
                            padding: '0.72rem 0.8rem',
                            background: 'transparent',
                            color: embeddedPalette.textPrimary,
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '0.5rem',
                            fontSize: '0.84rem',
                            fontWeight: 600,
                            textAlign: 'left',
                          }}
                        >
                          <span>刷新列表</span>
                          <IconArrowUp style={{ width: '0.9rem', height: '0.9rem', color: embeddedPalette.textSecondary }} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEmbeddedMenuOpen(false);
                            if (selectedConnector) {
                              void handleSyncSources();
                            }
                          }}
                          disabled={!selectedConnector}
                          style={{
                            width: '100%',
                            border: 'none',
                            borderRadius: '0.7rem',
                            padding: '0.72rem 0.8rem',
                            background: 'transparent',
                            color: embeddedPalette.textPrimary,
                            cursor: selectedConnector ? 'pointer' : 'not-allowed',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '0.5rem',
                            fontSize: '0.84rem',
                            fontWeight: 600,
                            textAlign: 'left',
                            opacity: selectedConnector ? 1 : 0.55,
                          }}
                        >
                          <span>{syncLoading ? '刷新中…' : '刷新来源'}</span>
                          <IconLoader style={{ width: '0.9rem', height: '0.9rem', color: embeddedPalette.textSecondary }} />
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setEmbeddedMenuOpen(false);
                            void handleDeleteSelected();
                          }}
                          disabled={!selectedConnector}
                          style={{
                            width: '100%',
                            border: 'none',
                            borderRadius: '0.7rem',
                            padding: '0.72rem 0.8rem',
                            background: 'transparent',
                            color: selectedConnector ? '#f3b7a8' : embeddedPalette.textSecondary,
                            cursor: selectedConnector ? 'pointer' : 'not-allowed',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '0.5rem',
                            fontSize: '0.84rem',
                            fontWeight: 600,
                            textAlign: 'left',
                            opacity: selectedConnector ? 1 : 0.55,
                          }}
                        >
                          <span>删除当前连接器</span>
                          <IconTrash style={{ width: '0.9rem', height: '0.9rem', color: selectedConnector ? '#f3b7a8' : embeddedPalette.textSecondary }} />
                        </button>
                      </div>
                    </>
                  ) : null}
                </div>
              </div>
            </div>

            <div
              style={{
                flex: 1,
                minHeight: 0,
                overflowY: 'auto',
                overflowX: 'hidden',
                padding: isMobile ? '0.9rem' : '1rem 1.15rem 1.15rem',
                boxSizing: 'border-box',
                overscrollBehavior: 'contain',
              }}
            >
              {embeddedView === 'chat' ? (
                <div style={{ display: 'grid', gap: '0.95rem', minWidth: 0 }}>
                  <button
                    type="button"
                    onClick={() => setEmbeddedView('sources')}
                    style={{
                      width: '100%',
                      border: 'none',
                      borderRadius: '18px',
                      padding: '0.2rem 0',
                      background: 'transparent',
                      color: embeddedPalette.textPrimary,
                      cursor: 'pointer',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '0.95rem',
                      textAlign: 'left',
                    }}
                  >
                    <span
                      style={{
                        width: '3rem',
                        height: '3rem',
                        borderRadius: '999px',
                        border: `1px solid ${embeddedPalette.border}`,
                        background: 'rgba(255,255,255,0.14)',
                        display: 'grid',
                        placeItems: 'center',
                        color: embeddedPalette.textPrimary,
                        flexShrink: 0,
                      }}
                    >
                      <IconPlus style={{ width: '1.1rem', height: '1.1rem' }} />
                    </span>
                    <span style={{ fontSize: '0.95rem', fontWeight: 700, letterSpacing: '0.01em' }}>添加源</span>
                  </button>
                  <div style={{ height: '1px', background: embeddedPalette.border }} />

                  {loading && connectors.length === 0 ? (
                    <div
                      style={{
                        border: `1px solid ${embeddedPalette.border}`,
                        borderRadius: '18px',
                        background: 'rgba(255,255,255,0.05)',
                        padding: '1rem',
                      }}
                    >
                      <SkeletonList rows={2} />
                    </div>
                  ) : error ? (
                    <div
                      style={{
                        border: '1px solid rgba(243, 183, 168, 0.28)',
                        borderRadius: '18px',
                        background: 'rgba(168, 102, 82, 0.12)',
                        padding: '1rem',
                        color: embeddedPalette.textPrimary,
                        lineHeight: 1.6,
                      }}
                    >
                      {error}
                    </div>
                  ) : chatSources.length === 0 ? (
                      <div
                        style={{
                          color: embeddedPalette.textSecondary,
                          fontSize: '0.84rem',
                          lineHeight: 1.65,
                          padding: '0.25rem 0 0',
                        }}
                      >
                        当前连接器还没有来源。点击「添加源」完成 Notion 认证、资源选择和同步后，这里会显示来源列表。
                      </div>
                  ) : (
                    <div style={{ display: 'grid', gap: '0.75rem', minWidth: 0 }}>
                      {chatSources.map((source) => (
                        <SourceCard key={source.id} source={source} theme="dark" />
                      ))}
                    </div>
                  )}
                </div>
              ) : !selectedConnector ? (
                <ConnectorEmptyState onCreate={openCreateModal} compact theme="dark" />
              ) : (
                <div style={{ display: 'grid', gap: '1rem', minWidth: 0 }}>
                  <SectionCard
                    title="连接器概览"
                    subtitle="可编辑名称、认证状态和基础操作都在这里。"
                    compact={compact}
                    theme="dark"
                    action={
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => setRenameEditing((current) => !current)}
                          style={{
                            border: `1px solid ${embeddedPalette.border}`,
                            borderRadius: '999px',
                            padding: '0.5rem 0.75rem',
                            background: 'rgba(255,255,255,0.05)',
                            color: embeddedPalette.textPrimary,
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                            fontSize: '0.78rem',
                            fontWeight: 600,
                          }}
                        >
                          <IconEdit style={{ width: '0.85rem', height: '0.85rem' }} />
                          {renameEditing ? '取消编辑' : '编辑名称'}
                        </button>
                        <button
                          type="button"
                          onClick={handleDeleteSelected}
                          style={{
                            border: '1px solid rgba(243, 183, 168, 0.24)',
                            borderRadius: '999px',
                            padding: '0.5rem 0.75rem',
                            background: 'rgba(168, 102, 82, 0.14)',
                            color: embeddedPalette.textPrimary,
                            cursor: 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.4rem',
                            fontSize: '0.78rem',
                            fontWeight: 600,
                          }}
                        >
                          <IconTrash style={{ width: '0.85rem', height: '0.85rem' }} />
                          删除
                        </button>
                      </div>
                    }
                  >
                    <div style={{ display: 'grid', gap: '0.9rem' }}>
                      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                        <div style={{ minWidth: 0, flex: 1 }}>
                          {renameEditing ? (
                            <div style={{ display: 'grid', gap: '0.5rem', maxWidth: '34rem' }}>
                              <label style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: embeddedPalette.textSecondary }}>
                                Connector name
                              </label>
                              <input
                                value={renameDraft}
                                onChange={(event) => setRenameDraft(event.target.value)}
                                onBlur={() => {
                                  void handleSaveRename();
                                }}
                                onKeyDown={(event) => {
                                  if (event.key === 'Enter') {
                                    event.preventDefault();
                                    void handleSaveRename();
                                  }
                                  if (event.key === 'Escape') {
                                    event.preventDefault();
                                    setRenameEditing(false);
                                    setRenameDraft(selectedConnector.name);
                                  }
                                }}
                                autoFocus
                                style={{
                                  width: '100%',
                                  border: `1px solid ${embeddedPalette.border}`,
                                  borderRadius: '18px',
                                  padding: '0.9rem 1rem',
                                  background: 'rgba(255,255,255,0.08)',
                                  color: embeddedPalette.textPrimary,
                                  fontSize: '1.05rem',
                                  fontWeight: 700,
                                  outline: 'none',
                                }}
                              />
                              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                                <button
                                  type="button"
                                  onClick={() => void handleSaveRename()}
                                  disabled={renameSaving}
                                  style={{
                                    border: 'none',
                                    borderRadius: '999px',
                                    padding: '0.6rem 0.9rem',
                                    background: 'rgba(255,255,255,0.92)',
                                    color: '#090909',
                                    cursor: 'pointer',
                                    fontSize: '0.82rem',
                                    fontWeight: 700,
                                  }}
                                >
                                  {renameSaving ? 'Saving…' : 'Save name'}
                                </button>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setRenameEditing(false);
                                    setRenameDraft(selectedConnector.name);
                                  }}
                                  style={{
                                    border: `1px solid ${embeddedPalette.border}`,
                                    borderRadius: '999px',
                                    padding: '0.6rem 0.9rem',
                                    background: 'rgba(255,255,255,0.05)',
                                    color: embeddedPalette.textPrimary,
                                    cursor: 'pointer',
                                    fontSize: '0.82rem',
                                    fontWeight: 600,
                                  }}
                                >
                                  Cancel
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div>
                              <h2
                                style={{
                                  margin: 0,
                                  fontSize: isMobile ? '1.35rem' : '1.65rem',
                                  fontFamily: 'Georgia, "Times New Roman", serif',
                                  color: embeddedPalette.textPrimary,
                                  lineHeight: 1.15,
                                }}
                              >
                                {selectedConnector.name}
                              </h2>
                              <p style={{ margin: '0.45rem 0 0', fontSize: '0.84rem', color: embeddedPalette.textSecondary }}>
                                {selectedConnector.platform.toUpperCase()} · {selectedConnector.sources.length} source
                                {selectedConnector.sources.length === 1 ? '' : 's'} · 最近更新 {formatDateTime(selectedConnector.updatedAt)}
                              </p>
                            </div>
                          )}
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <ConnectorStatusPill status={selectedConnector.status} theme="dark" />
                          <ConnectorStatusPill status={selectedConnector.auth.status} theme="dark" />
                        </div>
                      </div>

                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, minmax(0, 1fr))',
                          gap: '0.75rem',
                        }}
                      >
                        <div
                          style={{
                            border: `1px solid ${embeddedPalette.border}`,
                            borderRadius: '18px',
                            background: 'rgba(255,255,255,0.05)',
                            padding: '0.9rem',
                          }}
                        >
                          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: embeddedPalette.textSecondary }}>
                            Sources
                          </div>
                          <div style={{ marginTop: '0.35rem', fontSize: '1.25rem', fontWeight: 700, color: embeddedPalette.textPrimary }}>
                            {sourceStats.sourceCount}
                          </div>
                          <p style={{ margin: '0.3rem 0 0', fontSize: '0.78rem', color: embeddedPalette.textSecondary }}>
                            {sourceStats.databases} databases · {sourceStats.pages} pages
                          </p>
                        </div>
                        <div
                          style={{
                            border: `1px solid ${embeddedPalette.border}`,
                            borderRadius: '18px',
                            background: 'rgba(255,255,255,0.05)',
                            padding: '0.9rem',
                          }}
                        >
                          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: embeddedPalette.textSecondary }}>
                            Auth
                          </div>
                          <div style={{ marginTop: '0.35rem', fontSize: '1.25rem', fontWeight: 700, color: embeddedPalette.textPrimary }}>
                            {formatStatusLabel(selectedConnector.auth.status)}
                          </div>
                          <p style={{ margin: '0.3rem 0 0', fontSize: '0.78rem', color: embeddedPalette.textSecondary }}>
                            {selectedConnector.auth.message || 'Notion auth state is managed by the connector flow.'}
                          </p>
                        </div>
                        <div
                          style={{
                            border: `1px solid ${embeddedPalette.border}`,
                            borderRadius: '18px',
                            background: 'rgba(255,255,255,0.05)',
                            padding: '0.9rem',
                          }}
                        >
                          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: embeddedPalette.textSecondary }}>
                            Snapshot
                          </div>
                          <div style={{ marginTop: '0.35rem', fontSize: '1.25rem', fontWeight: 700, color: embeddedPalette.textPrimary }}>
                            {selectedConnector.lastSyncedAt ? 'Ready' : 'Pending'}
                          </div>
                          <p style={{ margin: '0.3rem 0 0', fontSize: '0.78rem', color: embeddedPalette.textSecondary }}>
                            {selectedConnector.lastSyncedAt ? formatDateTime(selectedConnector.lastSyncedAt) : '等待第一次同步'}
                          </p>
                        </div>
                      </div>

                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          onClick={() => void handleStartAuth()}
                          disabled={authLoading || selectedConnector.auth.status === 'authenticating'}
                          style={{
                            border: 'none',
                            borderRadius: '999px',
                            padding: '0.78rem 1rem',
                            background: 'rgba(255,255,255,0.92)',
                            color: '#090909',
                            cursor: authLoading || selectedConnector.auth.status === 'authenticating' ? 'not-allowed' : 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            fontSize: '0.88rem',
                            fontWeight: 700,
                          }}
                        >
                          <IconShare style={{ width: '0.95rem', height: '0.95rem' }} />
                          {selectedConnector.auth.status === 'authenticated'
                            ? '重新认证 Notion'
                            : selectedConnector.auth.status === 'authenticating'
                              ? '认证进行中'
                              : '连接 Notion'}
                        </button>
                        <button
                          type="button"
                          onClick={() => void handleSyncSources()}
                          disabled={syncLoading || !canEditResources}
                          style={{
                            border: `1px solid ${embeddedPalette.border}`,
                            borderRadius: '999px',
                            padding: '0.78rem 1rem',
                            background: 'rgba(255,255,255,0.05)',
                            color: embeddedPalette.textPrimary,
                            cursor: syncLoading || !canEditResources ? 'not-allowed' : 'pointer',
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            fontSize: '0.88rem',
                            fontWeight: 600,
                          }}
                        >
                          <IconArrowUp style={{ width: '0.95rem', height: '0.95rem' }} />
                          {syncLoading ? '同步中…' : '刷新来源'}
                        </button>
                      </div>
                    </div>
                  </SectionCard>

                  {selectedConnector.auth.status === 'authenticating' ? (
                    <SectionCard
                      title="Notion 认证"
                      subtitle="打开浏览器完成确认后，这里会自动轮询认证状态直到成功。"
                      compact={compact}
                      theme="dark"
                    >
                      <div
                        style={{
                          display: 'grid',
                          gridTemplateColumns: isMobile ? '1fr' : '1.1fr 0.9fr',
                          gap: '0.9rem',
                        }}
                      >
                        <div
                          style={{
                            border: `1px solid ${embeddedPalette.border}`,
                            borderRadius: '20px',
                            background: 'rgba(255,255,255,0.05)',
                            padding: '1rem',
                          }}
                        >
                          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: embeddedPalette.textSecondary }}>
                            Verification code
                          </div>
                          <div
                            style={{
                              marginTop: '0.55rem',
                              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                              fontSize: '1.3rem',
                              fontWeight: 700,
                              letterSpacing: '0.08em',
                              color: embeddedPalette.textPrimary,
                            }}
                          >
                            {selectedConnector.auth.verificationCode || '等待生成'}
                          </div>
                          <p style={{ margin: '0.65rem 0 0', fontSize: '0.84rem', lineHeight: 1.6, color: embeddedPalette.textSecondary }}>
                            {selectedConnector.auth.message || '在 Notion 中确认访问权限。'}
                          </p>
                        </div>
                        <div
                          style={{
                            border: `1px solid ${embeddedPalette.border}`,
                            borderRadius: '20px',
                            background: 'rgba(255,255,255,0.05)',
                            padding: '1rem',
                          }}
                        >
                          <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: embeddedPalette.textSecondary }}>
                            Browser step
                          </div>
                          <p style={{ margin: '0.55rem 0 0', fontSize: '0.84rem', lineHeight: 1.65, color: embeddedPalette.textSecondary }}>
                            打开浏览器确认后，认证状态会自动刷新。当前页面只负责展示状态与轮询，不处理 Notion CLI 逻辑。
                          </p>
                          {selectedConnector.auth.verificationUrl ? (
                            <a
                              href={selectedConnector.auth.verificationUrl}
                              target="_blank"
                              rel="noreferrer"
                              style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                gap: '0.45rem',
                                marginTop: '0.8rem',
                                color: embeddedPalette.textPrimary,
                                fontSize: '0.84rem',
                                fontWeight: 700,
                                textDecoration: 'none',
                              }}
                            >
                              <IconShare style={{ width: '0.9rem', height: '0.9rem' }} />
                              打开 Notion 验证页
                            </a>
                          ) : null}
                        </div>
                      </div>
                    </SectionCard>
                  ) : null}

                  <SectionCard
                    title="资源选择"
                    subtitle="认证完成后，从这里选择可访问的 Notion databases 和 standalone pages。"
                    compact={compact}
                    theme="dark"
                    action={
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <ConnectorStatusPill status={selectedConnector.auth.status} theme="dark" />
                        <button
                          type="button"
                          onClick={() => void handleSaveResources()}
                          disabled={!canEditResources || resourceSaving}
                          style={{
                            border: 'none',
                            borderRadius: '999px',
                            padding: '0.55rem 0.82rem',
                            background: 'rgba(255,255,255,0.92)',
                            color: '#090909',
                            cursor: !canEditResources || resourceSaving ? 'not-allowed' : 'pointer',
                            fontSize: '0.8rem',
                            fontWeight: 700,
                          }}
                        >
                          {resourceSaving ? '保存中…' : '保存选择'}
                        </button>
                      </div>
                    }
                  >
                    {!canEditResources ? (
                      <div
                        style={{
                          border: `1px dashed ${embeddedPalette.border}`,
                          borderRadius: '20px',
                          background: 'rgba(255,255,255,0.04)',
                          padding: '1rem',
                          color: embeddedPalette.textSecondary,
                          lineHeight: 1.65,
                        }}
                      >
                        完成 Notion 认证后，这里会列出可访问的数据库和页面。当前 connector 还未认证，资源选择会保持禁用。
                      </div>
                    ) : resourceLoading ? (
                      <div
                        style={{
                          border: `1px solid ${embeddedPalette.border}`,
                          borderRadius: '20px',
                          background: 'rgba(255,255,255,0.05)',
                          padding: '1rem',
                          color: embeddedPalette.textSecondary,
                          display: 'flex',
                          alignItems: 'center',
                          gap: '0.65rem',
                        }}
                      >
                        <IconLoader style={{ width: '1rem', height: '1rem' }} />
                        正在加载可访问资源…
                      </div>
                    ) : resourceError ? (
                      <div
                        style={{
                          border: '1px solid rgba(243, 183, 168, 0.24)',
                          borderRadius: '20px',
                          background: 'rgba(168, 102, 82, 0.14)',
                          padding: '1rem',
                          color: embeddedPalette.textPrimary,
                          lineHeight: 1.6,
                        }}
                      >
                        {resourceError}
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gap: '1rem' }}>
                        <div style={{ display: 'grid', gap: '0.85rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                            <div>
                              <h4 style={{ margin: 0, fontSize: '0.93rem', fontWeight: 700, color: embeddedPalette.textPrimary }}>Databases</h4>
                              <p style={{ margin: '0.35rem 0 0', fontSize: '0.78rem', color: embeddedPalette.textSecondary }}>
                                勾选连接器要同步的数据库。
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => setSelectedDatabaseIds(databaseOptions.map((option) => option.id))}
                              style={{
                                border: `1px solid ${embeddedPalette.border}`,
                                borderRadius: '999px',
                                padding: '0.48rem 0.72rem',
                                background: 'rgba(255,255,255,0.05)',
                                color: embeddedPalette.textPrimary,
                                cursor: 'pointer',
                                fontSize: '0.76rem',
                                fontWeight: 600,
                              }}
                            >
                              全选数据库
                            </button>
                          </div>
                          {databaseOptions.length === 0 ? (
                            <div
                              style={{
                                border: `1px dashed ${embeddedPalette.border}`,
                                borderRadius: '18px',
                                background: 'rgba(255,255,255,0.04)',
                                padding: '0.9rem',
                                color: embeddedPalette.textSecondary,
                              }}
                            >
                              没有可访问的 database。
                            </div>
                          ) : (
                            <div style={{ display: 'grid', gap: '0.65rem' }}>
                              {databaseOptions.map((option) => (
                                <ToggleRow
                                  key={option.id}
                                  label={option.title}
                                  helper={option.subtitle || 'Notion database'}
                                  checked={selectedDatabaseIds.includes(option.id)}
                                  onToggle={() => {
                                    setSelectedDatabaseIds((current) =>
                                      current.includes(option.id)
                                        ? current.filter((id) => id !== option.id)
                                        : [...current, option.id],
                                    );
                                  }}
                                  meta={typeof option.pageCount === 'number' ? `${option.pageCount} pages` : undefined}
                                  theme="dark"
                                />
                              ))}
                            </div>
                          )}
                        </div>

                        <div style={{ display: 'grid', gap: '0.85rem' }}>
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                            <div>
                              <h4 style={{ margin: 0, fontSize: '0.93rem', fontWeight: 700, color: embeddedPalette.textPrimary }}>Standalone Pages</h4>
                              <p style={{ margin: '0.35rem 0 0', fontSize: '0.78rem', color: embeddedPalette.textSecondary }}>
                                勾选连接器要同步的独立页面。
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() => setSelectedPageIds(pageOptions.map((option) => option.id))}
                              style={{
                                border: `1px solid ${embeddedPalette.border}`,
                                borderRadius: '999px',
                                padding: '0.48rem 0.72rem',
                                background: 'rgba(255,255,255,0.05)',
                                color: embeddedPalette.textPrimary,
                                cursor: 'pointer',
                                fontSize: '0.76rem',
                                fontWeight: 600,
                              }}
                            >
                              全选页面
                            </button>
                          </div>
                          {pageOptions.length === 0 ? (
                            <div
                              style={{
                                border: `1px dashed ${embeddedPalette.border}`,
                                borderRadius: '18px',
                                background: 'rgba(255,255,255,0.04)',
                                padding: '0.9rem',
                                color: embeddedPalette.textSecondary,
                              }}
                            >
                              没有可访问的 standalone page。
                            </div>
                          ) : (
                            <div style={{ display: 'grid', gap: '0.65rem' }}>
                              {pageOptions.map((option) => (
                                <ToggleRow
                                  key={option.id}
                                  label={option.title}
                                  helper={option.subtitle || 'Standalone page'}
                                  checked={selectedPageIds.includes(option.id)}
                                  onToggle={() => {
                                    setSelectedPageIds((current) =>
                                      current.includes(option.id)
                                        ? current.filter((id) => id !== option.id)
                                        : [...current, option.id],
                                    );
                                  }}
                                  theme="dark"
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </SectionCard>

                  <SectionCard
                    title="来源列表"
                    subtitle="这里显示 connector 已挂载的来源、同步状态和最近更新时间。"
                    compact={compact}
                    theme="dark"
                    action={
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span style={{ fontSize: '0.76rem', color: embeddedPalette.textSecondary }}>{selectedConnector.sources.length} items</span>
                        <IconSettings style={{ width: '0.95rem', height: '0.95rem', color: embeddedPalette.textSecondary }} />
                      </div>
                    }
                  >
                    {selectedConnector.sources.length === 0 ? (
                      <div
                        style={{
                          border: `1px dashed ${embeddedPalette.border}`,
                          borderRadius: '20px',
                          background: 'rgba(255,255,255,0.04)',
                          padding: '1rem',
                          color: embeddedPalette.textSecondary,
                          lineHeight: 1.65,
                        }}
                      >
                        当前还没有来源。完成认证并保存资源选择后，这里会出现 source cards。
                      </div>
                    ) : (
                      <div style={{ display: 'grid', gap: '0.75rem' }}>
                        {selectedConnector.sources.map((source) => (
                          <SourceCard key={source.id} source={source} theme="dark" />
                        ))}
                      </div>
                    )}
                  </SectionCard>

                  {selectedConnector.auth.status !== 'authenticated' ? (
                    <div
                      style={{
                        border: '1px solid rgba(243, 183, 168, 0.22)',
                        borderRadius: '20px',
                        background: 'rgba(199, 136, 85, 0.1)',
                        padding: '0.95rem 1rem',
                        color: embeddedPalette.textPrimary,
                        fontSize: '0.88rem',
                        lineHeight: 1.65,
                      }}
                    >
                      认证完成前，资源选择和来源刷新会保持禁用。点击上方按钮启动 Notion auth 后，页面会轮询状态直到完成或过期。
                    </div>
                  ) : null}
                </div>
              )}
            </div>
          </div>
        </div>

        <Modal
          open={createModalOpen}
          title="新建 Notion 连接器"
          onClose={() => {
            if (createSaving) return;
            setCreateModalOpen(false);
          }}
        >
          <div style={{ display: 'grid', gap: '0.9rem' }}>
            <div>
              <label style={{ display: 'block', marginBottom: '0.45rem', fontSize: '0.82rem', fontWeight: 700, color: 'var(--color-text-secondary)' }}>
                Connector name
              </label>
              <input
                value={createName}
                onChange={(event) => setCreateName(event.target.value)}
                placeholder={DEFAULT_CONNECTOR_NAME}
                autoFocus
                style={{
                  width: '100%',
                  border: '1px solid var(--color-border-paper)',
                  borderRadius: '16px',
                  background: 'var(--color-bg-paper)',
                  padding: '0.9rem 1rem',
                  fontSize: '0.95rem',
                  color: 'var(--color-text-primary)',
                  outline: 'none',
                }}
              />
            </div>
            <div
              style={{
                border: '1px dashed var(--color-border-paper)',
                borderRadius: '18px',
                background: 'var(--color-bg-surface)',
                padding: '0.9rem 1rem',
                fontSize: '0.84rem',
                lineHeight: 1.65,
                color: 'var(--color-text-secondary)',
              }}
            >
              当前只创建 Notion connector。创建后会自动进入同一工作台，接着发起认证、选择数据库和页面。
            </div>
            {createError ? (
              <div
                style={{
                  border: '1px solid color-mix(in srgb, var(--color-state-error) 34%, var(--color-border-paper))',
                  borderRadius: '18px',
                  background: 'color-mix(in srgb, var(--color-state-error) 12%, var(--color-bg-paper))',
                  padding: '0.9rem 1rem',
                  color: 'var(--color-state-error)',
                  fontSize: '0.84rem',
                  lineHeight: 1.6,
                }}
              >
                {createError}
              </div>
            ) : null}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.6rem' }}>
              <button
                type="button"
                onClick={() => setCreateModalOpen(false)}
                disabled={createSaving}
                style={{
                  border: '1px solid var(--color-border-paper)',
                  borderRadius: '999px',
                  padding: '0.68rem 0.95rem',
                  background: 'var(--color-bg-paper)',
                  color: 'var(--color-text-secondary)',
                  cursor: createSaving ? 'not-allowed' : 'pointer',
                  fontSize: '0.84rem',
                  fontWeight: 600,
                }}
              >
                取消
              </button>
              <button
                type="button"
                onClick={() => void handleCreateConnector()}
                disabled={createSaving}
                style={{
                  border: 'none',
                  borderRadius: '999px',
                  padding: '0.68rem 1rem',
                  background: 'var(--color-text-primary)',
                  color: 'var(--color-text-on-action)',
                  cursor: createSaving ? 'not-allowed' : 'pointer',
                  fontSize: '0.84rem',
                  fontWeight: 700,
                }}
              >
                {createSaving ? '创建中…' : '创建连接器'}
              </button>
            </div>
          </div>
        </Modal>
      </>
    );
  }

  return (
    <div
      style={{
        minHeight: '100%',
        height: isEmbedded ? '100%' : 'auto',
        display: 'flex',
        flexDirection: 'column',
        overflow: isEmbedded ? 'auto' : 'visible',
        padding: isEmbedded
          ? (isMobile ? '0.75rem 0.75rem 1rem' : '0.9rem')
          : (isMobile ? '1rem 1rem 5rem' : '1.5rem 1.5rem 2rem'),
        background: isEmbedded
          ? 'transparent'
          : 'var(--color-bg-app)',
        color: 'var(--color-text-primary)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: isEmbedded ? 'none' : '1220px',
          margin: isEmbedded ? 0 : '0 auto',
          border: '1px solid var(--color-border-paper)',
          borderRadius: isEmbedded ? '24px' : '32px',
          overflow: 'hidden',
          background: isEmbedded
            ? 'var(--color-bg-surface-solid)'
            : 'var(--color-bg-surface)',
          boxShadow: isEmbedded ? '0 18px 40px var(--color-shadow-soft)' : '0 30px 72px var(--color-shadow-medium)',
          backdropFilter: isEmbedded ? 'none' : 'blur(16px)',
          display: 'flex',
          flexDirection: 'column',
          minHeight: 0,
          flex: 1,
        }}
      >
        <div
          style={{
            padding: isEmbedded
              ? (isMobile ? '0.85rem' : '1rem 1.05rem')
              : (isMobile ? '1rem' : '1.2rem 1.25rem'),
            borderBottom: '1px solid var(--color-border-paper)',
            background:
              isEmbedded
                ? 'var(--color-bg-surface-solid)'
                : 'var(--color-bg-surface)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '0.45rem',
                    padding: '0.34rem 0.72rem',
                    borderRadius: '999px',
                    border: '1px solid var(--color-border-paper)',
                    background: 'var(--color-bg-hover)',
                    color: 'var(--color-text-secondary)',
                    fontSize: '0.72rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    letterSpacing: '0.12em',
                  }}
                >
                  <IconSparkles style={{ width: '0.82rem', height: '0.82rem' }} />
                  Resource Connector
                </span>
                <ConnectorStatusPill status={selectedConnector?.status ?? 'draft'} />
              </div>
              <h1
                style={{
                  margin: isEmbedded ? '0.6rem 0 0' : '0.8rem 0 0',
                  fontFamily: 'Georgia, "Times New Roman", serif',
                  fontSize: isEmbedded
                    ? (isMobile ? '1.35rem' : '1.7rem')
                    : (isMobile ? '1.65rem' : '2.15rem'),
                  fontWeight: 700,
                  lineHeight: 1.15,
                  color: 'var(--color-text-primary)',
                }}
              >
                创建、认证并查看 Notion 来源
              </h1>
              <p
                style={{
                  margin: isEmbedded ? '0.45rem 0 0' : '0.65rem 0 0',
                  maxWidth: isEmbedded ? '42rem' : '56rem',
                  fontSize: isEmbedded ? '0.84rem' : '0.95rem',
                  lineHeight: 1.6,
                  color: 'var(--color-text-secondary)',
                }}
              >
                这里是连接器工作台。先创建一个连接器，完成 Notion 认证，再选择数据库和页面，
                最后在来源卡片里检查同步状态与最新更新时间。
              </p>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={openCreateModal}
                style={{
                  border: 'none',
                  borderRadius: '999px',
                  padding: isEmbedded ? '0.72rem 0.95rem' : '0.82rem 1.1rem',
                  background: 'var(--color-text-primary)',
                  color: 'var(--color-text-on-action)',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                  fontSize: isEmbedded ? '0.84rem' : '0.9rem',
                  fontWeight: 700,
                  boxShadow: '0 16px 34px var(--color-shadow-medium)',
                }}
              >
                <IconPlus style={{ width: '1rem', height: '1rem' }} />
                新建连接器
              </button>
              <button
                type="button"
                onClick={() => void reloadConnectors()}
                style={{
                  border: '1px solid var(--color-border-paper)',
                  borderRadius: '999px',
                  padding: isEmbedded ? '0.72rem 0.9rem' : '0.82rem 1rem',
                  background: 'var(--color-bg-paper)',
                  color: 'var(--color-text-secondary)',
                  cursor: 'pointer',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.45rem',
                  fontSize: isEmbedded ? '0.82rem' : '0.88rem',
                  fontWeight: 600,
                }}
              >
                <IconArrowUp style={{ width: '0.95rem', height: '0.95rem' }} />
                刷新列表
              </button>
            </div>
          </div>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: isMobile ? '1fr' : isEmbedded ? '300px minmax(0, 1fr)' : '320px minmax(0, 1fr)',
            minHeight: isEmbedded ? 0 : (isMobile ? 'auto' : 'calc(100vh - 10rem)'),
            flex: isEmbedded ? 1 : undefined,
            overflow: isEmbedded ? 'hidden' : 'visible',
          }}
        >
          <aside
            style={{
              borderRight: isMobile ? 'none' : '1px solid var(--color-border-paper)',
              borderBottom: isMobile ? '1px solid var(--color-border-paper)' : 'none',
              padding: isEmbedded ? '0.85rem' : '1rem',
              background: 'var(--color-bg-surface)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', marginBottom: '0.9rem' }}>
              <div>
                <h2 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>连接器列表</h2>
                <p style={{ margin: '0.3rem 0 0', fontSize: '0.76rem', color: 'var(--color-text-secondary)' }}>
                  {connectors.length} connector{connectors.length === 1 ? '' : 's'}
                </p>
              </div>
              <span
                style={{
                  width: '2rem',
                  height: '2rem',
                  display: 'grid',
                  placeItems: 'center',
                  borderRadius: '0.8rem',
                  border: '1px solid var(--color-border-paper)',
                  background: 'var(--color-bg-hover)',
                  color: 'var(--color-text-secondary)',
                }}
              >
                <IconMoreHorizontal style={{ width: '1rem', height: '1rem' }} />
              </span>
            </div>

            {loading ? (
              <div
                style={{
                  border: '1px solid var(--color-border-paper)',
                  borderRadius: '20px',
                  background: 'var(--color-bg-surface)',
                  padding: '1rem',
                }}
              >
                <SkeletonList rows={2} />
              </div>
            ) : error ? (
              <div
                style={{
                  border: '1px solid color-mix(in srgb, var(--color-state-error) 34%, var(--color-border-paper))',
                  borderRadius: '20px',
                  background: 'color-mix(in srgb, var(--color-state-error) 12%, var(--color-bg-paper))',
                  padding: '1rem',
                  color: 'var(--color-state-error)',
                  fontSize: '0.88rem',
                  lineHeight: 1.6,
                }}
              >
                {error}
              </div>
            ) : connectors.length === 0 ? (
              <div
                style={{
                  border: '1px dashed var(--color-border-paper)',
                  borderRadius: '20px',
                  background: 'var(--color-bg-surface)',
                  padding: '1rem',
                  color: 'var(--color-text-secondary)',
                  lineHeight: 1.6,
                }}
              >
                还没有 connector。先创建一个 Notion 连接器，再开始认证和资源选择。
              </div>
            ) : (
              <div style={{ display: 'grid', gap: '0.75rem' }}>
                {connectors.map((connector) => (
                  <ConnectorListItem
                    key={connector.id}
                    connector={connector}
                    isActive={connector.id === selectedConnectorId}
                    onSelect={() => setSelectedConnectorId(connector.id)}
                  />
                ))}
              </div>
            )}
          </aside>

          <main style={{ padding: isEmbedded ? '0.85rem' : '1rem', background: 'var(--color-bg-paper)', minHeight: 0 }}>
            {!selectedConnector ? (
              <ConnectorEmptyState onCreate={openCreateModal} compact={compact} />
            ) : (
              <div style={{ display: 'grid', gap: '1rem' }}>
                <SectionCard
                  title="连接器概览"
                  subtitle="可编辑名称、认证状态和基础操作都在这里。"
                  compact={compact}
                  action={
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
                      <button
                        type="button"
                        onClick={() => setRenameEditing((current) => !current)}
                        style={{
                          border: '1px solid var(--color-border-paper)',
                          borderRadius: '999px',
                          padding: '0.5rem 0.75rem',
                          background: 'var(--color-bg-paper)',
                          color: 'var(--color-text-secondary)',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.4rem',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                        }}
                      >
                        <IconEdit style={{ width: '0.85rem', height: '0.85rem' }} />
                        {renameEditing ? '取消编辑' : '编辑名称'}
                      </button>
                      <button
                        type="button"
                        onClick={handleDeleteSelected}
                        style={{
                          border: '1px solid color-mix(in srgb, var(--color-state-error) 30%, var(--color-border-paper))',
                          borderRadius: '999px',
                          padding: '0.5rem 0.75rem',
                          background: 'color-mix(in srgb, var(--color-state-error) 12%, var(--color-bg-paper))',
                          color: 'var(--color-state-error)',
                          cursor: 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.4rem',
                          fontSize: '0.78rem',
                          fontWeight: 600,
                        }}
                      >
                        <IconTrash style={{ width: '0.85rem', height: '0.85rem' }} />
                        删除
                      </button>
                    </div>
                  }
                >
                  <div style={{ display: 'grid', gap: '0.9rem' }}>
                    <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        {renameEditing ? (
                          <div style={{ display: 'grid', gap: '0.5rem', maxWidth: '34rem' }}>
                            <label style={{ fontSize: '0.75rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-text-secondary)' }}>
                              Connector name
                            </label>
                            <input
                              value={renameDraft}
                              onChange={(event) => setRenameDraft(event.target.value)}
                              onBlur={() => {
                                void handleSaveRename();
                              }}
                              onKeyDown={(event) => {
                                if (event.key === 'Enter') {
                                  event.preventDefault();
                                  void handleSaveRename();
                                }
                                if (event.key === 'Escape') {
                                  event.preventDefault();
                                  setRenameEditing(false);
                                  setRenameDraft(selectedConnector.name);
                                }
                              }}
                              autoFocus
                              style={{
                                width: '100%',
                                border: '1px solid var(--color-border-paper)',
                                borderRadius: '18px',
                                padding: '0.9rem 1rem',
                                background: 'var(--color-bg-paper)',
                                color: 'var(--color-text-primary)',
                                fontSize: '1.05rem',
                                fontWeight: 700,
                                outline: 'none',
                                boxShadow: 'inset 0 1px 0 var(--color-shadow-soft)',
                              }}
                            />
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                              <button
                                type="button"
                                onClick={() => void handleSaveRename()}
                                disabled={renameSaving}
                                style={{
                                  border: 'none',
                                  borderRadius: '999px',
                                  padding: '0.6rem 0.9rem',
                                  background: 'var(--color-text-primary)',
                                  color: 'var(--color-text-on-action)',
                                  cursor: 'pointer',
                                  fontSize: '0.82rem',
                                  fontWeight: 700,
                                }}
                              >
                                {renameSaving ? 'Saving…' : 'Save name'}
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setRenameEditing(false);
                                  setRenameDraft(selectedConnector.name);
                                }}
                                style={{
                                  border: '1px solid var(--color-border-paper)',
                                  borderRadius: '999px',
                                  padding: '0.6rem 0.9rem',
                                  background: 'var(--color-bg-paper)',
                                  color: 'var(--color-text-secondary)',
                                  cursor: 'pointer',
                                  fontSize: '0.82rem',
                                  fontWeight: 600,
                                }}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <div>
                            <h2
                              style={{
                                margin: 0,
                                fontSize: isMobile ? '1.35rem' : '1.65rem',
                                fontFamily: 'Georgia, "Times New Roman", serif',
                                color: 'var(--color-text-primary)',
                                lineHeight: 1.15,
                              }}
                            >
                              {selectedConnector.name}
                            </h2>
                            <p style={{ margin: '0.45rem 0 0', fontSize: '0.84rem', color: 'var(--color-text-secondary)' }}>
                              {selectedConnector.platform.toUpperCase()} · {selectedConnector.sources.length} source
                              {selectedConnector.sources.length === 1 ? '' : 's'} · 最近更新 {formatDateTime(selectedConnector.updatedAt)}
                            </p>
                          </div>
                        )}
                      </div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <ConnectorStatusPill status={selectedConnector.status} />
                        <ConnectorStatusPill status={selectedConnector.auth.status} />
                      </div>
                    </div>

                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: isMobile ? '1fr' : 'repeat(3, minmax(0, 1fr))',
                        gap: '0.75rem',
                      }}
                    >
                      <div
                        style={{
                          border: '1px solid var(--color-border-paper)',
                          borderRadius: '18px',
                        background: 'var(--color-bg-surface)',
                          padding: '0.9rem',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--color-text-secondary)' }}>
                          Sources
                        </div>
                        <div style={{ marginTop: '0.35rem', fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                          {sourceStats.sourceCount}
                        </div>
                        <p style={{ margin: '0.3rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                          {sourceStats.databases} databases · {sourceStats.pages} pages
                        </p>
                      </div>
                      <div
                        style={{
                          border: '1px solid var(--color-border-paper)',
                          borderRadius: '18px',
                        background: 'var(--color-bg-surface)',
                          padding: '0.9rem',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--color-text-secondary)' }}>
                          Auth
                        </div>
                        <div style={{ marginTop: '0.35rem', fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                          {formatStatusLabel(selectedConnector.auth.status)}
                        </div>
                        <p style={{ margin: '0.3rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                          {selectedConnector.auth.message || 'Notion auth state is managed by the connector flow.'}
                        </p>
                      </div>
                      <div
                        style={{
                          border: '1px solid var(--color-border-paper)',
                          borderRadius: '18px',
                        background: 'var(--color-bg-surface)',
                          padding: '0.9rem',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--color-text-secondary)' }}>
                          Snapshot
                        </div>
                        <div style={{ marginTop: '0.35rem', fontSize: '1.25rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                          {selectedConnector.lastSyncedAt ? 'Ready' : 'Pending'}
                        </div>
                        <p style={{ margin: '0.3rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                          {selectedConnector.lastSyncedAt ? formatDateTime(selectedConnector.lastSyncedAt) : '等待第一次同步'}
                        </p>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <button
                        type="button"
                        onClick={() => void handleStartAuth()}
                        disabled={authLoading || selectedConnector.auth.status === 'authenticating'}
                        style={{
                          border: 'none',
                          borderRadius: '999px',
                          padding: '0.78rem 1rem',
                          background: 'var(--color-text-primary)',
                          color: 'var(--color-text-on-action)',
                          cursor: authLoading || selectedConnector.auth.status === 'authenticating' ? 'not-allowed' : 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          fontSize: '0.88rem',
                          fontWeight: 700,
                        }}
                      >
                        <IconShare style={{ width: '0.95rem', height: '0.95rem' }} />
                        {selectedConnector.auth.status === 'authenticated'
                          ? '重新认证 Notion'
                          : selectedConnector.auth.status === 'authenticating'
                            ? '认证进行中'
                            : '连接 Notion'}
                      </button>
                      <button
                        type="button"
                        onClick={() => void handleSyncSources()}
                        disabled={syncLoading || !canEditResources}
                        style={{
                          border: '1px solid var(--color-border-paper)',
                          borderRadius: '999px',
                          padding: '0.78rem 1rem',
                          background: 'var(--color-bg-paper)',
                          color: 'var(--color-text-secondary)',
                          cursor: syncLoading || !canEditResources ? 'not-allowed' : 'pointer',
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                          fontSize: '0.88rem',
                          fontWeight: 600,
                        }}
                      >
                        <IconArrowUp style={{ width: '0.95rem', height: '0.95rem' }} />
                        {syncLoading ? '同步中…' : '刷新来源'}
                      </button>
                    </div>
                  </div>
                </SectionCard>

                {selectedConnector.auth.status === 'authenticating' ? (
                  <SectionCard
                    title="Notion 认证"
                    subtitle="打开浏览器完成确认后，这里会自动轮询认证状态直到成功。"
                    compact={compact}
                  >
                    <div
                      style={{
                        display: 'grid',
                        gridTemplateColumns: isMobile ? '1fr' : '1.1fr 0.9fr',
                        gap: '0.9rem',
                      }}
                    >
                      <div
                        style={{
                          border: '1px solid var(--color-border-paper)',
                          borderRadius: '20px',
                          background: 'var(--color-bg-surface)',
                          padding: '1rem',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--color-text-secondary)' }}>
                          Verification code
                        </div>
                        <div
                          style={{
                            marginTop: '0.55rem',
                            fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
                            fontSize: '1.3rem',
                            fontWeight: 700,
                            letterSpacing: '0.08em',
                            color: 'var(--color-text-primary)',
                          }}
                        >
                          {selectedConnector.auth.verificationCode || '等待生成'}
                        </div>
                        <p style={{ margin: '0.65rem 0 0', fontSize: '0.84rem', lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
                          {selectedConnector.auth.message || '在 Notion 中确认访问权限。'}
                        </p>
                      </div>
                      <div
                        style={{
                          border: '1px solid var(--color-border-paper)',
                          borderRadius: '20px',
                          background: 'var(--color-bg-surface)',
                          padding: '1rem',
                        }}
                      >
                        <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--color-text-secondary)' }}>
                          Browser step
                        </div>
                        <p style={{ margin: '0.55rem 0 0', fontSize: '0.84rem', lineHeight: 1.65, color: 'var(--color-text-secondary)' }}>
                          打开浏览器确认后，认证状态会自动刷新。当前页面只负责展示状态与轮询，不处理 Notion CLI 逻辑。
                        </p>
                        {selectedConnector.auth.verificationUrl ? (
                          <a
                            href={selectedConnector.auth.verificationUrl}
                            target="_blank"
                            rel="noreferrer"
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              gap: '0.45rem',
                              marginTop: '0.8rem',
                              color: 'var(--color-text-primary)',
                              fontSize: '0.84rem',
                              fontWeight: 700,
                              textDecoration: 'none',
                            }}
                          >
                            <IconShare style={{ width: '0.9rem', height: '0.9rem' }} />
                            打开 Notion 验证页
                          </a>
                        ) : null}
                      </div>
                    </div>
                  </SectionCard>
                ) : null}

                <SectionCard
                  title="资源选择"
                  subtitle="认证完成后，从这里选择可访问的 Notion databases 和 standalone pages。"
                  compact={compact}
                  action={
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <ConnectorStatusPill status={selectedConnector.auth.status} />
                      <button
                        type="button"
                        onClick={() => void handleSaveResources()}
                        disabled={!canEditResources || resourceSaving}
                        style={{
                          border: 'none',
                          borderRadius: '999px',
                          padding: '0.55rem 0.82rem',
                          background: 'var(--color-text-primary)',
                          color: 'var(--color-text-on-action)',
                          cursor: !canEditResources || resourceSaving ? 'not-allowed' : 'pointer',
                          fontSize: '0.8rem',
                          fontWeight: 700,
                        }}
                      >
                        {resourceSaving ? '保存中…' : '保存选择'}
                      </button>
                    </div>
                  }
                >
                  {!canEditResources ? (
                    <div
                      style={{
                        border: '1px dashed var(--color-border-paper)',
                        borderRadius: '20px',
                        background: 'var(--color-bg-surface)',
                        padding: '1rem',
                        color: 'var(--color-text-secondary)',
                        lineHeight: 1.65,
                      }}
                    >
                      完成 Notion 认证后，这里会列出可访问的数据库和页面。当前 connector 还未认证，资源选择会保持禁用。
                    </div>
                  ) : resourceLoading ? (
                    <div
                      style={{
                        border: '1px solid var(--color-border-paper)',
                        borderRadius: '20px',
                        background: 'var(--color-bg-surface)',
                        padding: '1rem',
                        color: 'var(--color-text-secondary)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '0.65rem',
                      }}
                    >
                      <IconLoader style={{ width: '1rem', height: '1rem' }} />
                      正在加载可访问资源…
                    </div>
                  ) : resourceError ? (
                    <div
                      style={{
                        border: '1px solid color-mix(in srgb, var(--color-state-error) 34%, var(--color-border-paper))',
                        borderRadius: '20px',
                        background: 'color-mix(in srgb, var(--color-state-error) 12%, var(--color-bg-paper))',
                        padding: '1rem',
                        color: 'var(--color-state-error)',
                        lineHeight: 1.6,
                      }}
                    >
                      {resourceError}
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gap: '1rem' }}>
                      <div style={{ display: 'grid', gap: '0.85rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                          <div>
                            <h4 style={{ margin: 0, fontSize: '0.93rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>Databases</h4>
                            <p style={{ margin: '0.35rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                              勾选连接器要同步的数据库。
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => setSelectedDatabaseIds(databaseOptions.map((option) => option.id))}
                            style={{
                              border: '1px solid var(--color-border-paper)',
                              borderRadius: '999px',
                              padding: '0.48rem 0.72rem',
                              background: 'var(--color-bg-paper)',
                              color: 'var(--color-text-secondary)',
                              cursor: 'pointer',
                              fontSize: '0.76rem',
                              fontWeight: 600,
                            }}
                          >
                            全选数据库
                          </button>
                        </div>
                        {databaseOptions.length === 0 ? (
                          <div
                            style={{
                              border: '1px dashed var(--color-border-paper)',
                              borderRadius: '18px',
                              background: 'var(--color-bg-surface)',
                              padding: '0.9rem',
                              color: 'var(--color-text-secondary)',
                            }}
                          >
                            没有可访问的 database。
                          </div>
                        ) : (
                          <div style={{ display: 'grid', gap: '0.65rem' }}>
                            {databaseOptions.map((option) => (
                              <ToggleRow
                                key={option.id}
                                label={option.title}
                                helper={option.subtitle || 'Notion database'}
                                checked={selectedDatabaseIds.includes(option.id)}
                                onToggle={() => {
                                  setSelectedDatabaseIds((current) =>
                                    current.includes(option.id)
                                      ? current.filter((id) => id !== option.id)
                                      : [...current, option.id],
                                  );
                                }}
                                meta={typeof option.pageCount === 'number' ? `${option.pageCount} pages` : undefined}
                              />
                            ))}
                          </div>
                        )}
                      </div>

                      <div style={{ display: 'grid', gap: '0.85rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
                          <div>
                            <h4 style={{ margin: 0, fontSize: '0.93rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>Standalone Pages</h4>
                            <p style={{ margin: '0.35rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
                              勾选连接器要同步的独立页面。
                            </p>
                          </div>
                          <button
                            type="button"
                            onClick={() => setSelectedPageIds(pageOptions.map((option) => option.id))}
                            style={{
                              border: '1px solid var(--color-border-paper)',
                              borderRadius: '999px',
                              padding: '0.48rem 0.72rem',
                              background: 'var(--color-bg-paper)',
                              color: 'var(--color-text-secondary)',
                              cursor: 'pointer',
                              fontSize: '0.76rem',
                              fontWeight: 600,
                            }}
                          >
                            全选页面
                          </button>
                        </div>
                        {pageOptions.length === 0 ? (
                          <div
                            style={{
                              border: '1px dashed var(--color-border-paper)',
                              borderRadius: '18px',
                              background: 'var(--color-bg-surface)',
                              padding: '0.9rem',
                              color: 'var(--color-text-secondary)',
                            }}
                          >
                            没有可访问的 standalone page。
                          </div>
                        ) : (
                          <div style={{ display: 'grid', gap: '0.65rem' }}>
                            {pageOptions.map((option) => (
                              <ToggleRow
                                key={option.id}
                                label={option.title}
                                helper={option.subtitle || 'Standalone page'}
                                checked={selectedPageIds.includes(option.id)}
                                onToggle={() => {
                                  setSelectedPageIds((current) =>
                                    current.includes(option.id)
                                      ? current.filter((id) => id !== option.id)
                                      : [...current, option.id],
                                  );
                                }}
                              />
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </SectionCard>

                <SectionCard
                  title="来源列表"
                  subtitle="这里显示 connector 已挂载的来源、同步状态和最近更新时间。"
                  compact={compact}
                  action={
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ fontSize: '0.76rem', color: 'var(--color-text-secondary)' }}>{selectedConnector.sources.length} items</span>
                      <IconSettings style={{ width: '0.95rem', height: '0.95rem', color: 'var(--color-text-secondary)' }} />
                    </div>
                  }
                >
                  {selectedConnector.sources.length === 0 ? (
                    <div
                      style={{
                        border: '1px dashed var(--color-border-paper)',
                        borderRadius: '20px',
                        background: 'var(--color-bg-surface)',
                        padding: '1rem',
                        color: 'var(--color-text-secondary)',
                        lineHeight: 1.65,
                      }}
                    >
                      当前还没有来源。完成认证并保存资源选择后，这里会出现 source cards。
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gap: '0.75rem' }}>
                      {selectedConnector.sources.map((source) => (
                        <SourceCard key={source.id} source={source} />
                      ))}
                    </div>
                  )}
                </SectionCard>

                {selectedConnector.auth.status !== 'authenticated' ? (
                  <div
                    style={{
                      border: '1px solid color-mix(in srgb, var(--color-state-warning) 34%, var(--color-border-paper))',
                      borderRadius: '20px',
                      background: 'color-mix(in srgb, var(--color-state-warning) 12%, var(--color-bg-paper))',
                      padding: '0.95rem 1rem',
                      color: 'var(--color-text-primary)',
                      fontSize: '0.88rem',
                      lineHeight: 1.65,
                    }}
                  >
                    认证完成前，资源选择和来源刷新会保持禁用。点击上方按钮启动 Notion auth 后，页面会轮询状态直到完成或过期。
                  </div>
                ) : null}
              </div>
            )}
          </main>
        </div>
      </div>

      <Modal
        open={createModalOpen}
        title="新建 Notion 连接器"
        onClose={() => {
          if (createSaving) return;
          setCreateModalOpen(false);
        }}
      >
        <div style={{ display: 'grid', gap: '0.9rem' }}>
          <div>
            <label style={{ display: 'block', marginBottom: '0.45rem', fontSize: '0.82rem', fontWeight: 700, color: 'var(--color-text-secondary)' }}>
              Connector name
            </label>
            <input
              value={createName}
              onChange={(event) => setCreateName(event.target.value)}
              placeholder={DEFAULT_CONNECTOR_NAME}
              autoFocus
              style={{
                width: '100%',
                border: '1px solid var(--color-border-paper)',
                borderRadius: '16px',
                background: 'var(--color-bg-paper)',
                padding: '0.9rem 1rem',
                fontSize: '0.95rem',
                color: 'var(--color-text-primary)',
                outline: 'none',
              }}
            />
          </div>
          <div
            style={{
              border: '1px dashed var(--color-border-paper)',
              borderRadius: '18px',
              background: 'var(--color-bg-surface)',
              padding: '0.9rem 1rem',
              fontSize: '0.84rem',
              lineHeight: 1.65,
              color: 'var(--color-text-secondary)',
            }}
          >
            当前只创建 Notion connector。创建后会自动进入同一工作台，接着发起认证、选择数据库和页面。
          </div>
          {createError ? (
            <div
              style={{
                border: '1px solid color-mix(in srgb, var(--color-state-error) 34%, var(--color-border-paper))',
                borderRadius: '16px',
                background: 'color-mix(in srgb, var(--color-state-error) 12%, var(--color-bg-paper))',
                padding: '0.85rem 0.95rem',
                color: 'var(--color-state-error)',
                fontSize: '0.86rem',
                lineHeight: 1.6,
              }}
            >
              {createError}
            </div>
          ) : null}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: '0.7rem', flexWrap: 'wrap' }}>
            <button
              type="button"
              onClick={() => setCreateModalOpen(false)}
              disabled={createSaving}
              style={{
                border: '1px solid var(--color-border-paper)',
                borderRadius: '999px',
                padding: '0.75rem 1rem',
                background: 'var(--color-bg-paper)',
                color: 'var(--color-text-secondary)',
                cursor: createSaving ? 'not-allowed' : 'pointer',
                fontSize: '0.86rem',
                fontWeight: 600,
              }}
            >
              取消
            </button>
            <button
              type="button"
              onClick={() => void handleCreateConnector()}
              disabled={createSaving}
              style={{
                border: 'none',
                borderRadius: '999px',
                padding: '0.75rem 1rem',
                background: 'var(--color-text-primary)',
                color: 'var(--color-text-on-action)',
                cursor: createSaving ? 'not-allowed' : 'pointer',
                fontSize: '0.86rem',
                fontWeight: 700,
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.45rem',
              }}
            >
              <IconPlus style={{ width: '0.95rem', height: '0.95rem' }} />
              {createSaving ? 'Creating…' : '创建连接器'}
            </button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
