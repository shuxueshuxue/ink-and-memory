// [Input] Browser CustomEvent API.
// [Output] Shared same-tab system-config change events for Settings and chat UI.
// [Pos] system-config-events utility node in frontend/src/lib
// [Sync] 2026-06-09: add IM full-access change event so Settings toggles update
//                    Chat UI immediately without a page refresh.
// [Sync] 2026-06-22: add Workspace Mode change event so file/workspace UI
//                    surfaces close immediately when Settings disables workspace.

export const IM_FULL_ACCESS_CHANGED_EVENT = 'ink-memory:im-full-access-changed';
export const WORKSPACE_MODE_CHANGED_EVENT = 'ink-memory:workspace-mode-changed';

export interface ImFullAccessChangedDetail {
  enabled: boolean;
}

export interface WorkspaceModeChangedDetail {
  enabled: boolean;
}

export function emitImFullAccessChanged(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<ImFullAccessChangedDetail>(IM_FULL_ACCESS_CHANGED_EVENT, {
      detail: { enabled },
    }),
  );
}

export function emitWorkspaceModeChanged(enabled: boolean): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(
    new CustomEvent<WorkspaceModeChangedDetail>(WORKSPACE_MODE_CHANGED_EVENT, {
      detail: { enabled },
    }),
  );
}

export function subscribeImFullAccessChanged(
  listener: (enabled: boolean) => void,
): () => void {
  if (typeof window === 'undefined') return () => {};

  const handleEvent = (event: Event) => {
    const detail = (event as CustomEvent<ImFullAccessChangedDetail>).detail;
    if (typeof detail?.enabled === 'boolean') {
      listener(detail.enabled);
    }
  };

  window.addEventListener(IM_FULL_ACCESS_CHANGED_EVENT, handleEvent);
  return () => window.removeEventListener(IM_FULL_ACCESS_CHANGED_EVENT, handleEvent);
}

export function subscribeWorkspaceModeChanged(
  listener: (enabled: boolean) => void,
): () => void {
  if (typeof window === 'undefined') return () => {};

  const handleEvent = (event: Event) => {
    const detail = (event as CustomEvent<WorkspaceModeChangedDetail>).detail;
    if (typeof detail?.enabled === 'boolean') {
      listener(detail.enabled);
    }
  };

  window.addEventListener(WORKSPACE_MODE_CHANGED_EVENT, handleEvent);
  return () => window.removeEventListener(WORKSPACE_MODE_CHANGED_EVENT, handleEvent);
}
