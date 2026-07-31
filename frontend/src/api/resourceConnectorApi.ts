// [Input] Connector REST endpoints, auth token storage, and Notion resource selection payloads.
// [Output] Frontend client helpers for resource connector CRUD, auth polling, resource listing, and sync.
// [Pos] resource connector API client node in frontend/src/api
// [Sync] 2026-07-04: add Notion resource connector API helpers with local fallback storage for the frontend task.
// [Sync] 2026-07-04: preserve backend connector UUIDs from singular create responses so auth/discovery
//                    calls do not fall back to local connector_* ids.
// [Sync] 2026-07-05: send connector resource selections with the backend's selected_* field names so
//                    selection persistence reaches /api/connectors/{id}/resources/select instead of collapsing
//                    to empty lists.
// [Sync] 2026-07-05: normalize backend auth_session terminal states (`consumed`/`failed`) so UI can stop
//                    polling and surface actionable auth errors instead of indefinitely waiting.
// [Sync] 2026-07-07: keep normalized auth/session status ahead of stale top-level connector status so consumed
//                    sessions do not regress an already authenticated connector back to pending/error in the UI.
// [Sync] 2026-07-07: expose the connector normalizer for UI-only fallback workbench state so mock/fallback data
//                    follows the same client shape as backend and localStorage responses.
// [Sync] 2026-07-08: local fallback create now replaces same-platform connectors so the frontend preserves
//                    the single-account-per-platform business rule while backend enforcement lands separately.
// [Sync] 2026-07-08: persist selected resource metadata by posting full selected Notion resource objects and
//                    normalize backend connector_resources with external Notion ids for refresh-safe selection.
// [Sync] 2026-07-09: expose a browser-local connector change event so Settings saves can refresh
//                    Chat connector status panels without adding another backend endpoint.
/**
 * Resource connector API helpers.
 *
 * The frontend prefers the real backend connector endpoints when they exist,
 * but falls back to localStorage-backed state when the backend request itself
 * fails so the UI remains usable while the backend implementation is still
 * landing.
 */

import { getAuthToken } from '../contexts/AuthContext';
import { STORAGE_KEYS } from '../constants/storageKeys';
import { apiUrl } from '../lib/apiBase';

export type ConnectorPlatform = 'notion';

export const RESOURCE_CONNECTORS_CHANGED_EVENT = 'ink-and-memory:resource-connectors-changed';

export interface ResourceConnectorsChangedDetail {
  connectorId?: string;
  reason: 'resources-selected' | 'sources-refreshed' | 'auth-updated' | 'connector-updated';
}

export function notifyResourceConnectorsChanged(detail: ResourceConnectorsChangedDetail): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent<ResourceConnectorsChangedDetail>(RESOURCE_CONNECTORS_CHANGED_EVENT, { detail }));
}

export type ConnectorStatus =
  | 'draft'
  | 'authenticating'
  | 'authenticated'
  | 'syncing'
  | 'synced'
  | 'expired'
  | 'error';

export type ConnectorSourceType = 'notion_database' | 'notion_page';

export type ConnectorSourceStatus = 'idle' | 'syncing' | 'synced' | 'error';

export type ConnectorAuthStatus = 'idle' | 'authenticating' | 'authenticated' | 'expired' | 'error';

export interface ConnectorAuthSession {
  status: ConnectorAuthStatus;
  verificationCode?: string;
  verificationUrl?: string;
  pollAttempts?: number;
  expiresAt?: string;
  message?: string;
}

export interface ConnectorSource {
  id: string;
  title: string;
  type: ConnectorSourceType;
  status: ConnectorSourceStatus;
  updatedAt: string;
  syncedAt?: string;
  pageCount?: number;
  description?: string;
  url?: string;
}

export interface ResourceConnector {
  id: string;
  name: string;
  platform: ConnectorPlatform;
  status: ConnectorStatus;
  createdAt: string;
  updatedAt: string;
  lastSyncedAt?: string;
  auth: ConnectorAuthSession;
  sources: ConnectorSource[];
}

