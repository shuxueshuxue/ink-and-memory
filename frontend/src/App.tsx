// [Input] Consume React hooks, editor engine modules, app views/components, auth/session hooks, storage utilities, and API helpers.
// [Output] Render the authenticated Ink & Memory app shell and route current view state.
// [Pos] frontend app-root node in frontend/src
// [Sync] 2026-05-25: remove ChatView settings-navigation prop after left chat nav Settings button deletion.
// [Sync] 2026-05-29: pass state as editorState prop to ChatView so agent receives current EditorState snapshot.
// [Sync] 2026-05-29: add handleEditorWriteConfirmed callback; reloads session from DB after agent MCP write tool approved.
// [Sync] 2026-05-29: keep ChatView mounted after first open so chat state survives app view switches.
// [Sync] 2026-05-29: listen for editor:jump-to-cell custom event; switch to writing view and scroll+focus target textarea.
// [Sync] 2026-06-14: replace 2s MCP write blind wait with Edit Session SSE event sync plus timeout fallback.
// [Sync] 2026-05-30: fix handleAgentSelect to focus text cell after inserted widget; fixes "cannot insert cells after widget" bug.
// [Sync] 2026-05-30: restore inline Deck chat — handleAgentSelect inserts widget, stays in writing view; handleChatSend uses chatWithVoice with full context (allText, metaPrompt, statePrompt); "Chat →" button available when thread exists.
// [Sync] 2026-06-01: pass state as editorState to chatWithVoiceSSE in handleChatSend so inline widget agent receives editor_state.
// [Sync] 2026-06-01: pass current user_session.labels into StateChooser for writing-session metadata display.
// [Sync] 2026-05-29: fix bottom stats bar background from hardcoded #fafafa to var(--color-bg-paper) to match writing area.
// [Sync] 2026-06-23: route /oauth/device/verify to the Device Flow verification page before the main app shell.
// [Sync] 2026-07-04: add Resource Connector view entry and mobile/desktop navigation affordance.
// [Sync] 2026-07-05: make the connector viewport scrollable inside the fixed app shell so resource selection and source cards remain reachable.
// [Sync] 2026-07-07: route the connector entry into ChatView so the connector workbench lives under the chat shell instead of a standalone page.
// [Sync] 2026-07-07: mount ChatView in a fixed flex viewport so embedded connector panels cannot force page-level overflow.
// [Sync] 2026-07-08: route Connector navigation to Settings resource-link management and keep Chat on the lightweight landing panel only.
import React, { useState, useEffect, useLayoutEffect, useRef, useCallback, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import type { Commentor, EditorState, TextCell } from './engine/EditorEngine';
import { ChatWidget } from './engine/ChatWidget';
import type { ChatWidgetData } from './engine/ChatWidget';
import './App.css';
import {
  FaBrain, FaHeart, FaQuestion, FaCloud, FaTheaterMasks, FaEye,
  FaFistRaised, FaLightbulb, FaShieldAlt, FaWind, FaFire, FaCompass,
  FaPenNib, FaRegClock, FaChartBar, FaLayerGroup, FaCog, FaComments,
} from 'react-icons/fa';
import TopNavBar from './components/TopNavBar';
import LeftToolbar from './components/LeftToolbar';
import DeckManager from './components/DeckManager';
import CalendarPopup from './components/CalendarPopup';
import { type CalendarEntry } from './utils/calendarStorage';
import CollectionsView from './components/CollectionsView';
import AnalysisView from './components/AnalysisView';
import AboutView from './components/AboutView';
import AgentDropdown from './components/AgentDropdown';
import ChatWidgetUI from './components/ChatWidgetUI';
import StateChooser from './components/StateChooser';
import type { VoiceConfig } from './api/voiceApi';
import { getVoices, getStateConfig } from './utils/voiceStorage';
import { getDefaultVoices, chatWithVoiceSSE, importLocalData, loadVoicesFromDecks, ensureVoiceThread } from './api/voiceApi';
import { useMobile } from './utils/mobileDetect';
import { CommentGroupCard } from './components/CommentCard';
import { findNormalizedPhrase } from './utils/textNormalize';
import { useAuth } from './contexts/AuthContext';
import LoginForm from './components/Auth/LoginForm';
import RegisterForm from './components/Auth/RegisterForm';
import DeviceVerificationPage from './components/Auth/DeviceVerificationPage';
import { STORAGE_KEYS } from './constants/storageKeys';
import { getLocalDayKey, getTodayKeyInTimezone } from './utils/timezone';
import { useSessionLifecycle } from './hooks/useSessionLifecycle';
import { useInspiration } from './hooks/useInspiration';
import { InspirationHint } from './components/Editor/InspirationHint';
import { useComments } from './hooks/useComments';
import { useTextCells } from './hooks/useTextCells';
import { useVoiceInput } from './hooks/useVoiceInput';
import { useEditSessionEvents } from './hooks/useEditSessionEvents';
import ChatView from './components/chat/ChatView';
import ModelConfigSection from './components/dashboard/ModelConfigSection';
import ConnectorSettingsSection from './components/dashboard/ConnectorSettingsSection';
import ConnectorNotionDetailPage from './components/dashboard/ConnectorNotionDetailPage';
import type { ActiveChatVoice } from './lib/chat-schema';
import {
  EDITOR_WRITE_COMPLETED_TOOL_CACHE_MS,
  EDITOR_WRITE_EVENT_FALLBACK_TIMEOUT_MS,
} from './constants/sessionSync';

// @@@ Icon map with React Icons
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

const LANGUAGE_CODES: Array<'en' | 'zh'> = ['en', 'zh'];

// [Sync] 2026-07-08: Settings default sections use a narrower reading-width column;
// the Notion ConnectorNotionDetailPage owns a wider single-account resource
// configuration layout, so it gets its own max width instead of sharing SETTINGS_MAX_WIDTH_PX.
const SETTINGS_MAX_WIDTH_PX = 800;
const SETTINGS_CONNECTOR_DETAIL_MAX_WIDTH_PX = 1220;

// @@@ Color map with gradient colors for watercolor effect
const colorMap: Record<string, { gradient: string; text: string; glow: string }> = {
  blue: {
    gradient: 'linear-gradient(90deg, rgba(77,159,255,0) 0%, rgba(77,159,255,0.05) 30%, rgba(77,159,255,0.12) 60%, rgba(77,159,255,0.25) 100%)',
    text: '#0066cc',
    glow: 'rgba(77,159,255,0.15)'
  },
  pink: {
    gradient: 'linear-gradient(90deg, rgba(255,102,179,0) 0%, rgba(255,102,179,0.05) 30%, rgba(255,102,179,0.12) 60%, rgba(255,102,179,0.25) 100%)',
    text: '#cc0066',
    glow: 'rgba(255,102,179,0.15)'
  },
  yellow: {
    gradient: 'linear-gradient(90deg, rgba(255,221,51,0) 0%, rgba(255,221,51,0.05) 30%, rgba(255,221,51,0.12) 60%, rgba(255,221,51,0.25) 100%)',
    text: '#996600',
    glow: 'rgba(255,221,51,0.15)'
  },
  green: {
    gradient: 'linear-gradient(90deg, rgba(102,255,102,0) 0%, rgba(102,255,102,0.05) 30%, rgba(102,255,102,0.12) 60%, rgba(102,255,102,0.25) 100%)',
    text: '#006600',
    glow: 'rgba(102,255,102,0.15)'
  },
  purple: {
    gradient: 'linear-gradient(90deg, rgba(179,102,255,0) 0%, rgba(179,102,255,0.05) 30%, rgba(179,102,255,0.12) 60%, rgba(179,102,255,0.25) 100%)',
    text: '#6600cc',
    glow: 'rgba(179,102,255,0.15)'
  },
};

// @@@ Main App Component
export default function App() {
  const isMobile = useMobile();
  const { isAuthenticated, isLoading } = useAuth();
  const isDeviceVerificationRoute = window.location.pathname === '/oauth/device/verify';
  const { t, i18n } = useTranslation();
  const mobileNavHeight = 64;
  const mobileBottomOffset = isMobile
    ? `calc(${mobileNavHeight}px + env(safe-area-inset-bottom, 0px))`
    : '0px';
  const mobileTopInset = isMobile ? 'env(safe-area-inset-top, 0px)' : '48px';
  const viewTopOffset = isMobile ? 0 : 48;
  const writingBottomPadding = isMobile
    ? `calc(${mobileNavHeight}px + env(safe-area-inset-bottom, 0px) + 12px)`
    : '41px';

  // @@@ Auth screen state
  const [authScreen, setAuthScreen] = useState<'login' | 'register'>('login');
  const [showMigrationDialog, setShowMigrationDialog] = useState(false);
  const [isMigrating, setIsMigrating] = useState(false);
  const currentLanguage = (i18n.language || 'en').split('-')[0];
  const [showEnergyBar, setShowEnergyBar] = useState(() => {
    const stored = localStorage.getItem('show-energy-bar');
    return stored ? stored === 'true' : true;
  });

  useEffect(() => {
    localStorage.setItem('show-energy-bar', String(showEnergyBar));
  }, [showEnergyBar]);
  const handleUILanguageChange = useCallback((code: string) => {
    if (code !== currentLanguage) {
      i18n.changeLanguage(code);
    }
  }, [currentLanguage, i18n]);

  const [currentView, setCurrentView] = useState<'writing' | 'settings' | 'timeline' | 'analysis' | 'decks' | 'chat' | 'connector'>('writing');
  const [connectorSettingsFocusNonce, setConnectorSettingsFocusNonce] = useState(0);
  const [chatLandingTab, setChatLandingTab] = useState<'history' | 'connector'>('history');
  const [hasOpenedChatView, setHasOpenedChatView] = useState(false);
  const shouldRenderChatView = hasOpenedChatView || currentView === 'chat';
  const [showCalendarPopup, setShowCalendarPopup] = useState(false);
  const [voiceConfigs, setVoiceConfigs] = useState<Record<string, VoiceConfig>>({});
  // [Sync] 2026-07-08: track whether the dedicated Notion "具体配置页面" is open; navigating into it
  //                    replaces the whole Settings viewport instead of expanding inline within the
  //                    resource-link card, matching the connector interaction design's page navigation.
  const [showNotionConnectorDetail, setShowNotionConnectorDetail] = useState(false);

  const openConnectorSettings = useCallback(() => {
    setCurrentView('settings');
    setShowNotionConnectorDetail(false);
    setConnectorSettingsFocusNonce((value) => value + 1);
    setChatLandingTab('connector');
  }, []);

  const openNotionConnectorDetail = useCallback(() => {
    setShowNotionConnectorDetail(true);
  }, []);

  const closeNotionConnectorDetail = useCallback(() => {
    setShowNotionConnectorDetail(false);
    setConnectorSettingsFocusNonce((value) => value + 1);
  }, []);

  const handleAppViewChange = useCallback((view: 'writing' | 'settings' | 'timeline' | 'analysis' | 'decks' | 'chat' | 'connector') => {
    if (view === 'connector') {
      openConnectorSettings();
      return;
    }
    setCurrentView(view);
  }, [openConnectorSettings]);

  const browserTimezone = useMemo(() => {
    try {
      return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
    } catch {
      return 'UTC';
    }
  }, []);
  const [stateConfig, setStateConfig] = useState(() => getStateConfig());

  const {
    engineRef,
    state,
    setState,
    currentSessionLabels,
    setCurrentSessionLabels,
    selectedState,
    setSelectedState,
    selectedStateLoading,
    userTimezone,
    ensureStateForPersistence,
    getFirstLineFromState,
    saveSessionToDatabase,
    startDetachedBlankSession,
    handleNewSession,
    confirmStartFresh
  } = useSessionLifecycle({
    isAuthenticated,
    browserTimezone,
    setVoiceConfigs,
    setStateConfig
  });

  // @@@ Chat widget state
  const [dropdownVisible, setDropdownVisible] = useState(false);
  const [dropdownPosition, setDropdownPosition] = useState({ x: 0, y: 0 });
  const [dropdownTriggerCellId, setDropdownTriggerCellId] = useState<string | null>(null);
  const [chatProcessing, setChatProcessing] = useState<Set<string>>(new Set());
  /** Per-widget streaming state: text response + reasoning/thinking deltas. */
  const [chatStreaming, setChatStreaming] = useState<Map<string, { text: string; reasoning: string; reasoningDone: boolean }>>(new Map());
  /** @@@ Thread to open in ChatView (set when navigating from Deck or editor widget). */
  const [requestedChatThreadId, setRequestedChatThreadId] = useState<string | undefined>(undefined);
  /** @@@ Active deck voice shown in ChatView top-right badge; carries system prompt forwarded to the agent. */
  const [activeChatVoice, setActiveChatVoice] = useState<ActiveChatVoice | undefined>(undefined);

  // @@@ Warning dialog state
  const [showWarning, setShowWarning] = useState(false);

  const scrollContainerRef = useRef<HTMLDivElement>(null);  // @@@ Track scroll container for position preservation
  const savedScrollTop = useRef<number>(0);  // @@@ Save scroll position across re-renders

  // @@@ Comment alignment state
  const [commentsAligned, setCommentsAligned] = useState(false);

  // @@@ Writing inspiration/suggestion state
  const {
    currentInspiration,
    isDisappearing: inspirationDisappearing,
    isAppearing: inspirationAppearing,
    onTextChange: onInspirationTextChange,
    setTextGetter: setInspirationTextGetter,
  } = useInspiration();

  // @@@ Provide text getter to inspiration hook for validation
  useEffect(() => {
    setInspirationTextGetter(() => {
      if (!engineRef.current) return '';
      const cells = engineRef.current.getState().cells;
      return cells
        .filter(c => c.type === 'text')
        .map(c => (c as TextCell).content)
        .join('');
    });
  }, [setInspirationTextGetter]);

  // @@@ Text cell management (IME, refs, dropdown helpers)
  const {
    localTexts,
    composingCells,
    textareaRefs,
    refsReady,
    setRefsReady,
    handleTextChange,
    handleCompositionStart,
    handleCompositionEnd,
    handlePaste,
    handleKeyDown: handleTextCellKeyDown,
    createTextareaRef,
  } = useTextCells({
    engineRef,
    state,
    onInspirationTextChange,
    selectedState,
    dropdownVisible,
    dropdownTriggerCellId,
    onDropdownClose: () => {
      setDropdownVisible(false);
      setDropdownTriggerCellId(null);
    }
  });

  const { userTalking, handleToggleTalking } = useVoiceInput({
    engineRef,
    textareaRefs,
    isAuthenticated,
  });

  // @@@ Comment management (grouping, navigation, chat)
  const {
    commentGroups,
    groupPages,
    handleGroupNavigate,
    expandedCommentId,
    setExpandedCommentId,
    mobileActiveComment,
    handleCursorChange,
    handleCommentStar,
    handleCommentKill,
    handleCommentChatSend,
    commentChatProcessing,
  } = useComments({
    state,
    textareaRefs,
    refsReady,
    selectedState,
    stateConfig,
    isMobile,
    engineRef,
  });

  const pendingEditorWriteFallbacksRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());
  const completedEditorWriteToolIdsRef = useRef<Set<string>>(new Set());
  const completedEditorWriteCleanupRef = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const rememberCompletedEditorWriteTool = useCallback((toolCallId: string) => {
    completedEditorWriteToolIdsRef.current.add(toolCallId);

    const existingTimer = completedEditorWriteCleanupRef.current.get(toolCallId);
    if (existingTimer) clearTimeout(existingTimer);

    const cleanupTimer = setTimeout(() => {
      completedEditorWriteToolIdsRef.current.delete(toolCallId);
      completedEditorWriteCleanupRef.current.delete(toolCallId);
    }, EDITOR_WRITE_COMPLETED_TOOL_CACHE_MS);
    completedEditorWriteCleanupRef.current.set(toolCallId, cleanupTimer);
  }, []);

  const reloadEditorSessionFromDatabase = useCallback(async (sessionId: string) => {
    if (!isAuthenticated || !engineRef.current) return;
    const liveSessionId = engineRef.current.getState().id;
    if (liveSessionId !== sessionId) return;

    try {
      const { getSession } = await import('./api/voiceApi');
      const sessionData = await getSession(sessionId);
      if (sessionData?.editor_state && engineRef.current?.getState().id === sessionId) {
        const refreshed: EditorState = {
          ...sessionData.editor_state,
          id: sessionId,
        };
        engineRef.current.loadState(refreshed, { source: 'remote' });
        setState({ ...engineRef.current.getState() });
        setCurrentSessionLabels(sessionData.labels);
        setRefsReady(prev => prev + 1);
      }
    } catch (error) {
      console.error('Failed to reload editor state after agent write:', error);
    }
  }, [engineRef, isAuthenticated, setCurrentSessionLabels, setRefsReady, setState]);

  useEditSessionEvents(isAuthenticated, {
    onEvent: (event) => {
      if (event.type !== 'session_updated' || event.source !== 'agent' || !event.sessionId) {
        return;
      }

      if (event.toolCallId) {
        const pendingTimeout = pendingEditorWriteFallbacksRef.current.get(event.toolCallId);
        if (pendingTimeout) {
          clearTimeout(pendingTimeout);
          pendingEditorWriteFallbacksRef.current.delete(event.toolCallId);
        }
        rememberCompletedEditorWriteTool(event.toolCallId);
      }

      void reloadEditorSessionFromDatabase(event.sessionId);
    },
  });

  useEffect(() => {
    const pendingFallbacks = pendingEditorWriteFallbacksRef.current;
    const completedCleanup = completedEditorWriteCleanupRef.current;
    const completedToolIds = completedEditorWriteToolIdsRef.current;

    return () => {
      pendingFallbacks.forEach((timer) => clearTimeout(timer));
      pendingFallbacks.clear();
      completedCleanup.forEach((timer) => clearTimeout(timer));
      completedCleanup.clear();
      completedToolIds.clear();
    };
  }, []);

  const energyThreshold = 50;
  const appliedComments = state?.commentors.filter(c => c.appliedAt) ?? [];
  const lastEntry = state?.weightPath[state.weightPath.length - 1];
  const currentEnergy = lastEntry?.energy || 0;
  const usedEnergy = appliedComments.length * energyThreshold;
  const unusedEnergy = currentEnergy - usedEnergy;
  const safeUnusedEnergy = Math.max(unusedEnergy, 0);
  const energyLevel = Math.floor(safeUnusedEnergy / energyThreshold);
  const energyRemainder = safeUnusedEnergy % energyThreshold;
  const [energyPulseKey, setEnergyPulseKey] = useState(0);
  const energyLevelRef = useRef(0);
  const [showFullEnergy, setShowFullEnergy] = useState(false);
  const fullEnergyTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const energyProgress = showFullEnergy ? 1 : energyRemainder / energyThreshold;
  const mobileNavItems = [
    { key: 'writing' as const, label: t('nav.writing'), icon: FaPenNib },
    { key: 'timeline' as const, label: t('nav.timeline'), icon: FaRegClock },
    { key: 'analysis' as const, label: t('nav.analysis'), icon: FaChartBar },
    { key: 'decks' as const, label: t('nav.decks'), icon: FaLayerGroup },
    { key: 'chat' as const, label: t('nav.chat'), icon: FaComments },
    { key: 'settings' as const, label: t('nav.settings'), icon: FaCog },
  ];

  useEffect(() => {
    const prevLevel = energyLevelRef.current;
    if (energyLevel > prevLevel) {
      setEnergyPulseKey((key) => key + 1);
      setShowFullEnergy(true);
      if (fullEnergyTimeoutRef.current) {
        clearTimeout(fullEnergyTimeoutRef.current);
      }
      fullEnergyTimeoutRef.current = setTimeout(() => {
        setShowFullEnergy(false);
      }, 200);
    }
    energyLevelRef.current = energyLevel;
  }, [energyLevel]);

  useEffect(() => {
    return () => {
      if (fullEnergyTimeoutRef.current) {
        clearTimeout(fullEnergyTimeoutRef.current);
      }
    };
  }, []);

  // @@@ CRITICAL: Resize textareas then restore scroll position
  // Order matters: resize first (changes content height), then restore scroll
  // Triggers: on mount (refsReady) and when cells added/deleted (cells.length)
  useLayoutEffect(() => {
    // 1. Resize textareas first (if refs are ready)
    if (refsReady > 0) {
      textareaRefs.current.forEach((textarea) => {
        textarea.style.height = 'auto';
        textarea.style.height = textarea.scrollHeight + 'px';
      });
    }

    // 2. Then restore scroll position (after heights are correct)
    if (scrollContainerRef.current && savedScrollTop.current > 0) {
      scrollContainerRef.current.scrollTop = savedScrollTop.current;
    }
  }, [refsReady, state?.cells.length]);

  // @@@ Trigger re-render when returning to writing view to recalculate comment positions
  useEffect(() => {
    if (currentView === 'writing') {
      // Force re-render to recalculate comment positions
      setRefsReady(prev => prev + 1);
    }
  }, [currentView]);

  // @@@ Preserve ChatView local state after the first visit while avoiding eager thread creation on app load.
  useEffect(() => {
    if (currentView === 'chat') {
      setHasOpenedChatView(true);
    }
  }, [currentView]);

  // @@@ Force recalculation when selectedState changes (StateChooser height changes)
  useEffect(() => {
    if (selectedState) {
      // Small delay to ensure StateChooser has collapsed and DOM has settled
      const timer = setTimeout(() => {
        setRefsReady(prev => prev + 1);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [selectedState]);


  // @@@ Fetch default voices from backend and load from deck system
  useEffect(() => {
    getDefaultVoices().then(async backendVoices => {
      const converted: Record<string, VoiceConfig> = {};
      for (const [name, data] of Object.entries(backendVoices)) {
        const v = data as any;
        converted[name] = {
          name,
          systemPrompt: v.systemPrompt,  // @@@ Fixed: was v.tagline (wrong field name)
          enabled: true,
          icon: v.icon,
          color: v.color
        };
      }

      // @@@ Try loading from deck system first, then localStorage, then defaults
      const deckVoices = await loadVoicesFromDecks();
      const hasDecks = Object.keys(deckVoices).length > 0;
      const configs = hasDecks ? deckVoices : (getVoices() || converted);
      setVoiceConfigs(configs);

      console.log(`📚 Loaded voices from: ${hasDecks ? 'deck system' : 'localStorage or defaults'}`);

      // Update engine with voice configs
      if (engineRef.current) {
        engineRef.current.setVoiceConfigs(configs);
      }
    });
  }, []);

  // @@@ Update engine when voice configs change
  useEffect(() => {
    if (engineRef.current && Object.keys(voiceConfigs).length > 0) {
      engineRef.current.setVoiceConfigs(voiceConfigs);
    }
  }, [voiceConfigs]);

  // @@@ Reload state config when returning to writing view
  useEffect(() => {
    if (currentView === 'writing') {
      setStateConfig(getStateConfig());
    }
  }, [currentView]);

  // @@@ Check for localStorage migration after login
  useEffect(() => {
    const checkMigration = async () => {
      if (!isAuthenticated || isLoading) return;

      try {
        // Get user preferences from database (includes first_login_completed)
        const { getPreferences } = await import('./api/voiceApi');
        const preferences = await getPreferences();

        // If user has already completed first login, clear localStorage
        if (preferences?.first_login_completed) {
          // Clear all app data from localStorage (keep only auth token)
          Object.values(STORAGE_KEYS).forEach(key => {
            if (key !== STORAGE_KEYS.AUTH_TOKEN) {
              localStorage.removeItem(key);
            }
          });
          return;
        }

        // First time login - check for localStorage data to migrate
        const hasLocalData =
          localStorage.getItem(STORAGE_KEYS.EDITOR_STATE) ||
          localStorage.getItem(STORAGE_KEYS.CALENDAR_ENTRIES) ||
          localStorage.getItem(STORAGE_KEYS.DAILY_PICTURES) ||
          localStorage.getItem(STORAGE_KEYS.VOICE_CONFIGS) ||
          localStorage.getItem(STORAGE_KEYS.META_PROMPT) ||
          localStorage.getItem(STORAGE_KEYS.STATE_CONFIG) ||
          localStorage.getItem(STORAGE_KEYS.SELECTED_STATE) ||
          localStorage.getItem(STORAGE_KEYS.ANALYSIS_REPORTS);

        if (hasLocalData) {
          console.log('🔍 First login with localStorage data, showing migration dialog');
          setShowMigrationDialog(true);
        } else {
          // No localStorage data, just mark first login as completed
          console.log('🔍 First login without localStorage data, marking as completed');
          const { markFirstLoginCompleted } = await import('./api/voiceApi');
          await markFirstLoginCompleted();
        }
      } catch (error) {
        console.error('Failed to check migration status:', error);
      }
    };

    checkMigration();
  }, [isAuthenticated, isLoading]);

  // @@@ Keep focus on the lone blank text cell (after resets / clears)
  useEffect(() => {
    if (!state) return;

    const textCells = state.cells.filter(c => c.type === 'text') as TextCell[];
    if (textCells.length !== 1) return;

    const firstCell = textCells[0];
    if (firstCell.content.trim().length > 0) return;

    const focusEditor = () => {
      const textarea = textareaRefs.current.get(firstCell.id);
      if (textarea && document.activeElement !== textarea) {
        textarea.focus();
        textarea.selectionStart = 0;
        textarea.selectionEnd = 0;
      }
    };

    const textarea = textareaRefs.current.get(firstCell.id);
    if (textarea) {
      focusEditor();
      return;
    }

    const timer = window.setTimeout(focusEditor, 0);
    return () => window.clearTimeout(timer);
  }, [state, refsReady]);

  const handleConfirmStartFresh = useCallback(() => {
    setShowWarning(false);
    confirmStartFresh();
  }, [confirmStartFresh]);

  const handleNewSessionClick = useCallback(() => {
    handleNewSession(state);
  }, [handleNewSession, state]);

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
      }, 2000);
    } catch (error) {
      console.error('Failed to save:', error);
      // Show error toast
      const toast = document.createElement('div');
      toast.textContent = 'Save failed';
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
    }
  }, [ensureStateForPersistence, getFirstLineFromState, isAuthenticated, saveSessionToDatabase]);

  const handleLoadEntry = useCallback((entry: CalendarEntry) => {
    if (!engineRef.current) return;

    const nextState: EditorState = {
      ...entry.state,
      id: entry.id,
      createdAt: entry.state.createdAt ?? new Date().toISOString()
    };

    engineRef.current.loadState(nextState);
    setCurrentSessionLabels(entry.labels ?? []);
    if (nextState.selectedState !== undefined) {
      setSelectedState(nextState.selectedState);
    }

    setRefsReady(prev => prev + 1);
    setShowCalendarPopup(false);
  }, []);

  const handleCalendarEntryDeleted = useCallback((entryId: string) => {
    if (!entryId || !engineRef.current) return;
    const currentId = engineRef.current.getState().id;
    if (currentId === entryId) {
      startDetachedBlankSession();
    }
  }, [startDetachedBlankSession]);

    const handleStateChoose = useCallback(async (stateId: string) => {
      const todayKey = getTodayKeyInTimezone(userTimezone);

      if (engineRef.current) {
        const currentState = engineRef.current.getState();
        const sessionDate = currentState.createdAt
          ? getLocalDayKey(currentState.createdAt, userTimezone)
          : null;

        if (sessionDate && sessionDate !== todayKey) {
          console.log(`📅 State chosen for old session (${sessionDate}). Starting fresh for ${todayKey}.`);
          await startDetachedBlankSession(true);
        }

        const stateToUpdate = engineRef.current.getState();
        stateToUpdate.selectedState = stateId;
        if (!stateToUpdate.createdAt) {
          stateToUpdate.createdAt = new Date().toISOString();
        }
        setState(stateToUpdate);
      }

      setSelectedState(stateId);

      // @@@ KEEP: Also save to global preferences for daily reset check
      if (isAuthenticated) {
        try {
          const { savePreferences } = await import('./api/voiceApi');
          await savePreferences({ selected_state: stateId });
          // Database updated_at will be used for daily reset check
        } catch (error) {
          console.error('Failed to save state to database:', error);
        }
      } else {
        localStorage.setItem(STORAGE_KEYS.SELECTED_STATE, stateId);
        localStorage.setItem('selected-state-date', todayKey);
      }
    }, [isAuthenticated, startDetachedBlankSession, userTimezone]);

  // @@@ Insert @ character at the end of last text cell
  const handleInsertAgent = useCallback(() => {
    if (!state || !engineRef.current) return;

    // Find last text cell
    const lastTextCell = [...state.cells].reverse().find(c => c.type === 'text');
    if (!lastTextCell) return;

    const textarea = textareaRefs.current.get(lastTextCell.id);
    if (!textarea) return;

    // Insert @ character at the end
    const currentContent = (lastTextCell as TextCell).content;
    const newContent = currentContent + '@';

    // Update the text
    engineRef.current.updateTextCell(lastTextCell.id, newContent);

    // Focus the textarea and position cursor after @
    setTimeout(() => {
      textarea.focus();
      textarea.selectionStart = newContent.length;
      textarea.selectionEnd = newContent.length;

      // Show dropdown
      const rect = textarea.getBoundingClientRect();
      const computedStyle = window.getComputedStyle(textarea);
      const lineHeight = parseFloat(computedStyle.lineHeight) || 32;
      const linesBefore = newContent.substring(0, newContent.length).split('\n').length - 1;

      setDropdownPosition({
        x: rect.left + 10,
        y: rect.top + (linesBefore * lineHeight) + lineHeight + 5
      });
      setDropdownTriggerCellId(lastTextCell.id);
      setDropdownVisible(true);
    }, 0);
  }, [state]);

  // @@@ Toggle comment alignment
  const handleToggleAlign = useCallback(() => {
    setCommentsAligned(prev => !prev);
  }, []);

  // @@@ Reload editor state after Agent MCP write completion.
  // The primary path is /api/sessions/events (source=agent, keyed by toolCallId).
  // If the stream is unavailable, a bounded fallback pulls the current session.
  const handleEditorWriteConfirmed = useCallback((toolCallId?: string) => {
    if (!isAuthenticated || !state?.id || !engineRef.current) return;
    const sessionId = engineRef.current.getState().id || state.id;
    const fallbackKey = toolCallId || `session:${sessionId}`;

    if (toolCallId && completedEditorWriteToolIdsRef.current.has(toolCallId)) {
      return;
    }
    if (pendingEditorWriteFallbacksRef.current.has(fallbackKey)) {
      return;
    }

    const timeout = setTimeout(() => {
      pendingEditorWriteFallbacksRef.current.delete(fallbackKey);
      void reloadEditorSessionFromDatabase(sessionId);
    }, EDITOR_WRITE_EVENT_FALLBACK_TIMEOUT_MS);
    pendingEditorWriteFallbacksRef.current.set(fallbackKey, timeout);
  }, [engineRef, isAuthenticated, reloadEditorSessionFromDatabase, state?.id]);

  // @@@ Jump to a specific cell in the writing view (triggered by editor:jump-to-cell custom event)
  const jumpToCellRef = useRef<string | null>(null);

  useEffect(() => {
    const handler = (e: Event) => {
      const cellId = (e as CustomEvent<{ cellId: string }>).detail?.cellId;
      if (!cellId) return;
      jumpToCellRef.current = cellId;
      setCurrentView('writing');
    };
    window.addEventListener('editor:jump-to-cell', handler);
    return () => window.removeEventListener('editor:jump-to-cell', handler);
  }, []);

  useEffect(() => {
    if (currentView !== 'writing' || !jumpToCellRef.current) return;
    const cellId = jumpToCellRef.current;
    jumpToCellRef.current = null;
    const attemptScroll = (attempts = 0) => {
      const textarea = textareaRefs.current.get(cellId);
      if (textarea) {
        textarea.scrollIntoView({ behavior: 'smooth', block: 'center' });
        textarea.focus();
        return;
      }
      if (attempts < 10) {
        setTimeout(() => attemptScroll(attempts + 1), 80);
      }
    };
    setTimeout(() => attemptScroll(), 100);
  }, [currentView]);

  // @@@ Handle localStorage migration
  const handleMigrateData = useCallback(async () => {
    setIsMigrating(true);
    try {
      // Export all localStorage data (convert null to undefined)
      const migrationData = {
        currentSession: localStorage.getItem(STORAGE_KEYS.EDITOR_STATE) ?? undefined,
        calendarEntries: localStorage.getItem(STORAGE_KEYS.CALENDAR_ENTRIES) ?? undefined,
        dailyPictures: localStorage.getItem(STORAGE_KEYS.DAILY_PICTURES) ?? undefined,
        voiceCustomizations: localStorage.getItem(STORAGE_KEYS.VOICE_CONFIGS) ?? undefined,
        metaPrompt: localStorage.getItem(STORAGE_KEYS.META_PROMPT) ?? undefined,
        stateConfig: localStorage.getItem(STORAGE_KEYS.STATE_CONFIG) ?? undefined,
        selectedState: localStorage.getItem(STORAGE_KEYS.SELECTED_STATE) ?? undefined,
        analysisReports: localStorage.getItem(STORAGE_KEYS.ANALYSIS_REPORTS) ?? undefined,
        oldDocument: localStorage.getItem('document') ?? undefined
      };

      // Log what we're about to send
      console.log('📦 Migration data being sent:');
      console.log('  - currentSession:', migrationData.currentSession ? `${migrationData.currentSession.length} chars` : 'null');
      console.log('  - calendarEntries:', migrationData.calendarEntries ? `${migrationData.calendarEntries.length} chars` : 'null');
      console.log('  - dailyPictures:', migrationData.dailyPictures ? `${migrationData.dailyPictures.length} chars` : 'null');

      // Call backend migration endpoint
      const result = await importLocalData(migrationData);

      // Mark first login as completed in database
      const { markFirstLoginCompleted } = await import('./api/voiceApi');
      await markFirstLoginCompleted();

      // Clear ALL localStorage data (keep only auth token)
      Object.values(STORAGE_KEYS).forEach(key => {
        if (key !== STORAGE_KEYS.AUTH_TOKEN) {
          localStorage.removeItem(key);
        }
      });

      setShowMigrationDialog(false);

      // Show success message
      alert(`Migration successful! Imported:\n- ${result.imported.sessions} sessions\n- ${result.imported.pictures} pictures\n- ${result.imported.preferences} preferences\n- ${result.imported.reports} reports`);
    } catch (error: any) {
      console.error('Migration failed:', error);

      // Provide helpful error message based on error type
      let errorMsg = 'Migration failed: ';
      if (error.message?.includes('413') || error.message?.includes('too large')) {
        errorMsg += 'Your data is too large to migrate in one request.\n\n';
        errorMsg += 'This is a known issue that will be fixed soon.\n';
        errorMsg += 'For now, you can:\n';
        errorMsg += '1. Skip migration and start fresh, or\n';
        errorMsg += '2. Wait for the fix and try again later';
      } else {
        errorMsg += error.message + '\n\nYou can try again later from Settings.';
      }

      alert(errorMsg);
    } finally {
      setIsMigrating(false);
    }
  }, []);

  const handleSkipMigration = useCallback(async () => {
    try {
      // Mark first login as completed in database
      const { markFirstLoginCompleted } = await import('./api/voiceApi');
      await markFirstLoginCompleted();

      // Clear ALL localStorage data (keep only auth token)
      Object.values(STORAGE_KEYS).forEach(key => {
        if (key !== STORAGE_KEYS.AUTH_TOKEN) {
          localStorage.removeItem(key);
        }
      });

      setShowMigrationDialog(false);
    } catch (error) {
      console.error('Failed to skip migration:', error);
      alert('Failed to skip migration. Please try again.');
    }
  }, []);

  const handleAuthSuccess = useCallback(() => {
    // After successful login/register, check for migration
    // This is handled by the useEffect hook above
  }, []);

  // @@@ Handle @ key press for agent dropdown
  const handleKeyDown = useCallback((cellId: string, e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    handleTextCellKeyDown(cellId, e);

    if (e.key === '@' && !composingCells.has(cellId)) {
      const textarea = e.currentTarget;
      setTimeout(() => {
        if (textarea) {
          const cursorPos = textarea.selectionStart;
          const textBeforeCursor = textarea.value.substring(0, cursorPos);
          const lines = textBeforeCursor.split('\n');
          const linesBefore = lines.length - 1;
          const currentLineText = lines[lines.length - 1];

          const computedStyle = window.getComputedStyle(textarea);
          const lineHeight = parseFloat(computedStyle.lineHeight) || 32;
          const fontSize = parseFloat(computedStyle.fontSize) || 18;
          const rect = textarea.getBoundingClientRect();
          const padding = parseFloat(computedStyle.paddingLeft) || 0;

          const charWidth = fontSize * 0.6;
          const horizontalOffset = padding + (currentLineText.length * charWidth);

          setDropdownPosition({
            x: rect.left + horizontalOffset,
            y: rect.top + (linesBefore * lineHeight) + lineHeight + 5
          });
          setDropdownTriggerCellId(cellId);
          setDropdownVisible(true);
        }
      }, 0);
    }
  }, [composingCells, handleTextCellKeyDown]);

  // @@@ Navigate to Chat view with a specific thread (used by editor widgets and Deck manager).
  const handleOpenChatThread = useCallback((threadId: string, voiceInfo?: ActiveChatVoice) => {
    setRequestedChatThreadId(threadId);
    setActiveChatVoice(voiceInfo);
    setCurrentView('chat');
    setHasOpenedChatView(true);
  }, []);

  // @@@ Handle agent selection from dropdown — creates a Claude-agent thread and inserts an Agent Link widget.
  const handleAgentSelect = useCallback((voiceName: string, voiceConfig: VoiceConfig) => {
    setDropdownVisible(false);

    if (!engineRef.current || !dropdownTriggerCellId) return;

    const textarea = textareaRefs.current.get(dropdownTriggerCellId);
    if (!textarea) {
      setDropdownTriggerCellId(null);
      return;
    }

    const cursorPos = textarea.selectionStart;

    // Snapshot widget IDs before insertion to identify the newly added widget
    const beforeWidgetIds = new Set(
      engineRef.current.getState().cells
        .filter(c => c.type === 'widget')
        .map(c => c.id)
    );

    // Insert widget immediately (without thread_id yet – shows "Creating thread…")
    const chatWidget = new ChatWidget(voiceName, voiceConfig);
    engineRef.current.insertWidgetAtCursor(dropdownTriggerCellId, cursorPos, 'chat', chatWidget.getData());
    setDropdownTriggerCellId(null);

    // Identify the newly inserted widget
    const updatedCells = engineRef.current.getState().cells;
    const newWidget = updatedCells.find(c => c.type === 'widget' && !beforeWidgetIds.has(c.id));

    // Create Claude-agent thread asynchronously, then update widget with thread_id.
    // The user stays in the Writing view — the inline ChatWidgetUI handles the conversation.
    void (async () => {
      try {
        const threadId = await ensureVoiceThread(voiceName, voiceConfig.thread_id);
        if (newWidget && engineRef.current) {
          const widgetWithThread = new ChatWidget(voiceName, voiceConfig, threadId);
          engineRef.current.updateWidgetData(newWidget.id, widgetWithThread.getData());
        }
      } catch (err) {
        console.error('Failed to create Claude-agent thread for voice:', err);
      }
    })();

    // Focus the text cell immediately after the newly inserted widget
    if (newWidget) {
      const widgetIdx = updatedCells.findIndex(c => c.id === newWidget.id);
      const nextCell = widgetIdx >= 0 && widgetIdx + 1 < updatedCells.length
        ? updatedCells[widgetIdx + 1]
        : null;
      if (nextCell && nextCell.type === 'text') {
        const nextCellId = nextCell.id;
        setTimeout(() => {
          const nextTextarea = textareaRefs.current.get(nextCellId);
          if (nextTextarea) {
            nextTextarea.focus();
            nextTextarea.selectionStart = 0;
            nextTextarea.selectionEnd = 0;
          }
        }, 0);
      }
    }
  }, [dropdownTriggerCellId]);

  // @@@ Handle deleting chat widget
  const handleChatDelete = useCallback((widgetId: string) => {
    if (!engineRef.current) return;
    engineRef.current.deleteCell(widgetId);
  }, []);

  const handleChatToggleCollapse = useCallback((widgetId: string, collapsed: boolean) => {
    if (!engineRef.current || !state) return;
    const widgetCell = state.cells.find(c => c.type === 'widget' && c.id === widgetId);
    if (!widgetCell || widgetCell.type !== 'widget') return;
    const updated = { ...(widgetCell.data as ChatWidgetData), collapsed };
    engineRef.current.updateWidgetData(widgetId, updated);
  }, [state]);

  // @@@ Handle sending chat message — streams via Claude-agent SSE
  const handleChatSend = useCallback(async (widgetId: string, message: string) => {
    if (!engineRef.current || !state) return;

    const widgetCell = state.cells.find(c => c.type === 'widget' && c.id === widgetId);
    if (!widgetCell || widgetCell.type !== 'widget') return;

    const rawData = widgetCell.data as Partial<ChatWidgetData>;
    // Guard against malformed or old-format widget data
    const widgetData: ChatWidgetData = {
      id: rawData.id ?? widgetId,
      voiceName: rawData.voiceName ?? '',
      voiceConfig: rawData.voiceConfig ?? { name: 'Agent', tagline: '', icon: 'brain', color: 'blue' },
      threadId: rawData.threadId,
      messages: rawData.messages ?? [],
      createdAt: rawData.createdAt ?? Date.now(),
    };
    const chatWidget = ChatWidget.fromData(widgetData);

    // Optimistically add user message
    chatWidget.addUserMessage(message);
    engineRef.current.updateWidgetData(widgetId, chatWidget.getData());

    setChatProcessing(prev => new Set(prev).add(widgetId));
    setChatStreaming(prev => { const m = new Map(prev); m.set(widgetId, { text: '', reasoning: '', reasoningDone: false }); return m; });

    // Ensure the widget has a thread_id before sending
    let threadId = widgetData.threadId;
    if (!threadId) {
      try {
        threadId = await ensureVoiceThread(widgetData.voiceName, undefined);
        // Persist thread_id back into widget data
        chatWidget.getData().threadId = threadId;
        engineRef.current.updateWidgetData(widgetId, chatWidget.getData());
      } catch (err) {
        console.error('Failed to create thread for widget:', err);
        chatWidget.addAssistantMessage('Sorry, I could not start a session.');
        engineRef.current.updateWidgetData(widgetId, chatWidget.getData());
        setChatProcessing(prev => { const s = new Set(prev); s.delete(widgetId); return s; });
        setChatStreaming(prev => { const m = new Map(prev); m.delete(widgetId); return m; });
        return;
      }
    }

    const systemPrompt = widgetData.voiceConfig.tagline || '';

    await chatWithVoiceSSE({
      threadId,
      message,
      systemPrompt,
      editorState: state ? (state as unknown as Record<string, unknown>) : null,
      onDelta: (delta) => {
        setChatStreaming(prev => {
          const m = new Map(prev);
          const cur = m.get(widgetId) ?? { text: '', reasoning: '', reasoningDone: false };
          m.set(widgetId, { ...cur, text: cur.text + delta });
          return m;
        });
      },
      onReasoningDelta: (delta) => {
        setChatStreaming(prev => {
          const m = new Map(prev);
          const cur = m.get(widgetId) ?? { text: '', reasoning: '', reasoningDone: false };
          m.set(widgetId, { ...cur, reasoning: cur.reasoning + delta });
          return m;
        });
      },
      onReasoningEnd: () => {
        setChatStreaming(prev => {
          const m = new Map(prev);
          const cur = m.get(widgetId);
          if (cur) m.set(widgetId, { ...cur, reasoningDone: true });
          return m;
        });
      },
      onComplete: (fullText, reasoning) => {
        const currentCell = engineRef.current?.getState()?.cells.find(c => c.id === widgetId);
        const finalWidget = currentCell?.type === 'widget'
          ? ChatWidget.fromData(currentCell.data as ChatWidgetData)
          : chatWidget;
        finalWidget.addAssistantMessage(fullText || 'Sorry, I could not respond.', reasoning);
        engineRef.current?.updateWidgetData(widgetId, finalWidget.getData());
        setChatProcessing(prev => { const s = new Set(prev); s.delete(widgetId); return s; });
        setChatStreaming(prev => { const m = new Map(prev); m.delete(widgetId); return m; });
      },
      onError: (error) => {
        console.error('Chat SSE failed:', error);
        const currentCell = engineRef.current?.getState()?.cells.find(c => c.id === widgetId);
        const finalWidget = currentCell?.type === 'widget'
          ? ChatWidget.fromData(currentCell.data as ChatWidgetData)
          : chatWidget;
        finalWidget.addAssistantMessage('Sorry, I encountered an error.');
        engineRef.current?.updateWidgetData(widgetId, finalWidget.getData());
        setChatProcessing(prev => { const s = new Set(prev); s.delete(widgetId); return s; });
        setChatStreaming(prev => { const m = new Map(prev); m.delete(widgetId); return m; });
      },
    });
  }, [state]);

  // @@@ Helper to get watercolor background
  const getWatercolorBg = (color: string) => {
    const brushes: Record<string, string> = {
      yellow: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-9&color=ffff43)',
      blue: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-7&color=a3d5ff)',
      pink: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-8&color=ffb3d9)',
      green: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-6&color=b3ffb3)',
      purple: 'url(https://s2.svgbox.net/pen-brushes.svg?ic=brush-5&color=ddb3ff)'
    };
    return brushes[color] || 'none';
  };

  // @@@ Render highlighted text for a specific text content
  const renderHighlightedText = (text: string) => {
    if (!state) return null;

    const appliedComments = state.commentors.filter(c => c.appliedAt);

    if (appliedComments.length === 0) {
      return <div style={{ whiteSpace: 'pre-wrap' }}>{text}</div>;
    }

    // Find highlights in this specific text
    const highlights: Array<{ start: number; end: number; comment: Commentor }> = [];
    appliedComments.forEach(comment => {
      const index = findNormalizedPhrase(text, comment.phrase);
      if (index !== -1) {
        highlights.push({
          start: index,
          end: index + comment.phrase.length,
          comment
        });
      }
    });

    highlights.sort((a, b) => a.start - b.start);

    const elements: React.ReactNode[] = [];
    let lastEnd = 0;

    highlights.forEach((highlight, idx) => {
      if (highlight.start > lastEnd) {
        elements.push(
          <span key={`text-${idx}`}>
            {text.substring(lastEnd, highlight.start)}
          </span>
        );
      }

      elements.push(
        <span
          key={`highlight-${idx}`}
          className="voice-highlight"
          data-comment-id={highlight.comment.id}
          style={{
            margin: '-2px -6px',
            padding: '2px 6px',
            background: getWatercolorBg(highlight.comment.color),
            transition: 'all 0.2s ease'
          }}
        >
          {text.substring(highlight.start, highlight.end)}
        </span>
      );

      lastEnd = highlight.end;
    });

    if (lastEnd < text.length) {
      elements.push(
        <span key="text-final">
          {text.substring(lastEnd)}
        </span>
      );
    }

    return <div style={{ whiteSpace: 'pre-wrap' }}>{elements}</div>;
  };

  // @@@ Show loading state while checking auth
  if (isLoading) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
        fontSize: '18px',
        color: 'var(--color-text-secondary)'
      }}>
        Loading...
      </div>
    );
  }

  // @@@ Show auth screen if not authenticated
  const loginBannerUrl = `${import.meta.env.BASE_URL}login-banner.jpg`;

  if (isDeviceVerificationRoute) {
    return <DeviceVerificationPage />;
  }

  if (!isAuthenticated) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        background: `linear-gradient(135deg, rgba(245,240,232,0.8) 0%, rgba(232,220,200,0.9) 100%), url(${loginBannerUrl})`,
        backgroundSize: 'cover',
        backgroundPosition: 'center',
        backgroundRepeat: 'no-repeat',
        padding: '20px'
      }}>
        {authScreen === 'login' ? (
          <LoginForm
            onSuccess={handleAuthSuccess}
            onSwitchToRegister={() => setAuthScreen('register')}
          />
        ) : (
          <RegisterForm
            onSuccess={handleAuthSuccess}
            onSwitchToLogin={() => setAuthScreen('login')}
          />
        )}
      </div>
    );
  }

  if (!state || !engineRef.current) {
    return <div>Loading...</div>;
  }


  return (
    <>
      {/* @@@ Migration dialog */}
      {showMigrationDialog && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 10000,
          padding: '20px'
        }}>
          <div style={{
            backgroundColor: 'var(--color-bg-paper)',
            border: '2px solid var(--color-border-paper)',
            borderRadius: '12px',
            padding: '32px',
            maxWidth: '500px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.3)',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}>
            <h2 style={{
              margin: '0 0 16px 0',
              fontSize: '24px',
              color: 'var(--color-text-body)',
              fontWeight: 600
            }}>
              Migrate Your Data?
            </h2>
            <p style={{
              margin: '0 0 24px 0',
              fontSize: '16px',
              lineHeight: '1.6',
              color: 'var(--color-text-secondary)'
            }}>
              We found data in your browser. Would you like to migrate it to your account?
              This will move all your sessions, pictures, and preferences to the cloud.
            </p>
            <div style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'space-between'
            }}>
              <button
                onClick={handleMigrateData}
                disabled={isMigrating}
                style={{
                  flex: 1,
                  padding: '12px 20px',
                  border: 'none',
                  background: isMigrating ? 'var(--color-disabled-bg)' : 'var(--color-action-link)',
                  borderRadius: '6px',
                  cursor: isMigrating ? 'not-allowed' : 'pointer',
                  fontSize: '16px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: 'var(--color-text-on-action)',
                  fontWeight: 600,
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  if (!isMigrating) e.currentTarget.style.backgroundColor = 'var(--color-action-link-hover)';
                }}
                onMouseLeave={(e) => {
                  if (!isMigrating) e.currentTarget.style.backgroundColor = 'var(--color-action-link)';
                }}
              >
                {isMigrating ? 'Migrating...' : 'Migrate Data'}
              </button>
              <button
                onClick={handleSkipMigration}
                disabled={isMigrating}
                style={{
                  flex: 1,
                  padding: '12px 20px',
                  border: '1px solid var(--color-border-paper)',
                  background: 'var(--color-bg-surface-solid)',
                  borderRadius: '6px',
                  cursor: isMigrating ? 'not-allowed' : 'pointer',
                  fontSize: '16px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: 'var(--color-text-secondary)',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  if (!isMigrating) e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
                }}
                onMouseLeave={(e) => {
                  if (!isMigrating) e.currentTarget.style.backgroundColor = 'var(--color-bg-surface-solid)';
                }}
              >
                Skip
              </button>
            </div>
          </div>
        </div>
      )}

      {/* @@@ Hide top nav on mobile */}
      {!isMobile && <TopNavBar currentView={currentView} onViewChange={handleAppViewChange} />}

      {currentView === 'writing' && (
        <div style={{
          display: 'flex',
          height: '100vh',
          paddingTop: mobileTopInset,
          paddingBottom: writingBottomPadding,  // @@@ Space for fixed stats bar + mobile nav
          fontFamily: 'system-ui, -apple-system, sans-serif',
          boxSizing: 'border-box'
        }}>
          {/* New Session "+" button - top left (desktop only) */}
          {!isMobile && (
            <button
              onClick={handleNewSessionClick}
              title="New Session"
              style={{
                position: 'fixed',
                left: '20px',
                top: '72px',
                zIndex: 101,
                width: '32px',
                height: '32px',
                border: 'none',
                borderRadius: '50%',
                backgroundColor: 'var(--color-bg-surface-solid)',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 6px var(--color-shadow-medium)',
                fontSize: '20px',
                fontWeight: '300',
                color: 'var(--color-text-secondary)',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
                e.currentTarget.style.transform = 'scale(1.1)';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.backgroundColor = 'var(--color-bg-surface-solid)';
                e.currentTarget.style.transform = 'scale(1)';
              }}
            >
              +
            </button>
          )}

          {/* Left toolbar - floating on top (desktop only) */}
          {!isMobile && (
            <div style={{
              position: 'fixed',
              left: '12px',
              top: '100px',
              zIndex: 100
            }}>
              <LeftToolbar
                onInsertAgent={handleInsertAgent}
                onToggleAlign={handleToggleAlign}
                onShowCalendar={() => setShowCalendarPopup(true)}
                onSaveToday={handleSaveToday}
                onToggleTalking={handleToggleTalking}
                isAligned={commentsAligned}
                isTalking={userTalking}
              />
            </div>
          )}

          {/* @@@ Mobile floating toolbar - top right corner */}
          {isMobile && (
            <div style={{
              position: 'fixed',
              top: 'calc(10px + env(safe-area-inset-top, 0px))',
              right: '10px',
              display: 'flex',
              gap: '8px',
              zIndex: 1000
            }}>
              <button
                onClick={handleNewSessionClick}
                title="New Session"
                style={{
                  width: '44px',
                  height: '44px',
                  border: 'none',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-bg-surface-solid)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 6px var(--color-shadow-medium)',
                  fontSize: '24px',
                  fontWeight: '300',
                  color: 'var(--color-text-secondary)',
                  transition: 'all 0.2s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
                  e.currentTarget.style.transform = 'scale(1.1)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-bg-surface-solid)';
                  e.currentTarget.style.transform = 'scale(1)';
                }}
              >
                +
              </button>
              <button
                onClick={handleInsertAgent}
                title="Insert Agent Chat"
                style={{
                  width: '44px',
                  height: '44px',
                  border: 'none',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-bg-surface-solid)',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  boxShadow: '0 2px 8px var(--color-shadow-medium)',
                  transition: 'all 0.2s ease',
                  fontSize: '24px',
                  fontWeight: 600,
                  color: 'var(--color-text-body)',
                  fontFamily: 'monospace'
                }}
              >
                @
              </button>
            </div>
          )}

          <div
            style={{
              flex: 1,
              position: 'relative',
              overflow: 'hidden',
              // @@@ Disable horizontal scrolling on mobile
              ...(isMobile ? { overflowX: 'hidden', touchAction: 'pan-y' } : {})
            }}
          >
            <div style={{
              height: '100%',
              display: 'flex',
              flexDirection: 'column',
              width: '100%',
              margin: '0 auto'
            }}>
              <div
                ref={scrollContainerRef}  // @@@ Track scroll container for position preservation
                className="notebook-lines"
                onScroll={(e) => {
                  // @@@ Save scroll position whenever user scrolls manually
                  const target = e.currentTarget;
                  savedScrollTop.current = target.scrollTop;
                }}
                style={{
                  flex: 1,
                  position: 'relative',
                  overflow: 'auto',
                  padding: '20px',
                  paddingLeft: isMobile ? '20px' : '80px',  // @@@ Extra left padding for floating toolbar
                  paddingBottom: isMobile
                    ? `calc(80px + ${mobileNavHeight}px + env(safe-area-inset-bottom, 0px))`
                    : '80px',  // Extra space for smooth scrolling to bottom
                  backgroundColor: 'var(--color-bg-paper)'  // @@@ Cream paper background for notebook lines
                }}>
                <div style={{
                  position: 'relative',
                  maxWidth: '600px'
                }}>
                  {/* State chooser widget - always shown, collapses when state selected */}
                  <div style={{
                    height: '32px',  // @@@ Fixed height to match one line interval
                    marginBottom: '10.8px'  // @@@ 1/3 line interval (32.4px / 3)
                  }}>
                    <StateChooser
                      stateConfig={stateConfig}
                      selectedState={state?.selectedState ?? selectedState}
                      selectedStateLoading={selectedStateLoading}
                      createdAt={state?.createdAt}
                      sessionLabels={currentSessionLabels}
                      onChoose={handleStateChoose}
                    />
                  </div>

                  {/* Render cells sequentially with per-cell highlights */}
                  {state.cells.map((cell, idx) => {
                    if (cell.type === 'text') {
                      const textCell = cell as TextCell;
                      // Use local text if available, otherwise use engine state
                      const content = localTexts.get(cell.id) ?? textCell.content;

                      return (
                        <div key={cell.id} style={{
                          position: 'relative',
                          marginTop: idx === 0 ? '0.4px' : 0  // @@@ Align first line with 2nd notebook line
                        }}>
                          {/* Highlight layer for this cell */}
                          <div style={{
                            position: 'absolute',
                            top: 0,
                            left: 0,
                            right: 0,
                            pointerEvents: 'none',
                            fontSize: '18px',
                            lineHeight: '1.8',
                            color: 'transparent',
                            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                            zIndex: 0
                          }}>
                            {renderHighlightedText(content)}
                          </div>

                          {/* Textarea for this cell */}
                          <textarea
                            ref={createTextareaRef(cell.id)}
                            value={content}
                            onChange={(e) => handleTextChange(cell.id, e.target.value)}
                            onCompositionStart={() => handleCompositionStart(cell.id)}
                            onCompositionEnd={(e) => handleCompositionEnd(cell.id, e)}
                            onPaste={(e) => handlePaste(cell.id, e)}
                            onSelect={(e) => handleCursorChange(cell.id, e)}
                            onClick={(e) => handleCursorChange(cell.id, e)}
                            onKeyUp={(e) => handleCursorChange(cell.id, e)}
                            onKeyDown={(e) => handleKeyDown(cell.id, e)}
                            placeholder={idx === 0 ? "Start writing..." : "Continue writing..."}
                            style={{
                              width: '100%',
                              border: 'none',
                              outline: 'none',
                              resize: 'none',
                              fontSize: '18px',
                              lineHeight: '1.8',
                              fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                              background: 'transparent',
                              color: 'var(--color-text-body)',
                              caretColor: 'var(--color-text-body)',
                              position: 'relative',
                              zIndex: 1,
                              marginBottom: '0px',
                              overflow: 'hidden',
                              overflowWrap: 'break-word',
                              wordWrap: 'break-word',
                              whiteSpace: 'pre-wrap',
                              minHeight: '32px',
                              height: 'auto'
                            }}
                          />

                        </div>
                      );
                    } else if (cell.type === 'widget' && cell.widgetType === 'chat') {
                      return (
                        <ChatWidgetUI
                          key={cell.id}
                          data={cell.data as ChatWidgetData}
                          onSendMessage={(msg) => handleChatSend(cell.id, msg)}
                          onOpenChat={(cell.data as ChatWidgetData).threadId ? (threadId) => {
                            const d = cell.data as ChatWidgetData;
                            handleOpenChatThread(threadId, {
                              name: d.voiceConfig.name,
                              systemPrompt: d.voiceConfig.tagline,
                              icon: d.voiceConfig.icon,
                              color: d.voiceConfig.color,
                            });
                          } : undefined}
                          onDelete={() => handleChatDelete(cell.id)}
                          onToggleCollapse={(collapsed) => handleChatToggleCollapse(cell.id, collapsed)}
                          isProcessing={chatProcessing.has(cell.id)}
                          streamingText={chatStreaming.get(cell.id)?.text}
                          streamingReasoning={chatStreaming.get(cell.id)?.reasoning}
                          isReasoningDone={chatStreaming.get(cell.id)?.reasoningDone}
                        />
                      );
                    }
                    return null;
                  })}

                  {/* @@@ Inline Inspiration */}
                  <InspirationHint
                    inspiration={currentInspiration}
                    isDisappearing={inspirationDisappearing}
                    isAppearing={inspirationAppearing}
                  />
                </div>

                {/* Comments layer (absolute positioned) - hide on mobile */}
                {!isMobile && (() => {
                  // @@@ Calculate global max line width across all groups for alignment
                  const globalMaxLineWidth = Math.max(
                    0,
                    ...Array.from(commentGroups.values()).map(g => g.maxLineWidth)
                  );

                  return Array.from(commentGroups.entries()).map(([groupKey, group]) => {
                    const currentIndex = groupPages.get(groupKey) || 0;

                    // @@@ Get the specific textarea for this group's cell
                    const cellTextarea = textareaRefs.current.get(group.cellId);
                    if (!cellTextarea) return null;

                    // @@@ Use offsetTop relative to the content container (with maxWidth: 600px)
                    // This div is at line 1031 with position: relative
                    const cellWrapper = cellTextarea.parentElement; // The div with position: relative
                    if (!cellWrapper) return null;

                    const cellOffsetTop = cellWrapper.offsetTop;

                    // @@@ Calculate line height from textarea styles
                    const computedStyle = window.getComputedStyle(cellTextarea);
                    const fontSize = parseFloat(computedStyle.fontSize) || 18;
                    const lineHeightRatio = parseFloat(computedStyle.lineHeight) / fontSize || 1.8;
                    const lineHeight = fontSize * lineHeightRatio;

                    const containerPadding = parseFloat(window.getComputedStyle(cellWrapper.parentElement || cellWrapper).paddingLeft) || 20;
                    const gap = Math.max(30, window.innerWidth * 0.02);
                    // @@@ Use global max width when aligned, otherwise use group's max width
                    const lineWidthToUse = commentsAligned ? globalMaxLineWidth : group.maxLineWidth;
                    const leftPosition = containerPadding + lineWidthToUse + gap + (lineHeight * 2);  // @@@ Move right 2 line heights

                    // @@@ Position using offsetTop (scroll-independent)
                    // centerY is already relative to cell's top, so just add:
                    // - cellOffsetTop: position relative to content container
                    // - 20px: scroll container top padding
                    // - 32px: StateChooser fixed height
                    // - 10.8px: StateChooser marginBottom
                    // - subtract lineHeight * 2: move up to top of 2-line block
                    // - subtract lineHeight / 3: additional upward adjustment
                    const topPosition = cellOffsetTop + group.centerY + 20 + 32 + 10.8 - lineHeight * 2 - (lineHeight / 3);

                    // @@@ If expanded, use the expanded comment ID (stable), otherwise use current index
                    const isExpanded = group.comments.some(c => c.id === expandedCommentId);
                    const displayedComment = isExpanded
                      ? group.comments.find(c => c.id === expandedCommentId)!
                      : group.comments[currentIndex];
                    const displayedIndex = isExpanded
                      ? group.comments.findIndex(c => c.id === expandedCommentId)
                      : currentIndex;

                    if (!displayedComment) return null;

                    return (
                      <CommentGroupCard
                        key={groupKey}
                        comments={group.comments}
                        currentIndex={displayedIndex}
                        onNavigate={(idx) => handleGroupNavigate(groupKey, idx)}
                        position={{
                          top: topPosition,
                          left: leftPosition
                        }}
                        isExpanded={isExpanded}
                        onToggleExpand={() => {
                          setExpandedCommentId(prev => {
                            const anyExpanded = group.comments.some(c => c.id === prev);
                            if (anyExpanded) return null;
                            return displayedComment.id;
                          });
                        }}
                        onStar={() => handleCommentStar(displayedComment.id)}
                        onKill={() => handleCommentKill(displayedComment.id)}
                        onSendChatMessage={(msg) => handleCommentChatSend(displayedComment.id, msg)}
                        isChatProcessing={commentChatProcessing.has(displayedComment.id)}
                        voiceConfigs={voiceConfigs}
                      />
                    );
                  });
                })()}

                {/* @@@ Mobile comment popup - show when cursor is in highlighted area */}
                {isMobile && mobileActiveComment && (
                  <div style={{
                    position: 'fixed',
                    bottom: `calc(${mobileNavHeight}px + 20px + env(safe-area-inset-bottom, 0px))`,
                    left: '10px',
                    right: '10px',
                    background: 'var(--color-bg-surface-solid)',
                    border: '2px solid var(--color-border-neutral)',
                    borderRadius: '12px',
                    padding: '16px',
                    boxShadow: '0 8px 24px var(--color-shadow-medium)',
                    zIndex: 100,
                    fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                    animation: 'slideInFromBottom 0.3s ease-out'
                  }}>
                    <div style={{
                      display: 'flex',
                      gap: '12px',
                      alignItems: 'flex-start'
                    }}>
                      {(() => {
                        const Icon = iconMap[mobileActiveComment.icon as keyof typeof iconMap] || FaBrain;
                        const colors = colorMap[mobileActiveComment.color] || colorMap.blue;
                        return (
                          <>
                            <Icon size={20} color={colors.text} style={{ marginTop: '2px', flexShrink: 0 }} />
                            <div style={{ flex: 1 }}>
                              <div style={{ fontWeight: 600, fontSize: '16px', color: colors.text, marginBottom: '8px' }}>
                                {mobileActiveComment.voice}
                              </div>
                              <div style={{ fontSize: '15px', lineHeight: '1.5', color: 'var(--color-text-body)' }}>
                                {mobileActiveComment.comment}
                              </div>
                            </div>
                          </>
                        );
                      })()}
                    </div>
                  </div>
                )}
              </div>

              {/* Debug stats bar at bottom */}
              <div style={{
                position: 'fixed',
                bottom: isMobile ? mobileBottomOffset : 0,
                left: 0,
                right: 0,
                padding: isMobile ? '8px 12px' : '10px 20px',
                borderTop: '1px solid var(--color-border-neutral)',
                fontSize: isMobile ? '11px' : '12px',
                color: 'var(--color-text-secondary)',
                display: 'flex',
                gap: isMobile ? '12px' : '20px',
                flexWrap: isMobile ? 'wrap' : 'nowrap',
                backgroundColor: 'var(--color-bg-paper)',
                zIndex: 50
              }}>
                <span>Weight: {lastEntry?.weight || 0}</span>
                <span>Applied: {appliedComments.length}</span>
                <span>Groups: {commentGroups.size}</span>
                {showEnergyBar && (
                  <span style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span>Energy:</span>
                    <span
                      key={energyPulseKey}
                      style={{
                        display: 'inline-flex',
                        padding: '2px',
                        borderRadius: '999px',
                        animation: energyPulseKey > 0 ? 'energyPulse 0.6s ease-out' : 'none'
                      }}
                    >
                      <span style={{
                        width: isMobile ? '84px' : '120px',
                        height: '8px',
                        borderRadius: '999px',
                        background: 'rgba(102, 102, 102, 0.2)',
                        overflow: 'hidden',
                        display: 'block'
                      }}>
                        <span
                          style={{
                            display: 'block',
                            height: '100%',
                            width: `${Math.round(energyProgress * 100)}%`,
                            background: 'var(--color-text-secondary)',
                            borderRadius: '999px',
                            transition: 'width 0.25s ease',
                          }}
                        />
                      </span>
                    </span>
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Agent dropdown */}
          {dropdownVisible && (
            <AgentDropdown
              voices={voiceConfigs}
              position={dropdownPosition}
              onSelect={handleAgentSelect}
              onClose={() => setDropdownVisible(false)}
            />
          )}
        </div>
      )}
      {currentView === 'decks' && (
        <div style={{
          position: 'fixed',
          top: viewTopOffset,
          left: 0,
          right: 0,
          bottom: mobileBottomOffset,
          background: 'var(--color-bg-app)',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <DeckManager
            onUpdate={async () => {
            // @@@ Reload voice configs from deck system
            console.log('Deck system updated, reloading voices...');
            const updatedVoices = await loadVoicesFromDecks();
            setVoiceConfigs(updatedVoices);

            if (engineRef.current) {
              engineRef.current.setVoiceConfigs(updatedVoices);
            }

            console.log(`✅ Loaded ${Object.keys(updatedVoices).length} enabled voices`);
          }}
            onOpenChat={handleOpenChatThread}
          />
        </div>
      )}
      {currentView === 'settings' && (
        <div style={{
          flex: 1,
          display: 'flex',
          justifyContent: 'center',
          padding: isMobile ? '24px 16px 120px 16px' : '60px 40px 120px 40px',
          overflow: 'auto',
          position: 'fixed',
          top: viewTopOffset,
          left: 0,
          right: 0,
          bottom: mobileBottomOffset,
          background: 'var(--color-bg-app)'
        }}>
          {showNotionConnectorDetail ? (
            <div style={{ maxWidth: SETTINGS_CONNECTOR_DETAIL_MAX_WIDTH_PX, width: '100%' }}>
              <ConnectorNotionDetailPage onBack={closeNotionConnectorDetail} isMobile={isMobile} />
            </div>
          ) : (
          <div style={{
            maxWidth: SETTINGS_MAX_WIDTH_PX,
            width: '100%'
          }}>
            <section style={{ marginBottom: 48 }}>
              <h2 style={{
                fontSize: 24,
                fontWeight: 600,
                color: 'var(--color-text-primary)',
                marginBottom: 16,
                fontFamily: 'Georgia, "Times New Roman", serif'
              }}>
                {t('nav.settings')}
              </h2>
              <div style={{
                background: 'var(--color-bg-surface)',
                border: '1px solid var(--color-border-paper)',
                borderRadius: 8,
                padding: 24
              }}>
                <div style={{ marginBottom: 12 }}>
                  <label style={{
                    fontSize: 14,
                    fontWeight: 500,
                    color: 'var(--color-text-primary)',
                    marginBottom: 6,
                    display: 'block',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                  }}>
                    Language / 语言
                  </label>
                  <p style={{
                    margin: 0,
                    fontSize: 13,
                    color: 'var(--color-text-secondary)',
                    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                  }}>
                    {t('settings.language.description')}
                  </p>
                </div>

                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  {LANGUAGE_CODES.map(code => {
                    const isActive = currentLanguage === code;
                    return (
                      <button
                        key={code}
                        onClick={() => handleUILanguageChange(code)}
                        style={{
                          padding: '8px 16px',
                          background: isActive ? 'var(--color-text-primary)' : 'transparent',
                          color: isActive ? 'var(--color-text-on-action)' : 'var(--color-text-secondary)',
                          border: isActive ? 'none' : '1px solid var(--color-border-paper)',
                          borderRadius: 6,
                          fontSize: 14,
                          fontWeight: 500,
                          cursor: isActive ? 'default' : 'pointer',
                          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                          boxShadow: isActive ? '0 2px 8px var(--color-shadow-medium)' : 'none',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        {t(`settings.language.options.${code}`)}
                      </button>
                    );
                  })}
                </div>

                <p style={{
                  marginTop: 12,
                  fontSize: 12,
                  color: 'var(--color-text-muted)',
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                }}>
                  {t('settings.language.preview')}
                </p>

                <div style={{
                  marginTop: 20,
                  paddingTop: 16,
                  borderTop: '1px dashed var(--color-border-paper)'
                }}>
                  <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12
                  }}>
                    <div>
                      <div style={{
                        fontSize: 14,
                        fontWeight: 500,
                        color: 'var(--color-text-primary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                      }}>
                        Energy Bar / 能量条
                      </div>
                      <div style={{
                        marginTop: 6,
                        fontSize: 12,
                        color: 'var(--color-text-secondary)',
                        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
                      }}>
                        Toggle the energy progress bar in the bottom stats line.
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowEnergyBar(prev => !prev)}
                      aria-pressed={showEnergyBar}
                      style={{
                        width: 44,
                        height: 24,
                        borderRadius: 999,
                        border: showEnergyBar ? '1px solid var(--color-text-primary)' : '1px solid var(--color-border-paper)',
                        background: showEnergyBar ? 'var(--color-text-primary)' : 'transparent',
                        cursor: 'pointer',
                        position: 'relative',
                        padding: 0,
                        transition: 'all 0.2s ease'
                      }}
                    >
                      <span style={{
                        position: 'absolute',
                        top: 3,
                        left: showEnergyBar ? 'auto' : 4,
                        right: showEnergyBar ? 4 : 'auto',
                        width: 16,
                        height: 16,
                        borderRadius: '50%',
                        background: showEnergyBar ? 'var(--color-text-on-action)' : 'var(--color-text-muted)',
                        transition: 'all 0.2s ease'
                      }} />
                    </button>
                  </div>
                </div>
              </div>
            </section>

            {/* Resource Connector Settings */}
            <section style={{ marginBottom: 48 }}>
              <ConnectorSettingsSection
                focusNonce={connectorSettingsFocusNonce}
                isMobile={isMobile}
                onOpenNotionDetail={openNotionConnectorDetail}
              />
            </section>

            {/* AI Model Configuration */}
            <section style={{ marginBottom: 48 }}>
              <h2 style={{
                fontSize: 24,
                fontWeight: 600,
                color: 'var(--color-text-primary)',
                marginBottom: 16,
                fontFamily: 'Georgia, "Times New Roman", serif'
              }}>
                AI 模型配置
              </h2>
              <div style={{
                background: 'var(--color-bg-surface)',
                border: '1px solid var(--color-border-paper)',
                borderRadius: 8,
                padding: 24
              }}>
                <ModelConfigSection />
              </div>
            </section>

            {/* About Content */}
            <AboutView />
          </div>
          )}
        </div>
      )}
      {/* @@@ Always render timeline to pre-load data and position scroll */}
      <div style={{
        position: 'fixed',
        top: viewTopOffset,
        left: 0,
        right: 0,
        bottom: mobileBottomOffset,
        background: 'var(--color-bg-app)',
        display: currentView === 'timeline' ? 'flex' : 'none',
        overflow: 'hidden'
      }}>
        <CollectionsView
          isVisible={currentView === 'timeline'}
          voiceConfigs={voiceConfigs}
          timezone={userTimezone}
        />
      </div>
      {currentView === 'analysis' && (
        <div style={{
          position: 'fixed',
          top: viewTopOffset,
          left: 0,
          right: 0,
          bottom: mobileBottomOffset,
          background: 'var(--color-bg-app)',
          display: 'flex',
          overflow: 'hidden'
        }}>
          <AnalysisView />
        </div>
      )}

      {shouldRenderChatView && (
        <div style={{
          position: 'fixed',
          top: viewTopOffset,
          left: 0,
          right: 0,
          bottom: mobileBottomOffset,
          display: currentView === 'chat' ? 'flex' : 'none',
          minHeight: 0,
          minWidth: 0,
          overflow: 'hidden'
        }}>
          <ChatView
            editorState={state ? (state as unknown as Record<string, unknown>) : null}
            onEditorWriteConfirmed={handleEditorWriteConfirmed}
            requestedThreadId={requestedChatThreadId}
            activeVoice={activeChatVoice}
            isMobile={isMobile}
            landingTab={chatLandingTab}
            onOpenConnectorSettings={openConnectorSettings}
          />
        </div>
      )}

      {isMobile && (
        <nav style={{
          position: 'fixed',
          left: 0,
          right: 0,
          bottom: 0,
          height: `calc(${mobileNavHeight}px + env(safe-area-inset-bottom, 0px))`,
          paddingBottom: 'env(safe-area-inset-bottom, 0px)',
          background: 'var(--color-bg-app)',
          borderTop: '1px solid var(--color-border-paper)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-around',
          zIndex: 900
        }}>
          {mobileNavItems.map((item) => {
            const isActive = currentView === item.key;
            const Icon = item.icon;
            return (
              <button
                key={item.key}
                onClick={() => handleAppViewChange(item.key)}
                aria-pressed={isActive}
                style={{
                  flex: 1,
                  height: '100%',
                  border: 'none',
                  background: 'transparent',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 4,
                  color: isActive ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
                  fontSize: 11,
                  fontWeight: isActive ? 600 : 400,
                  fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
                  cursor: isActive ? 'default' : 'pointer'
                }}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      )}

      {/* Warning Dialog */}
      {showWarning && (
        <div style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: 'rgba(0, 0, 0, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: 'var(--color-bg-paper)',
            border: '2px solid var(--color-border-paper)',
            borderRadius: '8px',
            padding: '32px',
            maxWidth: '400px',
            boxShadow: '0 8px 24px rgba(0, 0, 0, 0.2)',
            fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif"
          }}>
            <h2 style={{
              margin: '0 0 16px 0',
              fontSize: '20px',
              color: 'var(--color-text-body)',
              fontWeight: 600
            }}>
              Start Fresh?
            </h2>
            <p style={{
              margin: '0 0 24px 0',
              fontSize: '16px',
              lineHeight: '1.6',
              color: 'var(--color-text-secondary)'
            }}>
              This will delete all your current writing and comments. This action cannot be undone.
            </p>
            <div style={{
              display: 'flex',
              gap: '12px',
              justifyContent: 'space-between'
            }}>
              <button
                onClick={handleConfirmStartFresh}
                style={{
                  padding: '8px 20px',
                  border: '1px solid var(--color-state-danger)',
                  background: 'var(--color-state-danger)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: 'var(--color-text-on-action)',
                  fontWeight: 600,
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-state-danger-hover)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-state-danger)';
                }}
              >
                Delete All
              </button>
              <button
                onClick={() => setShowWarning(false)}
                style={{
                  padding: '8px 20px',
                  border: '1px solid var(--color-border-paper)',
                  background: 'var(--color-bg-surface-solid)',
                  borderRadius: '4px',
                  cursor: 'pointer',
                  fontSize: '15px',
                  fontFamily: "'Excalifont', 'Xiaolai', 'Georgia', serif",
                  color: 'var(--color-text-body)',
                  transition: 'all 0.2s'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-bg-hover)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = 'var(--color-bg-surface-solid)';
                }}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Calendar Popup */}
      {showCalendarPopup && (
        <CalendarPopup
          onLoadEntry={handleLoadEntry}
          currentEntryId={state?.id}
          onEntryDeleted={handleCalendarEntryDeleted}
          onClose={() => setShowCalendarPopup(false)}
          timezone={userTimezone}
          initialDateKey={getLocalDayKey(state?.createdAt, userTimezone) ?? getTodayKeyInTimezone(userTimezone)}
        />
      )}
    </>
  );
}
