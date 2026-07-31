// [Input] VoiceConfig map, position coords, keyboard event listener.
// [Output] Fixed-position @ agent picker dropdown with keyboard navigation.
// [Pos] agent-dropdown component in frontend/src/components
// [Sync] 2026-05-29: replace hardcoded #fff/#ccc/#f0f0f0 with CSS tokens for dark theme support.
import React from 'react';
import type { VoiceConfig } from '../api/voiceApi';
import {
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass
} from 'react-icons/fa';

// Icon map
const iconMap = {
  brain: FaBrain,
  heart: FaHeart,
  question: FaQuestion,
  cloud: FaCloud,
  masks: FaTheaterMasks,
  eye: FaEye,
  fist: FaFistRaised,
  lightbulb: FaLightbulb,
  shield: FaShieldAlt,
  wind: FaWind,
  fire: FaFire,
  compass: FaCompass,
};

interface AgentDropdownProps {
  voices: Record<string, VoiceConfig>;
  position: { x: number; y: number };
  onSelect: (voiceName: string, voiceConfig: VoiceConfig) => void;
  onClose: () => void;
}

export default function AgentDropdown({ voices, position, onSelect, onClose }: AgentDropdownProps) {
  const enabledVoices = Object.entries(voices).filter(([_, cfg]) => cfg.enabled);
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const itemRefs = React.useRef<Map<number, HTMLDivElement>>(new Map());

  // Keyboard navigation
  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIndex(prev => Math.min(prev + 1, enabledVoices.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIndex(prev => Math.max(prev - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const [name, cfg] = enabledVoices[selectedIndex];
        onSelect(name, cfg);
      }
    };
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [onClose, enabledVoices, selectedIndex, onSelect]);

  // @@@ Auto-scroll to selected item
  React.useEffect(() => {
    const selectedItem = itemRefs.current.get(selectedIndex);
    const container = containerRef.current;

    if (selectedItem && container) {
      // Calculate positions relative to container
      const itemTop = selectedItem.offsetTop;
      const itemBottom = itemTop + selectedItem.offsetHeight;
      const containerScrollTop = container.scrollTop;
      const containerHeight = container.clientHeight;

      // Only scroll if item is not fully visible
      if (itemTop < containerScrollTop) {
        // Item is above visible area - scroll up
        container.scrollTop = itemTop;
      } else if (itemBottom > containerScrollTop + containerHeight) {
        // Item is below visible area - scroll down
        container.scrollTop = itemBottom - containerHeight;
      }
    }
  }, [selectedIndex]);

  if (enabledVoices.length === 0) {
    return (
      <div style={{
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
        background: 'var(--color-bg-surface-solid)',
        border: '1px solid var(--color-border-neutral)',
        borderRadius: '8px',
        boxShadow: '0 4px 12px var(--color-shadow-medium)',
        padding: '8px',
        zIndex: 1000,
        minWidth: '200px',
        fontSize: '14px',
        color: 'var(--color-text-secondary)'
      }}>
        No agents available
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        position: 'fixed',
        left: `${position.x}px`,
        top: `${position.y}px`,
        background: 'var(--color-bg-surface-solid)',
        border: '1px solid var(--color-border-neutral)',
        borderRadius: '8px',
        boxShadow: '0 4px 12px var(--color-shadow-medium)',
        padding: '4px 0',
        zIndex: 1000,
        minWidth: '220px',
        maxHeight: '300px',
        overflow: 'auto'
      }}
    >
      {enabledVoices.map(([name, cfg], idx) => {
        const Icon = iconMap[cfg.icon as keyof typeof iconMap] || FaBrain;
        const isSelected = idx === selectedIndex;
        return (
          <div
            key={name}
            ref={(el) => {
              if (el) {
                itemRefs.current.set(idx, el);
              } else {
                itemRefs.current.delete(idx);
              }
            }}
            onClick={() => onSelect(name, cfg)}
            onMouseEnter={() => setSelectedIndex(idx)}
            style={{
              padding: '8px 12px',
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              transition: 'background 0.15s',
              background: isSelected ? 'var(--color-bg-hover)' : 'transparent'
            }}
          >
            <Icon size={16} color="var(--color-text-secondary)" />
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--color-text-body)' }}>
                {cfg.name}
              </div>
              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '2px' }}>
                {cfg.systemPrompt.substring(0, 40)}...
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
