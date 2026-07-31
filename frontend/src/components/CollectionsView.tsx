import { useState, useEffect, useLayoutEffect, useRef, useMemo, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import type { Commentor } from '../engine/EditorEngine';
import { findNormalizedPhrase } from '../utils/textNormalize';
import { useAuth } from '../contexts/AuthContext';
import { STORAGE_KEYS } from '../constants/storageKeys';
import { getDateLocale } from '../i18n';
import { extractFirstLine } from '../utils/calendarStorage';
import { getLocalDayKey } from '../utils/timezone';
import { useMobile } from '../utils/mobileDetect';

// @@@ TypeScript interfaces
interface TimelineDay {
  date: string;
  isPast: boolean;
  isFuture: boolean;
  isToday: boolean;
  daysOffset: number;
}

type TimelinePicture = {
  date: string;
  base64: string;
  full_base64?: string;
  prompt: string;
};

interface TimelineEntryData {
  picture?: TimelinePicture;
  comments: Commentor[];
}

interface SessionSummary {
  id: string;
  date_key?: string | null;
  first_line?: string;
  name?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface CollectionsViewProps {
  isVisible: boolean;
  voiceConfigs: Record<string, any>;
  timezone: string;
}

export default function CollectionsView({ isVisible, voiceConfigs, timezone }: CollectionsViewProps) {
  const { i18n } = useTranslation();
  const dateLocale = getDateLocale(i18n.language);
  const isMobile = useMobile();
  return (
    <div style={{
      width: '100%',
      height: '100%',
      display: 'flex',
      fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
      background: 'var(--color-bg-app)',
      overflow: 'hidden'
    }}>
      <TimelinePage
        isVisible={isVisible}
        voiceConfigs={voiceConfigs}
        dateLocale={dateLocale}
        timezone={timezone}
        isMobile={isMobile}
      />
    </div>
  );
}

// @@@ Extract complete sentence containing a phrase
function extractCompleteSentence(text: string, phrase: string): string {
  const phraseIndex = findNormalizedPhrase(text, phrase);
  if (phraseIndex === -1) {
    return phrase;
  }

  const sentenceEndings = '.!?。！？\n';

  let sentenceStart = 0;
  for (let i = phraseIndex - 1; i >= 0; i--) {
    if (sentenceEndings.includes(text[i])) {
      sentenceStart = i + 1;
      break;
    }
  }

  let sentenceEnd = text.length;
  for (let i = phraseIndex + phrase.length; i < text.length; i++) {
    if (sentenceEndings.includes(text[i])) {
      sentenceEnd = i + 1;
      break;
    }
  }

  return text.slice(sentenceStart, sentenceEnd).trim();
}

// @@@ Helper to get icon emoji
function getIconForVoice(icon: string): string {
  const iconMap: Record<string, string> = {
    brain: '🧠',
    heart: '❤️',
    question: '❓',
    cloud: '☁️',
    masks: '🎭',
    eye: '👁️',
    fist: '✊',
    lightbulb: '💡',
    shield: '🛡️',
    wind: '💨',
    fire: '🔥',
    compass: '🧭'
  };
  return iconMap[icon] || '💭';
}

// @@@ Helper to get date in local timezone as YYYY-MM-DD
function getLocalDateString(date?: Date | string): string {
  const d = date ? new Date(date) : new Date();
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function formatDate(date: Date | string, locale: string): string {
  return new Date(date).toLocaleDateString(locale, {
    year: 'numeric',
    month: 'short',
    day: 'numeric'
  });
}

// @@@ Date helpers for dynamic timeline
function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function addDays(date: Date, delta: number): Date {
  const d = new Date(date);
  d.setDate(d.getDate() + delta);
  return d;
}

function makeTimelineDay(date: Date): TimelineDay {
  const today = startOfDay(new Date());
  const day = startOfDay(date);
  const diff = Math.round((day.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
  return {
    date: getLocalDateString(day),
    isPast: diff < 0,
    isFuture: diff > 0,
    isToday: diff === 0,
    daysOffset: diff
  };
}

function buildDayRange(startDate: Date, endDate: Date): TimelineDay[] {
  const days: TimelineDay[] = [];
  const cursor = startOfDay(startDate);
  const end = startOfDay(endDate);
  while (cursor.getTime() <= end.getTime()) {
    days.push(makeTimelineDay(cursor));
    cursor.setDate(cursor.getDate() + 1);
  }
  return days;
}

// @@@ Extract and truncate beginning of text for timeline preview
function getTextPreview(text: string, maxLength: number = 60): string {
  if (!text || text.trim().length === 0) return '';

  const cleaned = text.trim().replace(/\s+/g, ' ');
  const sentenceEndings = /[.!?。！？]/;
  const match = cleaned.match(sentenceEndings);

  let preview = '';
  if (match && match.index !== undefined && match.index < maxLength * 1.5) {
    preview = cleaned.substring(0, match.index + 1);
  } else {
    preview = cleaned.substring(0, maxLength);
  }

  if (preview.length > maxLength) {
    preview = preview.substring(0, maxLength).trim() + '...';
  }

  return preview;
}

// @@@ Card height for overlap calculation
const CARD_HEIGHT = 100;
const CARD_OVERLAP = 30; // 30% overlap for zigzag effect
const SLOT_HEIGHT = CARD_HEIGHT - CARD_OVERLAP;
const INITIAL_PAST_DAYS = 14;
const CHUNK_SIZE = 14;
const MAX_PAST_DAYS = 365;
const LOAD_THRESHOLD_PX = 200;
const VIRTUAL_BUFFER = 5;

interface TimelineCardProps {
  day: TimelineDay;
  dayData?: TimelineEntryData;
  hasData: boolean;
  isGenerating: boolean;
  textByDate: Map<string, string>;
  firstLineByDate: Map<string, string>;
  dateLocale: string;
  t: (key: string, options?: any) => string;
  onImageClick: (picture: TimelinePicture) => void;
  onGenerate?: (date: string) => void;
  side: 'left' | 'right';
  isMobile: boolean;
}

function TimelineCard({
  day,
  dayData,
  hasData,
  isGenerating,
  textByDate,
  firstLineByDate,
  dateLocale,
  t,
  onImageClick,
  onGenerate,
  side,
  isMobile
}: TimelineCardProps) {
  const cardCursor = dayData?.picture && !isGenerating ? 'pointer' : 'default';
  const textContent = textByDate.get(day.date);
  const firstLine = firstLineByDate.get(day.date);
  const commentCount = dayData?.comments?.length || 0;

  let description = '';
  if (isGenerating) {
    description = t('timeline.generating');
  } else if (day.isToday && !dayData?.picture) {
    description = '';
  } else if (firstLine) {
    description = firstLine;
  } else if (textContent) {
    description = getTextPreview(textContent);
  } else if (commentCount > 0) {
    description = t('timeline.entryCount', { count: commentCount });
  }

  // For left side: text on left, image on right (near center line)
  // For right side: image on left (near center line), text on right
  const isLeftSide = side === 'left';
  const useRowLayout = isMobile ? true : isLeftSide;
  const textAlign = isMobile ? 'left' : (isLeftSide ? 'right' : 'left');

  return (
    <div
      onClick={() => {
        if (dayData?.picture) {
          onImageClick(dayData.picture);
        }
      }}
      style={{
        display: 'flex',
        flexDirection: useRowLayout ? 'row' : 'row-reverse',
        alignItems: 'center',
        gap: '0.75rem',
        padding: '0.5rem',
        cursor: cardCursor,
        transition: 'transform 0.2s, box-shadow 0.2s',
        opacity: day.isPast && !hasData ? 0.5 : 1,
        width: '100%',
        height: `${CARD_HEIGHT}px`,
        boxSizing: 'border-box',
        background: 'color-mix(in srgb, var(--color-bg-app) 80%, transparent)',
        borderRadius: '8px',
      }}
      onMouseEnter={e => {
        if (dayData?.picture && !isGenerating) {
          e.currentTarget.style.transform = 'scale(1.02)';
          e.currentTarget.style.boxShadow = '0 4px 12px var(--color-shadow-soft)';
        }
      }}
      onMouseLeave={e => {
        e.currentTarget.style.transform = 'scale(1)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      {/* Text content - on the outer side */}
      <div style={{
        flex: 1,
        minWidth: 0,
        textAlign,
        paddingRight: isMobile ? 0 : (isLeftSide ? '0.5rem' : 0),
        paddingLeft: isMobile ? '0.5rem' : (isLeftSide ? 0 : '0.5rem'),
      }}>
        <div style={{
          fontSize: '13px',
          fontWeight: 600,
          color: day.isToday ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
          marginBottom: '0.25rem'
        }}>
          {day.isToday ? t('timeline.today') : formatDate(day.date, dateLocale)}
        </div>
        <div style={{
          fontSize: '12px',
          color: 'var(--color-text-secondary)',
          fontStyle: description ? 'normal' : 'normal',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          display: '-webkit-box',
          WebkitLineClamp: 2,
          WebkitBoxOrient: 'vertical',
          lineHeight: '1.4',
        }}>
          {description}
        </div>
      </div>

      {/* Image - on the inner side (near center line) */}
      <div style={{ flexShrink: 0 }}>
        {dayData?.picture ? (
          <div style={{ position: 'relative' }}>
            <img
              src={`data:image/${dayData.picture.base64?.startsWith('iVBOR') ? 'png' : 'jpeg'};base64,${dayData.picture.base64}`}
              alt={dayData.picture.prompt}
              style={{
                width: isMobile ? '64px' : '72px',
                height: isMobile ? '64px' : '72px',
                objectFit: 'cover',
                borderRadius: '6px',
                boxShadow: '0 2px 8px var(--color-shadow-medium)'
              }}
            />
            {onGenerate && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  if (!isGenerating) onGenerate(day.date);
                }}
                disabled={isGenerating}
                style={{
                  position: 'absolute',
                  top: '4px',
                  right: '4px',
                  width: '22px',
                  height: '22px',
                  borderRadius: '50%',
                  background: 'var(--color-bg-surface-solid)',
                  border: 'none',
                  cursor: isGenerating ? 'wait' : 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  opacity: 0.85,
                  transition: 'opacity 0.2s'
                }}
                onMouseEnter={e => {
                  if (!isGenerating) e.currentTarget.style.opacity = '1';
                }}
                onMouseLeave={e => {
                  e.currentTarget.style.opacity = '0.85';
                }}
                title="Redraw image"
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
                </svg>
              </button>
            )}
          </div>
        ) : (
          <div style={{
            width: isMobile ? '64px' : '72px',
            height: isMobile ? '64px' : '72px',
            background: day.isFuture
              ? 'linear-gradient(135deg, var(--color-bg-app) 0%, var(--color-bg-surface-solid) 100%)'
              : 'linear-gradient(135deg, var(--color-bg-paper) 0%, var(--color-bg-app) 100%)',
            border: day.isFuture ? '2px dashed var(--color-border-paper)' : '2px dashed var(--color-border-paper)',
            borderRadius: '6px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '20px',
            color: 'var(--color-text-muted)',
          }}>
            {isGenerating ? '⏳' : ''}
          </div>
        )}
      </div>
    </div>
  );
}

// @@@ Timeline page - combines pictures and comments by date
interface TimelinePageProps {
  isVisible: boolean;
  voiceConfigs: Record<string, any>;
  dateLocale: string;
  timezone: string;
  isMobile: boolean;
}

function TimelinePage({ isVisible, voiceConfigs, dateLocale, timezone, isMobile }: TimelinePageProps) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [days, setDays] = useState<TimelineDay[]>([]);
  const [sessionSummaries, setSessionSummaries] = useState<Map<string, SessionSummary>>(new Map());
  const [datesWithSessions, setDatesWithSessions] = useState<Set<string>>(new Set());
  const [allCommentsByDate, setAllCommentsByDate] = useState<Map<string, Commentor[]>>(new Map());
  const [textByDate, setTextByDate] = useState<Map<string, string>>(new Map());
  const [firstLineByDate, setFirstLineByDate] = useState<Map<string, string>>(new Map());
  const [picturesByDate, setPicturesByDate] = useState<Map<string, TimelinePicture>>(new Map());
  const [generatingForDate, setGeneratingForDate] = useState<string | null>(null);
  const [viewingImage, setViewingImage] = useState<{ base64: string; full_base64?: string; prompt: string; date: string; } | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);
  const [loadingCommentsForDate, setLoadingCommentsForDate] = useState<string | null>(null);
  const [loadingPast, setLoadingPast] = useState(false);
  const [hasMorePast, setHasMorePast] = useState(true);
  const [scrollTopValue, setScrollTopValue] = useState(0);
  const [viewportHeight, setViewportHeight] = useState(0);
  const [pendingInitialScroll, setPendingInitialScroll] = useState(true);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const topSentinelRef = useRef<HTMLDivElement | null>(null);
  const loadedRangesRef = useRef<Set<string>>(new Set());
  const cardInset = isMobile ? '1rem' : '2rem';
  const cardTopOffset = isMobile ? 20 : 32;

  const mergeSessions = useCallback((sessions: SessionSummary[]) => {
    setSessionSummaries(prev => {
      const next = new Map(prev);
      sessions.forEach((s) => next.set(s.id, s));
      return next;
    });
    setDatesWithSessions(prev => {
      const next = new Set(prev);
      sessions.forEach(s => {
        if (s.date_key) next.add(s.date_key);
      });
      return next;
    });
    setFirstLineByDate(prev => {
      const next = new Map(prev);
      sessions.forEach(s => {
        if (s.date_key && (s.first_line || s.name) && !next.has(s.date_key)) {
          next.set(s.date_key, s.first_line || s.name || 'Untitled');
        }
      });
      return next;
    });
  }, []);

  const mergePictures = useCallback((pictures: any[]) => {
    setPicturesByDate(prev => {
      const next = new Map(prev);
      pictures.forEach((p: any) => {
        next.set(p.date, {
          date: p.date,
          base64: p.base64,
          prompt: p.prompt || ''
        });
      });
      return next;
    });
  }, []);

  const loadRange = useCallback(async (rangeStart: Date, rangeEnd: Date) => {
    if (!isAuthenticated) return;
    const startKey = getLocalDateString(rangeStart);
    const endKey = getLocalDateString(rangeEnd);
    const cacheKey = `${startKey}|${endKey}|${timezone}`;
    if (loadedRangesRef.current.has(cacheKey)) return;
    loadedRangesRef.current.add(cacheKey);

    try {
      const { listSessions, getDailyPictures } = await import('../api/voiceApi');
      const [sessions, pictures] = await Promise.all([
        listSessions(timezone, { startDate: startKey, endDate: endKey }),
        getDailyPictures(CHUNK_SIZE * 2, { startDate: startKey, endDate: endKey })
      ]);
      mergeSessions(sessions);
      mergePictures(pictures);
    } catch (error) {
      loadedRangesRef.current.delete(cacheKey);
      console.error('Failed to load range:', error);
    }
  }, [isAuthenticated, mergePictures, mergeSessions, timezone]);

  useEffect(() => {
    let cancelled = false;
    const today = new Date();
    const start = addDays(today, -INITIAL_PAST_DAYS);
    const end = today;

    setInitialLoading(true);
    setLoadingPast(false);
    setHasMorePast(true);
    setPendingInitialScroll(true);
    setDays(buildDayRange(start, end));
    setSessionSummaries(new Map());
    setDatesWithSessions(new Set());
    setAllCommentsByDate(new Map());
    setTextByDate(new Map());
    setFirstLineByDate(new Map());
    setPicturesByDate(new Map());
    loadedRangesRef.current.clear();

    const run = async () => {
      if (isAuthenticated) {
        await loadRange(start, end);
      } else {
        const savedState = localStorage.getItem(STORAGE_KEYS.EDITOR_STATE);
        if (savedState) {
          try {
            const state = JSON.parse(savedState);
            const todayKey = formatDate(new Date(), dateLocale);
            const comments = state.commentors?.filter((c: Commentor) => c.appliedAt) || [];
            if (comments.length > 0) {
              setAllCommentsByDate(new Map([[todayKey, comments]]));
            }

            const guestTextMap = new Map<string, string>();
            const guestFirstLineMap = new Map<string, string>();
            if (state.cells) {
              const dateKey = state.createdAt || getLocalDateString();
              const combined = state.cells
                .filter((c: any) => c.type === 'text')
                .map((c: any) => c.content)
                .join(' ')
                .trim();

              if (combined) {
                guestTextMap.set(dateKey, combined);
                guestFirstLineMap.set(dateKey, extractFirstLine(state));
              }
            }
            setTextByDate(guestTextMap);
            setFirstLineByDate(guestFirstLineMap);
            setDatesWithSessions(new Set(Array.from(guestTextMap.keys())));
          } catch (error) {
            console.error('Failed to load guest state:', error);
          }
        }

        const savedPictures = localStorage.getItem(STORAGE_KEYS.DAILY_PICTURES);
        if (savedPictures) {
          try {
            const parsed = JSON.parse(savedPictures);
            mergePictures(parsed);
          } catch (error) {
            console.error('Failed to load pictures:', error);
          }
        }
      }

      if (!cancelled) {
        setInitialLoading(false);
      }
    };

    run();

    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, timezone, dateLocale, mergePictures, loadRange]);

  const loadPastChunk = useCallback(async () => {
    if (loadingPast || !hasMorePast || days.length === 0) return;
    setLoadingPast(true);
    const firstDay = days[0];
    const firstDate = startOfDay(new Date(firstDay.date));
    const desiredStart = addDays(firstDate, -CHUNK_SIZE);
    const minDate = addDays(startOfDay(new Date()), -MAX_PAST_DAYS);
    const actualStart = desiredStart < minDate ? minDate : desiredStart;
    const actualEnd = addDays(firstDate, -1);

    if (actualEnd.getTime() < actualStart.getTime()) {
      setHasMorePast(false);
      setLoadingPast(false);
      return;
    }

    const newDays = buildDayRange(actualStart, actualEnd);
    const container = scrollContainerRef.current;
    const prevScroll = container?.scrollTop ?? 0;
    const addedCount = newDays.length;

    setDays(prev => {
      const existing = new Set(prev.map(d => d.date));
      const merged = [...newDays.filter(d => !existing.has(d.date)), ...prev];
      return merged;
    });

    requestAnimationFrame(() => {
      if (container) {
        container.scrollTop = prevScroll + addedCount * SLOT_HEIGHT;
        setScrollTopValue(container.scrollTop);
      }
    });

    if (isAuthenticated) {
      await loadRange(actualStart, actualEnd);
    }

    const reachedMin = actualStart.getTime() <= minDate.getTime();
    setHasMorePast(!reachedMin);
    setLoadingPast(false);
  }, [days, hasMorePast, isAuthenticated, loadRange, loadingPast]);

  // @@@ Group items by date
  const timelineByDate = useMemo(() => {
    const map = new Map<string, TimelineEntryData>();

    datesWithSessions.forEach(date => {
      if (!map.has(date)) {
        map.set(date, { comments: [] });
      }
    });

    allCommentsByDate.forEach((comments, date) => {
      const entry = map.get(date) || { comments: [] };
      entry.comments = comments;
      map.set(date, entry);
    });

    picturesByDate.forEach((pic, date) => {
      const entry = map.get(date) || { comments: [] };
      entry.picture = pic;
      map.set(date, entry);
    });

    return map;
  }, [datesWithSessions, allCommentsByDate, picturesByDate]);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach(entry => {
          if (entry.isIntersecting && entry.target === topSentinelRef.current) {
            loadPastChunk();
          }
        });
      },
      {
        root: container,
        rootMargin: `${LOAD_THRESHOLD_PX}px 0px`,
        threshold: 0
      }
    );

    if (topSentinelRef.current) observer.observe(topSentinelRef.current);

    const handleScroll = () => {
      const top = container.scrollTop;
      setScrollTopValue(top);

      if (top < LOAD_THRESHOLD_PX) {
        loadPastChunk();
      }
    };

    const handleResize = () => {
      setViewportHeight(container.clientHeight);
      setScrollTopValue(container.scrollTop);
    };

    container.addEventListener('scroll', handleScroll);
    window.addEventListener('resize', handleResize);
    handleResize();

    return () => {
      observer.disconnect();
      container.removeEventListener('scroll', handleScroll);
      window.removeEventListener('resize', handleResize);
    };
  }, [loadPastChunk]);

  // @@@ Set initial scroll position to show today's row centered
  useLayoutEffect(() => {
    if (!isVisible || initialLoading || !scrollContainerRef.current || !pendingInitialScroll) return;
    const container = scrollContainerRef.current;
    requestAnimationFrame(() => {
      const bottom = Math.max(0, container.scrollHeight - container.clientHeight);
      container.scrollTop = bottom;
      setScrollTopValue(bottom);
      setPendingInitialScroll(false);
    });
  }, [days, initialLoading, isVisible, pendingInitialScroll]);

  const visibleMetrics = useMemo(() => {
    if (viewportHeight === 0) {
      return { renderStart: 0, renderEnd: days.length - 1 };
    }
    const effectiveScroll = Math.max(0, scrollTopValue - 32);
    const firstVisibleIndex = Math.floor(effectiveScroll / SLOT_HEIGHT);
    const visibleCount = Math.ceil((viewportHeight || 0) / SLOT_HEIGHT) + 1;
    const renderStart = Math.max(0, firstVisibleIndex - VIRTUAL_BUFFER);
    const renderEnd = Math.min(days.length - 1, firstVisibleIndex + visibleCount + VIRTUAL_BUFFER);
    return { renderStart, renderEnd };
  }, [days.length, scrollTopValue, viewportHeight]);

  const { renderStart, renderEnd } = visibleMetrics;
  const renderedDays = days.slice(renderStart, renderEnd + 1);
  const totalHeight = days.length > 0
    ? (days.length - 1) * SLOT_HEIGHT + CARD_HEIGHT + 32
    : 0;

  // @@@ Reload comments for a specific date from backend
  const reloadCommentsForDate = async (dateStr: string) => {
    setLoadingCommentsForDate(dateStr);

    try {
      if (isAuthenticated) {
        const sessionsForDate = Array.from(sessionSummaries.values()).filter(session => session.date_key === dateStr);

        if (sessionsForDate.length === 0) {
          setAllCommentsByDate(prev => {
            const next = new Map(prev);
            next.set(dateStr, []);
            return next;
          });
          return;
        }

        const { getSessionsBatch } = await import('../api/voiceApi');
        const batch = await getSessionsBatch(sessionsForDate.map(s => s.id));
        const commentsForDate: Commentor[] = [];

        batch.forEach((session: any) => {
          const comments = session.editor_state?.commentors || [];

          comments.filter((c: Commentor) => c.appliedAt).forEach((comment: Commentor) => {
            const rawTs = comment.appliedAt || comment.computedAt;
            const commentDate = getLocalDayKey(rawTs, timezone)
              || getLocalDateString(new Date(rawTs));
            if (commentDate === dateStr) {
              commentsForDate.push(comment);
            }
          });
        });

        setAllCommentsByDate(prev => {
          const next = new Map(prev);
          next.set(dateStr, commentsForDate);
          return next;
        });
      }
    } catch (error) {
      console.error('Failed to reload comments for date:', error);
    } finally {
      setLoadingCommentsForDate(null);
    }
  };

  const handleImageClick = async (picture: TimelinePicture) => {
    const stored = picturesByDate.get(picture.date) || picture;
    setViewingImage({ ...stored });

    if (!stored.full_base64 && isAuthenticated) {
      try {
        const { getDailyPictureFull } = await import('../api/voiceApi');
        const fullImage = await getDailyPictureFull(stored.date);

        const updatedPicture = { ...stored, full_base64: fullImage };
        setViewingImage(updatedPicture);

        setPicturesByDate(prev => {
          const next = new Map(prev);
          next.set(stored.date, updatedPicture);
          return next;
        });
      } catch (error) {
        console.error('Failed to load full image:', error);
      }
    }

    await reloadCommentsForDate(stored.date);
  };

  const handleGenerateForDate = async (dateStr: string) => {
    if (!isAuthenticated) {
      alert('Please log in to generate images. Image generation requires authentication.');
      return;
    }

    setGeneratingForDate(dateStr);

    try {
      const { generateDailyPicture, saveDailyPicture } = await import('../api/voiceApi');
      const { image_base64, thumbnail_base64, prompt } = await generateDailyPicture(dateStr, timezone);

      if (!image_base64) {
        alert('No notes found to generate an image. Please write and save entries first.');
        return;
      }

      const pictureDate = dateStr;

      const newPicture = {
        date: pictureDate,
        base64: thumbnail_base64 || image_base64,
        prompt: prompt
      };

      await saveDailyPicture(pictureDate, image_base64, prompt, thumbnail_base64);

      setPicturesByDate(prev => {
        const next = new Map(prev);
        next.set(pictureDate, newPicture);
        return next;
      });
    } catch (error) {
      console.error('Image generation failed:', error);
      const message = error instanceof Error ? error.message : 'Failed to generate image. Please try again.';
      alert(message);
    } finally {
      setGeneratingForDate(null);
    }
  };

  if (initialLoading) {
    return null;
  }

  return (
    <div
      ref={scrollContainerRef}
      style={{
        width: '100%',
        height: '100%',
        background: 'var(--color-bg-app)',
        overflowX: 'hidden',
        overflowY: 'auto',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        padding: '1rem 0'
      }}>
      {/* @@@ Alternating overlapping timeline - zigzag pattern */}
      <div
        style={{
          position: 'relative',
          maxWidth: '900px',
          width: '100%',
          padding: isMobile ? '1rem' : '2rem',
          paddingBottom: isMobile ? '4rem' : '5rem',
        }}
      >
        {/* Center line */}
        <div
          style={{
            position: 'absolute',
            left: '50%',
            top: isMobile ? '1rem' : '2rem',
            bottom: isMobile ? '4rem' : '5rem',
            width: isMobile ? '2px' : '4px',
            background: 'linear-gradient(180deg, transparent 0%, var(--color-border-paper) 2%, var(--color-border-paper) 98%, transparent 100%)',
            transform: 'translateX(-50%)',
            zIndex: 1,
            opacity: 1
          }}
        />

        {/* Manual load controls */}
        {hasMorePast && (
          <button
            onClick={loadPastChunk}
            disabled={loadingPast}
            style={{
              position: 'absolute',
              top: '0.5rem',
              left: '50%',
              transform: 'translateX(-50%)',
              padding: '6px 12px',
              border: '1px solid var(--color-border-paper)',
              background: loadingPast ? 'var(--color-disabled-bg)' : 'var(--color-bg-paper)',
              color: 'var(--color-text-secondary)',
              borderRadius: '6px',
              cursor: loadingPast ? 'wait' : 'pointer',
              zIndex: 20,
              fontSize: '12px'
            }}
          >
            {loadingPast ? 'Loading…' : 'Load earlier days'}
          </button>
        )}

        {/* Cards */}
        {renderedDays.map((day, localIndex) => {
          const globalIndex = renderStart + localIndex;
          const dayData = timelineByDate.get(day.date);
          const hasData = timelineByDate.has(day.date);
          const isGenerating = generatingForDate === day.date;
          const isLeftSide = globalIndex % 2 === 0;
          const topPosition = globalIndex * SLOT_HEIGHT;

          return (
            <div
              key={day.date}
              data-date={day.date}
              style={{
                position: 'absolute',
                top: `${topPosition + cardTopOffset}px`,
                left: isMobile ? '50%' : (isLeftSide ? cardInset : '50%'),
                right: isMobile ? 'auto' : (isLeftSide ? '50%' : cardInset),
                transform: isMobile ? 'translateX(-50%)' : 'none',
                paddingRight: isMobile ? 0 : (isLeftSide ? '24px' : '0'),
                paddingLeft: isMobile ? 0 : (isLeftSide ? '0' : '24px'),
                height: `${CARD_HEIGHT}px`,
                width: isMobile ? 'min(88vw, 460px)' : 'auto',
                zIndex: days.length - globalIndex, // Stack order for overlapping
              }}
            >
              {/* Timeline dot */}
              <div
                style={{
                  position: 'absolute',
                  top: '50%',
                  ...(isMobile
                    ? { left: '50%', transform: 'translate(-50%, -50%)' }
                    : { [isLeftSide ? 'right' : 'left']: '-10px', transform: 'translateY(-50%)' }),
                  width: '14px',
                  height: '14px',
                  borderRadius: '50%',
                  background: hasData ? 'var(--color-state-success)' : (day.isToday ? 'var(--color-text-secondary)' : 'var(--color-border-neutral)'),
                  border: '3px solid var(--color-bg-app)',
                  boxShadow: '0 2px 6px var(--color-shadow-medium)',
                  zIndex: 10,
                }}
              />
            
              <TimelineCard
                day={day}
                dayData={dayData}
                hasData={hasData}
                isGenerating={isGenerating}
                textByDate={textByDate}
                firstLineByDate={firstLineByDate}
                dateLocale={dateLocale}
                t={t}
                onImageClick={handleImageClick}
                onGenerate={handleGenerateForDate}
                side={isLeftSide ? 'left' : 'right'}
                isMobile={isMobile}
              />
            </div>
          );
        })}

        {/* Spacer to ensure container has correct height */}
        <div style={{ height: `${totalHeight}px` }} />
      </div>

      {/* Image Lightbox Modal */}
      {viewingImage && (
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
            zIndex: 9999,
            padding: isMobile ? '1rem' : '3rem'
          }}
          onClick={() => setViewingImage(null)}
        >
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              maxWidth: '1400px',
              width: '100%',
              maxHeight: isMobile ? '95vh' : '90vh',
              background: 'var(--color-bg-paper)',
              borderRadius: '12px',
              overflow: 'hidden',
              boxShadow: '0 8px 32px var(--color-shadow-medium)',
              marginTop: isMobile ? 0 : '2rem'
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Main content: Image + Comments */}
            <div style={{
              display: 'flex',
              flexDirection: isMobile ? 'column' : 'row',
              flex: 1,
              minHeight: 0,
              overflow: 'hidden'
            }}>
              {/* Image on left */}
              <div style={{
                flex: isMobile ? '0 0 auto' : '0 0 55%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: '#000',
                position: 'relative'
              }}>
                <img
                  src={`data:image/${(viewingImage.full_base64 || viewingImage.base64)?.startsWith('iVBOR') ? 'png' : 'jpeg'};base64,${viewingImage.full_base64 || viewingImage.base64}`}
                  alt="Generated image"
                  style={{
                    maxWidth: '100%',
                    maxHeight: '100%',
                    objectFit: 'contain'
                  }}
                />
                {/* Close button */}
                <button
                  onClick={() => setViewingImage(null)}
                  style={{
                    position: 'absolute',
                    top: '1.5rem',
                    right: '1.5rem',
                    background: 'var(--color-bg-surface-solid)',
                    border: 'none',
                    borderRadius: '50%',
                    width: '36px',
                    height: '36px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '22px',
                    color: 'var(--color-text-body)',
                    fontWeight: 'bold',
                    transition: 'all 0.2s',
                    boxShadow: '0 2px 8px var(--color-shadow-medium)'
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = 'var(--color-bg-hover)';
                    e.currentTarget.style.transform = 'scale(1.1)';
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = 'var(--color-bg-surface-solid)';
                    e.currentTarget.style.transform = 'scale(1)';
                  }}
                >
                  ×
                </button>
              </div>

              {/* Starred comments on right */}
              <div style={{
                flex: isMobile ? '1 1 auto' : '0 0 45%',
                background: 'var(--color-bg-surface)',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                minWidth: 0
              }}>
                {/* Header */}
                <div style={{
                  padding: isMobile ? '1rem 1.25rem 0.75rem' : '2rem 2rem 1rem',
                  borderBottom: '1px solid var(--color-border-paper)',
                  flexShrink: 0
                }}>
                  <div style={{
                    fontSize: '13px',
                    color: 'var(--color-text-muted)',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.1em'
                  }}>
                    Starred Comments
                  </div>
                </div>

                {/* Comments list - scrollable */}
                <div style={{
                  flex: 1,
                  overflowY: 'auto',
                  overflowX: 'hidden',
                  padding: isMobile ? '1rem 1.25rem' : '1.5rem 2rem',
                  minWidth: 0,
                  width: '100%',
                  boxSizing: 'border-box'
                }}>
                  {(() => {
                    const imageDate = viewingImage.date;

                    if (loadingCommentsForDate === imageDate) {
                      return (
                        <div style={{
                          textAlign: 'center',
                          color: 'var(--color-text-muted)',
                          fontSize: '14px',
                          fontStyle: 'italic',
                          padding: '2rem 1rem'
                        }}>
                          Loading comments...
                        </div>
                      );
                    }

                    const allCommentsForDate = allCommentsByDate.get(imageDate) || [];

                    let commentsToDisplay: Commentor[] = [];

                    const starredForDate = allCommentsForDate.filter(c => c.feedback === 'star');
                    if (starredForDate.length > 0) {
                      commentsToDisplay = starredForDate;
                    } else {
                      const chattedComments = allCommentsForDate.filter(c => c.chatHistory && c.chatHistory.length > 0);
                      if (chattedComments.length > 0) {
                        const mostRecentChatted = chattedComments.sort((a, b) =>
                          (b.appliedAt || b.computedAt) - (a.appliedAt || a.computedAt)
                        )[0];
                        commentsToDisplay = [mostRecentChatted];
                      } else {
                        if (allCommentsForDate.length > 0) {
                          const lastComment = allCommentsForDate.sort((a, b) =>
                            (b.appliedAt || b.computedAt) - (a.appliedAt || a.computedAt)
                          )[0];
                          commentsToDisplay = [lastComment];
                        }
                      }
                    }

                    if (commentsToDisplay.length === 0) {
                      return (
                        <div style={{
                          textAlign: 'center',
                          color: 'var(--color-text-muted)',
                          fontSize: '14px',
                          fontStyle: 'italic',
                          padding: '2rem 1rem'
                        }}>
                          No comments for this day
                        </div>
                      );
                    }

                    return (
                      <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '1rem',
                        minWidth: 0
                      }}>
                        {commentsToDisplay.map((comment) => (
                          <div
                            key={comment.id}
                            style={{
                              background: 'var(--color-bg-surface-solid)',
                              border: '1px solid var(--color-border-paper)',
                              borderRadius: '8px',
                              padding: '1rem',
                              transition: 'all 0.2s',
                              minWidth: 0
                            }}
                          >
                            <div style={{
                              display: 'flex',
                              alignItems: 'center',
                              gap: '0.5rem',
                              marginBottom: '0.75rem',
                              minWidth: 0
                            }}>
                              <span style={{ fontSize: '18px', flexShrink: 0 }}>{getIconForVoice(comment.icon)}</span>
                              <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--color-text-body)', flexShrink: 0 }}>{voiceConfigs[comment.voice]?.name || comment.voice}</span>
                              {comment.feedback === 'star' && (
                                <span style={{ fontSize: '14px', marginLeft: 'auto', flexShrink: 0 }}>⭐</span>
                              )}
                              {comment.chatHistory && comment.chatHistory.length > 0 && (
                                <span style={{ fontSize: '14px', marginLeft: comment.feedback === 'star' ? '0.5rem' : 'auto', flexShrink: 0 }}>💬</span>
                              )}
                            </div>
                            <div style={{
                              fontSize: '12px',
                              fontStyle: 'italic',
                              color: 'var(--color-text-muted)',
                              marginBottom: '0.75rem',
                              paddingLeft: '1.5rem',
                              borderLeft: '2px solid var(--color-border-paper)',
                              wordBreak: 'break-word',
                              overflowWrap: 'anywhere',
                              minWidth: 0
                            }}>
                              "{extractCompleteSentence(comment.textSnapshot || '', comment.phrase)}"
                            </div>
                            <div style={{
                              fontSize: '13px',
                              color: 'var(--color-text-secondary)',
                              lineHeight: '1.7',
                              paddingLeft: '0.5rem',
                              wordBreak: 'break-word',
                              overflowWrap: 'anywhere',
                              whiteSpace: 'pre-wrap',
                              minWidth: 0
                            }}>
                              {comment.comment}
                            </div>
                          </div>
                        ))}
                      </div>
                    );
                  })()}
                </div>
              </div>
            </div>

            {/* Bottom metadata bar */}
            <div style={{
              borderTop: '1px solid var(--color-border-paper)',
              background: 'var(--color-bg-app)',
              padding: isMobile ? '0.75rem 1.25rem' : '1rem 2rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexShrink: 0
            }}>
              <div style={{
                fontSize: '13px',
                color: 'var(--color-text-secondary)'
              }}>
                {new Date(viewingImage.date).toLocaleDateString(dateLocale, {
                  year: 'numeric',
                  month: 'long',
                  day: 'numeric'
                })}
              </div>
              <div style={{
                fontSize: '13px',
                color: 'var(--color-text-secondary)'
              }}>
                {(() => {
                  const commentCount =
                    (allCommentsByDate.get(viewingImage.date)?.length)
                    ?? (timelineByDate.get(viewingImage.date)?.comments?.length || 0);
                  return t('timeline.entryCount', { count: commentCount });
                })()}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}