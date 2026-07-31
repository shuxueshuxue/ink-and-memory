// [Input] Runtime API base config, AuthContext token, system config endpoint, and dashboard icons.
// [Output] Dashboard sidebar settings UI backed by backend system config.
// [Pos] dashboard sidebar component node
// [Sync] 2026-06-12: use centralized API_BASE for cross-origin system config requests.
// [Sync] 2026-06-22: emit same-tab Workspace Mode changes when the legacy
//                    sidebar toggles system_config.workspace_enabled.
// [Sync] 2026-07-23: theme control now reads/writes the unified theme store
//                    (utils/theme) instead of its own 'dashboard-theme' key and
//                    private data-theme effect, matching ModelConfigSection.
import { useCallback, useEffect, useState } from 'react';
import { IconMonitor, IconMoon, IconSun } from '../chat/Icons';
import { getAuthToken } from '../../contexts/AuthContext';
import { API_BASE } from '../../lib/apiBase';
import { emitWorkspaceModeChanged } from '../../lib/system-config-events';
import { getThemeMode, onThemeChange, setThemeMode, type ThemeMode } from '../../utils/theme';

export type { ThemeMode };

interface SystemConfigData {
  provider?: string;
  model?: string;
  system_prompt?: string;
  workspace_enabled?: boolean;
  theme?: ThemeMode;
}

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

const DEFAULT_SYSTEM_PROMPT = 'You are a concise and practical AI sales assistant.';

