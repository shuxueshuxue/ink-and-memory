// [Input] Resource connector API client, shared dashboard icons, and App-level focus nonce.
// [Output] Settings resource-link index section with remote/local connector choices; the Notion
//          "管理" action now navigates to the dedicated ConnectorNotionDetailPage instead of
//          toggling an inline embedded panel.
// [Pos] settings resource-link section in frontend/src/components/dashboard
// [Sync] 2026-07-08: initial Settings resource-link section for the connector migration.
// [Sync] 2026-07-08: remove the inline Notion detail toggle; 管理 now calls onOpenNotionDetail so
//                    App navigates to a dedicated 具体配置页面 page, matching the connector
//                    interaction design's page-navigation requirement.
// [Sync] 2026-07-08: replace light-only Settings connector card/status fills with semantic theme
//                    tokens and state color mixes so resource-link settings adapt to dark mode.
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { listConnectors, type ResourceConnector } from '../../api/resourceConnectorApi';
import {
  IconChevronRight,
  IconClock,
  IconDatabase,
  IconFile,
  IconLoader,
  IconSettings,
} from '../chat/Icons';

type ConnectorTone = 'neutral' | 'success' | 'warning' | 'danger';

interface ConnectorSettingsSectionProps {
  focusNonce?: number;
  isMobile?: boolean;
  /** Navigates to the dedicated Notion "具体配置页面" instead of expanding inline. */
  onOpenNotionDetail?: () => void;
}

interface ConnectorOptionCardProps {
  icon: ReactNode;
  title: string;
  subtitle: string;
  detail: string;
  statusLabel: string;
  tone: ConnectorTone;
  actionLabel: string;
  onAction?: () => void;
  disabled?: boolean;
}

