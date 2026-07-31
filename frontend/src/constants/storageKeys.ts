/**
 * Storage keys constants
 *
 * Single source of truth for localStorage keys used across the application.
 * Using const assertion for type safety and autocomplete.
 */

// [Sync] 2026-07-04: add resource connector storage key for frontend fallback state.

export const STORAGE_KEYS = {
  // Auth
  AUTH_TOKEN: 'auth_token',
  MIGRATION_COMPLETED: 'migration_completed',

  // Editor State
  EDITOR_STATE: 'ink_memory_state',
  SELECTED_STATE: 'selected-state',

  // Voice Configuration
  VOICE_CONFIGS: 'voice-configs',
  META_PROMPT: 'meta-prompt',
  STATE_CONFIG: 'state-config',

  // Calendar & Pictures
  CALENDAR_ENTRIES: 'calendarEntries',
  DAILY_PICTURES: 'daily-pictures',
  SELECTED_FRIEND: 'ink-selected-friend',
  RECENT_FRIENDS: 'ink-recent-friends',
  RESOURCE_CONNECTORS: 'ink-resource-connectors',

  // Analysis
  ANALYSIS_REPORTS: 'analysisReports',
  REFLECTIONS_ANALYSIS_CLICKED_DATE: 'reflections-analysis-clicked-date',
  REFLECTIONS_ACTIVE_TASK: 'reflections-active-task',

  // Language
  LANGUAGE: 'ink-language',

  // Theme
  THEME: 'ink-theme'
} as const;

// Type for autocomplete
export type StorageKey = typeof STORAGE_KEYS[keyof typeof STORAGE_KEYS];