export default function Sidebar({ open, desktopCollapsed = false, onClose }: { open: boolean; desktopCollapsed?: boolean; onClose: () => void }) {
  const [theme, setTheme] = useState<ThemeMode>(() => getThemeMode());
  const [systemPrompt, setSystemPrompt] = useState(DEFAULT_SYSTEM_PROMPT);
  const [workspaceMode, setWorkspaceMode] = useState(true);
  const [selectedModel, setSelectedModel] = useState('auto');
  const [dirty, setDirty] = useState(false);
  const [configLoading, setConfigLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/system-config`, {
          headers: { 'Authorization': `Bearer ${getAuthToken()}` },
        });
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as { data?: SystemConfigData } & SystemConfigData;
        const config = payload.data ?? payload;
        if (!active) {
          return;
        }
        // Apply the backend theme only when explicitly configured; otherwise
        // keep the local preference from the unified theme store.
        if (config.theme === 'light' || config.theme === 'dark' || config.theme === 'system') {
          setThemeMode(config.theme);
        }
        setSystemPrompt(config.system_prompt ?? DEFAULT_SYSTEM_PROMPT);
        setWorkspaceMode(config.workspace_enabled ?? true);
        const match = MODEL_OPTIONS.find((option) => option.model === config.model);
        setSelectedModel(match?.value ?? 'auto');
        setDirty(false);
      } catch {
        // ignore fetch errors
      } finally {
        if (active) {
          setConfigLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  // Keep the segmented control in sync with the unified theme store; applying
  // data-theme / colorScheme and following the system preference is handled
  // centrally by utils/theme.
  useEffect(() => {
    return onThemeChange((_resolved, mode) => setTheme(mode));
  }, []);

  const updateConfig = useCallback(async (patch: Partial<SystemConfigData>) => {
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/system-config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getAuthToken()}` },
        body: JSON.stringify(patch),
      });
      return response.ok;
    } catch {
      return false;
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
      const saved = await updateConfig({ workspace_enabled: next });
      if (saved) {
        return;
      }
      setWorkspaceMode(!next);
      emitWorkspaceModeChanged(!next);
    })();
  }, [updateConfig, workspaceMode]);

  const handleSavePrompt = useCallback(() => {
    void updateConfig({ system_prompt: systemPrompt });
    setDirty(false);
  }, [systemPrompt, updateConfig]);

  const handleResetPrompt = useCallback(() => {
    setSystemPrompt(DEFAULT_SYSTEM_PROMPT);
    setDirty(true);
  }, []);

  return (
    <>
      {open ? <div onClick={onClose} style={{ position: 'fixed', inset: 0, zIndex: 20, background: 'var(--color-bg-overlay)' }} /> : null}
      <aside style={{ position: 'relative', zIndex: 21, width: desktopCollapsed ? 0 : '18rem', minWidth: desktopCollapsed ? 0 : '18rem', overflow: 'hidden', borderRight: desktopCollapsed ? 'none' : '1px solid var(--color-border-paper)', background: 'var(--color-bg-app)', transition: 'width 0.25s ease, min-width 0.25s ease', display: open || !desktopCollapsed ? 'block' : 'none' }}>
        <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '1.25rem', height: '100%', boxSizing: 'border-box' }}>
          <div>
            <p style={{ margin: 0, fontSize: '0.72rem', letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--color-text-muted)' }}>Workspace</p>
            <h2 style={{ margin: '0.35rem 0 0', fontSize: '1.15rem', color: 'var(--color-text-primary)' }}>AI Sales Console</h2>
          </div>

          {configLoading ? <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--color-text-muted)' }}>Loading config…</p> : (
            <>
              <section>
                <p style={{ margin: 0, fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>Theme</p>
                <div style={{ display: 'flex', gap: '0.65rem', marginTop: '0.75rem' }}>
                  {THEME_OPTIONS.map(({ mode, label, Icon }) => {
                    const active = theme === mode;
                    return <button key={mode} type="button" onClick={() => handleThemeChange(mode)} title={label} style={{ width: '2.2rem', height: '2.2rem', borderRadius: '999px', border: `1px solid ${active ? 'var(--color-border-focus)' : 'var(--color-border-paper)'}`, background: active ? 'var(--color-bg-paper)' : 'transparent', color: active ? 'var(--color-text-primary)' : 'var(--color-text-muted)', cursor: 'pointer' }}><Icon style={{ width: '1rem', height: '1rem' }} /></button>;
                  })}
                </div>
              </section>

              <section>
                <p style={{ margin: 0, fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>Model</p>
                <select value={selectedModel} onChange={(event) => handleModelChange(event.target.value)} style={{ width: '100%', marginTop: '0.65rem', padding: '0.75rem 0.85rem', borderRadius: '12px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', color: 'var(--color-text-primary)' }}>
                  {MODEL_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                </select>
              </section>

              <section>
                <p style={{ margin: 0, fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>System prompt</p>
                <textarea value={systemPrompt} onChange={(event) => { setSystemPrompt(event.target.value); setDirty(true); }} rows={5} style={{ width: '100%', marginTop: '0.65rem', padding: '0.75rem 0.85rem', borderRadius: '12px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)', color: 'var(--color-text-primary)', resize: 'vertical', boxSizing: 'border-box' }} />
                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.65rem' }}>
                  <button type="button" onClick={handleResetPrompt} style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}>Reset</button>
                  <button type="button" onClick={handleSavePrompt} disabled={saving || !dirty} style={{ border: 'none', borderRadius: '999px', padding: '0.55rem 0.9rem', background: 'var(--color-action-link)', color: 'var(--color-text-on-action)', fontWeight: 600, cursor: saving || !dirty ? 'not-allowed' : 'pointer', opacity: saving || !dirty ? 0.55 : 1 }}>{saving ? 'Saving…' : 'Save'}</button>
                </div>
              </section>

              <section style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div>
                  <p style={{ margin: 0, fontSize: '0.88rem', fontWeight: 600, color: 'var(--color-text-primary)' }}>Workspace mode</p>
                  <p style={{ margin: '0.2rem 0 0', fontSize: '0.74rem', color: 'var(--color-text-muted)' }}>Enable file-side context while chatting.</p>
                </div>
                <button type="button" onClick={handleWorkspaceToggle} aria-pressed={workspaceMode} style={{ position: 'relative', width: '2.9rem', height: '1.7rem', border: 'none', borderRadius: '999px', background: workspaceMode ? 'var(--color-action-link)' : 'var(--color-disabled-bg)', cursor: 'pointer' }}>
                  <span style={{ position: 'absolute', top: '0.15rem', left: workspaceMode ? '1.45rem' : '0.15rem', width: '1.4rem', height: '1.4rem', borderRadius: '999px', background: 'var(--color-text-on-action)', transition: 'left 0.2s ease' }} />
                </button>
              </section>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
