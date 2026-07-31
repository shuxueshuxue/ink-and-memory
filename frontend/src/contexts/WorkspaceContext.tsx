// [Input] Runtime API base config, AuthContext token, and system-config change events.
// [Output] Provide active workspace session and Workspace Mode enabled state to chat/file UI.
// [Pos] workspace-context provider node in frontend/src/contexts
// [Sync] 2026-06-22: load Settings workspace_enabled and subscribe to same-tab
//                    Workspace Mode changes so file/workspace entry points can
//                    close without a page refresh.
import {
  createContext,
  useEffect,
  useContext,
  useMemo,
  useState,
  type Dispatch,
  type ReactNode,
  type SetStateAction,
} from 'react';
import { getAuthToken } from './AuthContext';
import { API_BASE } from '../lib/apiBase';
import { subscribeWorkspaceModeChanged } from '../lib/system-config-events';

interface WorkspaceContextValue {
  activeSessionId: string | null;
  setActiveSessionId: Dispatch<SetStateAction<string | null>>;
  workspaceEnabled: boolean;
  workspaceConfigLoaded: boolean;
}

const WorkspaceContext = createContext<WorkspaceContextValue | null>(null);

function normalizeWorkspaceEnabled(payload: {
  data?: { workspace_enabled?: boolean };
  workspace_enabled?: boolean;
}): boolean {
  const config = payload.data ?? payload;
  return config.workspace_enabled ?? true;
}

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [workspaceEnabled, setWorkspaceEnabled] = useState(true);
  const [workspaceConfigLoaded, setWorkspaceConfigLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    const unsubscribe = subscribeWorkspaceModeChanged((enabled) => {
      setWorkspaceEnabled(enabled);
      setWorkspaceConfigLoaded(true);
    });

    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/system-config`, {
          headers: { 'Authorization': `Bearer ${getAuthToken()}` },
        });
        if (!response.ok) return;
        const payload = (await response.json()) as {
          data?: { workspace_enabled?: boolean };
          workspace_enabled?: boolean;
        };
        if (active) {
          setWorkspaceEnabled(normalizeWorkspaceEnabled(payload));
        }
      } catch {
        // Preserve the existing enabled-by-default behavior on config errors.
      } finally {
        if (active) {
          setWorkspaceConfigLoaded(true);
        }
      }
    })();

    return () => {
      active = false;
      unsubscribe();
    };
  }, []);

  const value = useMemo(
    () => ({
      activeSessionId,
      setActiveSessionId,
      workspaceEnabled,
      workspaceConfigLoaded,
    }),
    [activeSessionId, workspaceConfigLoaded, workspaceEnabled],
  );

  return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}

export function useWorkspaceSession() {
  const context = useContext(WorkspaceContext);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  return context ?? {
    activeSessionId,
    setActiveSessionId,
    workspaceEnabled: true,
    workspaceConfigLoaded: false,
  };
}