export interface NotionResourceOption {
  id: string;
  title: string;
  subtitle?: string;
  pageCount?: number;
  selected?: boolean;
  url?: string;
  lastEdited?: string;
  propertiesSchema?: Record<string, unknown>;
  raw?: unknown;
}

export interface ConnectorResourceSelection {
  databaseIds: string[];
  pageIds: string[];
  databaseOptions?: NotionResourceOption[];
  pageOptions?: NotionResourceOption[];
}

export interface CreateConnectorInput {
  name: string;
  platform?: ConnectorPlatform;
}

export interface UpdateConnectorInput {
  name?: string;
  status?: ConnectorStatus;
}

const LOCAL_CONNECTOR_STORAGE_KEY = STORAGE_KEYS.RESOURCE_CONNECTORS;
const DEFAULT_CONNECTOR_NAME = 'Resource Connector';
const DEFAULT_NOTION_VERIFICATION_URL = 'https://www.notion.so/my-integrations';

const FALLBACK_DATABASES: NotionResourceOption[] = [
  {
    id: 'db-product-notes',
    title: '产品资料库',
    subtitle: 'Briefs, specs, and launch notes',
    pageCount: 18,
  },
  {
    id: 'db-research-log',
    title: '调研记录',
    subtitle: 'Interviews and research captures',
    pageCount: 12,
  },
  {
    id: 'db-roadmap',
    title: '路线图',
    subtitle: 'Milestones and release planning',
    pageCount: 9,
  },
];

const FALLBACK_PAGES: NotionResourceOption[] = [
  {
    id: 'page-brand-guide',
    title: '品牌规范',
    subtitle: 'Standalone page',
  },
  {
    id: 'page-quarterly-goals',
    title: '季度目标',
    subtitle: 'Standalone page',
  },
  {
    id: 'page-meeting-notes',
    title: '会议纪要',
    subtitle: 'Standalone page',
  },
];

function nowIso(): string {
  return new Date().toISOString();
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' ? value as Record<string, unknown> : {};
}

function asString(value: unknown): string | undefined {
  return typeof value === 'string' ? value : undefined;
}

