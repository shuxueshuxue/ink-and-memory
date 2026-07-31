// [Input] System config API, chat icons, AuthContext token, dashboard design tokens.
// [Output] Render Settings AI model/theme/system-prompt/workspace/full-access/env controls.
// [Pos] settings-model-config component node in frontend/src/components/dashboard
// [Sync] 2026-06-09: add IM full-access approval toggle backed by
//                    system_config.im_full_access_enabled.
// [Sync] 2026-06-09: emit same-tab IM full-access change events so Chat UI
//                    updates without a page refresh.
// [Sync] 2026-06-12: use centralized API_BASE for cross-origin system config requests.
// [Sync] 2026-06-13: clarify Workspace Mode as the frontend control for
//                    per-thread Claude Code Bash sandbox settings.
// [Sync] 2026-06-13: full-access copy clarifies AskUserQuestion forms still
//                    require confirmation.
// [Sync] 2026-06-21: add sandbox network policy controls backed by system_config.
// [Sync] 2026-06-22: emit same-tab Workspace Mode changes so chat/file sidebar
//                    entry points close immediately when disabled.
// [Sync] 2026-06-22: hide Sandbox Network and user env var controls whenever
//                    Workspace Mode is disabled because both rely on workspace
//                    runtime initialization.
// [Sync] 2026-06-25: hydrate Sandbox Network controls from PUT response so
//                    sanitized allowed domains and mode survive refresh.
// [Sync] 2026-07-26: add Sandbox File Writes control backed by
//                    system_config.sandbox_fs_allowed_write_paths — tag-list of
//                    extra absolute writable paths (same Workspace Mode gating
//                    as Sandbox Network), with hint covering the default-allowed
//                    Claude TMPDIR and denyWrite precedence. Hardcoded zh copy
//                    matches this section's existing convention (no i18n infra
//                    in this component).
// [Sync] 2026-06-25: hide the HTTP method placeholder in open network mode
//                    while keeping the high-risk internet access warning.
// [Sync] 2026-07-23: theme control now reads/writes the unified theme store
//                    (utils/theme) instead of its own 'dashboard-theme' key and
//                    private data-theme effect, fixing the two-click toggle and
//                    stale navbar icon caused by the two competing theme systems.
//                    Backend config.theme is applied only when explicitly set,
//                    so opening Settings no longer stomps a local toggle.
import { useCallback, useEffect, useState } from 'react';
import { IconMonitor, IconMoon, IconSun } from '../chat/Icons';
import { getAuthToken } from '../../contexts/AuthContext';
import { emitImFullAccessChanged, emitWorkspaceModeChanged } from '../../lib/system-config-events';
import { API_BASE } from '../../lib/apiBase';
import { getThemeMode, onThemeChange, setThemeMode, type ThemeMode } from '../../utils/theme';

export type { ThemeMode };
export type SandboxNetworkMode = 'disabled' | 'allowlist' | 'open';

interface EnvVar {
  key: string;
  value: string;
}

interface SystemConfigData {
  provider?: string;
  model?: string;
  system_prompt?: string;
  workspace_enabled?: boolean;
  sandbox_network_mode?: SandboxNetworkMode;
  sandbox_network_allowed_domains?: string[];
  sandbox_fs_allowed_write_paths?: string[];
  im_full_access_enabled?: boolean;
  theme?: ThemeMode;
  env_vars?: Record<string, string>;
}

type SystemConfigResponse = { success?: boolean; data?: SystemConfigData } & SystemConfigData;

const THEME_OPTIONS: { mode: ThemeMode; label: string; Icon: typeof IconSun }[] = [
  { mode: 'light', label: 'Light', Icon: IconSun },
  { mode: 'system', label: 'System', Icon: IconMonitor },
  { mode: 'dark', label: 'Dark', Icon: IconMoon },
];

const MODEL_OPTIONS = [
  { label: 'Auto', value: 'auto', model: 'claude-sonnet-4-20250514', provider: 'anthropic' },
  { label: 'Claude Sonnet', value: 'claude-sonnet-4-20250514', model: 'claude-sonnet-4-20250514', provider: 'anthropic' },
  { label: 'GPT-4.1', value: 'gpt-4.1-2025-04-14', model: 'gpt-4.1-2025-04-14', provider: 'openai' },
] as const;

const SANDBOX_NETWORK_ACCESS_OPTIONS: {
  enabled: boolean;
  label: string;
}[] = [
  { enabled: false, label: '关闭' },
  { enabled: true, label: '启用' },
];

const DEFAULT_SYSTEM_PROMPT = 'You are a concise and practical AI assistant for note-taking and writing.';

function isSandboxNetworkMode(value: unknown): value is SandboxNetworkMode {
  return value === 'disabled' || value === 'allowlist' || value === 'open';
}

function formatSandboxNetworkDomains(domains: string[] | undefined): string {
  return Array.isArray(domains) ? domains.join('\n') : '';
}

