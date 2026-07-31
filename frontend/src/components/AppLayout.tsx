// [Input] WorkspaceContext, dashboard navigation/sidebar components, and child route content.
// [Output] Render optional legacy app layout with Workspace Mode-gated file sidebar.
// [Pos] app-layout component node in frontend/src/components
// [Sync] 2026-06-22: hide and close the file sidebar when Settings Workspace
//                    Mode is disabled.
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { WorkspaceProvider, useWorkspaceSession } from '../contexts/WorkspaceContext';
import FileSidebar from './dashboard/FileSidebar';
import Sidebar from './dashboard/Sidebar';
import VerticalNav from './dashboard/VerticalNav';

function AppLayoutShell({ children }: { children: ReactNode }) {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [desktopCollapsed, setDesktopCollapsed] = useState(false);
  const [fileSidebarOpen, setFileSidebarOpen] = useState(false);
  const { activeSessionId, workspaceEnabled } = useWorkspaceSession();
  const fileSidebarSessionId = activeSessionId ?? 'shared-workspace';

  const handleToggleFileSidebar = useCallback(() => {
    if (!workspaceEnabled) return;
    const nextOpen = !fileSidebarOpen;
    setFileSidebarOpen(nextOpen);
    if (nextOpen) {
      setSidebarOpen(false);
      if (window.innerWidth >= 768) {
        setDesktopCollapsed(true);
      }
    }
  }, [fileSidebarOpen, workspaceEnabled]);

  useEffect(() => {
    if (!workspaceEnabled) {
      setFileSidebarOpen(false);
    }
  }, [workspaceEnabled]);

  return (
    <div style={{ display: 'flex', minHeight: '100vh', overflow: 'hidden', background: 'var(--color-bg-app)' }}>
      <VerticalNav onToggleFileSidebar={workspaceEnabled ? handleToggleFileSidebar : undefined} />
      <Sidebar open={sidebarOpen} desktopCollapsed={desktopCollapsed} onClose={() => setSidebarOpen(false)} />
      <main style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto', padding: '1rem 1rem 2rem' }}>{children}</main>
      {workspaceEnabled ? (
        <FileSidebar sessionId={fileSidebarSessionId} open={fileSidebarOpen} onClose={() => setFileSidebarOpen(false)} />
      ) : null}
    </div>
  );
}

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <WorkspaceProvider>
      <AppLayoutShell>{children}</AppLayoutShell>
    </WorkspaceProvider>
  );
}
