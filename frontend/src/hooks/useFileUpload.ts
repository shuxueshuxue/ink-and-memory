// [Input] Runtime API base config, AuthContext token, storage upload endpoints, and file proxy utility.
// [Output] File upload hook that supports server/direct upload and cross-origin backend URLs.
// [Pos] file-upload hook node in frontend/src/hooks
// [Sync] 2026-06-12: use centralized API_BASE for cross-origin deployments.
// [Sync] 2026-07-20: i18n — upload error messages resolve through the chat.upload namespace
//        (en + zh) via the shared i18n instance (module-level helpers cannot call hooks).
import { useCallback, useEffect, useState } from 'react';
import { toFileProxyUrl } from '../lib/toFileProxyUrl';
import { getAuthToken } from '../contexts/AuthContext';
import { API_BASE } from '../lib/apiBase';
import i18n from '../i18n';

interface StorageInfo {
  type: 's3' | 'vercel-blob' | 'unknown';
  supportsDirectUpload: boolean;
  isConfigured: boolean;
  error?: string;
}

interface UploadOptions {
  filename?: string;
  contentType?: string;
  onProgress?: (progress: number) => void;
}

interface UploadResult {
  key: string;
  url: string;
  contentType?: string;
  size?: number;
}

function getFallbackStorageInfo(): StorageInfo {
  return {
    type: 'unknown',
    supportsDirectUpload: false,
    isConfigured: true,
  };
}

async function uploadWithXHR(
  url: string,
  body: Document | XMLHttpRequestBodyInit | null,
  onProgress?: (progress: number) => void,
): Promise<UploadResult | undefined> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.upload.onprogress = (event) => {
      if (!onProgress || !event.lengthComputable) {
        return;
      }
      onProgress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status < 200 || xhr.status >= 300) {
        try {
          const errorBody = JSON.parse(xhr.responseText) as { error?: string };
          reject(new Error(errorBody.error || i18n.t('chat.upload.serverFailed')));
        } catch {
          reject(new Error(i18n.t('chat.upload.serverFailed')));
        }
        return;
      }

      try {
        const result = JSON.parse(xhr.responseText) as {
          key?: string;
          url?: string;
          metadata?: { contentType?: string; size?: number };
        };
        if (!result.key) {
          reject(new Error(i18n.t('chat.upload.noFileKey')));
          return;
        }
        resolve({
          key: result.key,
          url: result.url || toFileProxyUrl(result.key),
          contentType: result.metadata?.contentType,
          size: result.metadata?.size,
        });
      } catch {
        reject(new Error(i18n.t('chat.upload.parseFailed')));
      }
    };
    xhr.onerror = () => reject(new Error(i18n.t('chat.upload.failed')));
    const token = getAuthToken();
    if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
    xhr.send(body);
  });
}

async function serverUpload(
  file: File,
  filename: string,
  onProgress?: (progress: number) => void,
): Promise<UploadResult | undefined> {
  const formData = new FormData();
  formData.append('file', file, filename);

  if (onProgress) {
    return uploadWithXHR(`${API_BASE}/api/storage/upload`, formData, onProgress);
  }

  const response = await fetch(`${API_BASE}/api/storage/upload`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${getAuthToken()}` },
    body: formData,
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => ({}))) as { error?: string };
    throw new Error(errorBody.error || i18n.t('chat.upload.serverFailed'));
  }

  const result = (await response.json()) as {
    key?: string;
    url?: string;
    metadata?: { contentType?: string; size?: number };
  };

  if (!result.key) {
    throw new Error(i18n.t('chat.upload.noFileKey'));
  }

  return {
    key: result.key,
    url: result.url || toFileProxyUrl(result.key),
    contentType: result.metadata?.contentType,
    size: result.metadata?.size,
  };
}

export function useFileUpload() {
  const [storageInfo, setStorageInfo] = useState<StorageInfo | null>(null);
  const [isLoadingStorageInfo, setIsLoadingStorageInfo] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function fetchStorageInfo() {
      try {
        const response = await fetch(`${API_BASE}/api/storage`, {
          headers: { 'Authorization': `Bearer ${getAuthToken()}` },
        });
        if (!response.ok) {
          throw new Error('Failed to load storage info');
        }
        const data = (await response.json()) as StorageInfo;
        if (active) {
          setStorageInfo({ ...getFallbackStorageInfo(), ...data });
        }
      } catch {
        if (active) {
          setStorageInfo(getFallbackStorageInfo());
        }
      } finally {
        if (active) {
          setIsLoadingStorageInfo(false);
        }
      }
    }

    void fetchStorageInfo();
    return () => {
      active = false;
    };
  }, []);

  const upload = useCallback(
    async (file: File, options: UploadOptions = {}) => {
      if (!(file instanceof File)) {
        setError(i18n.t('chat.upload.fileRequired'));
        return undefined;
      }

      const info = storageInfo ?? getFallbackStorageInfo();
      const filename = options.filename ?? file.name;
      const contentType = options.contentType || file.type || 'application/octet-stream';

      if (isLoadingStorageInfo) {
        setError(i18n.t('chat.upload.storageLoading'));
        return undefined;
      }

      if (!info.isConfigured) {
        setError(info.error || i18n.t('chat.upload.storageNotConfigured'));
        return undefined;
      }

      setError(null);
      setIsUploading(true);

      try {
        if (info.supportsDirectUpload) {
          const uploadUrlResponse = await fetch(`${API_BASE}/api/storage/upload-url`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${getAuthToken()}` },
            body: JSON.stringify({ filename, contentType }),
          });

          if (uploadUrlResponse.ok) {
            const uploadUrlData = (await uploadUrlResponse.json()) as {
              directUploadSupported?: boolean;
              key?: string;
              url?: string;
              method?: string;
              headers?: Record<string, string>;
            };

            if (
              uploadUrlData.directUploadSupported &&
              uploadUrlData.key &&
              uploadUrlData.url
            ) {
              options.onProgress?.(25);
              const directResponse = await fetch(uploadUrlData.url, {
                method: uploadUrlData.method || 'PUT',
                headers: uploadUrlData.headers || { 'Content-Type': contentType },
                body: file,
              });
              if (!directResponse.ok) {
                throw new Error('Direct upload failed');
              }
              options.onProgress?.(100);
              return {
                key: uploadUrlData.key,
                url: toFileProxyUrl(uploadUrlData.key),
                contentType,
                size: file.size,
              };
            }
          }
        }

        return await serverUpload(file, filename, options.onProgress);
      } catch (uploadError) {
        const message = uploadError instanceof Error ? uploadError.message : i18n.t('chat.upload.failed');
        setError(message);
        return undefined;
      } finally {
        setIsUploading(false);
      }
    },
    [isLoadingStorageInfo, storageInfo],
  );

  return {
    upload,
    isUploading: isUploading || isLoadingStorageInfo,
    error,
    storageInfo,
    clearError: () => setError(null),
  };
}
