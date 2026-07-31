import { useEffect } from 'react';

interface ToastProps {
  message: string;
  onClose: () => void;
}

export default function Toast({ message, onClose }: ToastProps) {
  useEffect(() => {
    const timer = window.setTimeout(onClose, 2800);
    return () => window.clearTimeout(timer);
  }, [onClose]);

  return (
    <div
      style={{
        position: 'fixed',
        top: '1rem',
        left: '50%',
        transform: 'translateX(-50%)',
        zIndex: 60,
        maxWidth: '90%',
        padding: '0.625rem 1rem',
        borderRadius: '999px',
        background: 'var(--color-text-primary)',
        color: 'var(--color-text-on-action)',
        fontSize: '0.75rem',
        fontWeight: 600,
        boxShadow: '0 10px 24px var(--color-shadow-medium)',
      }}
    >
      {message}
    </div>
  );
}
