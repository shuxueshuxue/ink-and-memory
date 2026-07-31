// [Input] window.matchMedia for system preference; localStorage for persisted preference.
// [Output] Theme mode ('light' | 'dark' | 'system') persisted to localStorage; resolved theme applied as data-theme on <html>; change notifications to subscribers.
// [Pos] single source of truth for theme state in frontend/src/utils; all theme UI (TopNavBar toggle, settings segmented control) must read/write through this module.
// [Sync] 2026-05-29: created; implements initTheme / getTheme / setTheme / toggleTheme.
// [Sync] 2026-06-01: initTheme no longer persists system preference; removes data-theme when no explicit pref so CSS media query auto-follows system. Added onThemeChange() for live system updates.
// [Sync] 2026-07-23: unified the two competing theme systems (ink-theme toggle vs dashboard-theme settings control) into this module.
//                    Added ThemeMode ('system'), onThemeChange subscription, migration of the legacy 'dashboard-theme' key,
//                    and fixed the "needs two clicks / stale icon" bug caused by ModelConfigSection and TopNavBar each writing data-theme independently.

import { STORAGE_KEYS } from '../constants/storageKeys';

export type Theme = 'light' | 'dark';
export type ThemeMode = 'light' | 'dark' | 'system';

/** Legacy storage key previously written by the settings sidebar; migrated on first read. */
const LEGACY_THEME_STORAGE_KEY = 'dashboard-theme';

type ThemeListener = (resolved: Theme, mode: ThemeMode) => void;
const listeners = new Set<ThemeListener>();

let mediaQuery: MediaQueryList | null = null;

function isThemeMode(value: string | null): value is ThemeMode {
  return value === 'light' || value === 'dark' || value === 'system';
}

function prefersDark(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

/**
 * Read the persisted theme mode, migrating the legacy 'dashboard-theme' key if present.
 * Defaults to 'system' when no preference has been stored.
 */
export function getThemeMode(): ThemeMode {
  const stored = localStorage.getItem(STORAGE_KEYS.THEME);
  if (isThemeMode(stored)) return stored;
  const legacy = localStorage.getItem(LEGACY_THEME_STORAGE_KEY);
  if (isThemeMode(legacy)) {
    localStorage.setItem(STORAGE_KEYS.THEME, legacy);
    localStorage.removeItem(LEGACY_THEME_STORAGE_KEY);
    return legacy;
  }
  return 'system';
}

/** Read the effective theme: explicit user preference or current system preference. */
export function getTheme(): Theme {
  const mode = getThemeMode();
  if (mode === 'system') return prefersDark() ? 'dark' : 'light';
  return mode;
}

/** Whether the user has explicitly chosen a theme (vs. following system). */
export function hasExplicitTheme(): boolean {
  return getThemeMode() !== 'system';
}

/**
 * Apply a theme mode to the document root.
 * For 'system', data-theme is removed so the CSS `@media (prefers-color-scheme: dark)`
 * rule handles it automatically and keeps following system changes in real time.
 */
function applyThemeMode(mode: ThemeMode): void {
  const root = document.documentElement;
  if (mode === 'system') {
    root.removeAttribute('data-theme');
  } else {
    root.setAttribute('data-theme', mode);
  }
  root.dataset.themeMode = mode;
  root.style.colorScheme = mode === 'system' ? (prefersDark() ? 'dark' : 'light') : mode;
}

function notifyListeners(): void {
  const resolved = getTheme();
  const mode = getThemeMode();
  listeners.forEach((listener) => listener(resolved, mode));
}

/** Persist a theme mode, apply it to the document, and notify subscribers. */
export function setThemeMode(mode: ThemeMode): void {
  localStorage.setItem(STORAGE_KEYS.THEME, mode);
  applyThemeMode(mode);
  notifyListeners();
}

/** Apply an explicit theme to the document root and persist it as a user preference. */
export function setTheme(theme: Theme): void {
  setThemeMode(theme);
}

/** Toggle between light and dark (based on the effective theme), return the new theme. */
export function toggleTheme(): Theme {
  const next = getTheme() === 'dark' ? 'light' : 'dark';
  setThemeMode(next);
  return next;
}

/**
 * Subscribe to effective theme changes.
 * Fires when the user picks a mode (from any UI) and when the system preference
 * changes while following the system. Returns an unsubscribe function.
 */
export function onThemeChange(callback: ThemeListener): () => void {
  listeners.add(callback);
  return () => listeners.delete(callback);
}

/**
 * Call once on app start to apply the persisted theme and start watching the
 * system preference. Safe to call multiple times; the media listener is
 * registered only once.
 */
export function initTheme(): void {
  applyThemeMode(getThemeMode());
  if (!mediaQuery) {
    mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    mediaQuery.addEventListener('change', () => {
      // When following the system, data-theme is absent so CSS switches by itself;
      // we only need to notify subscribers (icons, segmented controls).
      if (!hasExplicitTheme()) {
        notifyListeners();
      }
    });
  }
}
