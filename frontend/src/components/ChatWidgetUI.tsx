// [Sync] 2026-05-30: restore inline Deck chat — onSendMessage/isProcessing props connect to
//   handleChatSend in App.tsx which calls chatWithVoice with full writing context (allText,
//   metaPrompt, statePrompt). "Chat →" button opens the full Chat view when thread is available.
// [Sync] 2026-05-30: add streamingText prop — renders partial SSE text as a streaming assistant
//   bubble with blinking cursor; auto-scroll on streamingText changes.
// [Sync] 2026-05-30: defensive null fallbacks for data.voiceConfig and data.messages to prevent
//   crash on old-format session data; move streaming bubble inside scroll container.
// [Sync] 2026-05-30: add reasoning/thinking display mirroring ChatMessageList — streaming block
//   with spin+cursor, completed-message collapsible block (default expanded); expandedThinking state.
// [Sync] 2026-05-30: add collapse/expand — header row shows Deck name + first user message preview;
//   ▾ arrow toggles; delete/Chat→ buttons hidden when collapsed.
// [Sync] 2026-05-30: persist collapsed state — data.collapsed init, onToggleCollapse prop writes
//   back via App.tsx handleChatToggleCollapse → engineRef.updateWidgetData.
import React, { useState, useRef, useEffect } from 'react';
import type { ChatWidgetData } from '../engine/ChatWidget';
import {
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass
} from 'react-icons/fa';

// @@@ Inject CSS keyframes for button pulse animation
if (typeof document !== 'undefined') {
  const styleId = 'chat-widget-pulse-animation';
  if (!document.getElementById(styleId)) {
    const style = document.createElement('style');
    style.id = styleId;
    style.textContent = `
      @keyframes pulse {
        0%, 100% {
          opacity: 0.5;
        }
        50% {
          opacity: 1;
        }
      }
    `;
    document.head.appendChild(style);
  }
}

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

interface ChatWidgetUIProps {
  data: ChatWidgetData;
  onSendMessage: (message: string) => void;
  /** Called when the user clicks "Chat →". Passes the linked thread_id. */
  onOpenChat?: (threadId: string) => void;
  onDelete: () => void;
  /** Called when the user toggles collapse; parent should persist the new state. */
  onToggleCollapse?: (collapsed: boolean) => void;
  isProcessing: boolean;
  /** Partial SSE response text being streamed for the current turn. */
  streamingText?: string;
  /** Partial SSE reasoning/thinking text accumulating during the current turn. */
  streamingReasoning?: string;
  /** True once the reasoning-end SSE event has been received. */
  isReasoningDone?: boolean;
}

