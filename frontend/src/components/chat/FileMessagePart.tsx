import { memo } from 'react';
import type { FileUIPart } from 'ai';
import { toFileProxyUrl, withStorageAuthToken } from '../../lib/toFileProxyUrl';
import { IconDownload, IconFile } from './Icons';

interface FileMessagePartProps {
  part: FileUIPart;
  isUserMessage: boolean;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function resolveFileUrl(url?: string) {
  if (!url) return undefined;
  if (url.startsWith('/') || url.startsWith('http')) {
    // Persisted proxy URLs carry no credentials; attach the current auth token
    // so <img src> / download links pass backend storage auth.
    return withStorageAuthToken(url);
  }
  if (url.startsWith('blob:') || url.startsWith('data:')) {
    return url;
  }
  return toFileProxyUrl(url);
}

export const FileMessagePart = memo(function FileMessagePart({ part, isUserMessage }: FileMessagePartProps) {
  const isImage = part.mediaType?.startsWith('image/');
  const fileExtension = part.filename?.split('.').pop()?.toUpperCase() || part.mediaType?.split('/').pop()?.toUpperCase() || 'FILE';
  const fileUrl = resolveFileUrl(part.url);
  const filename = part.filename || part.url?.split('/').pop() || 'Attachment';
  const fileSize = (part as FileUIPart & { size?: number }).size;
  const secondaryLabel = part.mediaType && part.mediaType !== 'application/octet-stream' ? part.mediaType : undefined;

  if (isImage && fileUrl) {
    return (
      <div style={{ maxWidth: '28rem', overflow: 'hidden', borderRadius: '14px', border: '1px solid var(--color-border-paper)', marginLeft: isUserMessage ? 'auto' : undefined, marginRight: isUserMessage ? undefined : 'auto', background: 'var(--color-bg-paper)' }}>
        <img src={fileUrl} alt={part.filename || 'Uploaded image'} loading="lazy" style={{ display: 'block', width: '100%', height: 'auto' }} />
        {part.filename ? <div style={{ padding: '0.625rem 0.875rem', fontSize: '0.875rem', color: 'var(--color-text-secondary)' }}>{part.filename}</div> : null}
      </div>
    );
  }

  return (
    <div style={{ maxWidth: '28rem', borderRadius: '18px', border: `1px solid ${isUserMessage ? 'rgba(255,255,255,0.25)' : 'var(--color-border-paper)'}`, padding: '1rem', boxShadow: '0 1px 4px rgba(0,0,0,0.06)', background: isUserMessage ? 'var(--color-action-link)' : 'var(--color-bg-paper)', color: isUserMessage ? '#fff' : 'var(--color-text-primary)', marginLeft: isUserMessage ? 'auto' : undefined, marginRight: isUserMessage ? undefined : 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '1rem' }}>
        <div style={{ flexShrink: 0, borderRadius: '14px', padding: '0.75rem', background: isUserMessage ? 'rgba(255,255,255,0.14)' : 'var(--color-bg-surface)' }}>
          <IconFile style={{ width: '1.5rem', height: '1.5rem', color: isUserMessage ? 'rgba(255,255,255,0.86)' : 'var(--color-text-muted)' }} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <p title={filename} style={{ margin: 0, fontSize: '0.92rem', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{filename}</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '0.5rem', marginTop: '0.4rem', fontSize: '0.75rem', color: isUserMessage ? 'rgba(255,255,255,0.8)' : 'var(--color-text-muted)' }}>
            <span style={{ padding: '0.15rem 0.45rem', borderRadius: '999px', border: `1px solid ${isUserMessage ? 'rgba(255,255,255,0.28)' : 'var(--color-border-paper)'}`, textTransform: 'uppercase', letterSpacing: '0.06em' }}>{fileExtension}</span>
            {fileSize ? <span>{formatFileSize(fileSize)}</span> : null}
            {secondaryLabel ? <span title={secondaryLabel} style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{secondaryLabel}</span> : null}
          </div>
        </div>
        {fileUrl ? (
          <a href={fileUrl} download={part.filename ?? filename} title={`Download ${filename}`} style={{ flexShrink: 0, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: '2rem', height: '2rem', borderRadius: '999px', color: isUserMessage ? 'rgba(255,255,255,0.84)' : 'var(--color-text-secondary)', textDecoration: 'none' }}>
            <IconDownload style={{ width: '1.25rem', height: '1.25rem' }} />
          </a>
        ) : null}
      </div>
    </div>
  );
});

export default FileMessagePart;
