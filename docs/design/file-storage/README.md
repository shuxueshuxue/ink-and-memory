# File Storage — Design Document

**Path**: `backend/libs/file_storage/` · `backend/server.py` (`/api/storage/*`)
**Last updated**: 2026-06-15
**Sync**: Client examples use root deployment API paths (`/api/...`).

---

## 📋 Overview

The File Storage subsystem provides a unified file-upload and retrieval service
for the Ink & Memory backend.  It is a direct Python port of the storage design
from
[`claude-agent-next-kit`](https://github.com/glide-the/claude-agent-next-kit/blob/feat/claude-agent-kit/docs/design/storage-api.md)
with Vercel Blob replaced by a **local filesystem** backend suitable for
self-hosted deployments.

Supported storage backends:

| Driver  | Description                                           |
|---------|-------------------------------------------------------|
| `s3`    | AWS S3 or any S3-compatible store (MinIO, DO Spaces…) |
| `local` | Local filesystem (default — suitable for development) |

---

## 🗂️ Module Layout

```
backend/
└── libs/
    └── file_storage/
        ├── __init__.py          # Public API, singleton factory
        ├── interface.py         # Abstract FileStorage + data classes
        ├── storage_utils.py     # sanitize_filename, MIME helpers, key encoding
        ├── storage_key.py       # Validated key codec (base64-segment, path-encode)
        ├── s3_file_storage.py   # S3FileStorage (boto3)
        └── local_file_storage.py# LocalFileStorage (disk)
```

---

## 🔧 Environment Variables

### Common

| Variable              | Default    | Description                                |
|-----------------------|------------|--------------------------------------------|
| `FILE_STORAGE_TYPE`   | `local`    | Backend driver: `s3` or `local`            |
| `FILE_STORAGE_PREFIX` | `uploads`  | Key prefix prepended to every stored file  |

### S3 backend (`FILE_STORAGE_TYPE=s3`)

| Variable                         | Required | Description                                              |
|----------------------------------|----------|----------------------------------------------------------|
| `FILE_STORAGE_S3_BUCKET`         | ✅       | S3 bucket name                                           |
| `FILE_STORAGE_S3_REGION`         | ✅       | AWS region (or use `AWS_REGION` as fallback)             |
| `FILE_STORAGE_S3_ENDPOINT`       | —        | Custom endpoint URL for S3-compatible stores             |
| `FILE_STORAGE_S3_FORCE_PATH_STYLE` | —      | Set `true` for MinIO / path-style URL                    |
| `FILE_STORAGE_S3_PUBLIC_BASE_URL`| —        | Override base URL (CDN in front of the bucket)           |

### Local backend (`FILE_STORAGE_TYPE=local`)

| Variable                  | Default                           | Description                      |
|---------------------------|-----------------------------------|----------------------------------|
| `FILE_STORAGE_LOCAL_DIR`  | `backend/data/file-storage`       | Absolute path to storage directory |

---

## 🐳 Docker Local Development (MinIO)

The project's `docker-compose.yml` (if present) can include MinIO for local S3
testing.  Example `.env` snippet:

```env
FILE_STORAGE_TYPE=s3
FILE_STORAGE_S3_BUCKET=ink-and-memory
FILE_STORAGE_S3_REGION=us-east-1
FILE_STORAGE_S3_ENDPOINT=http://localhost:9000
FILE_STORAGE_S3_FORCE_PATH_STYLE=true
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
FILE_STORAGE_PREFIX=uploads
```

---

## 📡 API Endpoints

### 1. Get storage configuration

```
GET /api/storage
Authorization: ******
```

Returns current storage state so the client can decide the upload strategy.

**Response (configured):**
```json
{
  "type": "s3",
  "supportsDirectUpload": true,
  "isConfigured": true
}
```

**Response (misconfigured):**
```json
{
  "type": "s3",
  "supportsDirectUpload": true,
  "isConfigured": false,
  "error": "Missing S3 configuration: FILE_STORAGE_S3_BUCKET",
  "solution": "Add required env vars for S3 file storage: ..."
}
```

---

### 2. Server-side file upload

```
POST /api/storage/upload
Authorization: ******
Content-Type: multipart/form-data
```

Upload a file directly through the server.

**Form field:** `file` — the binary file to upload.

**Supported MIME types:**

- Images: JPEG, PNG, GIF, WebP, SVG
- Documents: PDF, Word (.doc/.docx), Excel (.xls/.xlsx)
- Text: TXT, CSV, Markdown, JSON
- Archives: ZIP, TAR, GZIP
- Audio/Video: MP3, WAV, MP4, WebM

**Response (success):**
```json
{
  "success": true,
  "key": "uploads/abc123-photo.jpg",
  "url": "/api/storage/file/<base64-key>",
  "metadata": {
    "key": "uploads/abc123-photo.jpg",
    "filename": "abc123-photo.jpg",
    "contentType": "image/jpeg",
    "size": 204800,
    "uploadedAt": "2026-05-25T12:00:00.000Z"
  }
}
```

---

### 3. Pre-signed upload URL

```
POST /api/storage/upload-url
Authorization: ******
Content-Type: application/json
```

Get a pre-signed URL for direct client-to-S3 upload (bypasses server for large
files).  Falls back to `/api/storage/upload` when the backend does not support
pre-signed URLs (e.g. `local` driver).

**Request body:**
```json
{
  "filename": "document.pdf",
  "contentType": "application/pdf"
}
```

**Response (S3 — direct upload supported):**
```json
{
  "directUploadSupported": true,
  "key": "uploads/abc123-document.pdf",
  "url": "https://bucket.s3.us-east-1.amazonaws.com/uploads/abc123-document.pdf?X-Amz-...",
  "method": "PUT",
  "expiresAt": "2026-05-25T13:00:00.000Z",
  "headers": {
    "Content-Type": "application/pdf"
  }
}
```

**Response (local — fallback):**
```json
{
  "directUploadSupported": false,
  "fallbackUrl": "/api/storage/upload",
  "message": "Use multipart/form-data upload to fallbackUrl"
}
```

---

### 4. File proxy / download

```
GET /api/storage/file/{base64-encoded-key}
```

Streams the file content from storage.  The `base64-encoded-key` is a standard
Base64 encoding of the storage key string (produced by `encode_key_to_base64`
in `storage_utils.py`).

Authentication accepts any of (first match wins):

1. `Authorization: Bearer <token>` header
2. `access_token` / `token` login cookie
3. `?token=<access-token>` query parameter — required for browser-embedded
   URLs (`<img src>`, `<a href download>`) that cannot send headers

The frontend helper `toFileProxyUrl(key)` in
`frontend/src/lib/toFileProxyUrl.ts` builds this URL automatically and appends
the current auth token as `?token=`. `withStorageAuthToken(url)` re-attaches
the token to persisted proxy URLs stored in message parts.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React)                                       │
│  useFileUpload hook  →  /api/storage (check config)     │
│                      →  /api/storage/upload-url         │
│                      →  Direct PUT to S3 (presigned)    │
│                         OR POST /api/storage/upload     │
└────────────────────────────┬────────────────────────────┘
                             │  HTTP
