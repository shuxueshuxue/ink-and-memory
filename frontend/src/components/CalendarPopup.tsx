// [Input] Calendar storage, auth context, i18n locale, timezone utils.
// [Output] Modal calendar popup with month grid and entry list.
// [Pos] calendar-popup component in frontend/src/components
// [Sync] 2026-05-29: replace all hardcoded colors with CSS tokens / color-mix for dark theme support.
import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { getDateLocale } from '../i18n';
import {
  getCalendarData,
  getDateKey,
  getTodayKey,
  deleteEntry,
  type CalendarEntry
} from '../utils/calendarStorage';
import { useAuth } from '../contexts/AuthContext';
import { parseFlexibleTimestamp } from '../utils/timezone';

interface Props {
  onLoadEntry: (entry: CalendarEntry) => void;
  onClose: () => void;
  currentEntryId?: string | null;
  onEntryDeleted?: (entryId: string) => void;
  timezone: string;
  initialDateKey?: string | null;
}

type CalendarListEntry = {
  id: string;
  timestamp: number;
  firstLine: string;
  state?: CalendarEntry['state'];
};

export default function CalendarPopup({ onLoadEntry, onClose, currentEntryId, onEntryDeleted, timezone, initialDateKey }: Props) {
  const { isAuthenticated } = useAuth();
  const { t, i18n } = useTranslation();
  const dateLocale = getDateLocale(i18n.language);
  const [currentMonth, setCurrentMonth] = useState(() => {
    if (initialDateKey) {
      const [y, m] = initialDateKey.split('-').map(Number);
      return new Date(y, m - 1, 1);
    }
    return new Date();
  });
  const [selectedDate, setSelectedDate] = useState<string | null>(initialDateKey ?? getTodayKey());
  const [calendarData, setCalendarData] = useState<Record<string, CalendarListEntry[]>>({});

  useEffect(() => {
    if (initialDateKey) {
      setSelectedDate(initialDateKey);
      const [y, m] = initialDateKey.split('-').map(Number);
      setCurrentMonth(new Date(y, m - 1, 1));
    }
  }, [initialDateKey]);

  const refreshCalendarData = useCallback(async () => {
    if (isAuthenticated) {
      try {
        const { listSessions } = await import('../api/voiceApi');
        const sessions = await listSessions(timezone);
        const grouped: Record<string, CalendarListEntry[]> = {};

        sessions.forEach((session: any) => {
          const dateKey = session.date_key || getTodayKey();
          const tsRaw = session.updated_at || session.created_at;
          const ts = parseFlexibleTimestamp(tsRaw)?.getTime() ?? Date.now();
          const firstLine = session.first_line || session.name || 'Untitled';
          if (!grouped[dateKey]) grouped[dateKey] = [];
          grouped[dateKey].push({
            id: session.id,
            timestamp: ts,
            firstLine
          });
        });

        setCalendarData(grouped);
        return;
      } catch (error) {
        console.error('Failed to load calendar from database:', error);
      }
    }
    const localData = getCalendarData();
    const mapped: Record<string, CalendarListEntry[]> = {};
    Object.entries(localData).forEach(([dateKey, entries]) => {
      mapped[dateKey] = entries.map((entry) => ({
        id: entry.id,
        timestamp: entry.timestamp,
        firstLine: entry.firstLine,
        state: entry.state
      }));
    });
    setCalendarData(mapped);
  }, [isAuthenticated, timezone]);

  useEffect(() => {
    refreshCalendarData();
  }, [refreshCalendarData]);

  const today = getTodayKey();
  const datesWithEntries = Object.keys(calendarData);

  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);
  const daysInMonth = lastDay.getDate();
  const startingDayOfWeek = firstDay.getDay();

  const days: Array<{ date: number; dateKey: string; hasEntries: boolean; isToday: boolean } | null> = [];

  for (let i = 0; i < startingDayOfWeek; i++) {
    days.push(null);
  }

  for (let date = 1; date <= daysInMonth; date++) {
    const dateObj = new Date(year, month, date);
    const dateKey = getDateKey(dateObj);
    days.push({
      date,
      dateKey,
      hasEntries: datesWithEntries.includes(dateKey),
      isToday: dateKey === today
    });
  }

  const handlePrevMonth = () => {
    setCurrentMonth(new Date(year, month - 1));
  };

  const handleNextMonth = () => {
    setCurrentMonth(new Date(year, month + 1));
  };

  const handleDateClick = (dateKey: string) => {
    setSelectedDate(dateKey);
  };

  const weekdayFormatter = new Intl.DateTimeFormat(dateLocale, { weekday: 'short' });
  const weekdayLabels = Array.from({ length: 7 }, (_, idx) => weekdayFormatter.format(new Date(Date.UTC(2023, 0, idx + 1))));

  const handleDeleteEntry = async (dateKey: string, entryId: string) => {
    if (confirm(t('calendar.deleteConfirm'))) {
      if (isAuthenticated) {
        try {
          const { deleteSession } = await import('../api/voiceApi');
          await deleteSession(entryId);
          await refreshCalendarData();
          onEntryDeleted?.(entryId);
        } catch (error) {
          console.error('Failed to delete from database:', error);
          alert(t('calendar.deleteError'));
        }
      } else {
        deleteEntry(dateKey, entryId);
        setCalendarData(getCalendarData());
        onEntryDeleted?.(entryId);
      }
    }
  };

  const selectedEntries = selectedDate ? calendarData[selectedDate] || [] : [];

  const handleOpenEntry = async (entry: CalendarListEntry) => {
    if (isAuthenticated) {
      try {
        const { getSession } = await import('../api/voiceApi');
        const full = await getSession(entry.id);
        if (!full?.editor_state) {
          alert(t('calendar.loadError'));
          return;
        }
        const payload: CalendarEntry = {
          id: entry.id,
          timestamp: entry.timestamp,
          state: full.editor_state,
          firstLine: entry.firstLine
        };
        onLoadEntry(payload);
        onClose();
      } catch (error) {
        console.error('Failed to load session:', error);
        alert(t('calendar.loadError'));
      }
    } else if (entry.state) {
      onLoadEntry(entry as CalendarEntry);
      onClose();
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: 'var(--color-bg-overlay)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2000,
        backdropFilter: 'blur(4px)'
      }}
      onClick={onClose}
    >
      <div
        role="presentation"
        style={{
          display: 'flex',
          gap: '24px',
          alignItems: 'flex-start',
          justifyContent: 'center',
          maxWidth: '1100px',
          width: 'min(94vw, 1100px)',
          maxHeight: '85vh',
          margin: '0 auto'
        }}
      >
        {/* Calendar grid - LEFT */}
        <div
          onClick={(e) => e.stopPropagation()}
          style={{
            flex: '0 0 auto',
            width: '460px',
            background: 'var(--color-bg-paper)',
            border: '2px solid var(--color-border-paper)',
            borderRadius: '16px',
            padding: '20px',
            boxShadow: '0 12px 40px var(--color-shadow-medium)',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}
        >
          {/* Month header */}
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '20px'
          }}>
            <button
              onClick={handlePrevMonth}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                fontSize: '20px',
                padding: '8px 12px',
                borderRadius: '8px',
                color: 'var(--color-text-secondary)',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--color-bg-hover)';
                e.currentTarget.style.color = 'var(--color-text-body)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = 'var(--color-text-secondary)';
              }}
            >
              ‹
            </button>
            <div style={{
              fontSize: '20px',
              fontWeight: 600,
              color: 'var(--color-text-primary)',
              letterSpacing: '0.5px'
            }}>
              {currentMonth.toLocaleDateString(dateLocale, { month: 'long', year: 'numeric' })}
            </div>
            <button
              onClick={handleNextMonth}
              style={{
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                fontSize: '20px',
                padding: '8px 12px',
                borderRadius: '8px',
                color: 'var(--color-text-secondary)',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = 'var(--color-bg-hover)';
                e.currentTarget.style.color = 'var(--color-text-body)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = 'var(--color-text-secondary)';
              }}
            >
              ›
            </button>
          </div>

          {/* Weekday headers */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: '4px',
            marginBottom: '8px'
          }}>
            {weekdayLabels.map((label, idx) => (
              <div key={`${label}-${idx}`} style={{
                textAlign: 'center',
                fontSize: '12px',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
                padding: '8px 0',
                textTransform: 'uppercase',
                letterSpacing: '0.5px'
              }}>
                {label}
              </div>
            ))}
          </div>

          {/* Days grid */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(7, 1fr)',
            gap: '6px'
          }}>
            {days.map((day, idx) => {
              if (!day) {
                return <div key={`empty-${idx}`} style={{ aspectRatio: '1' }} />;
              }

              const isSelected = selectedDate === day.dateKey;

              return (
                <button
                  key={day.dateKey}
                  onClick={() => handleDateClick(day.dateKey)}
                  style={{
                    aspectRatio: '1',
                    background: day.hasEntries
                      ? 'var(--color-bg-surface-solid)'
                      : 'transparent',
                    border: isSelected
                      ? '2px solid var(--color-border-focus)'
                      : 'none',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    fontSize: '15px',
                    fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                    position: 'relative',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'all 0.2s',
                    boxShadow: day.hasEntries
                      ? '0 2px 8px var(--color-shadow-soft)'
                      : 'none',
                    color: 'var(--color-text-body)',
                    fontWeight: day.isToday || isSelected ? 700 : 400
                  }}
                  onMouseEnter={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.transform = 'scale(1.05)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isSelected) {
                      e.currentTarget.style.transform = 'scale(1)';
                    }
                  }}
                >
                  {day.isToday ? (
                    <span style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      width: 28,
                      height: 28,
                      borderRadius: '50%',
                      border: '2px solid var(--color-state-warning)',
                      color: 'var(--color-text-body)',
                      background: isSelected ? 'var(--color-bg-surface-solid)' : 'transparent'
                    }}>
                      {day.date}
                    </span>
                  ) : (
                    <span>{day.date}</span>
                  )}
                    {day.hasEntries && (
                      <div style={{
                        position: 'absolute',
                        bottom: '6px',
                        width: '5px',
                        height: '5px',
                        borderRadius: '50%',
                        background: 'var(--color-action-link)'
                      }} />
                    )}
                  </button>
                );
              })}
          </div>
        </div>

        {/* Entry list - RIGHT */}
        {selectedDate && (
          <div
            style={{
              flex: '1 1 380px',
              minWidth: '320px',
              maxWidth: '480px',
              maxHeight: '70vh',
              display: 'flex',
              flexDirection: 'column'
            }}
          >
            {/* Header */}
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                background: 'var(--color-bg-paper)',
                borderRadius: '12px 12px 0 0',
                padding: '16px 20px',
                borderBottom: '1px solid var(--color-border-paper)',
                backdropFilter: 'blur(8px)',
                boxShadow: '0 -4px 20px var(--color-shadow-soft)'
              }}
            >
              <div style={{
                fontSize: '16px',
                fontWeight: 600,
                color: 'var(--color-text-body)',
                fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
              }}>
                {selectedDate === today
                  ? t('calendar.todayLabel')
                  : new Date(selectedDate + 'T00:00:00').toLocaleDateString(dateLocale, {
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric',
                    weekday: 'short'
                  })}
              </div>
              {selectedEntries.length > 0 && (
                <div style={{
                  fontSize: '13px',
                  color: 'var(--color-text-secondary)',
                  marginTop: '4px'
                }}>
                  {t('calendar.entriesLabel', { count: selectedEntries.length })}
                </div>
              )}
            </div>

            {/* Entries list */}
            <div
              onClick={(e) => e.stopPropagation()}
              style={{
                background: 'var(--color-bg-paper)',
                borderRadius: '0 0 12px 12px',
                padding: '12px',
                flex: 1,
                overflow: 'auto',
                backdropFilter: 'blur(8px)',
                boxShadow: '0 12px 40px var(--color-shadow-medium)'
              }}
            >
              {selectedEntries.length === 0 ? (
                <div style={{
                  textAlign: 'center',
                  color: 'var(--color-text-muted)',
                  padding: '32px 20px',
                  fontSize: '14px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
                }}>
                  {t('calendar.noEntriesForDate')}
                </div>
              ) : (
                <div style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px'
                }}>
                  {selectedEntries.map((entry) => {
                    const isCurrentEntry = currentEntryId === entry.id;
                    const time = new Date(entry.timestamp).toLocaleTimeString(dateLocale, {
                      hour: '2-digit',
                      minute: '2-digit'
                    });

                    return (
                      <div
                        key={entry.id}
                        style={{
                          borderRadius: '10px',
                          padding: '14px 16px',
                          background: isCurrentEntry
                            ? 'color-mix(in srgb, var(--color-state-success) 10%, var(--color-bg-surface-solid))'
                            : 'var(--color-bg-surface-solid)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center',
                          gap: '12px',
                          boxShadow: isCurrentEntry
                            ? `0 2px 12px var(--color-shadow-soft), inset 0 0 0 2px var(--color-state-success)`
                            : '0 2px 8px var(--color-shadow-soft)',
                          transition: 'all 0.2s',
                          minWidth: 0
                        }}
                      >
                        <button
                          title={t('calendar.openButton')}
                          onClick={() => handleOpenEntry(entry)}
                          style={{
                            flex: 1,
                            textAlign: 'left',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            padding: 0,
                            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                            minWidth: 0
                          }}
                        >
                          <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            marginBottom: '6px'
                          }}>
                            <div style={{
                              fontSize: '12px',
                              color: 'var(--color-text-secondary)',
                              fontWeight: 500,
                              flexShrink: 0
                            }}>
                              {time}
                            </div>
                            {isCurrentEntry && (
                              <span style={{
                                fontSize: '10px',
                                letterSpacing: '0.05em',
                                textTransform: 'uppercase',
                                padding: '3px 8px',
                                borderRadius: '999px',
                                background: 'var(--color-state-success)',
                                color: 'var(--color-text-on-action)',
                                fontWeight: 600,
                                flexShrink: 0
                              }}>
                                {t('calendar.currentEntryLabel')}
                              </span>
                            )}
                          </div>
                          <div style={{
                            fontSize: '14px',
                            color: 'var(--color-text-body)',
                            lineHeight: 1.4,
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            whiteSpace: 'nowrap',
                            display: 'block',
                            maxWidth: '100%'
                          }}>
                            {entry.firstLine}
                          </div>
                        </button>
                        <button
                          onClick={() => handleDeleteEntry(selectedDate, entry.id)}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            borderRadius: '6px',
                            padding: '6px 10px',
                            cursor: 'pointer',
                            fontSize: '12px',
                            color: 'var(--color-text-muted)',
                            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                            transition: 'all 0.2s',
                            flexShrink: 0
                          }}
                          onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'color-mix(in srgb, var(--color-state-danger) 12%, transparent)';
                            e.currentTarget.style.color = 'var(--color-state-danger)';
                          }}
                          onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'transparent';
                            e.currentTarget.style.color = 'var(--color-text-muted)';
                          }}
                        >
                          {t('calendar.deleteButton')}
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
