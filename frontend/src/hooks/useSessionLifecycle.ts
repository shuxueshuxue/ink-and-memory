// [Input] Auth state, browser timezone, editor engine, session API helpers, and voice preference setters.
// [Output] Provide editor session lifecycle state, persistence helpers, and current user_session metadata.
// [Pos] session-lifecycle hook in frontend/src/hooks
// [Sync] 2026-06-01: expose current user_session.labels for the writing view StateChooser.
// [Sync] 2026-06-14: skip one automatic save after remote Agent-write session reload.
// [Sync] 2026-06-14: avoid scheduling auto-save debounce when the editor content signature is unchanged.
import { useCallback, useEffect, useRef, useState } from 'react';
import { EditorEngine } from '../engine/EditorEngine';
import type { EditorState, TextCell } from '../engine/EditorEngine';
import { STORAGE_KEYS } from '../constants/storageKeys';
import { EDIT_SESSION_AUTO_SAVE_DEBOUNCE_MS } from '../constants/sessionSync';
import { getLocalDayKey, getTodayKeyInTimezone } from '../utils/timezone';
import { saveMetaPrompt, getStateConfig as loadStateConfig } from '../utils/voiceStorage';
import type { SessionLabels, StateConfig, VoiceConfig } from '../api/voiceApi';

function createSessionId() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function getEditorStateContentSignature(editorState: EditorState): string {
  return JSON.stringify({
    cells: editorState.cells,
    commentors: editorState.commentors,
    tasks: editorState.tasks,
    weightPath: editorState.weightPath,
    overlappedPhrases: editorState.overlappedPhrases,
    notFoundPhrases: editorState.notFoundPhrases,
    selectedState: editorState.selectedState ?? null,
  });
}

type LegacyEditorState = EditorState & {
  currentEntryId?: string;
  sessionId?: string;
};

function collectTextCellContent(editorState: EditorState): Map<string, string> {
  const texts = new Map<string, string>();
  editorState.cells
    ?.filter((cell): cell is TextCell => cell.type === 'text')
    .forEach((cell) => {
      texts.set(cell.id, cell.content || '');
    });
  return texts;
}

type SetVoiceConfigs = React.Dispatch<React.SetStateAction<Record<string, VoiceConfig>>>;
type SetStateConfig = React.Dispatch<React.SetStateAction<StateConfig>>;

interface UseSessionLifecycleParams {
  isAuthenticated: boolean;
  browserTimezone: string;
  setVoiceConfigs: SetVoiceConfigs;
  setStateConfig: SetStateConfig;
}

