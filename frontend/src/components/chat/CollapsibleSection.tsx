import { useCallback, useState, type ReactNode } from 'react';
import { IconChevronDown, IconChevronUp } from './Icons';

interface CollapsibleSectionProps {
  title: string;
  defaultCollapsed?: boolean;
  children: ReactNode;
  className?: string;
  rightElement?: ReactNode;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
}

export default function CollapsibleSection({
  title,
  defaultCollapsed = false,
  children,
  className = '',
  rightElement,
  collapsed,
  onToggleCollapse,
}: CollapsibleSectionProps) {
  const [internalCollapsed, setInternalCollapsed] = useState(defaultCollapsed);
  const isCollapsed = collapsed ?? internalCollapsed;

  const handleToggle = useCallback(() => {
    if (onToggleCollapse) {
      onToggleCollapse();
      return;
    }
    setInternalCollapsed((value) => !value);
  }, [onToggleCollapse]);

  return (
    <div className={className} style={{ transition: 'all 0.3s ease' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', padding: '0.875rem 1rem', borderRadius: '12px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)' }}>
        <button type="button" onClick={handleToggle} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flex: 1, border: 'none', background: 'transparent', padding: 0, textAlign: 'left', cursor: 'pointer' }}>
          <span style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{title}</span>
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {rightElement}
          <button type="button" onClick={handleToggle} style={{ border: 'none', background: 'transparent', padding: 0, cursor: 'pointer', color: 'var(--color-text-secondary)' }}>
            {isCollapsed ? <IconChevronDown style={{ width: '1rem', height: '1rem' }} /> : <IconChevronUp style={{ width: '1rem', height: '1rem' }} />}
          </button>
        </div>
      </div>
      {!isCollapsed ? <div style={{ marginTop: '0.75rem', borderRadius: '12px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-surface)', padding: '1rem' }}>{children}</div> : null}
    </div>
  );
}
