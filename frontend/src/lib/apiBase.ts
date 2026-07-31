// [Input] Browser runtime config, Vite env, and current window origin.
// [Output] Centralized REST/SSE/WebSocket endpoint base URLs for frontend API callers.
// [Pos] frontend API base-url utility node
// [Sync] 2026-06-12: add runtime API_BASE_URL / WS_BASE_URL support for cross-origin deployments.
// [Sync] 2026-06-12: resolve API_BASE lazily so runtime-config load timing cannot lock the app to same-origin paths.
// [Sync] 2026-06-15: remove /ink-and-memory same-origin fallback prefix; root deploy uses /api directly.

type RuntimeConfig = {
  apiBaseUrl?: string;
  wsBaseUrl?: string;
};

declare global {
  interface Window {
    __INK_RUNTIME_CONFIG__?: RuntimeConfig;
  }
}

const DEFAULT_API_BASE = '';

function cleanBaseUrl(value: string | undefined | null): string | undefined {
  const trimmed = value?.trim();
  if (!trimmed) return undefined;
  return trimmed.replace(/\/+$/, '');
}

function getRuntimeConfig(): RuntimeConfig {
  if (typeof window === 'undefined') return {};
  return window.__INK_RUNTIME_CONFIG__ ?? {};
}

export function getApiBase(): string {
  return cleanBaseUrl(
    getRuntimeConfig().apiBaseUrl || import.meta.env.VITE_API_BASE_URL,
  ) ?? DEFAULT_API_BASE;
}

export const API_BASE = {
  toString: getApiBase,
  valueOf: getApiBase,
  [Symbol.toPrimitive]: getApiBase,
} as unknown as string;

export function apiUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${getApiBase()}${normalizedPath}`;
}

function websocketProtocolFor(protocol: string): string {
  return protocol === 'https:' ? 'wss:' : 'ws:';
}

function deriveWebSocketBase(): string {
  const explicit = cleanBaseUrl(
    getRuntimeConfig().wsBaseUrl || import.meta.env.VITE_WS_BASE_URL,
  );
  if (explicit) return explicit;

  if (typeof window === 'undefined') return '';

  try {
    const api = new URL(getApiBase(), window.location.origin);
    api.protocol = websocketProtocolFor(api.protocol);
    return `${api.protocol}//${api.host}`;
  } catch {
    const protocol = websocketProtocolFor(window.location.protocol);
    return `${protocol}//${window.location.host}`;
  }
}

export function webSocketUrl(path: string): string {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${deriveWebSocketBase()}${normalizedPath}`;
}