export function useSessionLifecycle({
  isAuthenticated,
  browserTimezone,
  setVoiceConfigs,
  setStateConfig
}: UseSessionLifecycleParams) {
  const engineRef = useRef<EditorEngine | null>(null);
  const [state, setState] = useState<EditorState | null>(null);
  const [localTexts, setLocalTexts] = useState<Map<string, string>>(new Map());
  const [selectedState, setSelectedState] = useState<string | null>(null);
  const [selectedStateLoading, setSelectedStateLoading] = useState(true);
  const [userTimezone, setUserTimezone] = useState(browserTimezone);
  const [currentSessionLabels, setCurrentSessionLabels] = useState<SessionLabels>([]);

  const ensuredSessionForDayRef = useRef<string | null>(null);
  const userTimezoneRef = useRef(userTimezone);
  const timezoneSyncRef = useRef<string | null>(null);
  const latestStateRef = useRef<EditorState | null>(null);
  const autoSaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingAutoSaveSignatureRef = useRef<string | null>(null);
  const lastPersistedSessionSignatureRef = useRef<string | null>(null);

  latestStateRef.current = state;

  useEffect(() => {
    userTimezoneRef.current = userTimezone;
  }, [userTimezone]);

  const clearAutoSaveTimer = useCallback(() => {
    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
      autoSaveTimerRef.current = null;
    }
    pendingAutoSaveSignatureRef.current = null;
  }, []);

  const markSessionPersisted = useCallback((editorState: EditorState) => {
    const signature = getEditorStateContentSignature(editorState);
    lastPersistedSessionSignatureRef.current = signature;
    if (pendingAutoSaveSignatureRef.current === signature) {
      pendingAutoSaveSignatureRef.current = null;
    }
  }, []);

  const ensureStateForPersistence = useCallback((): EditorState | null => {
    if (!state) {
      console.error('Editor state is missing, cannot persist');
      return null;
    }

    if (state && !state.id) {
      throw new Error('Editor state is missing id');
    }

    return state;
  }, [state]);

  const getFirstLineFromState = useCallback((editorState: EditorState) => {
    const firstTextCell = editorState.cells.find(c => c.type === 'text') as TextCell | undefined;
    return firstTextCell?.content.split('\n')[0].trim() || 'Untitled';
  }, []);

  const saveSessionToDatabase = useCallback(async (editorState: EditorState, firstLine?: string) => {
    const line = firstLine ?? getFirstLineFromState(editorState);
    const { saveSession } = await import('../api/voiceApi');
    const idToSave = editorState.id || createSessionId();
    await saveSession(idToSave, editorState, line);
    markSessionPersisted(
      editorState.id === idToSave ? editorState : { ...editorState, id: idToSave }
    );

    if (engineRef.current) {
      const liveId = engineRef.current.getState().id;
      const snapshotId = editorState.id;
      const isSafeToUpdate = liveId === idToSave || liveId === snapshotId;

      if (isSafeToUpdate) {
        engineRef.current.setCurrentEntryId(idToSave);
      } else {
        console.warn(`🛡️ Race Condition Caught: Save finished for ${idToSave}, but editor is on ${liveId}. Skipping ID reset.`);
      }
    }
    return idToSave;
  }, [getFirstLineFromState, markSessionPersisted]);

  const persistSessionImmediately = useCallback(async (editorState: EditorState) => {
    if (!isAuthenticated) return;
    try {
      const firstLine = getFirstLineFromState(editorState);
      await saveSessionToDatabase(editorState, firstLine);
    } catch (error) {
      console.error('Failed to persist session immediately:', error);
    }
  }, [getFirstLineFromState, isAuthenticated, saveSessionToDatabase]);

  const buildBlankState = useCallback((options: { preserveSelectedState?: boolean; selectedStateOverride?: string | null } = {}): EditorState => {
    const {
      preserveSelectedState = true,
      selectedStateOverride
    } = options;
    const resolvedSelectedState = selectedStateOverride !== undefined
      ? selectedStateOverride
      : (preserveSelectedState
        ? (engineRef.current?.getState().selectedState ?? selectedState ?? null)
        : null);
    const newSessionId = createSessionId();
    return {
      cells: [{ id: Math.random().toString(36).slice(2), type: 'text' as const, content: '' }],
      commentors: [],
      tasks: [],
      weightPath: [],
      overlappedPhrases: [],
      notFoundPhrases: [],
      id: newSessionId,
      selectedState: resolvedSelectedState ?? undefined,
      createdAt: new Date().toISOString()
    };
  }, [selectedState]);

  const startDetachedBlankSession = useCallback(async (persistImmediately: boolean = false) => {
    if (!engineRef.current) return;
    const blankState = buildBlankState();

    engineRef.current.loadState(blankState);
    setState(blankState);
    setLocalTexts(new Map());
    setCurrentSessionLabels([]);

    if (!isAuthenticated) {
      localStorage.setItem(STORAGE_KEYS.EDITOR_STATE, JSON.stringify(blankState));
    } else if (persistImmediately) {
      await persistSessionImmediately(blankState);
    }
  }, [buildBlankState, isAuthenticated, persistSessionImmediately]);

  const handleNewSession = useCallback(async (currentState?: EditorState | null) => {
    const workingState = currentState ?? state;
    if (!workingState || !engineRef.current) return;

    if (isAuthenticated) {
      const hasContent = workingState.cells.some(c => c.type === 'text' && (c as TextCell).content.trim());

      if (hasContent) {
        try {
          const firstLine = getFirstLineFromState(workingState);
          await saveSessionToDatabase(workingState, firstLine);
        } catch (error) {
          console.error('❌ Failed to save current session:', error);
        }
      }
    }

    const emptyState = buildBlankState({ preserveSelectedState: false });
    engineRef.current.loadState(emptyState);
    setState(emptyState);
    setLocalTexts(new Map());
    setCurrentSessionLabels([]);

    if (!isAuthenticated) {
      localStorage.removeItem(STORAGE_KEYS.EDITOR_STATE);
      localStorage.removeItem(STORAGE_KEYS.SELECTED_STATE);
    }
  }, [buildBlankState, getFirstLineFromState, isAuthenticated, saveSessionToDatabase, state]);

  const confirmStartFresh = useCallback(async () => {
    if (!engineRef.current) return;

    const emptyState = buildBlankState({ preserveSelectedState: false });
    engineRef.current.loadState(emptyState);
    setState(emptyState);
    setLocalTexts(new Map());
    setCurrentSessionLabels([]);

    if (isAuthenticated) {
      try {
        const { saveSession } = await import('../api/voiceApi');
        await saveSession(emptyState.id, emptyState);
        markSessionPersisted(emptyState);
      } catch (error) {
        console.error('Failed to save new session:', error);
      }
    } else {
      localStorage.removeItem(STORAGE_KEYS.EDITOR_STATE);
      localStorage.removeItem(STORAGE_KEYS.SELECTED_STATE);
    }
  }, [buildBlankState, isAuthenticated, markSessionPersisted]);

  const handleSaveToday = useCallback(async () => {
    if (!engineRef.current) return;
    if (!isAuthenticated) {
      const toast = document.createElement('div');
      toast.textContent = 'Please sign in to save';
      toast.style.cssText = `
        position: fixed;
        top: 70px;
        right: 20px;
        background: var(--color-state-error);
        color: white;
        padding: 12px 20px;
        borderRadius: 6px;
        fontSize: 14px;
        fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
        zIndex: 10000;
        boxShadow: 0 4px 12px var(--color-shadow-medium);
      `;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => document.body.removeChild(toast), 300);
      }, 2000);
      return;
    }
    const currentState = ensureStateForPersistence();
    if (!currentState) return;

    try {
      const firstLine = getFirstLineFromState(currentState);
      const savedSessionId = await saveSessionToDatabase(currentState, firstLine);
      engineRef.current.setCurrentEntryId(savedSessionId);
      const toast = document.createElement('div');
      toast.textContent = 'Saved';
      toast.style.cssText = `
        position: fixed;
        top: 70px;
        right: 20px;
        background: var(--color-state-success);
        color: white;
        padding: 12px 20px;
        borderRadius: 6px;
        fontSize: 14px;
        fontFamily: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto;
        zIndex: 10000;
        boxShadow: 0 4px 12px var(--color-shadow-medium);
      `;
      document.body.appendChild(toast);
      setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => document.body.removeChild(toast), 300);
      }, 1200);
    } catch (error) {
      console.error('Failed to save session:', error);
    }
  }, [ensureStateForPersistence, getFirstLineFromState, isAuthenticated, saveSessionToDatabase]);

  useEffect(() => {
    if (!isAuthenticated) {
      setUserTimezone(browserTimezone);
      return;
    }

    if (timezoneSyncRef.current === browserTimezone) {
      return;
    }

    const syncTimezone = async () => {
      try {
        const timezone = browserTimezone || 'UTC';
        const { getPreferences, savePreferences } = await import('../api/voiceApi');
        const prefs = await getPreferences();
        if ((prefs?.timezone || 'UTC') !== timezone) {
          await savePreferences({ timezone });
          setUserTimezone(timezone);
        } else {
          setUserTimezone(prefs?.timezone || timezone);
        }
      } catch (error) {
        console.error('Failed to sync timezone preference:', error);
      } finally {
        timezoneSyncRef.current = browserTimezone;
      }
    };

    syncTimezone();
  }, [browserTimezone, isAuthenticated]);

  useEffect(() => {
    const sessionId = createSessionId();
    const engine = new EditorEngine(sessionId);
    engineRef.current = engine;

    const initialState = engine.getState();
    if (!initialState.createdAt) {
      initialState.createdAt = new Date().toISOString();
      setState(initialState);
    }
    markSessionPersisted(initialState);

    engine.subscribe((newState) => {
      setState({ ...newState });
      if (!isAuthenticated) {
        localStorage.setItem(STORAGE_KEYS.EDITOR_STATE, JSON.stringify(newState));
      }
    });
    const unsubscribeBlankReset = engine.onBlankReset(async () => {
      if (!isAuthenticated) return;
      const blankState = engine.getState();
      await persistSessionImmediately(blankState);
    });

    return () => {
      unsubscribeBlankReset();
    };
  }, [isAuthenticated, markSessionPersisted, persistSessionImmediately]);

  useEffect(() => {
    const loadInitialState = async () => {
      setSelectedStateLoading(true);
      try {
        if (isAuthenticated) {
          try {
            const { listSessions, getSession, getPreferences } = await import('../api/voiceApi');

            const sessions = await listSessions(userTimezoneRef.current);

            let sessionToLoad: LegacyEditorState | null = null;
            let loadedSessionId: string | undefined = undefined;
            let loadedSessionLabels: SessionLabels = [];
            let startedFreshForToday = false;
            const currentSessionId = 'current-session';
            const currentSession = sessions.find(s => s.id === currentSessionId);

            if (currentSession) {
              const fullSession = await getSession(currentSessionId);
              sessionToLoad = fullSession.editor_state;
              loadedSessionId = currentSessionId;
              loadedSessionLabels = fullSession.labels;
            } else if (sessions.length > 0) {
              const mostRecent = sessions.sort((a, b) =>
                new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
              )[0];

              const timezoneForDay = userTimezoneRef.current || 'UTC';
              const today = getTodayKeyInTimezone(timezoneForDay);
              const sessionDate = getLocalDayKey(mostRecent.updated_at, timezoneForDay);

              if (sessionDate === today) {
                const fullSession = await getSession(mostRecent.id);
                sessionToLoad = fullSession.editor_state;
                loadedSessionId = mostRecent.id;
                loadedSessionLabels = fullSession.labels;
              } else {
                console.log(`📅 New day detected. Last session was from ${sessionDate}, today is ${today}. Starting fresh.`);
                if (engineRef.current) {
                  // @@@ New Day Reset - force blank state so the chooser saves to today
                  const blankState: EditorState = {
                    cells: [{ id: Math.random().toString(36).slice(2), type: 'text', content: '' }],
                    commentors: [],
                    tasks: [],
                    weightPath: [],
                    overlappedPhrases: [],
                    notFoundPhrases: [],
                    id: createSessionId(),
                    selectedState: undefined,
                    createdAt: new Date().toISOString()
                  };

                  engineRef.current.loadState(blankState);
                  setState(blankState);
                  setLocalTexts(new Map());
                  setCurrentSessionLabels([]);
                  ensuredSessionForDayRef.current = today;
                  startedFreshForToday = true;
                  // @@@ New Day Guard - hand the fresh state to the loader so nothing older overwrites it below
                  sessionToLoad = blankState;
                  loadedSessionId = blankState.id;

                  await persistSessionImmediately(blankState);
                } else {
                  console.error('Engine not ready when starting fresh for new day');
                }
              }
            }

            if (sessionToLoad && loadedSessionId) {
              const normalizedState: EditorState = {
                ...sessionToLoad,
                id: sessionToLoad.id || sessionToLoad.currentEntryId || sessionToLoad.sessionId || loadedSessionId
              };
              engineRef.current?.loadState(normalizedState);
              markSessionPersisted(normalizedState);
              setState(engineRef.current?.getState() || normalizedState);
              setCurrentSessionLabels(loadedSessionLabels);
              setLocalTexts(collectTextCellContent(sessionToLoad));
            } else if (!startedFreshForToday) {
              setState(engineRef.current?.getState() || null);
              setCurrentSessionLabels([]);
            }

            try {
              const prefs = await getPreferences();
              if (prefs.voice_configs) {
                setVoiceConfigs(prefs.voice_configs);
              }
              if (prefs.meta_prompt) {
                saveMetaPrompt(prefs.meta_prompt);
              }
              if (prefs.state_config) {
                setStateConfig(prefs.state_config);
              }
              if (prefs.timezone) {
                setUserTimezone(prefs.timezone);
              }

              if (prefs.selected_state !== undefined && prefs.selected_state !== null) {
                const timezoneForDay = userTimezoneRef.current || 'UTC';
                const today = getTodayKeyInTimezone(timezoneForDay);
                const updatedAtDate = prefs.updated_at
                  ? getLocalDayKey(prefs.updated_at, timezoneForDay)
                  : null;

                if (updatedAtDate === today) {
                  setSelectedState(prefs.selected_state);
                } else {
                  setSelectedState(null);
                }
              }
            } catch {
              console.log('No preferences found, using defaults');
            }
          } catch (error) {
            console.error('Failed to load from database:', error);
            setState(engineRef.current?.getState() || null);
          }
        } else {
          const saved = localStorage.getItem(STORAGE_KEYS.EDITOR_STATE);
          if (saved) {
            try {
              const parsed = JSON.parse(saved) as EditorState;
              engineRef.current?.loadState(parsed);
              setState(engineRef.current?.getState() || parsed);
              setCurrentSessionLabels([]);
              setLocalTexts(collectTextCellContent(parsed));
            } catch (e) {
              console.error('Failed to load saved state:', e);
            }
          } else {
            setState(engineRef.current?.getState() || null);
            setCurrentSessionLabels([]);
          }

          const savedState = localStorage.getItem(STORAGE_KEYS.SELECTED_STATE);
          const savedDate = localStorage.getItem('selected-state-date');
          const today = getTodayKeyInTimezone(userTimezoneRef.current || browserTimezone);

          if (savedState && savedDate === today) {
            setSelectedState(savedState);
          } else {
            localStorage.removeItem(STORAGE_KEYS.SELECTED_STATE);
            localStorage.removeItem('selected-state-date');
            setSelectedState(null);
          }
        }
        if (!isAuthenticated) {
          setUserTimezone(browserTimezone);
        }
      } catch (error) {
        console.error('Failed to initialize session lifecycle:', error);
      } finally {
        setSelectedStateLoading(false);
      }
    };

    loadInitialState();
  }, [browserTimezone, isAuthenticated, markSessionPersisted, persistSessionImmediately, setStateConfig, setVoiceConfigs]);

  useEffect(() => {
    if (!isAuthenticated) return;
    if (!engineRef.current) return;
    if (selectedState !== null) return;
    const todayKey = getTodayKeyInTimezone(userTimezone);
    if (!todayKey) return;

    const currentState = engineRef.current.getState();
    const currentKey = currentState.createdAt
      ? getLocalDayKey(currentState.createdAt, userTimezone)
      : null;

    if (currentKey === todayKey) return;
    if (ensuredSessionForDayRef.current === todayKey) return;

    ensuredSessionForDayRef.current = todayKey;
    startDetachedBlankSession(true);
  }, [isAuthenticated, selectedState, startDetachedBlankSession, userTimezone]);

  useEffect(() => {
    if (!isAuthenticated) {
      clearAutoSaveTimer();
      return;
    }

    if (engineRef.current?.consumeLastLoadSource() === 'remote') {
      const remoteState = state ?? engineRef.current?.getState();
      if (remoteState) {
        markSessionPersisted(remoteState);
      }
      clearAutoSaveTimer();
      return;
    }

    if (!state) {
      clearAutoSaveTimer();
      return;
    }

    const currentSignature = getEditorStateContentSignature(state);
    if (currentSignature === lastPersistedSessionSignatureRef.current) {
      clearAutoSaveTimer();
      return;
    }

    if (currentSignature === pendingAutoSaveSignatureRef.current) {
      return;
    }

    if (autoSaveTimerRef.current) {
      clearTimeout(autoSaveTimerRef.current);
      autoSaveTimerRef.current = null;
    }
    pendingAutoSaveSignatureRef.current = currentSignature;

    const autoSaveTimer = setTimeout(async () => {
      autoSaveTimerRef.current = null;
      const stateSnapshot = latestStateRef.current;
      if (!stateSnapshot) {
        pendingAutoSaveSignatureRef.current = null;
        return;
      }

      const snapshotSignature = getEditorStateContentSignature(stateSnapshot);
      if (snapshotSignature === lastPersistedSessionSignatureRef.current) {
        pendingAutoSaveSignatureRef.current = null;
        return;
      }

      if (engineRef.current) {
        const liveId = engineRef.current.getState().id;
        const snapshotId = stateSnapshot.id;
        if (liveId && snapshotId && liveId !== snapshotId) {
          console.warn(`✋ Auto-save aborted: timer captured ${snapshotId} but editor is now on ${liveId}`);
          pendingAutoSaveSignatureRef.current = null;
          return;
        }
      }

      if (!stateSnapshot.id) {
        console.error('BUG: session id should always be defined after engine init');
        pendingAutoSaveSignatureRef.current = null;
        return;
      }

      try {
        const firstLine = getFirstLineFromState(stateSnapshot);
        await saveSessionToDatabase(stateSnapshot, firstLine);
        console.log('Auto-saved to database');
      } catch (error) {
        console.error('Auto-save failed:', error);
      } finally {
        if (pendingAutoSaveSignatureRef.current === snapshotSignature) {
          pendingAutoSaveSignatureRef.current = null;
        }
      }
    }, EDIT_SESSION_AUTO_SAVE_DEBOUNCE_MS);
    autoSaveTimerRef.current = autoSaveTimer;
  }, [clearAutoSaveTimer, getFirstLineFromState, isAuthenticated, markSessionPersisted, saveSessionToDatabase, state]);

  useEffect(() => {
    return () => clearAutoSaveTimer();
  }, [clearAutoSaveTimer]);

  useEffect(() => {
    setStateConfig(loadStateConfig());
  }, [setStateConfig]);

  return {
    engineRef,
    state,
    setState,
    localTexts,
    setLocalTexts,
    currentSessionLabels,
    setCurrentSessionLabels,
    selectedState,
    setSelectedState,
    selectedStateLoading,
    userTimezone,
    setUserTimezone,
    ensureStateForPersistence,
    getFirstLineFromState,
    saveSessionToDatabase,
    persistSessionImmediately,
    startDetachedBlankSession,
    handleNewSession,
    confirmStartFresh,
    handleSaveToday
  };
}
