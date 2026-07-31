// [Input] Runtime API base config, AuthContext token, workspace file APIs, and dashboard file UI state.
// [Output] Workspace file sidebar with list/upload/delete/download behavior.
// [Pos] dashboard file-sidebar component node
// [Sync] 2026-06-12: use centralized API_BASE for cross-origin workspace file requests.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { IconChevronDown, IconChevronRight, IconDownload, IconFile, IconFolder, IconLoader, IconPlus, IconTrash, IconX } from '../chat/Icons';
import { getAuthToken } from '../../contexts/AuthContext';
import { API_BASE } from '../../lib/apiBase';

export interface FileInfo {
  name: string;
  path: string;
  isDirectory: boolean;
  size: number;
  modifiedAt: string;
  children?: FileInfo[];
}

interface FileSidebarProps {
  sessionId: string;
  open: boolean;
  onClose: () => void;
  title?: string;
}

interface UploadQueueItem {
  id: string;
  relativePath: string;
  size: number;
  source: 'file-picker' | 'folder-picker' | 'drag';
  status: 'pending' | 'uploading' | 'success' | 'error';
  error?: string;
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB'];
  const unitIndex = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / 1024 ** unitIndex).toFixed(unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
}

function normalizePath(value: string) {
  return value.replace(/\\/g, '/').replace(/^\/+|\/+$/g, '');
}

function buildTree(files: FileInfo[]): FileInfo[] {
  const root: FileInfo[] = [];
  const directoryMap = new Map<string, FileInfo>();

  const ensureDirectory = (directoryPath: string) => {
    const normalized = normalizePath(directoryPath);
    if (!normalized) return null;
    const existing = directoryMap.get(normalized);
    if (existing) return existing;
    const parts = normalized.split('/');
    const name = parts[parts.length - 1];
    const parentPath = parts.slice(0, -1).join('/');
    const node: FileInfo = { name, path: normalized, isDirectory: true, size: 0, modifiedAt: new Date().toISOString(), children: [] };
    directoryMap.set(normalized, node);
    if (parentPath) {
      ensureDirectory(parentPath)?.children?.push(node);
    } else {
      root.push(node);
    }
    return node;
  };

  files.forEach((file) => {
    const normalizedPath = normalizePath(file.path);
    if (file.isDirectory) {
      ensureDirectory(normalizedPath);
      return;
    }
    const parentPath = normalizedPath.split('/').slice(0, -1).join('/');
    const node: FileInfo = { ...file, path: normalizedPath };
    if (parentPath) {
      ensureDirectory(parentPath)?.children?.push(node);
    } else {
      root.push(node);
    }
  });

  const sortNodes = (nodes: FileInfo[]) => {
    nodes.sort((a, b) => Number(b.isDirectory) - Number(a.isDirectory) || a.name.localeCompare(b.name));
    nodes.forEach((node) => node.children && sortNodes(node.children));
  };
  sortNodes(root);
  return root;
}

function flattenVisible(nodes: FileInfo[], currentPath: string): FileInfo[] {
  if (!currentPath) {
    return nodes;
  }
  const walk = (entries: FileInfo[]): FileInfo[] => {
    for (const entry of entries) {
      if (entry.path === currentPath && entry.isDirectory) {
        return entry.children ?? [];
      }
      if (entry.children?.length) {
        const nested = walk(entry.children);
        if (nested.length || entry.path === currentPath) {
          return nested;
        }
      }
    }
    return [];
  };
  return walk(nodes);
}

function buildWorkspaceFileDownloadUrl(sessionId: string, filePath: string): string {
  const params = new URLSearchParams({ sessionId, path: filePath });
  return `${API_BASE}/api/workspace/files/download?${params.toString()}`;
}