┌────────────────────────────▼────────────────────────────┐
│  FastAPI (server.py)                                    │
│                                                         │
│  GET  /api/storage           check config               │
│  POST /api/storage/upload    server upload              │
│  POST /api/storage/upload-url presigned URL             │
│  GET  /api/storage/file/{k}  file proxy                 │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│  libs/file_storage  (Python module)                     │
│                                                         │
│  FileStorage (ABC)                                      │
│   ├── S3FileStorage        (boto3 → AWS S3 / MinIO)     │
│   └── LocalFileStorage     (disk → /data/file-storage/) │
└─────────────────────────────────────────────────────────┘
```

---

## 📐 Class / Interface Summary

### `FileStorage` (abstract)

| Method                          | Description                                       |
|---------------------------------|---------------------------------------------------|
| `upload(content, options)`      | Upload bytes; return `UploadResult`               |
| `create_upload_url(options)`    | Return `UploadUrl` or `None` (not supported)      |
| `download(key)`                 | Return raw bytes                                  |
| `delete(key)`                   | Delete by key                                     |
| `exists(key)`                   | Check existence                                   |
| `get_metadata(key)`             | Return `FileMetadata` or `None`                   |
| `get_source_url(key)`           | Return public URL or `None`                       |
| `get_download_url(key)`         | Return forced-download URL or `None`              |

### Data classes

| Class          | Fields                                                     |
|----------------|------------------------------------------------------------|
| `FileMetadata` | `key`, `filename`, `content_type`, `size`, `uploaded_at`  |
| `UploadOptions`| `filename`, `content_type`                                 |
| `UploadResult` | `key`, `source_url`, `metadata`                           |
| `UploadUrl`    | `key`, `url`, `method`, `expires_at`, `headers`, `fields` |
| `UploadUrlOptions` | `filename`, `content_type`, `expires_in_seconds`      |

---

## 🔐 Security Notes

1. **Authentication** — all `/api/storage/*` endpoints require a valid JWT
   (`Authorization: ******
2. **Content-type validation** — uploads are validated against an allow-list of
   MIME types; unknown types are normalised to `application/octet-stream`.
3. **Filename sanitisation** — all filenames are sanitised with
   `sanitize_filename()` before use as storage keys.
4. **Key validation** — storage keys and path segments are validated against
   `is_valid_storage_key()` before reads or proxy responses.
5. **Pre-signed URL expiry** — S3 pre-signed URLs expire after at most 12 hours
   (clamped server-side); the default is 1 hour.

---

## 📝 Usage Examples

### Server-side upload (Python)

```python
from libs.file_storage import server_file_storage, UploadOptions

async def save_generated_image(png_bytes: bytes, name: str) -> str:
    result = await server_file_storage.upload(
        png_bytes,
        UploadOptions(filename=name, content_type="image/png"),
    )
    return result.source_url  # public URL
```

### Client upload flow (TypeScript — see `useFileUpload.ts`)

```typescript
// 1. Check storage config
const info = await fetch('/api/storage', { headers: authHeaders }).then(r => r.json());

// 2. Try presigned URL first
const uploadData = await fetch('/api/storage/upload-url', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', ...authHeaders },
  body: JSON.stringify({ filename: file.name, contentType: file.type }),
}).then(r => r.json());

if (uploadData.directUploadSupported) {
  // 3a. Direct PUT to S3
  await fetch(uploadData.url, { method: 'PUT', headers: uploadData.headers, body: file });
} else {
  // 3b. Server upload fallback
  const form = new FormData();
  form.append('file', file);
  await fetch('/api/storage/upload', { method: 'POST', body: form });
}
```

---

## 🔗 Related Links

- [Reference design (Node.js)](https://github.com/glide-the/claude-agent-next-kit/blob/feat/claude-agent-kit/docs/design/storage-api.md)
- [AWS S3 documentation](https://docs.aws.amazon.com/s3/)
- [MinIO documentation](https://min.io/docs/minio/linux/index.html)
- [boto3 S3 client](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html)
