import React from 'react';
import { FaStar, FaTrash, FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye, FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass } from 'react-icons/fa';
import type { Commentor } from '../engine/EditorEngine';

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
  compass: FaCompass
};

const colorMap: Record<string, { gradient: string; text: string; glow: string }> = {
  blue: {
    gradient: 'linear-gradient(135deg, rgba(173,216,230,0.3), rgba(135,206,250,0.2))',
    text: '#1e3a5f',
    glow: 'rgba(135,206,250,0.15)'
  },
  pink: {
    gradient: 'linear-gradient(135deg, rgba(255,182,193,0.3), rgba(255,105,180,0.2))',
    text: '#5f1e3a',
    glow: 'rgba(255,105,180,0.15)'
  },
  yellow: {
    gradient: 'linear-gradient(135deg, rgba(255,255,153,0.3), rgba(255,255,102,0.2))',
    text: '#5f5f1e',
    glow: 'rgba(255,255,102,0.15)'
  },
  green: {
    gradient: 'linear-gradient(135deg, rgba(144,238,144,0.3), rgba(102,205,170,0.2))',
    text: '#1e5f3a',
    glow: 'rgba(102,205,170,0.15)'
  },
  purple: {
    gradient: 'linear-gradient(135deg, rgba(221,160,221,0.3), rgba(179,102,255,0.2))',
    text: '#3a1e5f',
    glow: 'rgba(179,102,255,0.15)'
  },
};