function createId(prefix: string): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}_${crypto.randomUUID()}`;
  }

  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
}

function safeJsonParse<T>(value: string | null, fallback: T): T {
  if (!value) return fallback;

  try {
    return JSON.parse(value) as T;
  } catch {
    return fallback;
  }
}

function readLocalConnectors(): ResourceConnector[] {
  if (typeof window === 'undefined') return [];
  return safeJsonParse<ResourceConnector[]>(localStorage.getItem(LOCAL_CONNECTOR_STORAGE_KEY), []);
}

function writeLocalConnectors(connectors: ResourceConnector[]): ResourceConnector[] {
  if (typeof window !== 'undefined') {
    localStorage.setItem(LOCAL_CONNECTOR_STORAGE_KEY, JSON.stringify(connectors));
  }
  return connectors;
}

function mutateLocalConnector(
  connectorId: string,
  mutator: (connector: ResourceConnector) => ResourceConnector,
): ResourceConnector | null {
  const connectors = readLocalConnectors();
  const index = connectors.findIndex((connector) => connector.id === connectorId);
  if (index === -1) return null;

  const nextConnector = mutator({ ...connectors[index], sources: connectors[index].sources.map((source) => ({ ...source })), auth: { ...connectors[index].auth } });
  connectors[index] = nextConnector;
  writeLocalConnectors(connectors);
  return nextConnector;
}

function hasBackendAuthSession(raw: unknown): boolean {
  const record = asRecord(raw);
  const auth = asRecord(record.auth ?? record.authentication);
  const config = asRecord(record.config);
  const authSession = asRecord(auth.auth_session);
  const configSession = asRecord(config.auth_session);
  return Boolean(
    auth.verificationUrl
      || auth.verification_url
      || auth.verificationCode
      || auth.verification_code
      || auth.pollIntervalSeconds
      || auth.poll_interval_seconds
      || record.verificationUrl
      || record.verification_url
      || record.verificationCode
      || record.verification_code
      || record.pollIntervalSeconds
      || record.poll_interval_seconds
      || authSession.auth_session_id
      || authSession.auth_session_status
      || authSession.auth_session_started_at
      || authSession.auth_session_last_polled_at
      || configSession.auth_session_id
      || configSession.auth_session_status
      || configSession.auth_session_started_at
      || configSession.auth_session_last_polled_at
      || config.verificationUrl
      || config.verification_url
      || config.verificationCode
      || config.verification_code
      || config.pollIntervalSeconds
      || config.poll_interval_seconds,
  );
}

function localizeAuthStatus(status?: string | null, hasSession = false): ConnectorAuthStatus {
  switch ((status || '').toLowerCase()) {
    case 'authenticated':
      return 'authenticated';
    case 'authenticating':
    case 'pending':
      return hasSession ? 'authenticating' : 'idle';
    case 'consumed':
    case 'failed':
      return 'error';
    case 'expired':
      return 'expired';
    case 'error':
      return 'error';
    default:
      return 'idle';
  }
}

function localizeConnectorStatus(status?: string | null, sourceCount = 0, hasSession = false): ConnectorStatus {
  switch ((status || '').toLowerCase()) {
    case 'authenticated':
    case 'synced':
      return 'synced';
    case 'syncing':
      return 'syncing';
    case 'authenticating':
    case 'pending':
      return hasSession ? 'authenticating' : 'draft';
    case 'consumed':
    case 'failed':
      return 'error';
    case 'expired':
      return 'expired';
    case 'error':
      return 'error';
    default:
      return sourceCount > 0 ? 'synced' : 'draft';
  }
}

function normalizeSourceType(value?: string | null): ConnectorSourceType {
  return value === 'notion_page' || value === 'page' ? 'notion_page' : 'notion_database';
}

function normalizeSourceStatus(value?: string | null): ConnectorSourceStatus {
  switch (value) {
    case 'syncing':
      return 'syncing';
    case 'synced':
      return 'synced';
    case 'error':
      return 'error';
    default:
      return 'idle';
  }
}

function normalizeConnectorSource(raw: unknown): ConnectorSource {
  const record = asRecord(raw);
  const metadata = asRecord(record.metadata);
  const updatedAt = typeof record.updated_at === 'string'
    ? record.updated_at
    : typeof record.updatedAt === 'string'
      ? record.updatedAt
      : typeof metadata.last_edited === 'string'
        ? metadata.last_edited
      : nowIso();
  return {
    id: String(record.external_id ?? record.database_id ?? record.page_id ?? record.source_id ?? record.resource_id ?? record.id ?? createId('source')),
    title: String(record.title ?? record.name ?? record.label ?? 'Untitled source'),
    type: normalizeSourceType(asString(record.type ?? record.resource_type ?? record.kind)),
    status: normalizeSourceStatus(asString(record.status ?? record.sync_status)),
    updatedAt,
    syncedAt: asString(record.synced_at)
      ?? asString(record.syncedAt)
      ?? asString(record.last_synced_at)
      ?? asString(record.lastSyncedAt),
    pageCount: typeof record.page_count === 'number'
      ? record.page_count
      : typeof record.pageCount === 'number'
        ? record.pageCount
        : typeof metadata.page_count === 'number'
          ? metadata.page_count
          : undefined,
    description: asString(record.description) ?? asString(record.subtitle) ?? asString(record.summary),
    url: asString(record.url) ?? asString(record.source_url) ?? asString(record.sourceUrl) ?? asString(metadata.url),
  };
}

function normalizeConnectorAuth(raw: unknown): ConnectorAuthSession {
  const record = asRecord(raw);
  const auth = asRecord(record.auth ?? record.authentication ?? record);
  const config = asRecord(record.config);
  const session = asRecord(auth.auth_session ?? config.auth_session);
  const resolvedStatus = asString(auth.status)
    ?? asString(record.auth_status)
    ?? asString(record.status)
    ?? asString(session.auth_session_status);
  return {
    status: localizeAuthStatus(resolvedStatus, hasBackendAuthSession(raw)),
    verificationCode:
      asString(auth.verificationCode)
      ?? asString(auth.verification_code)
      ?? asString(record.verification_code)
      ?? asString(record.code)
      ?? asString(config.verificationCode)
      ?? asString(config.verification_code),
    verificationUrl:
      asString(auth.verificationUrl)
      ?? asString(auth.verification_url)
      ?? asString(record.verification_url)
      ?? asString(config.verificationUrl)
      ?? asString(config.verification_url)
      ?? DEFAULT_NOTION_VERIFICATION_URL,
    pollAttempts: typeof auth.pollAttempts === 'number'
      ? auth.pollAttempts
      : typeof auth.poll_attempts === 'number'
        ? auth.poll_attempts
        : undefined,
    expiresAt: asString(auth.expiresAt)
      ?? asString(auth.expires_at)
      ?? asString(session.auth_session_expires_at)
      ?? asString(record.expires_at),
    message:
      asString(auth.message)
      ?? asString(auth.detail)
      ?? asString(record.message)
      ?? asString(record.detail)
      ?? asString(config.auth_error)
      ?? asString(session.auth_error),
  };
}

function normalizeConnector(raw: unknown): ResourceConnector {
  const record = asRecord(raw);
  const now = nowIso();
  const sources = Array.isArray(record.sources)
    ? record.sources.map(normalizeConnectorSource)
    : Array.isArray(record.resources)
      ? record.resources.map(normalizeConnectorSource)
      : [];
  const auth = normalizeConnectorAuth(raw);
  const config = asRecord(record.config);
  const authSession = asRecord(config.auth_session);
  const sourceCount = sources.length;
  const hasSession = hasBackendAuthSession(raw);
  const connectorStatus =
    asString(record.auth_status)
    ?? auth.status
    ?? asString(record.status)
    ?? asString(record.sync_status)
    ?? asString(authSession.auth_session_status);

  return {
    id: String(record.id ?? record.connector_id ?? record.resource_connector_id ?? createId('connector')),
    name: String(record.name ?? record.title ?? DEFAULT_CONNECTOR_NAME),
    platform: 'notion',
    status: localizeConnectorStatus(connectorStatus, sourceCount, hasSession),
    createdAt: asString(record.created_at) ?? asString(record.createdAt) ?? now,
    updatedAt: asString(record.updated_at) ?? asString(record.updatedAt) ?? now,
    lastSyncedAt: asString(record.last_synced_at)
      ?? asString(record.lastSyncedAt)
      ?? asString(record.synced_at)
      ?? asString(record.syncedAt),
    auth,
    sources,
  };
}

function normalizeConnectorListResponse(response: unknown): ResourceConnector[] {
  if (Array.isArray(response)) {
    return response.map(normalizeConnector);
  }

  const payload = response as { connectors?: unknown[]; connector?: unknown; data?: unknown[]; items?: unknown[] };
  if (payload?.connector) return [normalizeConnector(payload.connector)];
  if (Array.isArray(payload?.connectors)) return payload.connectors.map(normalizeConnector);
  if (Array.isArray(payload?.data)) return payload.data.map(normalizeConnector);
  if (Array.isArray(payload?.items)) return payload.items.map(normalizeConnector);
  return [];
}

function normalizeConnectorResponse(response: unknown): ResourceConnector {
  return normalizeConnector(
    response && typeof response === 'object' && 'connector' in response
      ? (response as { connector?: unknown }).connector
      : response,
  );
}

export function normalizeResourceConnectorFallback(raw: unknown): ResourceConnector {
  return normalizeConnector(raw);
}

async function fetchJson<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  headers.set('Accept', 'application/json');

  const token = getAuthToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(apiUrl(path), {
    credentials: 'include',
    ...init,
    headers,
  });

  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

async function remoteOrLocal<T>(remote: () => Promise<T>, local: () => Promise<T> | T): Promise<T> {
  try {
    return await remote();
  } catch {
    return await local();
  }
}

function buildLocalAuthSession(auth?: Partial<ConnectorAuthSession>): ConnectorAuthSession {
  const verificationCode = auth?.verificationCode ?? `NTN-${Math.floor(1000 + Math.random() * 9000)}`;
  const expiresAt = auth?.expiresAt ?? new Date(Date.now() + 10 * 60 * 1000).toISOString();
  return {
    status: auth?.status ?? 'authenticating',
    verificationCode,
    verificationUrl: auth?.verificationUrl ?? DEFAULT_NOTION_VERIFICATION_URL,
    pollAttempts: auth?.pollAttempts ?? 0,
    expiresAt,
    message: auth?.message ?? 'Open Notion in your browser and confirm the integration.',
  };
}

function buildLocalConnector(input: CreateConnectorInput): ResourceConnector {
  const now = nowIso();
  return {
    id: createId('connector'),
    name: input.name.trim() || DEFAULT_CONNECTOR_NAME,
    platform: input.platform ?? 'notion',
    status: 'draft',
    createdAt: now,
    updatedAt: now,
    auth: buildLocalAuthSession({ status: 'idle', message: 'Connector created. Start Notion auth to continue.' }),
    sources: [],
  };
}

function mergeSelectedSources(
  connector: ResourceConnector,
  databaseOptions: NotionResourceOption[],
  pageOptions: NotionResourceOption[],
  selection: ConnectorResourceSelection,
): ResourceConnector {
  const now = nowIso();
  const selectedDatabaseIds = new Set(selection.databaseIds);
  const selectedPageIds = new Set(selection.pageIds);

  const sources: ConnectorSource[] = [
    ...databaseOptions
      .filter((option) => selectedDatabaseIds.has(option.id))
      .map((option) => ({
        id: option.id,
        title: option.title,
        type: 'notion_database' as const,
        status: 'synced' as const,
        updatedAt: now,
        syncedAt: now,
        pageCount: option.pageCount,
        description: option.subtitle,
      })),
    ...pageOptions
      .filter((option) => selectedPageIds.has(option.id))
      .map((option) => ({
        id: option.id,
        title: option.title,
        type: 'notion_page' as const,
        status: 'synced' as const,
        updatedAt: now,
        syncedAt: now,
        description: option.subtitle,
      })),
  ];

  return {
    ...connector,
    status: sources.length > 0 ? 'synced' : connector.status,
    updatedAt: now,
    lastSyncedAt: sources.length > 0 ? now : connector.lastSyncedAt,
    sources,
    auth: {
      ...connector.auth,
      status: connector.auth.status === 'authenticated' ? 'authenticated' : connector.auth.status,
    },
  };
}

export async function listConnectors(): Promise<ResourceConnector[]> {
  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>('/api/connectors');
      return normalizeConnectorListResponse(response);
    },
    () => readLocalConnectors(),
  );
}

export async function createConnector(input: CreateConnectorInput): Promise<ResourceConnector> {
  const localFallback = () => {
    const connector = buildLocalConnector(input);
    const platform = input.platform ?? 'notion';
    const connectors = readLocalConnectors().filter((item) => item.platform !== platform);
    writeLocalConnectors([connector, ...connectors]);
    return connector;
  };

  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>('/api/connectors', {
        method: 'POST',
        body: JSON.stringify({
          name: input.name,
          platform: input.platform ?? 'notion',
        }),
      });
      const [connector] = normalizeConnectorListResponse(response);
      return connector ?? localFallback();
    },
    localFallback,
  );
}

export async function updateConnector(
  connectorId: string,
  input: UpdateConnectorInput,
): Promise<ResourceConnector | null> {
  const localFallback = () => mutateLocalConnector(connectorId, (connector) => ({
    ...connector,
    ...input,
    name: input.name?.trim() || connector.name,
    updatedAt: nowIso(),
  }));

  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}`, {
        method: 'PATCH',
        body: JSON.stringify(input),
      });

      const normalized = normalizeConnectorResponse(response);
      return normalized.id ? normalized : localFallback();
    },
    localFallback,
  );
}