export default function FileSidebar({ sessionId, open, onClose, title = 'Files' }: FileSidebarProps) {
  const [fileTree, setFileTree] = useState<FileInfo[]>([]);
  const [currentPath, setCurrentPath] = useState('');
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [directoryError, setDirectoryError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  const loadDirectoryData = useCallback(async () => {
    if (!sessionId) return;
    setLoading(true);
    setDirectoryError(null);
    try {
      const response = await fetch(`${API_BASE}/api/workspace/files?${new URLSearchParams({ sessionId, recursive: '1' }).toString()}`, {
        headers: { 'Authorization': `Bearer ${getAuthToken()}` },
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { error?: string };
        throw new Error(payload.error || `目录刷新失败 (${response.status})`);
      }
      const payload = (await response.json()) as { tree?: FileInfo[]; files?: FileInfo[] };
      const files = payload.tree?.length ? payload.tree : buildTree(payload.files ?? []);
      setFileTree(files.map((entry) => ({ ...entry, path: normalizePath(entry.path), children: entry.children })));
    } catch (error) {
      setDirectoryError(error instanceof Error ? error.message : '目录刷新失败');
    } finally {
      setLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    const input = folderInputRef.current;
    if (!input) return;
    input.setAttribute('webkitdirectory', '');
  }, []);

  useEffect(() => {
    if (open && sessionId) {
      void loadDirectoryData();
    }
  }, [loadDirectoryData, open, sessionId]);

  useEffect(() => {
    if (!open || !sessionId) return;
    const timer = window.setInterval(() => {
      void loadDirectoryData();
    }, 60000);
    return () => window.clearInterval(timer);
  }, [loadDirectoryData, open, sessionId]);

  const uploadFiles = useCallback(async (files: FileList | null, source: UploadQueueItem['source']) => {
    if (!files?.length || !sessionId) {
      return;
    }
    const ids = Array.from(files).map(() => `${Date.now()}-${Math.random().toString(36).slice(2)}`);
    const queued = Array.from(files).map((file, index) => ({
      id: ids[index],
      relativePath: normalizePath(file.webkitRelativePath || file.name),
      size: file.size,
      source,
      status: 'pending' as const,
    }));
    setUploadQueue((current) => [...current, ...queued]);
    setUploading(true);
    setNotice(null);
    try {
      const formData = new FormData();
      formData.set('sessionId', sessionId);
      if (currentPath) {
        formData.set('path', currentPath);
      }
      Array.from(files).forEach((file) => {
        formData.append('file', file);
        formData.append('relativePath', normalizePath(file.webkitRelativePath || file.name));
      });
      setUploadQueue((current) => current.map((item) => ids.includes(item.id) ? { ...item, status: 'uploading' } : item));
      const response = await fetch(`${API_BASE}/api/workspace/files`, { method: 'POST', headers: { 'Authorization': `Bearer ${getAuthToken()}` }, body: formData });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { error?: string };
        throw new Error(payload.error || `上传失败 (${response.status})`);
      }
      setUploadQueue((current) => current.map((item) => ids.includes(item.id) ? { ...item, status: 'success' } : item));
      setNotice(`Uploaded ${files.length} item${files.length === 1 ? '' : 's'}.`);
      await loadDirectoryData();
    } catch (error) {
      const message = error instanceof Error ? error.message : '上传失败';
      setUploadQueue((current) => current.map((item) => ids.includes(item.id) ? { ...item, status: 'error', error: message } : item));
      setNotice(message);
    } finally {
      setUploading(false);
    }
  }, [currentPath, loadDirectoryData, sessionId]);

  const handleDelete = useCallback(async (filePath: string) => {
    if (!sessionId) return;
    try {
      const response = await fetch(`${API_BASE}/api/workspace/files`, {
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId, path: filePath }),
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { error?: string };
        throw new Error(payload.error || `删除失败 (${response.status})`);
      }
      await loadDirectoryData();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '删除失败');
    }
  }, [loadDirectoryData, sessionId]);

  const handleDownload = useCallback(async (file: FileInfo) => {
    if (!sessionId || file.isDirectory) return;
    try {
      const response = await fetch(buildWorkspaceFileDownloadUrl(sessionId, file.path), {
        headers: { 'Authorization': `Bearer ${getAuthToken()}` },
      });
      if (!response.ok) {
        const payload = (await response.json().catch(() => ({}))) as { error?: string };
        throw new Error(payload.error || `下载失败 (${response.status})`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = file.name;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
      setNotice(`Started download: ${file.name}`);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : '下载失败');
    }
  }, [sessionId]);

  const visibleFiles = useMemo(() => flattenVisible(fileTree, currentPath), [currentPath, fileTree]);
  const breadcrumbs = useMemo(() => ['workspace', ...currentPath.split('/').filter(Boolean)], [currentPath]);

  return (
    <aside style={{ width: open ? '20rem' : 0, minWidth: open ? '20rem' : 0, overflow: 'hidden', borderLeft: open ? '1px solid var(--color-border-paper)' : 'none', background: 'var(--color-bg-app)', transition: 'width 0.25s ease, min-width 0.25s ease', display: 'flex', flexDirection: 'column' }}>
      {open ? (
        <>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '1rem', borderBottom: '1px solid var(--color-border-paper)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--color-text-primary)' }}>
              <IconFolder style={{ width: '1.1rem', height: '1.1rem', color: 'var(--color-action-link)' }} />
              <span style={{ fontWeight: 600 }}>{title}</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <button type="button" onClick={() => void loadDirectoryData()} style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}>{loading ? <IconLoader style={{ width: '0.95rem', height: '0.95rem' }} /> : '↻'}</button>
              <button type="button" onClick={() => fileInputRef.current?.click()} disabled={uploading} style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}><IconPlus style={{ width: '1rem', height: '1rem' }} /></button>
              <button type="button" onClick={() => folderInputRef.current?.click()} disabled={uploading} style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}><IconFolder style={{ width: '1rem', height: '1rem' }} /></button>
              <button type="button" onClick={onClose} style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}><IconX style={{ width: '1rem', height: '1rem' }} /></button>
            </div>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.2rem', padding: '0.65rem 1rem', borderBottom: '1px solid var(--color-border-paper)', fontSize: '0.75rem', color: 'var(--color-text-muted)' }}>
            {breadcrumbs.map((part, index) => (
              <span key={`${part}-${index}`}>
                {index > 0 ? ' / ' : ''}
                <button type="button" onClick={() => setCurrentPath(index === 0 ? '' : breadcrumbs.slice(1, index + 1).join('/'))} style={{ border: 'none', background: 'transparent', color: 'inherit', cursor: 'pointer' }}>{part}</button>
              </span>
            ))}
          </div>

          <input ref={fileInputRef} type="file" multiple style={{ display: 'none' }} onChange={(event) => { void uploadFiles(event.target.files, 'file-picker'); event.target.value = ''; }} />
          <input ref={folderInputRef} type="file" multiple style={{ display: 'none' }} onChange={(event) => { void uploadFiles(event.target.files, 'folder-picker'); event.target.value = ''; }} />

          <div onDragOver={(event) => { event.preventDefault(); setDragOver(true); }} onDragLeave={(event) => { event.preventDefault(); setDragOver(false); }} onDrop={(event) => { event.preventDefault(); setDragOver(false); void uploadFiles(event.dataTransfer.files, 'drag'); }} style={{ flex: 1, overflow: 'auto', padding: '0.75rem', background: dragOver ? 'rgba(74,144,226,0.08)' : 'transparent' }}>
            {directoryError ? <div style={{ marginBottom: '0.75rem', padding: '0.7rem 0.85rem', borderRadius: '10px', background: 'rgba(217,83,79,0.1)', color: '#d9534f', fontSize: '0.8rem' }}>{directoryError}</div> : null}
            {visibleFiles.length === 0 && !loading ? <div style={{ padding: '1rem', borderRadius: '12px', background: 'var(--color-bg-paper)', color: 'var(--color-text-muted)', fontSize: '0.84rem' }}>No files yet.</div> : null}
            {visibleFiles.map((node) => {
              const isOpen = expandedDirs.has(node.path);
              return (
                <div key={node.path} style={{ marginBottom: '0.35rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem', padding: '0.55rem 0.6rem', borderRadius: '10px', background: 'var(--color-bg-paper)' }}>
                    {node.isDirectory ? <button type="button" onClick={() => { setExpandedDirs((current) => { const next = new Set(current); if (next.has(node.path)) next.delete(node.path); else next.add(node.path); return next; }); setCurrentPath(node.path); }} style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}>{isOpen ? <IconChevronDown style={{ width: '0.9rem', height: '0.9rem' }} /> : <IconChevronRight style={{ width: '0.9rem', height: '0.9rem' }} />}</button> : <span style={{ width: '0.9rem' }} />}
                    {node.isDirectory ? <IconFolder style={{ width: '1rem', height: '1rem', color: 'var(--color-action-link)' }} /> : <IconFile style={{ width: '1rem', height: '1rem', color: 'var(--color-text-muted)' }} />}
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: '0.83rem', color: 'var(--color-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{node.name}</div>
                      {!node.isDirectory ? <div style={{ fontSize: '0.7rem', color: 'var(--color-text-muted)' }}>{formatFileSize(node.size)}</div> : null}
                    </div>
                    {!node.isDirectory ? <button type="button" onClick={() => void handleDownload(node)} style={{ border: 'none', background: 'transparent', color: 'var(--color-text-muted)', cursor: 'pointer' }}><IconDownload style={{ width: '0.95rem', height: '0.95rem' }} /></button> : null}
                    <button type="button" onClick={() => void handleDelete(node.path)} style={{ border: 'none', background: 'transparent', color: '#d9534f', cursor: 'pointer' }}><IconTrash style={{ width: '0.95rem', height: '0.95rem' }} /></button>
                  </div>
                </div>
              );
            })}
          </div>

          <div style={{ padding: '0.75rem', borderTop: '1px solid var(--color-border-paper)' }}>
            <div style={{ marginBottom: '0.6rem', padding: '0.8rem', borderRadius: '12px', border: `2px dashed ${dragOver ? 'var(--color-action-link)' : 'var(--color-border-paper)'}`, color: 'var(--color-text-muted)', fontSize: '0.78rem', textAlign: 'center' }}>拖拽文件或文件夹到这里，或使用顶部按钮上传。</div>
            {notice ? <div style={{ marginBottom: '0.6rem', padding: '0.7rem 0.85rem', borderRadius: '10px', background: 'var(--color-bg-paper)', color: 'var(--color-text-secondary)', fontSize: '0.8rem' }}>{notice}</div> : null}
            {uploadQueue.length > 0 ? (
              <div style={{ maxHeight: '9rem', overflow: 'auto', borderRadius: '10px', border: '1px solid var(--color-border-paper)', background: 'var(--color-bg-paper)' }}>
                {uploadQueue.map((item) => (
                  <div key={item.id} style={{ padding: '0.6rem 0.75rem', borderBottom: '1px solid var(--color-border-paper)' }}>
                    <div style={{ fontSize: '0.78rem', color: 'var(--color-text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{item.relativePath}</div>
                    <div style={{ marginTop: '0.2rem', fontSize: '0.7rem', color: item.status === 'error' ? '#d9534f' : 'var(--color-text-muted)' }}>{item.source} · {item.status} · {formatFileSize(item.size)}{item.error ? ` · ${item.error}` : ''}</div>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </>
      ) : null}
    </aside>
  );
}