export function CommentGroupCard({
  comments,
  currentIndex,
  onNavigate,
  position,
  isExpanded,
  onToggleExpand,
  onStar,
  onKill,
  onSendChatMessage,
  isChatProcessing,
  voiceConfigs
}: {
  comments: Commentor[];
  currentIndex: number;
  onNavigate: (index: number) => void;
  position: { top: number; left: number };
  isExpanded: boolean;
  onToggleExpand: () => void;
  onStar: () => void;
  onKill: () => void;
  onSendChatMessage: (message: string) => void;
  isChatProcessing: boolean;
  voiceConfigs: Record<string, any>;
}) {
  const [isHovered, setIsHovered] = React.useState(false);
  const [inputValue, setInputValue] = React.useState('');

  if (comments.length === 0) return null;

  const safeIndex = Math.min(Math.max(0, currentIndex), comments.length - 1);
  const currentComment = comments[safeIndex];

  if (!currentComment) return null;

  const Icon = iconMap[currentComment.icon as keyof typeof iconMap] || FaBrain;
  const colors = colorMap[currentComment.color] || colorMap.blue;

  // Get chat history (original comment is always first message)
  const chatHistory = currentComment.chatHistory || [{
    role: 'assistant' as const,
    content: currentComment.comment,
    timestamp: currentComment.computedAt
  }];

  const handleSend = () => {
    if (!inputValue.trim() || isChatProcessing) return;
    onSendChatMessage(inputValue);
    setInputValue('');
  };

  return (
    <div
      style={{
        position: 'absolute',
        top: `${position.top}px`, // @@@ Fixed top position - comment stays here
        left: `${position.left}px`,
        minWidth: '200px',
        maxWidth: '600px',
        zIndex: isExpanded ? 100 : 10,
        fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
        transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)', // @@@ Smooth expansion animation
      }}
    >
      {/* @@@ White backdrop when expanded - creates solid appearance */}
      {isExpanded && (
        <div
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            right: 0,
            background: 'var(--color-bg-surface-solid)',
            borderLeft: `2px solid ${colors.glow}`,
            borderRadius: '4px 4px 0 0',
            marginBottom: '-4px',
            animation: 'slideDownFadeIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)', // @@@ Toolbar animation
          }}
        >
          {/* Toolbar on top of white backdrop */}
          <div
            style={{
              background: colors.gradient,
              borderRadius: '4px 4px 0 0',
              fontSize: '13px',
              boxShadow: '0 4px 12px var(--color-shadow-medium)',
            }}
          >
          <div style={{
            padding: '6px 8px',
            borderBottom: `1px solid ${colors.glow}`,
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center'
          }}>
            {/* @@@ Tab navigation on left side */}
            <div style={{
              display: 'flex',
              gap: '4px',
              alignItems: 'center',
            }}>
              {comments.length > 1 ? (
                comments.map((_, idx) => (
                  <React.Fragment key={idx}>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onNavigate(idx);
                      }}
                      style={{
                        background: idx === safeIndex ? colors.text : 'transparent',
                        color: idx === safeIndex ? 'var(--color-text-on-action)' : colors.text,
                        border: 'none',
                        borderRadius: '3px',
                        padding: '2px 6px',
                        cursor: 'pointer',
                        fontSize: '10px',
                        fontWeight: 600,
                        opacity: idx === safeIndex ? 1 : 0.5,
                        transition: 'all 0.2s',
                      }}
                    >
                      {idx + 1}
                    </button>
                    {idx < comments.length - 1 && (
                      <span style={{ color: colors.text, opacity: 0.3, fontSize: '10px' }}>|</span>
                    )}
                  </React.Fragment>
                ))
              ) : (
                <div style={{ width: '1px' }} /> // Empty placeholder when single comment
              )}
            </div>

            {/* @@@ Action buttons on right side */}
            <div style={{
              display: 'flex',
              gap: '4px',
            }}>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onStar();
                }}
                style={{
                  background: currentComment.feedback === 'star' ? 'var(--color-state-warning)' : 'transparent',
                  border: 'none',
                  borderRadius: '3px',
                  padding: '3px 5px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'background 0.2s',
                }}
              >
                <FaStar size={10} color={currentComment.feedback === 'star' ? 'var(--color-text-on-action)' : colors.text} style={{ opacity: currentComment.feedback === 'star' ? 1 : 0.5 }} />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onKill();
                }}
                style={{
                  background: currentComment.feedback === 'kill' ? 'var(--color-state-danger)' : 'transparent',
                  border: 'none',
                  borderRadius: '3px',
                  padding: '3px 5px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'background 0.2s',
                }}
              >
                <FaTrash size={10} color={currentComment.feedback === 'kill' ? 'var(--color-text-on-action)' : colors.text} style={{ opacity: currentComment.feedback === 'kill' ? 1 : 0.5 }} />
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onToggleExpand();
                }}
                style={{
                  background: 'transparent',
                  border: 'none',
                  borderRadius: '3px',
                  padding: '3px 5px',
                  cursor: 'pointer',
                  fontSize: '14px',
                  color: colors.text,
                  opacity: 0.5,
                  lineHeight: 1,
                }}
              >
                ×
              </button>
            </div>
          </div>
          </div>
        </div>
      )}

      {/* @@@ Comment (first message) - click to expand/collapse, position is FIXED */}
      <div
        style={{
          position: 'relative', // For white backdrop positioning
        }}
      >
        {/* White backdrop layer when expanded */}
        {isExpanded && (
          <div
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: 'var(--color-bg-surface-solid)',
              borderLeft: `2px solid ${colors.glow}`,
              borderRadius: '0 0 4px 4px',
            }}
          />
        )}

        {/* Color gradient layer on top */}
        <div
          style={{
            position: 'relative', // Stack on top of backdrop
            background: colors.gradient,
            borderLeft: `2px solid ${colors.glow}`,
            borderRadius: isExpanded ? '0' : '4px',
            fontSize: '13px',
            lineHeight: '1.4',
            boxShadow: isHovered || isExpanded ? '0 4px 12px var(--color-shadow-medium)' : 'none',
            transition: 'box-shadow 0.2s ease',
          }}
        >
        <div
          style={{
            minHeight: '54px',
            padding: '8px 12px',
            cursor: 'pointer',
            transform: isHovered && !isExpanded ? 'scale(1.02)' : 'scale(1)', // @@@ Subtle scale on hover
            transition: 'transform 0.2s ease-out',
          }}
          onClick={onToggleExpand}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          <div style={{
            display: 'flex',
            gap: '10px',
            alignItems: 'flex-start'
          }}>
            <div style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'flex-start',
              flexShrink: 0,
              width: '24px',
              paddingTop: '2px'
            }}>
              <Icon size={15} color={colors.text} style={{ opacity: 0.75 }} />
              {comments.length > 1 && !isExpanded && (
                <span style={{
                  fontSize: '8px',
                  color: colors.text,
                  opacity: 0.5,
                  marginTop: '1px',
                  fontWeight: 500
                }}>
                  {safeIndex + 1}/{comments.length}
                </span>
              )}
            </div>

            <div style={{
              flex: 1,
              color: colors.text,
              opacity: 0.85,
              wordWrap: 'break-word',
              overflowWrap: 'break-word',
              display: '-webkit-box',
              WebkitLineClamp: 3,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden'
            }}>
              <strong style={{ fontWeight: 600 }}>{voiceConfigs[currentComment.voice]?.name || currentComment.voice}:</strong> {currentComment.comment}
            </div>
          </div>
        </div>

          {/* @@@ Rest of chat messages - only visible when expanded */}
          {isExpanded && chatHistory.length > 1 && (
            <div style={{
              maxHeight: '200px',
              overflowY: 'auto',
              padding: '0 12px 8px 12px',
              borderTop: `1px solid ${colors.glow}`,
              animation: 'fadeIn 0.4s ease-out', // @@@ Fade in chat messages
            }}>
              {chatHistory.slice(1).map((msg, idx) => (
                <div
                  key={idx + 1}
                  style={{
                    marginTop: '12px',
                    color: colors.text,
                    opacity: msg.role === 'assistant' ? 0.85 : 0.95,
                  }}
                >
                  <div style={{
                    fontSize: '10px',
                    opacity: 0.6,
                    marginBottom: '2px',
                    fontWeight: 500,
                  }}>
                    {msg.role === 'assistant' ? (voiceConfigs[currentComment.voice]?.name || currentComment.voice) : 'You'}
                  </div>
                  <div style={{
                    fontSize: '13px',
                    lineHeight: '1.4',
                    wordWrap: 'break-word',
                  }}>
                    {msg.content}
                  </div>
                </div>
              ))}
              {isChatProcessing && (
                <div style={{
                  marginTop: '12px',
                  color: colors.text,
                  opacity: 0.5,
                  fontSize: '12px',
                  fontStyle: 'italic',
                }}>
                  Thinking...
                </div>
              )}
            </div>
          )}

          {/* @@@ Input box - only visible when expanded */}
          {isExpanded && (
            <div style={{
              padding: '8px',
              borderTop: `1px solid ${colors.glow}`,
              display: 'flex',
              gap: '6px',
              animation: 'fadeIn 0.5s ease-out', // @@@ Fade in input box
            }}>
              <input
                type="text"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyPress={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                onClick={(e) => e.stopPropagation()}
                placeholder={`Reply to ${voiceConfigs[currentComment.voice]?.name || currentComment.voice}...`}
                disabled={isChatProcessing}
                style={{
                  flex: 1,
                  padding: '6px 8px',
                  fontSize: '12px',
                  border: `1px solid ${colors.glow}`,
                  borderRadius: '3px',
                  background: 'var(--color-bg-surface-solid)',
                  color: 'var(--color-text-body)',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                }}
              />
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleSend();
                }}
                disabled={!inputValue.trim() || isChatProcessing}
                style={{
                  padding: '6px 12px',
                  fontSize: '12px',
                  background: inputValue.trim() && !isChatProcessing ? 'var(--color-action-link)' : '#ccc',
                  color: 'var(--color-text-on-action)',
                  border: 'none',
                  borderRadius: '3px',
                  cursor: inputValue.trim() && !isChatProcessing ? 'pointer' : 'not-allowed',
                  fontWeight: 600,
                }}
              >
                Send
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
