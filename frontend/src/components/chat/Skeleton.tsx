// [Input] None — pure presentational placeholder primitives.
// [Output] Reusable skeleton-screen building blocks (bar / circle / row) matching the
//          gray placeholder skeletons defined in 《链接器概念的交互设计稿》 for Chat 入口页
//          first-load state and 链接器具体配置页面 first-load state.
// [Pos] skeleton primitives in frontend/src/components/chat
// [Sync] 2026-07-08: initial skeleton primitives, replacing plain "加载中..." text loading states.
// [Sync] 2026-07-20: i18n — SkeletonList aria-label resolves through chat.skeleton.loading.
import type { CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';

interface SkeletonBarProps {
  width?: string;
  height?: string;
  style?: CSSProperties;
}

export function SkeletonBar({ width = '100%', height = '0.85rem', style }: SkeletonBarProps) {
  return (
    <div
      className="skeleton-block"
      aria-hidden="true"
      style={{ width, height, ...style }}
    />
  );
}

export function SkeletonCircle({ size = '2.4rem', style }: { size?: string; style?: CSSProperties }) {
  return (
    <div
      className="skeleton-block"
      aria-hidden="true"
      style={{ width: size, height: size, borderRadius: '999px', ...style }}
    />
  );
}

/** A single skeleton row: circle/icon placeholder + stacked text-line placeholders. */
export function SkeletonRow({ lines = 2 }: { lines?: number }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
      <SkeletonCircle size="2.4rem" />
      <div style={{ flex: 1, minWidth: 0, display: 'grid', gap: '0.4rem' }}>
        {Array.from({ length: lines }, (_, index) => (
          <SkeletonBar key={index} width={index === 0 ? '55%' : '85%'} />
        ))}
      </div>
    </div>
  );
}

/** Skeleton screen for a first-load list (Chat 历史对话 / 连接器摘要面板 / 连接器列表). */
export function SkeletonList({ rows = 3 }: { rows?: number }) {
  const { t } = useTranslation();
  return (
    <div role="status" aria-label={t('chat.skeleton.loading')} style={{ display: 'grid', gap: '0.85rem' }}>
      {Array.from({ length: rows }, (_, index) => (
        <SkeletonRow key={index} />
      ))}
    </div>
  );
}
