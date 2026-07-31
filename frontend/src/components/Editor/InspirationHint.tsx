import {
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass,
} from 'react-icons/fa';
import type { VoiceInspiration } from '../../api/voiceApi';

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

interface InspirationHintProps {
  inspiration: VoiceInspiration | null;
  isDisappearing: boolean;
  isAppearing: boolean;
}

export function InspirationHint({
  inspiration,
  isDisappearing,
  isAppearing,
}: InspirationHintProps) {
  if (!inspiration) {
    return null;
  }

  const Icon = iconMap[inspiration.icon as keyof typeof iconMap] || FaBrain;

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '10px',
        marginTop: '12px',
        color: '#999',
        fontSize: '16px',
        fontStyle: 'italic',
        pointerEvents: 'none',
        transition: 'all 0.8s cubic-bezier(0.4, 0, 0.6, 1)',
        opacity: isDisappearing ? 0 : (isAppearing ? 0 : 1),
        transform: isDisappearing
          ? 'scale(0.95) translateY(-3px)'
          : (isAppearing ? 'scale(0.95) translateY(-3px)' : 'scale(1) translateY(0)'),
        filter: isDisappearing
          ? 'blur(2px)'
          : (isAppearing ? 'blur(2px)' : 'blur(0)'),
      }}
    >
      <div
        style={{
          fontSize: '24px',
          flexShrink: 0,
          color: 'var(--color-text-secondary)',
        }}
      >
        <Icon />
      </div>

      <div>
        <span style={{ fontWeight: 'normal', color: '#888' }}>
          {inspiration.voice}:
        </span>
        {' '}
        {inspiration.inspiration}
      </div>
    </div>
  );
}
