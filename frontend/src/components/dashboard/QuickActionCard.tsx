import { IconCalendar, IconDatabase, IconEnvelope, IconTable, IconTasks } from '../chat/Icons';
import type { QuickActionCardItem } from './const';

interface QuickActionCardProps {
  item: QuickActionCardItem;
  onClick: (prompt: string) => void;
}

function CardIcon({ icon }: { icon: QuickActionCardItem['icon'] }) {
  if (icon === 'table') return <IconTable style={{ width: '1.2rem', height: '1.2rem' }} />;
  if (icon === 'calendar' || icon === 'calendarAlt') return <IconCalendar style={{ width: '1.2rem', height: '1.2rem' }} />;
  if (icon === 'tasks') return <IconTasks style={{ width: '1.2rem', height: '1.2rem' }} />;
  if (icon === 'database') return <IconDatabase style={{ width: '1.2rem', height: '1.2rem' }} />;
  return <IconEnvelope style={{ width: '1.2rem', height: '1.2rem' }} />;
}

function colorToStyles(color: QuickActionCardItem['color']) {
  switch (color) {
    case 'warning':
      return { background: 'rgba(243, 156, 18, 0.14)', color: 'var(--color-state-warning)' };
    case 'voice-blue':
      return { background: 'rgba(74, 144, 226, 0.12)', color: 'var(--color-voice-blue)' };
    case 'voice-purple':
      return { background: 'rgba(155, 89, 182, 0.12)', color: 'var(--color-voice-purple)' };
    case 'voice-pink':
      return { background: 'rgba(233, 30, 99, 0.12)', color: 'var(--color-voice-pink)' };
    case 'voice-green':
      return { background: 'rgba(39, 174, 96, 0.12)', color: 'var(--color-voice-green)' };
    default:
      return { background: 'rgba(76, 175, 80, 0.12)', color: 'var(--color-state-success)' };
  }
}

export default function QuickActionCard({ item, onClick }: QuickActionCardProps) {
  const accent = colorToStyles(item.color);
  return (
    <button type="button" onClick={() => onClick(item.prompt)} style={{ width: '100%', padding: '1.15rem', borderRadius: '18px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', textAlign: 'left', boxShadow: '0 1px 4px rgba(0,0,0,0.06)', cursor: 'pointer' }}>
      <div style={{ display: 'flex', gap: '1rem' }}>
        <div style={{ display: 'inline-flex', width: '2.5rem', height: '2.5rem', alignItems: 'center', justifyContent: 'center', borderRadius: '14px', ...accent }}>
          <CardIcon icon={item.icon} />
        </div>
        <div>
          <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>{item.title}</h3>
          <p style={{ margin: '0.35rem 0 0', fontSize: '0.84rem', lineHeight: 1.55, color: 'var(--color-text-muted)' }}>{item.description}</p>
        </div>
      </div>
    </button>
  );
}