function parseSandboxNetworkDomains(value: string): string[] {
  const domains: string[] = [];
  for (const rawPart of value.split(/[\n,;]+/)) {
    const part = rawPart.trim().toLowerCase();
    if (!part || part === '*') continue;
    const withoutProtocol = part.replace(/^[a-z][a-z0-9+.-]*:\/\//, '');
    const host = withoutProtocol.split('/')[0].split('?')[0].split('#')[0].replace(/:\d+$/, '').replace(/\.$/, '');
    if (host && !domains.includes(host)) {
      domains.push(host);
    }
  }
  return domains;
}

function normalizeSandboxNetworkDomain(value: string): string | null {
  return parseSandboxNetworkDomains(value)[0] ?? null;
}

function formatSandboxFsWritePaths(paths: string[] | undefined): string {
  return Array.isArray(paths) ? paths.join('\n') : '';
}

function parseSandboxFsWritePaths(value: string): string[] {
  const paths: string[] = [];
  for (const rawPart of value.split(/[\n,;]+/)) {
    const part = rawPart.trim();
    if (!part || !part.startsWith('/')) continue;
    const normalized = part.replace(/\/+$/, '') || '/';
    if (!paths.includes(normalized)) {
      paths.push(normalized);
    }
  }
  return paths;
}

function normalizeSandboxFsWritePath(value: string): string | null {
  return parseSandboxFsWritePaths(value)[0] ?? null;
}

function readSystemConfigResponse(payload: SystemConfigResponse): SystemConfigData {
  return payload.data ?? payload;
}

function hasSystemConfigFields(config: SystemConfigData): boolean {
  return Boolean(
    config.provider !== undefined
    || config.model !== undefined
    || config.system_prompt !== undefined
    || config.workspace_enabled !== undefined
    || config.sandbox_network_mode !== undefined
    || config.sandbox_network_allowed_domains !== undefined
    || config.sandbox_fs_allowed_write_paths !== undefined
    || config.im_full_access_enabled !== undefined
    || config.theme !== undefined
    || config.env_vars !== undefined
  );
}

export default function ModelConfigSection() {
  const [theme, setTheme] = useState<ThemeMode>(() => getThemeMode());
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [workspaceMode, setWorkspaceMode] = useState(true);
  const [sandboxNetworkMode, setSandboxNetworkMode] = useState<SandboxNetworkMode>('allowlist');
  const [sandboxNetworkDomains, setSandboxNetworkDomains] = useState('');
  const [sandboxNetworkSaving, setSandboxNetworkSaving] = useState(false);
  const [sandboxNetworkStatus, setSandboxNetworkStatus] = useState<string | null>(null);
  const [sandboxNetworkAddingDomain, setSandboxNetworkAddingDomain] = useState(false);
  const [sandboxNetworkNewDomain, setSandboxNetworkNewDomain] = useState('');
  const [sandboxFsPaths, setSandboxFsPaths] = useState('');
  const [sandboxFsSaving, setSandboxFsSaving] = useState(false);
  const [sandboxFsStatus, setSandboxFsStatus] = useState<string | null>(null);
  const [sandboxFsAddingPath, setSandboxFsAddingPath] = useState(false);
  const [sandboxFsNewPath, setSandboxFsNewPath] = useState('');
  const [imFullAccessEnabled, setImFullAccessEnabled] = useState(false);
  const [selectedModel, setSelectedModel] = useState('auto');
  const [dirty, setDirty] = useState(false);
  const [configLoading, setConfigLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [envVars, setEnvVars] = useState<EnvVar[]>([]);
  const [envVarsDirty, setEnvVarsDirty] = useState(false);
  const [envVarsSaving, setEnvVarsSaving] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/system-config`, {
          headers: { 'Authorization': `Bearer ${getAuthToken()}` },
        });
        if (!response.ok) return;
        const payload = (await response.json()) as SystemConfigResponse;
        const config = readSystemConfigResponse(payload);
        if (!active) return;
        // Apply the backend theme only when it is explicitly configured, so a
        // local toggle made via the navbar is not stomped by opening Settings.
        if (config.theme === 'light' || config.theme === 'dark' || config.theme === 'system') {
          setThemeMode(config.theme);
        }
        setSystemPrompt(config.system_prompt ?? DEFAULT_SYSTEM_PROMPT);
        setWorkspaceMode(config.workspace_enabled ?? true);
        setSandboxNetworkMode(isSandboxNetworkMode(config.sandbox_network_mode) ? config.sandbox_network_mode : 'allowlist');
        setSandboxNetworkDomains(formatSandboxNetworkDomains(config.sandbox_network_allowed_domains));
        setSandboxFsPaths(formatSandboxFsWritePaths(config.sandbox_fs_allowed_write_paths));
        setSandboxFsStatus(null);
        setSandboxNetworkStatus(null);
        setImFullAccessEnabled(config.im_full_access_enabled ?? false);
        const match = MODEL_OPTIONS.find((option) => option.model === config.model);
        setSelectedModel(match?.value ?? 'auto');
        const savedEnvVars = config.env_vars ?? {};
        setEnvVars(Object.entries(savedEnvVars).map(([key, value]) => ({ key, value })));
        setDirty(false);
        setEnvVarsDirty(false);
      } catch {
        // ignore fetch errors
      } finally {
        if (active) setConfigLoading(false);
      }
    })();
    return () => { active = false; };
  }, []);

  // Keep the segmented control in sync with the unified theme store; applying
  // data-theme / colorScheme and following the system preference is handled
  // centrally by utils/theme.
  useEffect(() => {
    return onThemeChange((_resolved, mode) => setTheme(mode));
  }, []);

  const updateConfig = useCallback(async (patch: Partial<SystemConfigData>): Promise<SystemConfigData | null> => {
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/system-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getAuthToken()}` },
        body: JSON.stringify(patch),
      });
      if (!response.ok) return null;
      const payload = (await response.json().catch(() => null)) as SystemConfigResponse | null;
      if (!payload) return patch;
      const config = readSystemConfigResponse(payload);
      return hasSystemConfigFields(config) ? config : patch;
    } catch {
      return null;
    } finally {
      setSaving(false);
    }
  }, []);

  const handleThemeChange = useCallback((mode: ThemeMode) => {
    setThemeMode(mode);
    void updateConfig({ theme: mode });
  }, [updateConfig]);

  const handleModelChange = useCallback((value: string) => {
    setSelectedModel(value);
    const option = MODEL_OPTIONS.find((entry) => entry.value === value) ?? MODEL_OPTIONS[0];
    void updateConfig({ model: option.model, provider: option.provider });
  }, [updateConfig]);

  const handleWorkspaceToggle = useCallback(() => {
    const next = !workspaceMode;
    setWorkspaceMode(next);
    emitWorkspaceModeChanged(next);
    void (async () => {
      const savedConfig = await updateConfig({ workspace_enabled: next });
      if (savedConfig) {
        const persisted = savedConfig.workspace_enabled ?? next;
        setWorkspaceMode(persisted);
        emitWorkspaceModeChanged(persisted);
        return;
      }
      setWorkspaceMode(!next);
      emitWorkspaceModeChanged(!next);
    })();
  }, [updateConfig, workspaceMode]);

  const saveSandboxNetworkDomains = useCallback(async (domains: string[]) => {
    setSandboxNetworkSaving(true);
    const savedConfig = await updateConfig({ sandbox_network_allowed_domains: domains });
    if (savedConfig) {
      setSandboxNetworkDomains(formatSandboxNetworkDomains(savedConfig.sandbox_network_allowed_domains ?? domains));
      if (isSandboxNetworkMode(savedConfig.sandbox_network_mode)) {
        setSandboxNetworkMode(savedConfig.sandbox_network_mode);
      }
      setSandboxNetworkStatus('域名允许列表已保存。');
    } else {
      setSandboxNetworkStatus('域名允许列表保存失败，请稍后重试。');
    }
    setSandboxNetworkSaving(false);
    return Boolean(savedConfig);
  }, [updateConfig]);

  const handleSandboxNetworkModeChange = useCallback((mode: SandboxNetworkMode) => {
    const previousMode = sandboxNetworkMode;
    setSandboxNetworkMode(mode);
    setSandboxNetworkStatus(null);
    void (async () => {
      const savedConfig = await updateConfig({ sandbox_network_mode: mode });
      if (savedConfig) {
        setSandboxNetworkMode(isSandboxNetworkMode(savedConfig.sandbox_network_mode) ? savedConfig.sandbox_network_mode : mode);
        setSandboxNetworkDomains(formatSandboxNetworkDomains(savedConfig.sandbox_network_allowed_domains ?? parseSandboxNetworkDomains(sandboxNetworkDomains)));
        setSandboxNetworkStatus('网络策略已保存。');
        return;
      }
      setSandboxNetworkMode(previousMode);
      setSandboxNetworkStatus('网络策略保存失败，请稍后重试。');
    })();
  }, [sandboxNetworkDomains, sandboxNetworkMode, updateConfig]);

  const handleSandboxNetworkAccessToggle = useCallback((enabled: boolean) => {
    const nextMode: SandboxNetworkMode = enabled
      ? (sandboxNetworkMode === 'disabled' ? 'allowlist' : sandboxNetworkMode)
      : 'disabled';
    void handleSandboxNetworkModeChange(nextMode);
  }, [handleSandboxNetworkModeChange, sandboxNetworkMode]);

  const handleSandboxNetworkPolicySelect = useCallback((value: string) => {
    const mode: SandboxNetworkMode = value === 'open' ? 'open' : 'allowlist';
    void handleSandboxNetworkModeChange(mode);
  }, [handleSandboxNetworkModeChange]);

  const handleAddSandboxNetworkDomain = useCallback(() => {
    if (!sandboxNetworkAddingDomain) {
      setSandboxNetworkAddingDomain(true);
      setSandboxNetworkStatus(null);
      return;
    }
    const domain = normalizeSandboxNetworkDomain(sandboxNetworkNewDomain);
    if (!domain) {
      setSandboxNetworkStatus('请输入有效域名。');
      return;
    }
    const domains = parseSandboxNetworkDomains(sandboxNetworkDomains);
    if (!domains.includes(domain)) {
      domains.push(domain);
    }
    setSandboxNetworkNewDomain('');
    setSandboxNetworkAddingDomain(false);
    void saveSandboxNetworkDomains(domains);
  }, [
    sandboxNetworkAddingDomain,
    sandboxNetworkDomains,
    sandboxNetworkNewDomain,
    saveSandboxNetworkDomains,
  ]);

  const handleRemoveSandboxNetworkDomain = useCallback((domain: string) => {
    const domains = parseSandboxNetworkDomains(sandboxNetworkDomains)
      .filter((item) => item !== domain);
    void saveSandboxNetworkDomains(domains);
  }, [sandboxNetworkDomains, saveSandboxNetworkDomains]);

  const saveSandboxFsWritePaths = useCallback(async (paths: string[]) => {
    setSandboxFsSaving(true);
    const savedConfig = await updateConfig({ sandbox_fs_allowed_write_paths: paths });
    if (savedConfig) {
      setSandboxFsPaths(formatSandboxFsWritePaths(savedConfig.sandbox_fs_allowed_write_paths ?? paths));
      setSandboxFsStatus('可写路径已保存。');
    } else {
      setSandboxFsStatus('可写路径保存失败，请稍后重试。');
    }
    setSandboxFsSaving(false);
    return Boolean(savedConfig);
  }, [updateConfig]);

  const handleAddSandboxFsPath = useCallback(() => {
    if (!sandboxFsAddingPath) {
      setSandboxFsAddingPath(true);
      setSandboxFsStatus(null);
      return;
    }
    const path = normalizeSandboxFsWritePath(sandboxFsNewPath);
    if (!path) {
      setSandboxFsStatus('请输入以 / 开头的绝对路径。');
      return;
    }
    const paths = parseSandboxFsWritePaths(sandboxFsPaths);
    if (!paths.includes(path)) {
      paths.push(path);
    }
    setSandboxFsNewPath('');
    setSandboxFsAddingPath(false);
    void saveSandboxFsWritePaths(paths);
  }, [
    sandboxFsAddingPath,
    sandboxFsNewPath,
    sandboxFsPaths,
    saveSandboxFsWritePaths,
  ]);

  const handleRemoveSandboxFsPath = useCallback((path: string) => {
    const paths = parseSandboxFsWritePaths(sandboxFsPaths)
      .filter((item) => item !== path);
    void saveSandboxFsWritePaths(paths);
  }, [sandboxFsPaths, saveSandboxFsWritePaths]);

  const handleImFullAccessToggle = useCallback(() => {
    const next = !imFullAccessEnabled;
    setImFullAccessEnabled(next);
    emitImFullAccessChanged(next);
    void (async () => {
      const savedConfig = await updateConfig({ im_full_access_enabled: next });
      if (savedConfig) {
        const persisted = savedConfig.im_full_access_enabled ?? next;
        setImFullAccessEnabled(persisted);
        emitImFullAccessChanged(persisted);
        return;
      }
      setImFullAccessEnabled(!next);
      emitImFullAccessChanged(!next);
    })();
  }, [imFullAccessEnabled, updateConfig]);

  const handleSavePrompt = useCallback(() => {
    void (async () => {
      const savedConfig = await updateConfig({ system_prompt: systemPrompt });
      if (savedConfig) {
        setSystemPrompt(savedConfig.system_prompt ?? systemPrompt);
        setDirty(false);
      }
    })();
  }, [systemPrompt, updateConfig]);

  const handleResetPrompt = useCallback(() => {
    setSystemPrompt(DEFAULT_SYSTEM_PROMPT);
    setDirty(true);
  }, []);

  const handleAddEnvVar = useCallback(() => {
    setEnvVars((prev) => [...prev, { key: '', value: '' }]);
    setEnvVarsDirty(true);
  }, []);

  const handleRemoveEnvVar = useCallback((index: number) => {
    setEnvVars((prev) => prev.filter((_, i) => i !== index));
    setEnvVarsDirty(true);
  }, []);

  const handleUpdateEnvVar = useCallback((index: number, field: 'key' | 'value', val: string) => {
    setEnvVars((prev) => prev.map((item, i) => i === index ? { ...item, [field]: val } : item));
    setEnvVarsDirty(true);
  }, []);

  const handleSaveEnvVars = useCallback(async () => {
    const record: Record<string, string> = {};
    for (const { key, value } of envVars) {
      if (key.trim()) record[key.trim()] = value.trim();
    }
    setEnvVarsSaving(true);
    try {
      const savedConfig = await updateConfig({ env_vars: record });
      if (savedConfig) {
        const savedEnvVars = savedConfig.env_vars ?? record;
        setEnvVars(Object.entries(savedEnvVars).map(([key, value]) => ({ key, value })));
        setEnvVarsDirty(false);
      }
    } finally {
      setEnvVarsSaving(false);
    }
  }, [envVars, updateConfig]);

  const fieldStyle: React.CSSProperties = {
    width: '100%',
    padding: '0.75rem 0.85rem',
    borderRadius: '12px',
    border: '1px solid var(--color-border-paper)',
    background: 'var(--color-bg-paper)',
    color: 'var(--color-text-primary)',
    fontFamily: 'inherit',
    fontSize: '0.9rem',
    boxSizing: 'border-box',
  };

  if (configLoading) {
    return <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Loading config…</p>;
  }

  const sandboxNetworkEnabled = sandboxNetworkMode !== 'disabled';
  const sandboxNetworkDomainsList = parseSandboxNetworkDomains(sandboxNetworkDomains);
  const sandboxFsPathsList = parseSandboxFsWritePaths(sandboxFsPaths);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Theme */}
      <div>
        <p style={{ margin: '0 0 0.75rem', fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
          外观主题 / Theme
        </p>
        <div style={{ display: 'flex', gap: '0.65rem' }}>
          {THEME_OPTIONS.map(({ mode, label, Icon }) => {
            const active = theme === mode;
            return (
              <button
                key={mode}
                type="button"
                onClick={() => handleThemeChange(mode)}
                title={label}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.5rem 0.9rem',
                  borderRadius: '999px',
                  border: `1px solid ${active ? 'var(--color-border-focus)' : 'var(--color-border-paper)'}`,
                  background: active ? 'var(--color-bg-paper)' : 'transparent',
                  color: active ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
                  cursor: 'pointer',
                  fontSize: '0.82rem',
                  fontWeight: active ? 600 : 400,
                  transition: 'all 0.2s ease',
                }}
              >
                <Icon style={{ width: '0.9rem', height: '0.9rem' }} />
                {label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Model */}
      <div>
        <p style={{ margin: '0 0 0.65rem', fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
          AI 模型 / Model
        </p>
        <select
          value={selectedModel}
          onChange={(event) => handleModelChange(event.target.value)}
          style={fieldStyle}
        >
          {MODEL_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>{option.label}</option>
          ))}
        </select>
      </div>

      {/* System Prompt */}
      <div>
        <p style={{ margin: '0 0 0.65rem', fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
          系统提示词 / System Prompt
        </p>
        <textarea
          value={systemPrompt}
          onChange={(event) => { setSystemPrompt(event.target.value); setDirty(true); }}
          rows={5}
          style={{ ...fieldStyle, resize: 'vertical' }}
        />
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.65rem' }}>
          <button
            type="button"
            onClick={handleResetPrompt}
            style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: '0.82rem' }}
          >
            恢复默认
          </button>
          <button
            type="button"
            onClick={handleSavePrompt}
            disabled={saving || !dirty}
            style={{
              border: 'none',
              borderRadius: '999px',
              padding: '0.55rem 1.1rem',
              background: 'var(--color-action-link)',
              color: 'var(--color-text-on-action)',
              fontWeight: 600,
              fontSize: '0.82rem',
              cursor: saving || !dirty ? 'not-allowed' : 'pointer',
              opacity: saving || !dirty ? 0.55 : 1,
              transition: 'opacity 0.2s ease',
            }}
          >
            {saving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>

      {/* Workspace mode */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
        <div>
          <p style={{ margin: 0, fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            工作区模式 / Workspace Mode
          </p>
          <p style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
            对话时启用文件侧边栏上下文，并为当前 thread 开启 Bash 沙箱。
          </p>
        </div>
        <button
          type="button"
          onClick={handleWorkspaceToggle}
          aria-pressed={workspaceMode}
          style={{
            flexShrink: 0,
            position: 'relative',
            width: '2.9rem',
            height: '1.7rem',
            border: 'none',
            borderRadius: '999px',
            background: workspaceMode ? 'var(--color-action-link)' : 'var(--color-disabled-bg)',
            cursor: 'pointer',
            transition: 'background 0.2s ease',
          }}
        >
          <span
            style={{
              position: 'absolute',
              top: '0.15rem',
              left: workspaceMode ? '1.45rem' : '0.15rem',
              width: '1.4rem',
              height: '1.4rem',
              borderRadius: '999px',
              background: 'var(--color-text-on-action)',
              transition: 'left 0.2s ease',
            }}
          />
        </button>
      </div>

      {/* Sandbox network */}
      {workspaceMode ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <p style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            沙箱网络 / Sandbox Network
          </p>
          <p style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
            控制 Bash、curl、git、npm 等沙箱子进程的出站网络；WebFetch 仍由工具权限和域名规则控制。
          </p>
        </div>

        <div>
          <p style={{ margin: '0 0 0.55rem', fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            代理网络访问
          </p>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', padding: '0.25rem', borderRadius: '999px', background: 'var(--color-disabled-bg)' }}>
            {SANDBOX_NETWORK_ACCESS_OPTIONS.map((option) => {
              const active = sandboxNetworkEnabled === option.enabled;
              return (
                <button
                  key={option.label}
                  type="button"
                  onClick={() => handleSandboxNetworkAccessToggle(option.enabled)}
                  aria-pressed={active}
                  style={{
                    minWidth: '4.6rem',
                    height: '2.25rem',
                    border: 'none',
                    borderRadius: '999px',
                    background: active ? 'var(--color-bg-paper)' : 'transparent',
                    color: active ? 'var(--color-text-primary)' : 'var(--color-text-muted)',
                    cursor: 'pointer',
                    fontSize: '0.86rem',
                    fontWeight: 700,
                    transition: 'background 0.2s ease, color 0.2s ease',
                  }}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
          {!sandboxNetworkEnabled ? (
            <p style={{ margin: '0.55rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
              设置完成后将禁用网络访问。
            </p>
          ) : null}
        </div>

        {sandboxNetworkEnabled ? (
          <div style={{ borderLeft: '3px solid var(--color-border-paper)', paddingLeft: '1.35rem', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
            <div>
              <p style={{ margin: '0 0 0.55rem', fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                域允许列表
              </p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
                <select
                  value={sandboxNetworkMode === 'open' ? 'open' : 'allowlist'}
                  onChange={(event) => handleSandboxNetworkPolicySelect(event.target.value)}
                  style={{ ...fieldStyle, maxWidth: '24rem', height: '3.15rem', fontWeight: 700 }}
                >
                  <option value="allowlist">自定义域</option>
                  <option value="open">所有域</option>
                </select>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
                  <span aria-hidden="true" style={{ display: 'inline-grid', placeItems: 'center', width: '1rem', height: '1rem', borderRadius: '999px', border: '1px solid var(--color-text-muted)', fontSize: '0.68rem' }}>?</span>
                  域详情
                </span>
              </div>
            </div>

            {sandboxNetworkMode === 'allowlist' ? (
              <div>
                <p style={{ margin: '0 0 0.55rem', fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                  其他允许的域
                </p>
                {sandboxNetworkDomainsList.length ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem', marginBottom: '0.65rem' }}>
                    {sandboxNetworkDomainsList.map((domain) => (
                      <span
                        key={domain}
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.4rem',
                          maxWidth: '100%',
                          border: '1px solid var(--color-border-paper)',
                          borderRadius: '999px',
                          padding: '0.35rem 0.5rem 0.35rem 0.75rem',
                          background: 'var(--color-bg-paper)',
                          color: 'var(--color-text-primary)',
                          fontSize: '0.76rem',
                          fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                        }}
                      >
                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{domain}</span>
                        <button
                          type="button"
                          onClick={() => handleRemoveSandboxNetworkDomain(domain)}
                          aria-label={`Remove ${domain}`}
                          style={{
                            border: 'none',
                            background: 'transparent',
                            color: 'var(--color-text-muted)',
                            cursor: 'pointer',
                            fontSize: '0.85rem',
                            lineHeight: 1,
                            padding: 0,
                          }}
                        >
                          x
                        </button>
                      </span>
                    ))}
                  </div>
                ) : null}

                {sandboxNetworkAddingDomain ? (
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <input
                      type="text"
                      value={sandboxNetworkNewDomain}
                      onChange={(event) => setSandboxNetworkNewDomain(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          event.preventDefault();
                          handleAddSandboxNetworkDomain();
                        }
                      }}
                      placeholder="example.com 或 *.example.com"
                      autoFocus
                      style={{ ...fieldStyle, maxWidth: '24rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.82rem' }}
                    />
                    <button
                      type="button"
                      onClick={handleAddSandboxNetworkDomain}
                      disabled={sandboxNetworkSaving}
                      style={{
                        border: '1px solid var(--color-border-paper)',
                        borderRadius: '999px',
                        padding: '0.55rem 0.9rem',
                        background: 'var(--color-bg-paper)',
                        color: 'var(--color-text-primary)',
                        cursor: sandboxNetworkSaving ? 'not-allowed' : 'pointer',
                        fontSize: '0.82rem',
                        fontWeight: 700,
                        opacity: sandboxNetworkSaving ? 0.55 : 1,
                      }}
                    >
                      保存
                    </button>
                    <button
                      type="button"
                      onClick={() => { setSandboxNetworkAddingDomain(false); setSandboxNetworkNewDomain(''); }}
                      style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: '0.82rem' }}
                    >
                      取消
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    onClick={handleAddSandboxNetworkDomain}
                    style={{
                      border: '1px solid var(--color-border-paper)',
                      borderRadius: '999px',
                      padding: '0.55rem 0.95rem',
                      background: 'transparent',
                      color: 'var(--color-text-primary)',
                      cursor: 'pointer',
                      fontSize: '0.82rem',
                      fontWeight: 700,
                    }}
                  >
                    <span aria-hidden="true" style={{ fontSize: '1.05rem', marginRight: '0.45rem' }}>+</span>
                    添加域
                  </button>
                )}
              </div>
            ) : null}

            {sandboxNetworkMode === 'allowlist' ? (
              <div>
                <p style={{ margin: '0 0 0.55rem', fontSize: '0.88rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
                  允许的 HTTP 方法
                </p>
                <select
                  value="all"
                  disabled
                  title="Claude Code sandbox 当前按域名控制网络访问，不提供 HTTP 方法级策略。"
                  style={{ ...fieldStyle, maxWidth: '24rem', height: '3.15rem', fontWeight: 700, opacity: 0.72, cursor: 'not-allowed' }}
                >
                  <option value="all">所有方法</option>
                </select>
              </div>
            ) : null}
          </div>
        ) : null}

        {sandboxNetworkEnabled ? (
          <div style={{
            border: '1px solid color-mix(in srgb, var(--color-action-link) 30%, var(--color-border-paper))',
            borderRadius: '8px',
            background: 'color-mix(in srgb, var(--color-action-link) 12%, var(--color-bg-paper))',
            padding: '1rem',
            color: 'var(--color-text-primary)',
          }}>
            <p style={{ margin: '0 0 0.55rem', fontSize: '0.84rem', fontWeight: 800, color: 'var(--color-text-primary)' }}>
              <span style={{ display: 'inline-block', marginRight: '0.45rem', color: 'var(--color-action-link)' }}>高风险</span>
              启用互联网访问会使你的环境暴露于安全风险之中
            </p>
            <p style={{ margin: 0, fontSize: '0.78rem', lineHeight: 1.65, color: 'var(--color-text-secondary)' }}>
              这些风险包括提示注入、泄露代码或机密、添加恶意软件或漏洞，或者访问受许可证限制的内容。为了降低风险，请仅允许必要的域，并检查 Agent 的输出和工作日志。
            </p>
          </div>
        ) : null}

        {sandboxNetworkStatus ? (
          <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
            {sandboxNetworkStatus}
          </p>
        ) : null}
      </div>
      ) : null}

      {/* Sandbox filesystem extra write paths */}
      {workspaceMode ? (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        <div>
          <p style={{ margin: 0, fontSize: '1rem', fontWeight: 700, color: 'var(--color-text-primary)' }}>
            沙箱文件写入 / Sandbox File Writes
          </p>
          <p style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-muted)', lineHeight: 1.65 }}>
            除线程工作区外，额外允许沙箱内 Bash 写入的绝对路径。Claude Code 自身的临时目录（/tmp/claude-$UID 或 $CLAUDE_TMPDIR）已默认放行；工作区内部配置（.claude/settings、.editor 等）仍始终禁止写入。
          </p>
        </div>

        {sandboxFsPathsList.length ? (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.45rem' }}>
            {sandboxFsPathsList.map((path) => (
              <span
                key={path}
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  maxWidth: '100%',
                  border: '1px solid var(--color-border-paper)',
                  borderRadius: '999px',
                  padding: '0.35rem 0.5rem 0.35rem 0.75rem',
                  background: 'var(--color-bg-paper)',
                  color: 'var(--color-text-primary)',
                  fontSize: '0.76rem',
                  fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace',
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{path}</span>
                <button
                  type="button"
                  onClick={() => handleRemoveSandboxFsPath(path)}
                  aria-label={`Remove ${path}`}
                  style={{
                    border: 'none',
                    background: 'transparent',
                    color: 'var(--color-text-muted)',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    lineHeight: 1,
                    padding: 0,
                  }}
                >
                  x
                </button>
              </span>
            ))}
          </div>
        ) : null}

        <div>
          {sandboxFsAddingPath ? (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <input
                type="text"
                value={sandboxFsNewPath}
                onChange={(event) => setSandboxFsNewPath(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') {
                    event.preventDefault();
                    handleAddSandboxFsPath();
                  }
                }}
                placeholder="/absolute/path"
                autoFocus
                style={{ ...fieldStyle, maxWidth: '24rem', fontFamily: 'ui-monospace, SFMono-Regular, Menlo, monospace', fontSize: '0.82rem' }}
              />
              <button
                type="button"
                onClick={handleAddSandboxFsPath}
                disabled={sandboxFsSaving}
                style={{
                  border: '1px solid var(--color-border-paper)',
                  borderRadius: '999px',
                  padding: '0.55rem 0.9rem',
                  background: 'var(--color-bg-paper)',
                  color: 'var(--color-text-primary)',
                  cursor: sandboxFsSaving ? 'not-allowed' : 'pointer',
                  fontSize: '0.82rem',
                  fontWeight: 700,
                  opacity: sandboxFsSaving ? 0.55 : 1,
                }}
              >
                保存
              </button>
              <button
                type="button"
                onClick={() => { setSandboxFsAddingPath(false); setSandboxFsNewPath(''); }}
                style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer', fontSize: '0.82rem' }}
              >
                取消
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={handleAddSandboxFsPath}
              style={{
                border: '1px solid var(--color-border-paper)',
                borderRadius: '999px',
                padding: '0.55rem 0.95rem',
                background: 'transparent',
                color: 'var(--color-text-primary)',
                cursor: 'pointer',
                fontSize: '0.82rem',
                fontWeight: 700,
              }}
            >
              <span aria-hidden="true" style={{ fontSize: '1.05rem', marginRight: '0.45rem' }}>+</span>
              添加可写路径
            </button>
          )}
        </div>

        {sandboxFsStatus ? (
          <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--color-text-muted)' }}>
            {sandboxFsStatus}
          </p>
        ) : null}
      </div>
      ) : null}

      {/* IM approval mode */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
        <div>
          <p style={{ margin: 0, fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
            应如何批准 IM
          </p>
          <p style={{ margin: '0.2rem 0 0', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
            开启后普通工具自动批准，问答表单仍需用户确认。
          </p>
        </div>
        <button
          type="button"
          onClick={handleImFullAccessToggle}
          aria-pressed={imFullAccessEnabled}
          title={imFullAccessEnabled ? '完全访问已开启' : '完全访问已关闭'}
          style={{
            flexShrink: 0,
            minWidth: '6.25rem',
            height: '1.9rem',
            border: 'none',
            borderRadius: '999px',
            padding: '0 0.85rem',
            background: imFullAccessEnabled ? 'var(--color-text-primary)' : 'var(--color-disabled-bg)',
            color: imFullAccessEnabled ? 'var(--color-bg-paper)' : 'var(--color-text-secondary)',
            cursor: 'pointer',
            fontSize: '0.78rem',
            fontWeight: 600,
            transition: 'background 0.2s ease, color 0.2s ease',
            whiteSpace: 'nowrap',
          }}
        >
          完全访问
        </button>
      </div>

      {/* Environment Variables */}
      {workspaceMode ? (
      <div>
        <p style={{ margin: '0 0 0.3rem', fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>
          环境变量 / Environment Variables
        </p>
        <p style={{ margin: '0 0 0.75rem', fontSize: '0.78rem', color: 'var(--color-text-muted)' }}>
          为 Skills / MCP 工具配置运行时环境变量。
        </p>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {envVars.map((ev, i) => (
            <div key={i} style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <input
                type="text"
                placeholder="KEY"
                value={ev.key}
                onChange={(e) => handleUpdateEnvVar(i, 'key', e.target.value)}
                style={{ ...fieldStyle, flex: 1, fontFamily: 'monospace', fontSize: '0.82rem' }}
              />
              <input
                type="password"
                placeholder="value"
                value={ev.value}
                onChange={(e) => handleUpdateEnvVar(i, 'value', e.target.value)}
                style={{ ...fieldStyle, flex: 2, fontFamily: 'monospace', fontSize: '0.82rem' }}
              />
              <button
                type="button"
                onClick={() => handleRemoveEnvVar(i)}
                style={{
                  flexShrink: 0,
                  border: 'none',
                  background: 'transparent',
                  color: 'var(--color-text-muted)',
                  cursor: 'pointer',
                  fontSize: '1rem',
                  padding: '0.25rem 0.4rem',
                  borderRadius: '6px',
                }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
          <button
            type="button"
            onClick={handleAddEnvVar}
            style={{
              border: '1px dashed var(--color-border-paper)',
              borderRadius: '8px',
              padding: '0.4rem 0.85rem',
              background: 'transparent',
              color: 'var(--color-text-muted)',
              fontSize: '0.82rem',
              cursor: 'pointer',
            }}
          >
            + 添加变量
          </button>
          <button
            type="button"
            disabled={!envVarsDirty || envVarsSaving}
            onClick={handleSaveEnvVars}
            style={{
              border: 'none',
              borderRadius: '999px',
              padding: '0.4rem 1rem',
              background: 'var(--color-action-link)',
              color: 'var(--color-text-on-action)',
              fontWeight: 600,
              fontSize: '0.82rem',
              cursor: !envVarsDirty || envVarsSaving ? 'not-allowed' : 'pointer',
              opacity: !envVarsDirty || envVarsSaving ? 0.55 : 1,
              transition: 'opacity 0.2s ease',
            }}
          >
            {envVarsSaving ? '保存中…' : '保存'}
          </button>
        </div>
      </div>
      ) : null}
    </div>
  );
}
