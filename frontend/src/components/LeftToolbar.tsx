// [Input] React icons (FaAlignRight, FaMicrophone), parent props for toolbar actions.
// [Output] Floating left toolbar with tool buttons and hover tooltips.
// [Pos] left-toolbar component in frontend/src/components
// [Sync] 2026-05-29: replace all hardcoded colors (#fff, #e3f2fd, #1976d2 etc.) with CSS tokens for theme support.
import React, { useState } from 'react';
import { FaAlignRight, FaMicrophone } from 'react-icons/fa';

// @@@ Hover-label tool button lives outside to avoid re-creation on each render
function ToolButton({
  label,
  onClick,
  icon,
  active = false,
}: {
  label: string;
  onClick: () => void;
  icon: React.ReactNode;
  active?: boolean;
}) {
  const [hovered, setHovered] = useState(false);

  const baseBg = active
    ? 'var(--color-bg-active)'
    : 'var(--color-bg-surface-solid)';
  const hoverBg = active
    ? 'var(--color-bg-active-hover)'
    : 'var(--color-bg-hover)';

  return (
    <div
      style={{
        position: 'relative',
        width: '40px',
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <button
        onClick={onClick}
        aria-label={label}
        style={{
          width: '36px',
          height: '36px',
          border: 'none',
          borderRadius: '4px',
          backgroundColor: hovered ? hoverBg : baseBg,
          color: 'var(--color-text-secondary)',
          cursor: 'pointer',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          transition: 'all 0.2s ease',
        }}
      >
        {icon}
      </button>
      {hovered && (
        <div
          style={{
            position: 'absolute',
            left: '44px',
            top: '50%',
            transform: 'translateY(-50%)',
            padding: '6px 10px',
            background: 'var(--color-bg-surface-solid)',
            border: '1px solid var(--color-border-neutral)',
            borderRadius: '6px',
            boxShadow: '0 4px 12px var(--color-shadow-soft)',
            whiteSpace: 'nowrap',
            fontSize: '12px',
            color: 'var(--color-text-body)',
            pointerEvents: 'none',
            zIndex: 5,
          }}
        >
          {label}
        </div>
      )}
    </div>
  );
}

type Props = {
  onInsertAgent: () => void;
  onToggleAlign: () => void;
  onShowCalendar: () => void;
  onSaveToday: () => void;
  onToggleTalking: () => void;
  isAligned: boolean;
  isTalking: boolean;
};

export default function LeftToolbar({
  onInsertAgent,
  onToggleAlign,
  onShowCalendar,
  onSaveToday,
  onToggleTalking,
  isAligned,
  isTalking,
}: Props) {
  return (
    <div
      style={{
        position: 'sticky',
        top: '80px',
        width: '40px',
        margin: '30px auto 0',
        backgroundColor: 'var(--color-bg-surface-solid)',
        border: '1px solid var(--color-border-neutral)',
        borderRadius: '8px',
        boxShadow: '0 2px 8px var(--color-shadow-soft)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '10px 0',
        gap: '4px',
      }}
    >
      <ToolButton
        label="Calendar"
        onClick={onShowCalendar}
        icon={
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="16" y1="2" x2="16" y2="6"></line>
            <line x1="8" y1="2" x2="8" y2="6"></line>
            <line x1="3" y1="10" x2="21" y2="10"></line>
          </svg>
        }
      />

      <ToolButton
        label="Save today"
        onClick={onSaveToday}
        icon={
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
            <polyline points="17 21 17 13 7 13 7 21"></polyline>
            <polyline points="7 3 7 8 15 8"></polyline>
          </svg>
        }
      />

      <ToolButton
        label="Insert chat"
        onClick={onInsertAgent}
        icon={<span style={{ fontSize: '20px', fontWeight: 600, color: 'var(--color-text-body)', fontFamily: 'monospace' }}>@</span>}
      />

      <ToolButton
        label={isAligned ? 'Unpin comments' : 'Align comments'}
        onClick={onToggleAlign}
        active={isAligned}
        icon={<FaAlignRight size={18} color={isAligned ? 'var(--color-action-link)' : 'var(--color-text-body)'} />}
      />

      <ToolButton
        label="Voice input"
        onClick={onToggleTalking}
        active={isTalking}
        icon={<FaMicrophone size={18} color={isTalking ? 'var(--color-action-link)' : 'var(--color-text-body)'} />}
      />
    </div>
  );
}