export async function deleteConnector(connectorId: string): Promise<boolean> {
  return remoteOrLocal(
    async () => {
      await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}`, {
        method: 'DELETE',
      });
      return true;
    },
    () => {
      const connectors = readLocalConnectors().filter((connector) => connector.id !== connectorId);
      writeLocalConnectors(connectors);
      return true;
    },
  );
}

export async function startConnectorAuth(connectorId: string): Promise<ResourceConnector | null> {
  const localFallback = () => mutateLocalConnector(connectorId, (connector) => {
    const auth = buildLocalAuthSession({
      status: 'authenticating',
      verificationCode: connector.auth.verificationCode,
      verificationUrl: connector.auth.verificationUrl,
      pollAttempts: 0,
      message: 'Open Notion and confirm access. Polling will continue automatically.',
    });

    return {
      ...connector,
      status: 'authenticating',
      updatedAt: nowIso(),
      auth,
    };
  });

  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}/auth/login`, {
        method: 'POST',
      });
      const normalized = normalizeConnectorResponse(response);
      return normalized.id ? normalized : localFallback();
    },
    localFallback,
  );
}

export async function pollConnectorAuth(connectorId: string): Promise<ResourceConnector | null> {
  const localFallback = () => mutateLocalConnector(connectorId, (connector) => {
    const nextAttempts = (connector.auth.pollAttempts ?? 0) + 1;
    const expired = connector.auth.expiresAt ? Date.now() >= new Date(connector.auth.expiresAt).getTime() : false;
    const authStatus: ConnectorAuthStatus = expired ? 'expired' : nextAttempts >= 2 ? 'authenticated' : 'authenticating';

    return {
      ...connector,
      status: authStatus === 'authenticated' ? 'authenticated' : authStatus === 'expired' ? 'expired' : 'authenticating',
      updatedAt: nowIso(),
      auth: {
        ...connector.auth,
        status: authStatus,
        pollAttempts: nextAttempts,
        message: authStatus === 'authenticated'
          ? 'Notion authentication completed.'
          : authStatus === 'expired'
            ? 'Notion authentication expired. Please start a new session.'
            : 'Waiting for the browser confirmation in Notion.',
      },
    };
  });

  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}/auth/poll`, {
        method: 'POST',
      });
      const normalized = normalizeConnectorResponse(response);
      return normalized.id ? normalized : localFallback();
    },
    localFallback,
  );
}

export async function listConnectorDatabases(connectorId: string): Promise<NotionResourceOption[]> {
  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}/databases`);
      const databaseItems = (response as { databases?: unknown[] }).databases;
      const responseItems = (response as { items?: unknown[] }).items;
      const items: unknown[] = Array.isArray(response)
        ? response
        : Array.isArray(databaseItems)
          ? databaseItems
          : Array.isArray(responseItems)
            ? responseItems
            : [];

      return items.map((raw): NotionResourceOption => {
        const record = raw as Record<string, unknown>;
        const pageCountValue = record.page_count ?? record.pageCount;
        const propertiesSchema = asRecord(record.properties_schema ?? record.propertiesSchema);

        return {
          id: String(record.id ?? record.database_id ?? createId('database')),
          title: String(record.title ?? record.name ?? 'Untitled database'),
          subtitle: typeof record.subtitle === 'string'
            ? record.subtitle
            : typeof record.description === 'string'
              ? record.description
              : 'Notion database',
          pageCount: typeof pageCountValue === 'number' ? pageCountValue : undefined,
          selected: Boolean(record.selected),
          url: typeof record.url === 'string' ? record.url : undefined,
          lastEdited: typeof record.last_edited === 'string'
            ? record.last_edited
            : typeof record.lastEdited === 'string'
              ? record.lastEdited
              : undefined,
          propertiesSchema,
          raw: record.raw,
        };
      });
    },
    () => FALLBACK_DATABASES.map((item) => ({ ...item })),
  );
}

