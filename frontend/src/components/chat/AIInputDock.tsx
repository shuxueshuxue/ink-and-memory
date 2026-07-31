// [Input] Consume file upload hook, file proxy utility, input-dock helpers, chat icons, auth token, and keyboard interaction helpers.
// [Output] Render the chat input dock, attachment upload controls, and message submit/stop actions.
// [Pos] chat-input-dock component node in frontend/src/components/chat
// [Sync] 2026-05-25: remove frontend customer-context props and move helper exports to AIInputDock.helpers.
// [Sync] 2026-05-27: add internal toolChoice state with Auto/逐步确认 segmented toggle; sends selected toolChoice via onSendMessage.
// [Sync] 2026-06-09: hide the manual approval switch when IM full-access mode
//                    is enabled; show static "完全访问" and send auto mode.
// [Sync] 2026-06-09: subscribe to same-tab IM full-access config events so
//                    draft chat input updates immediately after Settings changes.
// [Sync] 2026-06-09: show stop button when loading+onStop; spinner when loading without onStop.
// [Sync] 2026-06-12: use centralized API_BASE for cross-origin system config and workspace file APIs.
// [Sync] 2026-06-25: expose a stopPending state so backend stop requests cannot
//                    be double-submitted from the stop button.
// [Sync] 2026-07-20: i18n — tool-choice toggle, upload errors/hints, aria labels, and
//                    send/stop button copy resolve through the chat.inputDock namespace
//                    (en + zh) via useTranslation.
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type ClipboardEvent,
  type DragEvent,
  type KeyboardEvent,
} from 'react';
import { useTranslation } from 'react-i18next';
import type { TFunction } from 'i18next';
import { useFileUpload } from '../../hooks/useFileUpload';
import { toFileProxyUrl } from '../../lib/toFileProxyUrl';
import type { ToolChoice } from '../../lib/chat-schema';
import { IconArrowUp, IconFile, IconLoader, IconStop, IconX } from './Icons';
import {
  runWithFileDialogTaskLock,
  shouldHandleOpenFileDialogSignal,
  shouldShowUploadHint,
  type UploadedFile,
} from './AIInputDock.helpers';
import { shouldSendMessageOnKeyDown } from './interaction-utils';
import { getAuthToken } from '../../contexts/AuthContext';
import { subscribeImFullAccessChanged } from '../../lib/system-config-events';
import { API_BASE } from '../../lib/apiBase';

type AIInputDockMode = 'simple' | 'full';

interface AIInputDockProps {
  onSendMessage: (
    message: string,
    files?: UploadedFile[],
    toolChoice?: ToolChoice,
  ) => void;
  placeholder?: string;
  disabled?: boolean;
  loading?: boolean;
  defaultToolChoice?: ToolChoice;
  openFileDialogSignal?: number;
  onStop?: () => void | Promise<void>;
  stopPending?: boolean;
  mode?: AIInputDockMode;
  workspaceSessionId?: string;
  fullAccessEnabled?: boolean;
}

const QUERY_INPUT_MAX_HEIGHT = 320;
const QUERY_INPUT_MIN_HEIGHT = 72;
const MAX_UPLOAD_FILE_SIZE_BYTES = 50 * 1024 * 1024;

