import type { ReactNode } from 'react';

interface ModalProps {
  open: boolean;
  title: string;
  children: ReactNode;
  onClose: () => void;
}

export default function Modal({ open, title, children, onClose }: ModalProps) {
  if (!open) return null;

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
        background: 'var(--color-bg-overlay)',
      }}
      onClick={onClose}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '40rem',
          borderRadius: '24px',
          border: '1px solid var(--color-border-paper)',
          background: 'var(--color-bg-paper)',
          padding: '1.25rem',
          boxShadow: '0 20px 45px var(--color-shadow-medium)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <h2 style={{ margin: 0, fontSize: '1.125rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{title}</h2>
          <button
            type="button"
            onClick={onClose}
            style={{
              display: 'grid',
              placeItems: 'center',
              width: '2rem',
              height: '2rem',
              borderRadius: '999px',
              border: '1px solid var(--color-border-paper)',
              background: 'var(--color-bg-surface-solid)',
              color: 'var(--color-text-secondary)',
              cursor: 'pointer',
            }}
          >
            ×
          </button>
        </div>
        <div style={{ marginTop: '1rem' }}>{children}</div>
      </div>
    </div>
  );
}