function formatLastInteraction(connector: ResourceConnector | null): string {
  const value = connector?.lastSyncedAt ?? connector?.updatedAt ?? connector?.createdAt;
  if (!value) return '暂无交互';

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function getResourceHealthTone(connector: ResourceConnector | null): ConnectorTone {
  if (!connector) return 'neutral';
  if (connector.status === 'authenticated' || connector.status === 'synced' || connector.auth.status === 'authenticated') {
    return 'success';
  }
  if (connector.status === 'authenticating' || connector.auth.status === 'authenticating') {
    return 'warning';
  }
  if (connector.status === 'expired' || connector.auth.status === 'expired' || connector.status === 'error' || connector.auth.status === 'error') {
    return 'danger';
  }
  return 'neutral';
}

function toneStyles(tone: ConnectorTone) {
  switch (tone) {
    case 'success':
      return {
        background: 'color-mix(in srgb, var(--color-state-success) 16%, var(--color-bg-paper))',
        border: 'color-mix(in srgb, var(--color-state-success) 34%, var(--color-border-paper))',
        color: 'var(--color-state-success)',
      };
    case 'warning':
      return {
        background: 'color-mix(in srgb, var(--color-state-warning) 16%, var(--color-bg-paper))',
        border: 'color-mix(in srgb, var(--color-state-warning) 34%, var(--color-border-paper))',
        color: 'var(--color-state-warning)',
      };
    case 'danger':
      return {
        background: 'color-mix(in srgb, var(--color-state-error) 16%, var(--color-bg-paper))',
        border: 'color-mix(in srgb, var(--color-state-error) 34%, var(--color-border-paper))',
        color: 'var(--color-state-error)',
      };
    default:
      return {
        background: 'var(--color-bg-hover)',
        border: 'var(--color-border-paper)',
        color: 'var(--color-text-secondary)',
      };
  }
}

function ConnectorOptionCard({
  icon,
  title,
  subtitle,
  detail,
  statusLabel,
  tone,
  actionLabel,
  onAction,
  disabled = false,
}: ConnectorOptionCardProps) {
  const palette = toneStyles(tone);

  return (
    <button
      type="button"
      onClick={onAction}
      disabled={disabled || !onAction}
      style={{
        width: '100%',
        border: `1px solid ${palette.border}`,
        borderRadius: '1rem',
        background: disabled ? 'var(--color-bg-surface)' : 'var(--color-bg-surface-solid)',
        padding: '0.9rem 0.95rem',
        cursor: disabled || !onAction ? 'not-allowed' : 'pointer',
        textAlign: 'left',
        display: 'grid',
        gridTemplateColumns: '2.4rem minmax(0, 1fr) auto',
        gap: '0.85rem',
        alignItems: 'center',
        opacity: disabled ? 0.74 : 1,
        boxShadow: '0 10px 24px var(--color-shadow-soft)',
      }}
    >
      <div
        style={{
          width: '2.4rem',
          height: '2.4rem',
          borderRadius: '0.85rem',
          border: `1px solid ${palette.border}`,
          background: disabled ? 'var(--color-bg-surface)' : 'var(--color-bg-hover)',
          color: 'var(--color-text-primary)',
          display: 'grid',
          placeItems: 'center',
          flexShrink: 0,
        }}
      >
        {icon}
      </div>

      <div style={{ minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
          <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            {title}
          </h3>
          <span
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.28rem',
              borderRadius: '999px',
              border: `1px solid ${palette.border}`,
              background: palette.background,
              color: palette.color,
              padding: '0.25rem 0.5rem',
              fontSize: '0.72rem',
              fontWeight: 700,
            }}
          >
            <span
              aria-hidden="true"
              style={{
                width: '0.38rem',
                height: '0.38rem',
                borderRadius: '999px',
                background: palette.color,
              }}
            />
            {statusLabel}
          </span>
        </div>
        <p style={{ margin: '0.32rem 0 0', fontSize: '0.78rem', lineHeight: 1.55, color: 'var(--color-text-secondary)' }}>
          {subtitle}
        </p>
        <div style={{ marginTop: '0.42rem', display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
          <IconClock style={{ width: '0.82rem', height: '0.82rem' }} />
          {detail}
        </div>
      </div>

      <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.38rem', justifySelf: 'end', color: disabled ? 'var(--color-text-muted)' : 'var(--color-action-link)' }}>
        <span style={{ fontSize: '0.76rem', fontWeight: 700 }}>{actionLabel}</span>
        <IconChevronRight style={{ width: '0.88rem', height: '0.88rem' }} />
      </div>
    </button>
  );
}

export default function ConnectorSettingsSection({ focusNonce = 0, isMobile = false, onOpenNotionDetail }: ConnectorSettingsSectionProps) {
  const sectionRef = useRef<HTMLElement>(null);
  const [connectors, setConnectors] = useState<ResourceConnector[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadConnectors = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const items = await listConnectors();
      setConnectors(items);
    } catch (err) {
      setError(err instanceof Error ? err.message : '资源链接读取失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (focusNonce <= 0) return;
    sectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    sectionRef.current?.focus({ preventScroll: true });
  }, [focusNonce]);

  useEffect(() => {
    void loadConnectors();
  }, [loadConnectors, focusNonce]);

  const notionConnector = useMemo(
    () => connectors.find((connector) => connector.platform === 'notion') ?? null,
    [connectors],
  );
  const notionStatusLabel = useMemo(
    () => {
      if (!notionConnector) return '未连接';
      if (notionConnector.status === 'authenticated' || notionConnector.status === 'synced' || notionConnector.auth.status === 'authenticated') {
        return '健康';
      }
      if (notionConnector.status === 'authenticating' || notionConnector.auth.status === 'authenticating') {
        return '认证中';
      }
      if (notionConnector.status === 'expired' || notionConnector.auth.status === 'expired') {
        return '已过期';
      }
      if (notionConnector.status === 'error' || notionConnector.auth.status === 'error') {
        return '异常';
      }
      return '未连接';
    },
    [notionConnector],
  );
  const notionStatusTone = getResourceHealthTone(notionConnector);
  const notionLastInteraction = formatLastInteraction(notionConnector);

  return (
    <section
      ref={sectionRef}
      tabIndex={-1}
      aria-label="资源链接设置"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '0.9rem',
        border: '1px solid var(--color-border-paper)',
        borderRadius: '1.15rem',
        background: 'var(--color-bg-surface)',
        padding: isMobile ? '1rem' : '1.15rem',
        boxShadow: '0 12px 28px var(--color-shadow-soft)',
      }}
    >
      <header style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', color: 'var(--color-text-muted)', fontSize: '0.72rem', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
            <IconSettings style={{ width: '0.86rem', height: '0.86rem' }} />
            Settings
          </div>
          <h2 style={{ margin: '0.4rem 0 0', fontSize: isMobile ? '1.15rem' : '1.25rem', fontWeight: 700, color: 'var(--color-text-primary)', fontFamily: 'Georgia, "Times New Roman", serif' }}>
            资源链接
          </h2>
          <p style={{ margin: '0.35rem 0 0', maxWidth: '42rem', fontSize: '0.82rem', lineHeight: 1.6, color: 'var(--color-text-secondary)' }}>
            远程资源链接集中管理 Notion / 飞书，本地资源链接预留给 CLI 执行器。Chat 入口只保留状态摘要和跳转按钮。
          </p>
        </div>
      </header>

      <div style={{ display: 'grid', gap: '1rem' }}>
        <section style={{ display: 'grid', gap: '0.7rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
              远程资源链接
            </h3>
            <p style={{ margin: '0.28rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
              连接后可读取外部知识源。Notion 可继续管理资源，飞书先保留占位。
            </p>
          </div>

          <div style={{ display: 'grid', gap: '0.75rem' }}>
            <ConnectorOptionCard
              icon={<IconDatabase style={{ width: '1rem', height: '1rem' }} />}
              title="Notion"
              subtitle="可访问的数据库和页面会在这里管理，认证与同步仍复用现有 Notion connector 页面。"
              detail={`${notionConnector ? `最近交互 ${notionLastInteraction}` : '暂无交互'} · ${notionConnector?.sources.length ?? 0} 个来源`}
              statusLabel={notionStatusLabel}
              tone={notionStatusTone}
              actionLabel="管理"
              onAction={onOpenNotionDetail}
            />
            <ConnectorOptionCard
              icon={<IconSettings style={{ width: '1rem', height: '1rem' }} />}
              title="飞书"
              subtitle="远程资源链接预留位，不调用不存在的 API。"
              detail="暂不实现"
              statusLabel="禁用"
              tone="neutral"
              actionLabel="暂不可用"
              disabled
            />
          </div>
        </section>

        <div style={{ height: '1px', background: 'var(--color-border-paper)' }} />

        <section style={{ display: 'grid', gap: '0.7rem' }}>
          <div>
            <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
              本地资源链接
            </h3>
            <p style={{ margin: '0.28rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-secondary)' }}>
              本地资源由当前系统 CLI 执行器接入，当前版本只放占位，不在前端设计完整流程。
            </p>
          </div>

          <ConnectorOptionCard
            icon={<IconFile style={{ width: '1rem', height: '1rem' }} />}
            title="CLI 执行器"
            subtitle="用户下载后，这里显示本地可用资源入口。"
            detail="暂不设计"
            statusLabel="占位"
            tone="neutral"
            actionLabel="暂不可用"
            disabled
          />
        </section>

        {loading ? (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', color: 'var(--color-text-muted)', fontSize: '0.78rem' }}>
            <IconLoader style={{ width: '0.9rem', height: '0.9rem' }} />
            刷新连接器状态中…
          </div>
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
