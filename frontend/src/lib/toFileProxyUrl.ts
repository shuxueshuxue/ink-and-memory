// [Input] Runtime API base config and backend storage file endpoint contract.
// [Output] Browser-accessible file proxy URL for stored file keys.
// [Pos] file-proxy-url utility node
// [Sync] 2026-06-12: prefix file proxy URLs with centralized API base for cross-origin deployments.
// [Sync] 2026-07-21: append the current auth token as ?token= so browser-embedded
//                    file URLs (<img src>, download links) that cannot send
//                    Authorization headers pass backend storage auth (fixes 401).
import { apiUrl } from './apiBase';
import { STORAGE_KEYS } from '../constants/storageKeys';

function getAuthTokenParam(): string | null {
  const token = typeof localStorage !== 'undefined' ? localStorage.getItem(STORAGE_KEYS.AUTH_TOKEN) : null;
  return token ? `token=${encodeURIComponent(token)}` : null;
}

export function toFileProxyUrl(storageKey: string): string {
  const encoded = typeof globalThis.btoa === 'function' ? globalThis.btoa(storageKey) : storageKey;
  const base = apiUrl('/api/storage/file/' + encoded);
  const authParam = getAuthTokenParam();
  return authParam ? `${base}?${authParam}` : base;
}

/**
 * Append the current auth token to an existing /api/storage/file/ proxy URL
 * (e.g. a URL persisted in a stored message part without credentials).
 * Non-storage URLs are returned unchanged.
 */
export function withStorageAuthToken(url: string): string {
  if (!url.includes('/api/storage/file/') || url.includes('token=')) return url;
  const authParam = getAuthTokenParam();
  if (!authParam) return url;
  return url + (url.includes('?') ? '&' : '?') + authParam;
}