function generateFileId(): string {
  return `file_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function revokeObjectPreviewUrl(url?: string) {
  if (url?.startsWith('blob:')) {
    URL.revokeObjectURL(url);
  }
}

function shouldSendWithKeyboard(
  mode: AIInputDockMode,
  event: KeyboardEvent<HTMLInputElement | HTMLTextAreaElement>,
): boolean {
  if (event.nativeEvent.isComposing) {
    return false;
  }
  if (mode === 'full') {
    return shouldSendMessageOnKeyDown({
      key: event.key,
      metaKey: event.metaKey || event.ctrlKey,
      shiftKey: event.shiftKey,
      isComposing: event.nativeEvent.isComposing,
    });
  }
  return event.key === 'Enter' && !event.shiftKey;
}

function buildToolChoiceOptions(t: TFunction): { value: ToolChoice; label: string; title: string }[] {
  return [
    { value: 'auto', label: t('chat.inputDock.toolChoiceAuto'), title: t('chat.inputDock.toolChoiceAutoTitle') },
    { value: 'manual', label: t('chat.inputDock.toolChoiceManual'), title: t('chat.inputDock.toolChoiceManualTitle') },
  ];
}

export default function AIInputDock({
  onSendMessage,
  placeholder = 'Ask Ink & Memory…',
  disabled = false,
  loading = false,
  defaultToolChoice = 'auto',
  openFileDialogSignal,
  onStop,
  stopPending = false,
  mode = 'simple',
  workspaceSessionId,
  fullAccessEnabled,
}: AIInputDockProps) {
  const { t } = useTranslation();
  const toolChoiceOptions = useMemo(() => buildToolChoiceOptions(t), [t]);
  const [query, setQuery] = useState('');
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);
  const [isInputFocused, setIsInputFocused] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [toolChoice, setToolChoice] = useState<ToolChoice>(defaultToolChoice);
  const [resolvedFullAccessEnabled, setResolvedFullAccessEnabled] = useState(fullAccessEnabled ?? false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const queryInputRef = useRef<HTMLTextAreaElement>(null);
  const lastHandledOpenFileDialogSignalRef = useRef(0);
  const { upload, error: uploadHookError } = useFileUpload();

  useEffect(() => {
    if (fullAccessEnabled !== undefined) {
      setResolvedFullAccessEnabled(fullAccessEnabled);
      return undefined;
    }

    let active = true;
    const unsubscribe = subscribeImFullAccessChanged((enabled) => {
      setResolvedFullAccessEnabled(enabled);
    });

    void (async () => {
      try {
        const response = await fetch(`${API_BASE}/api/system-config`, {
          headers: { 'Authorization': `Bearer ${getAuthToken()}` },
        });
        if (!response.ok) return;
        const payload = (await response.json()) as { data?: { im_full_access_enabled?: boolean }; im_full_access_enabled?: boolean };
        const config = payload.data ?? payload;
        if (active) {
          setResolvedFullAccessEnabled(config.im_full_access_enabled === true);
        }
      } catch {
        // Keep default non-full-access UI on config fetch failures.
      }
    })();

    return () => {
      active = false;
      unsubscribe();
    };
  }, [fullAccessEnabled]);

  const openAttachmentDialog = useCallback(() => {
    runWithFileDialogTaskLock(() => {
      fileInputRef.current?.click();
    });
  }, []);

  useEffect(() => {
    if (
      !shouldHandleOpenFileDialogSignal(
        openFileDialogSignal,
        lastHandledOpenFileDialogSignalRef.current,
      )
    ) {
      return;
    }
    lastHandledOpenFileDialogSignalRef.current = openFileDialogSignal;
    openAttachmentDialog();
  }, [openAttachmentDialog, openFileDialogSignal]);

  useEffect(
    () => () => {
      uploadedFiles.forEach((file) => revokeObjectPreviewUrl(file.previewUrl));
    },
    [uploadedFiles],
  );

  const syncFileToWorkspace = useCallback(
    async (file: File) => {
      if (!workspaceSessionId) {
        return undefined;
      }

      const formData = new FormData();
      formData.set('sessionId', workspaceSessionId);
      formData.set('path', 'files');
      formData.append('file', file);

      const response = await fetch(`${API_BASE}/api/workspace/files`, {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${getAuthToken()}` },
        body: formData,
      });

      const responseBody = (await response.json().catch(() => ({}))) as {
        error?: string;
        code?: string;
        uploaded?: string[];
        files?: Array<{ workspacePath: string; savedAt: string; hash?: string }>;
      };

      if (!response.ok) {
        const message = responseBody.error || t('chat.inputDock.workspaceSyncFailed');
        throw new Error(responseBody.code ? `${message} (${responseBody.code})` : message);
      }

      const metadata = responseBody.files?.[0];
      if (metadata?.workspacePath) {
        return metadata;
      }

      const fallbackPath = responseBody.uploaded?.[0];
      if (!fallbackPath) {
        return undefined;
      }

      return { workspacePath: fallbackPath, savedAt: new Date().toISOString() };
    },
    [workspaceSessionId, t],
  );

  const uploadFileToStorage = useCallback(
    async (fileId: string, file: File) => {
      try {
        const workspaceMetadata = await syncFileToWorkspace(file);
        const result = await upload(file, {
          filename: file.name,
          contentType: file.type || 'application/octet-stream',
          onProgress: (progress) => {
            setUploadedFiles((prev) =>
              prev.map((entry) => (entry.id === fileId ? { ...entry, progress } : entry)),
            );
          },
        });

        if (!result) {
          setUploadedFiles((prev) => prev.filter((entry) => entry.id !== fileId));
          return;
        }

        setUploadedFiles((prev) =>
          prev.map((entry) =>
            entry.id === fileId
              ? {
                  ...entry,
                  url: result.url,
                  storageKey: result.key,
                  progress: 100,
                  isUploading: false,
                  workspacePath: workspaceMetadata?.workspacePath,
                  savedAt: workspaceMetadata?.savedAt,
                  hash: workspaceMetadata?.hash,
                }
              : entry,
          ),
        );
      } catch (error) {
        setUploadedFiles((prev) => {
          const current = prev.find((entry) => entry.id === fileId);
          revokeObjectPreviewUrl(current?.previewUrl);
          return prev.filter((entry) => entry.id !== fileId);
        });
        setUploadError(error instanceof Error ? error.message : t('chat.inputDock.uploadFailed'));
      }
    },
    [syncFileToWorkspace, upload, t],
  );

  const handleFiles = useCallback(
    (files: FileList | null, uploadSource: 'click' | 'paste' | 'drag') => {
      if (!files?.length) {
        return;
      }

      const nextFiles: UploadedFile[] = [];
      const filesToUpload: Array<{ id: string; file: File }> = [];

      Array.from(files).forEach((file) => {
        if (file.size > MAX_UPLOAD_FILE_SIZE_BYTES) {
          setUploadError(t('chat.inputDock.fileTooLarge', { name: file.name, max: formatFileSize(MAX_UPLOAD_FILE_SIZE_BYTES) }));
          return;
        }

        const id = generateFileId();
        const previewUrl = file.type.startsWith('image/') ? URL.createObjectURL(file) : undefined;
        nextFiles.push({
          id,
          name: file.name,
          mimeType: file.type || 'application/octet-stream',
          size: file.size,
          previewUrl,
          progress: 0,
          isUploading: true,
          file,
          uploadSource,
        });
        filesToUpload.push({ id, file });
      });

      if (!nextFiles.length) {
        return;
      }

      setUploadError(null);
      setUploadedFiles((prev) => [...prev, ...nextFiles]);
      filesToUpload.forEach(({ id, file }) => {
        void uploadFileToStorage(id, file);
      });
    },
    [uploadFileToStorage, t],
  );

  const deleteFile = useCallback((fileId: string) => {
    setUploadedFiles((prev) => {
      const target = prev.find((entry) => entry.id === fileId);
      revokeObjectPreviewUrl(target?.previewUrl);
      return prev.filter((entry) => entry.id !== fileId);
    });
  }, []);

  const handleFileInputChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => {
      handleFiles(event.target.files, 'click');
      event.target.value = '';
    },
    [handleFiles],
  );

  const handleDragOver = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (event: DragEvent<HTMLDivElement>) => {
      event.preventDefault();
      setIsDragOver(false);
      handleFiles(event.dataTransfer.files, 'drag');
    },
    [handleFiles],
  );

  const handlePaste = useCallback(
    (event: ClipboardEvent<HTMLDivElement>) => {
      const clipboardFiles = event.clipboardData?.files;
      if (!clipboardFiles?.length) {
        return;
      }
      event.preventDefault();
      handleFiles(clipboardFiles, 'paste');
    },
    [handleFiles],
  );

  const updateQueryInputHeight = useCallback(() => {
    const input = queryInputRef.current;
    if (!input) {
      return;
    }
    input.style.height = 'auto';
    const nextHeight = Math.min(
      Math.max(input.scrollHeight, QUERY_INPUT_MIN_HEIGHT),
      QUERY_INPUT_MAX_HEIGHT,
    );
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > QUERY_INPUT_MAX_HEIGHT ? 'auto' : 'hidden';
  }, []);

  useEffect(() => {
    updateQueryInputHeight();
  }, [query, updateQueryInputHeight]);

  const handleSend = useCallback(() => {
    if (loading) {
      return;
    }
    if (uploadedFiles.some((file) => file.isUploading)) {
      setUploadError(t('chat.inputDock.waitForUpload'));
      return;
    }

    const trimmedQuery = query.trim();
    if (!trimmedQuery && uploadedFiles.length === 0) {
      return;
    }

    onSendMessage(
      trimmedQuery,
      uploadedFiles.length > 0 ? uploadedFiles : undefined,
      resolvedFullAccessEnabled ? 'auto' : toolChoice,
    );
    setQuery('');
    uploadedFiles.forEach((file) => revokeObjectPreviewUrl(file.previewUrl));
    setUploadedFiles([]);
  }, [
    resolvedFullAccessEnabled,
    toolChoice,
    loading,
    onSendMessage,
    query,
    uploadedFiles,
    t,
  ]);

  const hasUploadingFiles = uploadedFiles.some((file) => file.isUploading);
  const showUploadHint = shouldShowUploadHint(query, isInputFocused);
  const canSend = useMemo(
    () => !loading && !disabled && !hasUploadingFiles && (query.trim().length > 0 || uploadedFiles.length > 0),
    [disabled, hasUploadingFiles, loading, query, uploadedFiles.length],
  );

  return (
    <div
      data-mode={mode}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onPaste={handlePaste}
      style={{
        width: '100%',
        minWidth: 0,
        padding: '0.85rem 1rem',
        borderRadius: '1.25rem',
        border: `1px solid ${isDragOver ? 'var(--color-action-link)' : 'var(--color-border-paper)'}`,
        background: isDragOver ? 'color-mix(in srgb, var(--color-action-link) 6%, var(--color-bg-paper))' : 'var(--color-bg-paper)',
        boxShadow: '0 2px 8px var(--color-shadow-soft)',
        boxSizing: 'border-box',
        transition: 'border-color 0.18s ease, background 0.18s ease',
      }}
    >
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.txt,.md,.csv,.json,.doc,.docx,.xls,.xlsx,.ppt,.pptx,.zip,.rar,.7z,.tar,.gz,.mp3,.wav,.m4a,.ogg,.mp4,.webm,.mov,image/*"
        onChange={handleFileInputChange}
        disabled={disabled}
        style={{ display: 'none' }}
      />

      {(uploadError || uploadHookError) ? (
        <div
          style={{
            marginBottom: '0.75rem',
            borderRadius: '0.65rem',
            padding: '0.6rem 0.8rem',
            background: 'color-mix(in srgb, var(--color-state-error) 8%, transparent)',
            color: 'var(--color-state-error)',
            fontSize: '0.82rem',
            border: '1px solid color-mix(in srgb, var(--color-state-error) 20%, transparent)',
          }}
        >
          {uploadError || uploadHookError}
        </div>
      ) : null}

      {uploadedFiles.length > 0 ? (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
          {uploadedFiles.map((file) => {
            const isImage = file.mimeType.startsWith('image/');
            const previewUrl = file.storageKey ? toFileProxyUrl(file.storageKey) : file.previewUrl;
            const displayExt = file.name.split('.').pop()?.toUpperCase() || 'FILE';
            return (
              <div
                key={file.id}
                style={{
                  position: 'relative',
                  overflow: 'hidden',
                  borderRadius: '0.65rem',
                  border: '1px solid var(--color-border-paper)',
                  background: 'var(--color-bg-app)',
                }}
              >
                {isImage && previewUrl ? (
                  <img src={previewUrl} alt={file.name} style={{ display: 'block', width: '5rem', height: '5rem', objectFit: 'cover' }} />
                ) : (
                  <div style={{ width: '7rem', height: '5rem', padding: '0.5rem', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', background: 'var(--color-bg-app)' }}>
                    <IconFile style={{ width: '1.4rem', height: '1.4rem', color: 'var(--color-text-muted)', marginBottom: '0.2rem' }} />
                    <span style={{ width: '100%', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontSize: '0.68rem', color: 'var(--color-text-secondary)' }}>{file.name}</span>
                    <span style={{ fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>{displayExt} · {formatFileSize(file.size)}</span>
                  </div>
                )}
                {file.isUploading ? (
                  <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', background: 'color-mix(in srgb, var(--color-bg-paper) 90%, transparent)' }}>
                    <IconLoader style={{ width: '1rem', height: '1rem', color: 'var(--color-action-link)', marginBottom: '0.25rem' }} className="spin" />
                    <div style={{ width: '3rem', height: '0.25rem', borderRadius: '999px', overflow: 'hidden', background: 'var(--color-border-paper)' }}>
                      <div style={{ width: `${file.progress || 0}%`, height: '100%', background: 'var(--color-action-link)', transition: 'width 0.2s ease' }} />
                    </div>
                    <span style={{ marginTop: '0.2rem', fontSize: '0.6rem', color: 'var(--color-text-muted)' }}>{Math.round(file.progress || 0)}%</span>
                  </div>
                ) : null}
                <button
                  type="button"
                  onClick={() => deleteFile(file.id)}
                  disabled={file.isUploading}
                  aria-label={t('chat.inputDock.deleteFileAria', { name: file.name })}
                  style={{
                    position: 'absolute',
                    top: '0.35rem',
                    right: '0.35rem',
                    width: '1.5rem',
                    height: '1.5rem',
                    border: '1px solid var(--color-border-paper)',
                    borderRadius: '999px',
                    background: 'var(--color-bg-surface-solid)',
                    color: 'var(--color-state-danger)',
                    cursor: file.isUploading ? 'not-allowed' : 'pointer',
                    display: 'grid',
                    placeItems: 'center',
                  }}
                >
                  <IconX style={{ width: '0.85rem', height: '0.85rem' }} />
                </button>
              </div>
            );
          })}
        </div>
      ) : null}

      {(showUploadHint || mode === 'full') ? (
        <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '0.4rem', fontSize: '0.73rem', color: 'var(--color-text-muted)' }}>
          {showUploadHint ? <span id="chat-upload-hint">{t('chat.inputDock.uploadHint')}</span> : null}
          {mode === 'full' ? <span style={{ marginLeft: 'auto', letterSpacing: '0.01em' }}>{t('chat.inputDock.sendShortcut')}</span> : null}
        </div>
      ) : null}

      <textarea
        id="chat-input"
        ref={queryInputRef}
        aria-label={t('chat.inputDock.inputAria')}
        aria-describedby={showUploadHint ? 'chat-upload-hint' : undefined}
        placeholder={placeholder}
        value={query}
        rows={1}
        onChange={(event) => setQuery(event.target.value)}
        onFocus={() => setIsInputFocused(true)}
        onBlur={() => setIsInputFocused(false)}
        disabled={disabled}
        onKeyDown={(event) => {
          if (!shouldSendWithKeyboard(mode, event)) {
            return;
          }
          event.preventDefault();
          handleSend();
        }}
        style={{
          width: '100%',
          minHeight: '4.5rem',
          resize: 'none',
          border: 'none',
          outline: 'none',
          background: 'transparent',
          color: 'var(--color-text-body)',
          fontSize: '1rem',
          lineHeight: 1.65,
          fontFamily: "'Excalifont', 'Xiaolai', Georgia, serif",
          boxSizing: 'border-box',
        }}
      />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem', marginTop: '0.65rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.45rem' }}>
          <button
            type="button"
            aria-label={t('chat.inputDock.addAttachmentAria')}
            onClick={openAttachmentDialog}
            disabled={disabled}
            style={{
              border: '1px solid var(--color-border-paper)',
              borderRadius: '999px',
              padding: '0.42rem 0.85rem',
              background: 'var(--color-bg-app)',
              color: 'var(--color-text-secondary)',
              cursor: disabled ? 'not-allowed' : 'pointer',
              fontSize: '0.8rem',
              transition: 'background 0.15s ease, color 0.15s ease',
            }}
          >
            {t('chat.inputDock.addAttachment')}
          </button>

          {resolvedFullAccessEnabled ? (
            <div
              aria-label={t('chat.inputDock.toolAccessAria')}
              title={t('chat.inputDock.fullAccess')}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                minHeight: '1.75rem',
                borderRadius: '999px',
                border: '1px solid var(--color-border-paper)',
                padding: '0 0.75rem',
                fontSize: '0.76rem',
                fontWeight: 600,
                background: 'var(--color-text-primary)',
                color: 'var(--color-bg-paper)',
                whiteSpace: 'nowrap',
              }}
            >
              {t('chat.inputDock.fullAccess')}
            </div>
          ) : (
            <div
              role="group"
              aria-label={t('chat.inputDock.toolModeAria')}
              style={{
                display: 'flex',
                borderRadius: '999px',
                border: '1px solid var(--color-border-paper)',
                overflow: 'hidden',
                fontSize: '0.76rem',
                background: 'var(--color-bg-app)',
              }}
            >
              {toolChoiceOptions.map((option) => {
                const isActive = toolChoice === option.value;
                return (
                  <button
                    key={option.value}
                    type="button"
                    title={option.title}
                    disabled={disabled || loading}
                    onClick={() => setToolChoice(option.value)}
                    style={{
                      border: 'none',
                      padding: '0.35rem 0.7rem',
                      background: isActive ? 'var(--color-text-primary)' : 'transparent',
                      color: isActive ? 'var(--color-bg-paper)' : 'var(--color-text-muted)',
                      cursor: disabled || loading ? 'not-allowed' : 'pointer',
                      fontWeight: isActive ? 600 : 400,
                      transition: 'background 0.15s ease, color 0.15s ease',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {option.label}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {loading && onStop ? (
          <button
            type="button"
            onClick={() => { void onStop(); }}
            disabled={stopPending}
            title={stopPending ? t('chat.inputDock.stopping') : t('chat.inputDock.stopGenerating')}
            aria-label={stopPending ? t('chat.inputDock.stopping') : t('chat.inputDock.stopGenerating')}
            style={{
              display: 'grid',
              placeItems: 'center',
              width: '2.25rem',
              height: '2.25rem',
              borderRadius: '999px',
              border: 'none',
              background: stopPending ? 'var(--color-disabled-bg)' : 'var(--color-state-danger)',
              color: stopPending ? 'var(--color-text-muted)' : 'var(--color-text-on-action)',
              cursor: stopPending ? 'not-allowed' : 'pointer',
            }}
          >
            {stopPending ? (
              <IconLoader style={{ width: '0.95rem', height: '0.95rem' }} className="spin" />
            ) : (
              <IconStop style={{ width: '0.9rem', height: '0.9rem' }} />
            )}
          </button>
        ) : loading ? (
          <button
            type="button"
            disabled
            title={t('chat.inputDock.generating')}
            aria-label={t('chat.inputDock.generating')}
            style={{
              display: 'grid',
              placeItems: 'center',
              width: '2.25rem',
              height: '2.25rem',
              borderRadius: '999px',
              border: 'none',
              background: 'var(--color-disabled-bg)',
              color: 'var(--color-text-muted)',
              cursor: 'not-allowed',
            }}
          >
            <IconLoader style={{ width: '0.95rem', height: '0.95rem' }} className="spin" />
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSend}
            disabled={!canSend}
            title={hasUploadingFiles ? t('chat.inputDock.waitingUpload') : t('chat.inputDock.send')}
            aria-label={t('chat.inputDock.sendAria')}
            style={{
              display: 'grid',
              placeItems: 'center',
              width: '2.25rem',
              height: '2.25rem',
              borderRadius: '999px',
              border: 'none',
              background: canSend ? 'var(--color-text-primary)' : 'var(--color-disabled-bg)',
              color: canSend ? 'var(--color-bg-paper)' : 'var(--color-text-muted)',
              cursor: canSend ? 'pointer' : 'not-allowed',
              transition: 'background 0.18s ease',
            }}
          >
            {hasUploadingFiles ? (
              <IconLoader style={{ width: '0.95rem', height: '0.95rem' }} className="spin" />
            ) : (
              <IconArrowUp style={{ width: '0.95rem', height: '0.95rem' }} />
            )}
          </button>
        )}
      </div>
    </div>
  );
}
