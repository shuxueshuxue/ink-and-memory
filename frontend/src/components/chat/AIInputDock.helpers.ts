// [Input] Consume file proxy URL utility and AIInputDock upload file metadata.
// [Output] Provide chat input attachment conversion, upload hint, and file-dialog guard helpers.
// [Pos] chat-input-dock helper node in frontend/src/components/chat
// [Sync] 2026-05-25: split input-dock helper exports out of the component file while removing customer-context plumbing.
import { toFileProxyUrl } from '../../lib/toFileProxyUrl';

export interface UploadedFile {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  previewUrl?: string;
  url?: string;
  storageKey?: string;
  dataUrl?: string;
  progress?: number;
  isUploading?: boolean;
  abortController?: AbortController;
  file?: File;
  workspacePath?: string;
  savedAt?: string;
  hash?: string;
  uploadSource?: 'click' | 'paste' | 'drag';
}

export interface Attachment {
  name: string;
  type: string;
  size: number;
  url?: string;
  storageKey?: string;
  workspacePath?: string;
  savedAt?: string;
  hash?: string;
  uploadSource?: 'click' | 'paste' | 'drag';
}

let fileDialogOpenLocked = false;

export function toAttachment(file: UploadedFile): Attachment {
  return {
    name: file.name,
    type: file.mimeType,
    size: file.size,
    url: file.storageKey ? toFileProxyUrl(file.storageKey) : file.url,
    storageKey: file.storageKey,
    workspacePath: file.workspacePath,
    savedAt: file.savedAt,
    hash: file.hash,
    uploadSource: file.uploadSource,
  };
}

export function shouldHandleOpenFileDialogSignal(
  signal: number | undefined,
  lastHandledSignal: number,
): signal is number {
  return typeof signal === 'number' && signal > 0 && signal !== lastHandledSignal;
}

export function runWithFileDialogTaskLock(callback: () => void): boolean {
  if (fileDialogOpenLocked) {
    return false;
  }
  fileDialogOpenLocked = true;
  callback();
  queueMicrotask(() => {
    fileDialogOpenLocked = false;
  });
  return true;
}

export function shouldShowUploadHint(query: string, isInputFocused: boolean): boolean {
  return query.length === 0 && !isInputFocused;
}
