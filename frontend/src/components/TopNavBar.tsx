// [Sync] 2026-07-04: add Resource Connector navigation entry alongside the existing dashboard views.
// [Sync] 2026-07-08: Connector navigation now opens Settings -> resource links instead of the old chat-embedded workbench.
// [Sync] 2026-07-23: theme toggle now subscribes to the unified theme store (utils/theme), so the icon stays in sync
//                    when the theme is changed from Settings and the first click always switches visually.
import { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../contexts/AuthContext';
import { toggleTheme, getTheme, onThemeChange } from '../utils/theme';

interface Props {
  currentView: 'writing' | 'settings' | 'timeline' | 'analysis' | 'decks' | 'chat' | 'connector';
  onViewChange: (view: 'writing' | 'settings' | 'timeline' | 'analysis' | 'decks' | 'chat' | 'connector') => void;
}

export default function LeftSidebar({ currentView, onViewChange }: Props) {
  const { user, logout } = useAuth();
  const { t } = useTranslation();
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [isDark, setIsDark] = useState(() => getTheme() === 'dark');

  useEffect(() => {
    return onThemeChange((resolved) => {
      setIsDark(resolved === 'dark');
    });
  }, []);

  const handleToggleTheme = () => {
    toggleTheme();
  };

  const buttonStyle = (isActive: boolean) => ({
    height: '100%',
    minWidth: 120,
    padding: '0 26px',
    border: 'none',
    background: isActive ? 'var(--color-bg-hover)' : 'transparent',
    fontSize: 16,
    fontWeight: isActive ? 600 : 400,
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    transition: 'all 0.2s',
    color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
    position: 'relative' as const,
    borderBottom: isActive ? '3px solid var(--color-text-primary)' : '3px solid transparent',
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    letterSpacing: '-0.2px'
  });

  return (
    <div style={{
      position: 'fixed',
      left: 0,
      top: 0,
      right: 0,
      height: 52,
      background: 'var(--color-bg-app)',
      borderBottom: '1px solid var(--color-border-paper)',
      display: 'flex',
      flexDirection: 'row',
      alignItems: 'center',
      padding: '0 24px',
      gap: 8,
      zIndex: 999
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        marginRight: 40,
        fontSize: 17,
        fontFamily: 'Georgia, "Times New Roman", serif',
        letterSpacing: '-0.2px'
      }}>
        <span style={{
          fontSize: 20,
          fontWeight: 700,
          color: 'var(--color-text-primary)',
          fontStyle: 'italic'
        }}>I</span>
        <span style={{
          fontWeight: 400,
          color: 'var(--color-text-primary)'
        }}>nk & </span>
        <span style={{
          fontSize: 20,
          fontWeight: 700,
          color: 'var(--color-text-primary)',
          fontStyle: 'italic'
        }}>M</span>
        <span style={{
          fontWeight: 400,
          color: 'var(--color-text-primary)'
        }}>emory</span>
      </div>

      <div style={{
        display: 'flex',
        height: '100%',
        gap: 0
      }}>
        <button
          onClick={() => onViewChange('writing')}
          style={buttonStyle(currentView === 'writing')}
          title={t('nav.writing')}
          onMouseEnter={e => {
            if (currentView !== 'writing') {
              e.currentTarget.style.background = 'var(--color-bg-hover)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'writing') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          {t('nav.writing')}
        </button>

        <button
          onClick={() => onViewChange('timeline')}
          style={buttonStyle(currentView === 'timeline')}
          title={t('nav.timeline')}
          onMouseEnter={e => {
            if (currentView !== 'timeline') {
              e.currentTarget.style.background = 'var(--color-bg-hover)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'timeline') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          {t('nav.timeline')}
        </button>

        <button
          onClick={() => onViewChange('analysis')}
          style={buttonStyle(currentView === 'analysis')}
          title={t('nav.analysis')}
          onMouseEnter={e => {
            if (currentView !== 'analysis') {
              e.currentTarget.style.background = 'var(--color-bg-hover)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'analysis') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          {t('nav.analysis')}
        </button>

        <button
          onClick={() => onViewChange('decks')}
          style={buttonStyle(currentView === 'decks')}
          title={t('nav.decks')}
          onMouseEnter={e => {
            if (currentView !== 'decks') {
              e.currentTarget.style.background = 'var(--color-bg-hover)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'decks') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          {t('nav.decks')}
        </button>

        <button
          onClick={() => onViewChange('chat')}
          style={buttonStyle(currentView === 'chat')}
          title={t('nav.chat')}
          onMouseEnter={e => {
            if (currentView !== 'chat') {
              e.currentTarget.style.background = 'var(--color-bg-hover)';
            }
          }}
          onMouseLeave={e => {
            if (currentView !== 'chat') {
              e.currentTarget.style.background = 'transparent';
            }
          }}
        >
          {t('nav.chat')}
        </button>

      {/* Connector is no longer a standalone nav entry; it is reached via Settings -> resource links. */}
      </div>

      <div style={{ flex: 1 }} />

      {/* Theme toggle button */}
      <button
        onClick={handleToggleTheme}
        title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
        style={{
          width: 28,
          height: 28,
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          transition: 'all 0.2s',
          color: 'var(--color-text-secondary)',
          fontSize: 15,
          marginRight: 4
        }}
        onMouseEnter={e => { e.currentTarget.style.background = 'var(--color-bg-hover)'; }}
        onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; }}
      >
        {isDark ? '☀️' : '🌙'}
      </button>

      <button
        onClick={() => onViewChange('settings')}
        style={{
          width: 28,
          height: 28,
          borderRadius: 6,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: currentView === 'settings' ? 'var(--color-bg-hover)' : 'transparent',
          border: 'none',
          cursor: 'pointer',
          transition: 'all 0.2s',
          color: 'var(--color-text-secondary)',
          fontSize: 16
        }}
        onMouseEnter={e => {
          if (currentView !== 'settings') {
            e.currentTarget.style.background = 'var(--color-bg-hover)';
          }
        }}
        onMouseLeave={e => {
          if (currentView !== 'settings') {
            e.currentTarget.style.background = 'transparent';
          }
        }}
        title={t('nav.settings')}
      >
        <svg width="16" height="16" viewBox="0 0 20 20" fill="currentColor">
          <path d="M17.502 10c0 .34-.03.66-.07.98l2.11 1.65c.19.15.24.42.12.64l-2 3.46c-.12.22-.39.3-.61.22l-2.49-1c-.52.4-1.08.73-1.69.98l-.38 2.65c-.03.24-.24.42-.49.42h-4c-.25 0-.46-.18-.49-.42l-.38-2.65c-.61-.25-1.17-.59-1.69-.98l-2.49 1c-.23.09-.49 0-.61-.22l-2-3.46c-.13-.22-.07-.49.12-.64l2.11-1.65c-.04-.32-.07-.65-.07-.98 0-.33.03-.66.07-.98L.93 7.37c-.19-.15-.24-.42-.12-.64l2-3.46c.12-.22.39-.3.61-.22l2.49 1c.52-.4 1.08-.73 1.69-.98l.38-2.65C7.01.18 7.22 0 7.47 0h4c.25 0 .46.18.49.42l.38 2.65c.61.25 1.17.59 1.69.98l2.49-1c.23-.09.49 0 .61.22l2 3.46c.12.22.07.49-.12.64l-2.11 1.65c.04.32.07.65.07.98zm-7.5 3c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3z"/>
        </svg>
      </button>

      <div style={{ position: 'relative' }}>
        <button
          onClick={() => setShowUserMenu(!showUserMenu)}
          style={{
            width: 28,
            height: 28,
            borderRadius: 14,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'var(--color-state-success)',
            border: 'none',
            cursor: 'pointer',
            transition: 'all 0.2s',
            color: 'var(--color-text-on-action)',
            fontSize: 12,
            fontWeight: 600,
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
          }}
          onMouseEnter={e => {
            e.currentTarget.style.background = 'var(--color-state-success-hover)';
          }}
          onMouseLeave={e => {
            e.currentTarget.style.background = 'var(--color-state-success)';
          }}
          title="User Profile"
        >
          {user?.display_name?.[0]?.toUpperCase() || user?.email?.[0]?.toUpperCase() || 'U'}
        </button>

        {showUserMenu && (
          <>
            <div
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                zIndex: 998
              }}
              onClick={() => setShowUserMenu(false)}
            />
            <div style={{
              position: 'absolute',
              top: '100%',
              right: 0,
              marginTop: 8,
              width: 200,
              background: 'var(--color-bg-surface-solid)',
              border: '1px solid var(--color-border-paper)',
              borderRadius: 8,
              boxShadow: '0 4px 12px var(--color-shadow-medium)',
              zIndex: 999,
              overflow: 'hidden'
            }}>
              <div style={{
                padding: '12px 16px',
                borderBottom: '1px solid var(--color-border-neutral)',
                fontSize: 13,
                color: 'var(--color-text-body)'
              }}>
                <div style={{ fontWeight: 600, marginBottom: 4, color: 'var(--color-text-primary)' }}>
                  {user?.display_name || 'User'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--color-text-secondary)' }}>
                  {user?.email}
                </div>
              </div>
              <button
                onClick={() => {
                  logout();
                  setShowUserMenu(false);
                }}
                style={{
                  width: '100%',
                  padding: '10px 16px',
                  border: 'none',
                  background: 'transparent',
                  textAlign: 'left',
                  fontSize: 13,
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto',
                  color: 'var(--color-text-body)'
                }}
                onMouseEnter={e => {
                  e.currentTarget.style.background = 'var(--color-bg-hover)';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.background = 'transparent';
                }}
              >
                Logout
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