export async function listConnectorPages(connectorId: string): Promise<NotionResourceOption[]> {
  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}/pages`);
      const pageItems = (response as { pages?: unknown[] }).pages;
      const responseItems = (response as { items?: unknown[] }).items;
      const items: unknown[] = Array.isArray(response)
        ? response
        : Array.isArray(pageItems)
          ? pageItems
          : Array.isArray(responseItems)
            ? responseItems
            : [];

      return items.map((raw): NotionResourceOption => {
        const record = raw as Record<string, unknown>;
        return {
          id: String(record.id ?? record.page_id ?? createId('page')),
          title: String(record.title ?? record.name ?? 'Untitled page'),
          subtitle: typeof record.subtitle === 'string'
            ? record.subtitle
            : typeof record.description === 'string'
              ? record.description
              : 'Standalone page',
          selected: Boolean(record.selected),
          url: typeof record.url === 'string' ? record.url : undefined,
          lastEdited: typeof record.last_edited === 'string'
            ? record.last_edited
            : typeof record.lastEdited === 'string'
              ? record.lastEdited
              : undefined,
          raw: record.raw,
        };
      });
    },
    () => FALLBACK_PAGES.map((item) => ({ ...item })),
  );
}

export async function selectConnectorResources(
  connectorId: string,
  selection: ConnectorResourceSelection,
): Promise<ResourceConnector | null> {
  const selectedDatabaseIdSet = new Set(selection.databaseIds);
  const selectedPageIdSet = new Set(selection.pageIds);
  const databaseOptions = selection.databaseOptions ?? FALLBACK_DATABASES;
  const pageOptions = selection.pageOptions ?? FALLBACK_PAGES;
  const databaseOptionById = new Map(databaseOptions.map((item) => [item.id, item]));
  const pageOptionById = new Map(pageOptions.map((item) => [item.id, item]));
  const selectedDatabasePayload = selection.databaseIds.map((id) => {
    const option = databaseOptionById.get(id);
    if (!option) return id;
    return {
      database_id: option.id,
      title: option.title,
      subtitle: option.subtitle,
      page_count: option.pageCount,
      url: option.url,
      last_edited: option.lastEdited,
      properties_schema: option.propertiesSchema,
      raw: option.raw,
    };
  });
  const selectedPagePayload = selection.pageIds.map((id) => {
    const option = pageOptionById.get(id);
    if (!option) return id;
    return {
      page_id: option.id,
      title: option.title,
      subtitle: option.subtitle,
      url: option.url,
      last_edited: option.lastEdited,
      raw: option.raw,
    };
  });

  const localFallback = () => {
    const connectors = readLocalConnectors();
    const connector = connectors.find((item) => item.id === connectorId);
    if (!connector) return null;

    const databases = databaseOptions.filter((item) => selectedDatabaseIdSet.has(item.id));
    const pages = pageOptions.filter((item) => selectedPageIdSet.has(item.id));
    const nextConnector = {
      ...connector,
      ...mergeSelectedSources(connector, databases, pages, selection),
      status: selection.databaseIds.length + selection.pageIds.length > 0 ? 'synced' as const : connector.status,
    };

    writeLocalConnectors(connectors.map((item) => (item.id === connectorId ? nextConnector : item)));
    return nextConnector;
  };

  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}/resources/select`, {
        method: 'POST',
        body: JSON.stringify({
          selected_databases: selectedDatabasePayload,
          selected_pages: selectedPagePayload,
        }),
      });
      const normalized = normalizeConnectorResponse(response);
      return normalized.id ? normalized : localFallback();
    },
    localFallback,
  );
}