export default function ChatWidgetUI({ data, onSendMessage, onOpenChat, onDelete, onToggleCollapse, isProcessing, streamingText, streamingReasoning, isReasoningDone }: ChatWidgetUIProps) {
  const [inputValue, setInputValue] = useState('');
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const [isHovered, setIsHovered] = useState(false);
  const [isCollapsed, setIsCollapsed] = useState(() => data?.collapsed ?? false);
  // Track which completed-message reasoning blocks are expanded (index → bool).
  // Default true so users see thinking content after it was streamed.
  const [expandedThinking, setExpandedThinking] = useState<Record<number, boolean>>({});

  // Defensive fallbacks for potentially missing data fields (e.g. old session format)
  const voiceConfig = data?.voiceConfig ?? { name: 'Agent', tagline: '', icon: 'brain', color: 'blue' };
  const messages = data?.messages ?? [];

  // First user message preview for collapsed state
  const firstUserMsg = messages.find(m => m.role === 'user');
  const collapsedPreview = firstUserMsg
    ? firstUserMsg.content.slice(0, 30) + (firstUserMsg.content.length > 30 ? '…' : '')
    : null;

  // @@@ Auto-scroll to bottom when new messages arrive or streaming text updates
  useEffect(() => {
    setTimeout(() => {
      if (messagesContainerRef.current) {
        messagesContainerRef.current.scrollTop = messagesContainerRef.current.scrollHeight;
      }
    }, 50);
  }, [messages.length, streamingText, streamingReasoning]);

  const handleSend = () => {
    if (inputValue.trim() && !isProcessing) {
      onSendMessage(inputValue.trim());
      setInputValue('');
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const Icon = iconMap[voiceConfig.icon as keyof typeof iconMap] || FaBrain;

  return (
    <div
      style={{
        margin: '20px 0',
        padding: '16px 20px',
        background: 'var(--color-bg-surface)',
        borderRadius: '12px',
        maxWidth: '600px',
        position: 'relative',
        transition: 'all 0.2s ease'
      }}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Collapsed header row — always visible, click to toggle */}
      <div
        onClick={() => {
          const next = !isCollapsed;
          setIsCollapsed(next);
          onToggleCollapse?.(next);
        }}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
          marginBottom: isCollapsed ? 0 : '12px',
          userSelect: 'none',
        }}
      >
        <Icon size={15} color="var(--color-text-secondary)" style={{ flexShrink: 0 }} />
        <span style={{
          fontSize: '13px',
          fontWeight: 600,
          color: 'var(--color-text-secondary)',
          fontFamily: 'system-ui',
          flexShrink: 0,
        }}>
          {voiceConfig.name}
        </span>
        {collapsedPreview && (
          <>
            <span style={{ color: 'var(--color-border-neutral)', fontSize: '13px' }}>·</span>
            <span style={{
              fontSize: '13px',
              color: 'var(--color-text-muted)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              flex: 1,
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
            }}>
              {collapsedPreview}
            </span>
          </>
        )}
        <span style={{
          marginLeft: 'auto',
          flexShrink: 0,
          fontSize: '11px',
          color: 'var(--color-text-muted)',
          transform: isCollapsed ? 'rotate(0deg)' : 'rotate(180deg)',
          transition: 'transform 0.2s',
          lineHeight: 1,
        }}>
          ▾
        </span>
      </div>

      {/* Delete button - only visible on hover */}
      {!isCollapsed && (
      <button
        onClick={onDelete}
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          padding: '4px 8px',
          backgroundColor: 'transparent',
          color: 'var(--color-text-muted)',
          border: 'none',
          borderRadius: '4px',
          fontSize: '16px',
          cursor: 'pointer',
          transition: 'all 0.2s',
          opacity: isHovered ? 0.6 : 0,
          pointerEvents: isHovered ? 'auto' : 'none',
          lineHeight: '1'
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.opacity = '1';
          e.currentTarget.style.color = 'var(--color-state-danger)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.opacity = '0.6';
          e.currentTarget.style.color = 'var(--color-text-muted)';
        }}
        title="Delete chat"
      >
        ×
      </button>
      )}

      {/* "Chat →" button - only visible when a thread is linked */}
      {!isCollapsed && onOpenChat && data?.threadId && (
        <button
          onClick={() => onOpenChat(data.threadId as string)}
          style={{
            position: 'absolute',
            top: '8px',
            right: '36px',
            padding: '3px 8px',
            backgroundColor: 'transparent',
            color: 'var(--color-action-link)',
            border: '1px solid var(--color-action-link)',
            borderRadius: '4px',
            fontSize: '12px',
            fontWeight: 600,
            cursor: 'pointer',
            transition: 'all 0.2s',
            opacity: isHovered ? 1 : 0,
            pointerEvents: isHovered ? 'auto' : 'none',
            lineHeight: '1.5',
            whiteSpace: 'nowrap',
          }}
          title="Open full Chat view"
        >
          Chat →
        </button>
      )}

      {/* Collapsed: nothing below the header */}
      {isCollapsed ? null : (
      <>
      {/* Initial greeting or first message */}
      <div style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'flex-start',
        marginBottom: '16px'
      }}>
        <Icon size={18} color="var(--color-text-secondary)" style={{ marginTop: '2px', flexShrink: 0 }} />
        <div style={{
          color: 'var(--color-text-body)',
          fontSize: '15px',
          lineHeight: '1.6',
          fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
          flex: 1
        }}>
          {messages.length === 0
            ? "What's up?"
            : messages[0].role === 'assistant'
              ? messages[0].content
              : "What's up?"
          }
        </div>
      </div>

      {/* Messages (skip first if it's assistant) + streaming bubble — all in the scroll area */}
      <div
        ref={messagesContainerRef}
        style={{
          maxHeight: '300px',
          overflowY: 'auto',
          marginBottom: '16px'
        }}
      >
        {messages.length > 0 && (
          messages
            .slice(messages[0].role === 'assistant' ? 1 : 0)
            .map((msg, idx) => (
              <div key={idx} style={{ marginBottom: '12px' }}>
                {/* Reasoning block for completed assistant messages */}
                {msg.role === 'assistant' && msg.thinking && (() => {
                  const isExp = expandedThinking[idx] ?? true;
                  return (
                    <div style={{
                      paddingLeft: '0.75rem',
                      borderLeft: '2px solid var(--color-border-paper)',
                      marginBottom: '8px',
                      transition: 'border-color 0.3s',
                    }}>
                      <button
                        type="button"
                        onClick={() => setExpandedThinking(prev => ({ ...prev, [idx]: !isExp }))}
                        style={{
                          width: '100%', display: 'flex', alignItems: 'center', gap: '0.4rem',
                          border: 'none', background: 'transparent', padding: 0,
                          color: 'var(--color-text-muted)', fontSize: '0.8rem',
                          fontStyle: 'italic', cursor: 'pointer', textAlign: 'left',
                        }}
                      >
                        <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {msg.thinking.slice(0, 60) || 'Thinking…'}
                        </span>
                        <span style={{ flexShrink: 0 }}>{isExp ? '‹' : '›'}</span>
                      </button>
                      {isExp && (
                        <div style={{
                          marginTop: '0.4rem', whiteSpace: 'pre-wrap',
                          fontSize: '0.8rem', lineHeight: 1.6,
                          color: 'var(--color-text-secondary)',
                        }}>
                          {msg.thinking}
                        </div>
                      )}
                    </div>
                  );
                })()}

                <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                  {msg.role === 'user' ? (
                    <>
                      <div style={{
                        width: '26px', height: '26px', borderRadius: '50%',
                        backgroundColor: 'var(--color-bg-hover)', flexShrink: 0,
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: '11px', color: 'var(--color-text-secondary)',
                        fontWeight: 600, fontFamily: 'system-ui'
                      }}>U</div>
                      <div style={{
                        color: 'var(--color-text-secondary)', fontSize: '15px',
                        lineHeight: '1.6', paddingTop: '2px',
                        fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
                      }}>{msg.content}</div>
                    </>
                  ) : (
                    <>
                      <Icon size={18} color="var(--color-text-secondary)" style={{ marginTop: '2px', flexShrink: 0 }} />
                      <div style={{
                        color: 'var(--color-text-body)', fontSize: '15px',
                        lineHeight: '1.6', paddingTop: '2px',
                        fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
                      }}>{msg.content}</div>
                    </>
                  )}
                </div>
              </div>
            ))
        )}

        {/* Streaming reasoning block — mirrors ChatMessageList style */}
        {isProcessing && streamingReasoning !== undefined && (
          <div style={{
            paddingLeft: '0.75rem',
            borderLeft: `2px solid ${isReasoningDone ? 'var(--color-border-paper)' : 'var(--color-action-link)'}`,
            marginBottom: '8px',
            transition: 'border-color 0.3s',
          }}>
            <button
              type="button"
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '0.4rem',
                border: 'none', background: 'transparent', padding: 0,
                color: 'var(--color-text-muted)', fontSize: '0.8rem',
                fontStyle: 'italic', cursor: 'default',
              }}
            >
              {!isReasoningDone && (
                <span style={{
                  width: '0.6rem', height: '0.6rem', borderRadius: '999px',
                  border: '2px solid var(--color-action-link)', borderTopColor: 'transparent',
                  display: 'inline-block', flexShrink: 0,
                  animation: 'spin 0.8s linear infinite',
                }} />
              )}
              <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                {streamingReasoning.slice(0, 60) || 'Thinking…'}
              </span>
            </button>
            <div style={{
              marginTop: '0.4rem', whiteSpace: 'pre-wrap',
              fontSize: '0.8rem', lineHeight: 1.6,
              color: 'var(--color-text-secondary)',
            }}>
              {streamingReasoning}
              {!isReasoningDone && (
                <span style={{
                  display: 'inline-block', width: '2px', height: '0.8em',
                  background: 'var(--color-text-muted)', marginLeft: '1px',
                  verticalAlign: 'text-bottom', animation: 'pulse 1s ease-in-out infinite',
                }} />
              )}
            </div>
          </div>
        )}

        {/* Streaming response bubble */}
        {isProcessing && streamingText !== undefined && (
          <div style={{ marginBottom: '4px', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
            <Icon size={18} color="var(--color-text-secondary)" style={{ marginTop: '2px', flexShrink: 0 }} />
            <div style={{
              color: 'var(--color-text-body)', fontSize: '15px',
              lineHeight: '1.6', paddingTop: '2px',
              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
            }}>
              {streamingText || ''}
              <span style={{
                display: 'inline-block', width: '2px', height: '1em',
                background: 'var(--color-text-secondary)', marginLeft: '2px',
                verticalAlign: 'text-bottom', animation: 'pulse 1s ease-in-out infinite'
              }} />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{
        display: 'flex',
        gap: '10px',
        alignItems: 'center',
        paddingTop: '4px'
      }}>
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={`Chat with ${voiceConfig.name}...`}
          disabled={isProcessing}
          style={{
            flex: 1,
            padding: '8px 12px',
            border: 'none',
            borderBottom: '2px solid var(--color-border-neutral)',
            fontSize: '15px',
            outline: 'none',
            backgroundColor: 'transparent',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
            color: 'var(--color-text-body)',
            transition: 'border-color 0.2s'
          }}
          onFocus={(e) => {
            e.currentTarget.style.borderBottomColor = 'var(--color-border-focus)';
          }}
          onBlur={(e) => {
            e.currentTarget.style.borderBottomColor = 'var(--color-border-neutral)';
          }}
        />
        <button
          onClick={handleSend}
          disabled={!inputValue.trim() || isProcessing}
          style={{
            padding: '6px 14px',
            backgroundColor: 'transparent',
            color: isProcessing || !inputValue.trim() ? 'var(--color-text-muted)' : 'var(--color-text-secondary)',
            border: '1.5px solid',
            borderColor: isProcessing || !inputValue.trim() ? 'var(--color-border-neutral)' : 'var(--color-border-paper)',
            borderRadius: '6px',
            fontSize: '14px',
            fontWeight: 500,
            cursor: isProcessing || !inputValue.trim() ? 'not-allowed' : 'pointer',
            transition: 'all 0.2s',
            fontFamily: 'system-ui',
            animation: isProcessing ? 'pulse 1.5s ease-in-out infinite' : 'none'
          }}
          onMouseEnter={(e) => {
            if (!isProcessing && inputValue.trim()) {
              e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
            }
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
        >
          {isProcessing ? '...' : '↵'}
        </button>
      </div>
      </>
      )}
    </div>
  );
}
