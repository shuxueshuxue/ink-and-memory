// [Input] Landing quick-action items and shared chat icons.
// [Output] Render the single pill-style quick-action strip shown directly below the Chat composer.
// [Pos] chat-quick-action-strip component node in frontend/src/components/chat
// [Sync] 2026-07-07: replace the older grid-style quick action cards with a single pill strip under the Chat input.
import { useMemo, useState } from 'react';
import { IconEdit, IconImage, IconSearch } from './Icons';

export type QuickActionStripIcon = 'image' | 'edit' | 'search';

export interface QuickActionStripItem {
  id: string;
  label: string;
  prompt: string;
  icon: QuickActionStripIcon;
  description?: string;
}

interface QuickActionStripProps {
  items: QuickActionStripItem[];
  onSelect: (item: QuickActionStripItem) => void;
  className?: string;
}

function ActionIcon({ icon }: { icon: QuickActionStripIcon }) {
  const iconStyle = { width: '1rem', height: '1rem', flexShrink: 0 };
  switch (icon) {
    case 'image':
      return <IconImage style={iconStyle} />;
    case 'edit':
      return <IconEdit style={iconStyle} />;
    case 'search':
    default:
      return <IconSearch style={iconStyle} />;
  }
}

function ActionPill({
  item,
  onSelect,
}: {
  item: QuickActionStripItem;
  onSelect: (item: QuickActionStripItem) => void;
}) {
  const [isHovered, setIsHovered] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [isPressed, setIsPressed] = useState(false);

  const palette = useMemo(() => {
    if (isPressed) {
      return {
        border: 'var(--color-border-focus)',
        background: 'var(--color-bg-surface)',
        shadow: '0 10px 20px rgba(91, 69, 44, 0.10)',
        transform: 'translateY(1px)',
      };
    }
    if (isHovered || isFocused) {
      return {
        border: 'rgba(91, 69, 44, 0.28)',
        background: 'color-mix(in srgb, var(--color-bg-paper) 84%, #f2e8d8)',
        shadow: '0 12px 24px rgba(91, 69, 44, 0.09)',
        transform: 'translateY(-1px)',
      };
    }
    return {
      border: 'var(--color-border-paper)',
      background: 'var(--color-bg-paper)',
      shadow: '0 8px 18px rgba(91, 69, 44, 0.05)',
      transform: 'translateY(0)',
    };
  }, [isFocused, isHovered, isPressed]);

  return (
    <button
      type="button"
      title={item.description ?? item.label}
      aria-label={item.label}
      onClick={() => onSelect(item)}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => {
        setIsHovered(false);
        setIsPressed(false);
      }}
      onFocus={() => setIsFocused(true)}
      onBlur={() => {
        setIsFocused(false);
        setIsPressed(false);
      }}
      onMouseDown={() => setIsPressed(true)}
      onMouseUp={() => setIsPressed(false)}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.55rem',
        padding: '0.72rem 1rem',
        borderRadius: '999px',
        border: `1px solid ${palette.border}`,
        background: palette.background,
        color: 'var(--color-text-primary)',
        boxShadow: palette.shadow,
        cursor: 'pointer',
        transform: palette.transform,
        transition: 'transform 0.16s ease, box-shadow 0.16s ease, border-color 0.16s ease, background 0.16s ease',
        whiteSpace: 'nowrap',
        maxWidth: '100%',
        touchAction: 'manipulation',
      }}
    >
      <span
        style={{
          width: '1.5rem',
          height: '1.5rem',
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderRadius: '999px',
          background: 'rgba(91, 69, 44, 0.08)',
          color: 'var(--color-text-primary)',
          flexShrink: 0,
        }}
      >
        <ActionIcon icon={item.icon} />
      </span>
      <span
        style={{
          fontSize: '0.88rem',
          fontWeight: 600,
          letterSpacing: '0.01em',
        }}
      >
        {item.label}
      </span>
    </button>
  );
}

export default function QuickActionStrip({ items, onSelect, className }: QuickActionStripProps) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div
      className={className}
      style={{
        display: 'flex',
        flexWrap: 'wrap',
        justifyContent: 'center',
        gap: '0.65rem',
        width: '100%',
        padding: '0.2rem 0 0.1rem',
      }}
    >
      {items.map((item) => (
        <ActionPill key={item.id} item={item} onSelect={onSelect} />
      ))}
    </div>
  );
}