export async function refreshConnectorSources(connectorId: string): Promise<ResourceConnector | null> {
  const localFallback = () => mutateLocalConnector(connectorId, (connector) => {
    const now = nowIso();
    return {
      ...connector,
      status: connector.sources.length > 0 ? 'synced' : connector.status,
      updatedAt: now,
      lastSyncedAt: connector.sources.length > 0 ? now : connector.lastSyncedAt,
      sources: connector.sources.map((source) => ({
        ...source,
        status: source.status === 'error' ? 'error' : 'synced',
        updatedAt: now,
        syncedAt: now,
      })),
      auth: {
        ...connector.auth,
        status: connector.auth.status === 'authenticated' ? 'authenticated' : connector.auth.status,
      },
    };
  });

  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}/sync`, {
        method: 'POST',
      });
      const normalized = normalizeConnectorResponse(response);
      return normalized.id ? normalized : localFallback();
    },
    localFallback,
  );
}

export async function getConnector(connectorId: string): Promise<ResourceConnector | null> {
  return remoteOrLocal(
    async () => {
      const response = await fetchJson<unknown>(`/api/connectors/${encodeURIComponent(connectorId)}`);
      return normalizeConnectorResponse(response);
    },
    () => readLocalConnectors().find((connector) => connector.id === connectorId) ?? null,
  );
}
