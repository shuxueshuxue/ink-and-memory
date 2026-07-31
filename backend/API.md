# Ink & Memory API Documentation
<!--
[Input] Backend FastAPI routes and deployment public URL configuration.
[Output] Human-readable API reference for authenticated app APIs and public utility endpoints.
[Sync] 2026-06-14: document public SEO endpoints generated from INK_PUBLIC_BASE_URL and INK_BACKEND_PUBLIC_BASE_URL.
[Sync] 2026-06-15: remove /ink-and-memory frontend path prefix from public SEO endpoint notes.
[Sync] 2026-06-21: document system-config sandbox network policy fields.
[Sync] 2026-06-23: document Google OAuth, auth cookie aliases, and OAuth Device Flow endpoints.
-->

**Version:** 2.0.0
**Base URL:** `http://localhost:8765` (dev backend) | `https://ink-backend.suoxya.com` (prod backend). Public app URLs in crawler files come from `INK_PUBLIC_BASE_URL`; backend API links come from `INK_BACKEND_PUBLIC_BASE_URL`.

## Authentication

All endpoints except `/api/register`, `/api/login`, Google OAuth entry/callback, Device Flow code issuance, and `/api/default-voices` require authentication.

**Header:** `Authorization: Bearer <JWT_TOKEN>`

Browser clients may also authenticate with the backend-issued `access_token`
HttpOnly cookie. Google `id_token` / `access_token` values are never accepted
as business API credentials.

JWT access token lifetime is configured by `JWT_EXPIRES_IN` and defaults to 7 days in this project.

---

## Public SEO Endpoints

These endpoints do not require authentication. The frontend nginx service proxies root-level requests for these files to the backend so crawler content stays environment-driven.

### GET `/robots.txt`

Returns crawler policy for the public app. Search visibility crawlers such as `GPTBot`, `OAI-SearchBot`, `ChatGPT-User`, `ClaudeBot`, and `PerplexityBot` can access the public app path, while private API and websocket paths are excluded.

### GET `/sitemap.xml`

Returns an XML sitemap for the public SPA surface using `INK_PUBLIC_BASE_URL` as the canonical app URL.

### GET `/llms.txt`

Returns a structured AI-search summary describing Ink & Memory, primary public pages, product facts, keywords, backend API origin, and authenticated API boundaries.

---

## Auth Endpoints

### POST `/api/register`

Register a new user.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123",
  "display_name": "Optional Name"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "Optional Name"
  }
}
```

**Errors:**
- `400` - Email/password missing or password < 6 chars
- `400` - Email already exists

---

### POST `/api/login`

Login with email and password.

**Request:**
```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

**Response:**
```json
{
  "token": "eyJhbGciOiJIUzI1...",
  "user": {
    "id": 1,
    "email": "user@example.com",
    "display_name": "Optional Name"
  }
}
```

**Errors:**
- `401` - Invalid email or password

---

### GET `/api/me`

Get current user info from token.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "id": 1,
  "email": "user@example.com",
  "display_name": "Optional Name",
  "created_at": "2025-11-02 05:20:53"
}
```

**Errors:**
- `401` - Missing or invalid token
- `404` - User not found

---

### GET `/auth/me`

Alias of `/api/me` for OAuth-oriented clients. Accepts either
`Authorization: Bearer <token>` or the backend-issued `access_token` cookie.

---

### POST `/auth/logout`

Revokes the current refresh token when present and clears auth cookies.

**Headers:** `Authorization: Bearer <token>` or auth cookie

**Response:**
```json
{
  "success": true
}
```

---

### GET `/oauth/google/login`

Starts Google OAuth/OIDC login through the Python backend Authlib client.

**Query:**
- `return_to` - Optional frontend-relative path to return to after login, for example `/` or `/oauth/device/verify?user_code=ABCD-1234`.

**Response:** `302` redirect to Google.

---

### GET `/oauth/google/callback`

OAuth callback registered in Google Cloud Console. The backend validates OAuth
state through the session cookie, exchanges the Google code, binds or creates
the local user, then issues this system's own access/refresh tokens.

**Response:** `302` redirect to frontend with auth cookies set.

**Errors:** redirects to the frontend with `auth_error`.

---

## OAuth Device Flow Endpoints

### POST `/oauth/device/code`

Create a Device Authorization request for CLI/Desktop/Agent/MCP clients.

**Request:**
```json
{
  "client_id": "ink-cli",
  "scope": "profile"
}
```

**Response:**
```json
{
  "device_code": "opaque-device-code",
  "user_code": "ABCD-1234",
  "verification_uri": "http://localhost:5173/oauth/device/verify",
  "verification_uri_complete": "http://localhost:5173/oauth/device/verify?user_code=ABCD-1234",
  "expires_in": 600,
  "interval": 5
}
```

---

### GET `/oauth/device/verify`

Returns verification metadata for the browser confirmation page.

**Query:** `user_code=ABCD-1234`

---

### POST `/oauth/device/verify`

Approve or deny a pending user code. Requires the browser user to be logged in.

**Headers:** `Authorization: Bearer <token>` or auth cookie

**Request:**
```json
{
  "user_code": "ABCD-1234",
  "approve": true
}
```

---

### POST `/oauth/token`

Supports Device Code Grant and refresh-token rotation.

**Device Code Request:**
```json
{
  "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
  "device_code": "opaque-device-code",
  "client_id": "ink-cli"
}
```

**Success:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1...",
  "refresh_token": "opaque-refresh-token",
  "token_type": "Bearer",
  "expires_in": 900
}
```

**OAuth errors:**
```json
{
  "error": "authorization_pending",
  "error_description": "Authorization has not completed yet."
}
```

Known Device Flow errors include `authorization_pending`, `slow_down`,
`expired_token`, `access_denied`, `invalid_grant`, and `invalid_client`.

---

## Migration Endpoint

### POST `/api/import-local-data`

One-time import of localStorage data to database on first login.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "currentSession": "{\"cells\": [...]}",
  "calendarEntries": "{\"2025-11-01\": [...]}",
  "dailyPictures": "[{\"date\": \"2025-11-01\", \"base64\": \"...\"}]",
  "voiceCustomizations": "{\"Logic\": {...}}",
  "metaPrompt": "Be helpful",
  "stateConfig": "{\"states\": {...}}",
  "selectedState": "happy",
  "analysisReports": "[{\"type\": \"echoes\", \"data\": {...}}]",
  "oldDocument": "{\"document\": \"...\"}"
}
```

All fields are optional. Strings should be JSON-stringified.

**Response:**
```json
{
  "success": true,
  "imported": {
    "sessions": 6,
    "pictures": 2,
    "preferences": 4,
    "reports": 3
  }
}
```

**Errors:**
- `401` - Missing or invalid token

---

## System Config

### GET `/api/system-config`

Returns the current user's Settings configuration as a JSON object.

Known fields include:

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "system_prompt": "You are...",
  "workspace_enabled": true,
  "sandbox_network_mode": "allowlist",
  "sandbox_network_allowed_domains": ["raw.githubusercontent.com", "github.com"],
  "sandbox_fs_allowed_write_paths": ["/data/out"],
  "im_full_access_enabled": false,
  "theme": "system",
  "env_vars": {
    "ANTHROPIC_MODEL": "claude-sonnet-4-20250514"
  }
}
```

### PUT `/api/system-config`

Merges accepted fields into the current user's Settings configuration.
Unknown keys are ignored. `sandbox_network_mode` accepts `disabled`,
`allowlist`, or `open`. `sandbox_network_allowed_domains` is sanitized to a
flat domain-pattern list; use `open` mode instead of sending a bare `*`.
`sandbox_fs_allowed_write_paths` is sanitized to absolute paths only
(trailing slashes stripped, deduped, capped).

The sandbox network fields are consumed on the next Claude Agent workspace
initialization and written to the thread-local `.claude/settings.json`
`sandbox.network` block; `sandbox_fs_allowed_write_paths` is appended to the
`sandbox.filesystem.allowWrite` list after the thread workspace and Claude
Code's own sandbox TMPDIR (`$CLAUDE_TMPDIR` or `/tmp/claude-$UID`, always
allowed when the sandbox is enabled).

---

## Session Storage

### POST `/api/sessions`

Save or update a session.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "session_id": "my-session-123",
  "name": "My Session Name",
  "editor_state": {
    "cells": [
      {"type": "text", "content": "Hello world"}
    ],
    "commentors": []
  }
}
```

**Response:**
```json
{
  "success": true
}
```

---

### GET `/api/sessions`

List all sessions for current user (metadata only, no editor_state).

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "sessions": [
    {
      "id": "session-123",
      "name": "My Session",
      "created_at": "2025-11-02 05:22:41",
      "updated_at": "2025-11-02 05:22:41"
    }
  ]
}
```

---

### GET `/api/sessions/events`

Stream Edit Session update/delete events for the authenticated user.

**Headers:** `Authorization: Bearer <token>`, `Accept: text/event-stream`

**Response:** `text/event-stream`

```text
event: session_updated
data: {"type":"session_updated","sessionId":"session-123","source":"agent","toolCallId":"tool-call-1","toolName":"mcp__editor__write_segment","timestamp":"2026-06-14T00:00:00Z"}
```

**Event sources:**
- `api` - regular `/api/sessions` save/delete calls
- `agent` - successful Agent MCP editor write tool results

**Errors:**
- `401` - Missing or invalid token

---

### GET `/api/sessions/{session_id}`

Get a specific session including full editor_state.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "id": "session-123",
  "name": "My Session",
  "created_at": "2025-11-02 05:22:41",
  "updated_at": "2025-11-02 05:22:41",
  "editor_state": {
    "cells": [...],
    "commentors": []
  }
}
```

**Errors:**
- `404` - Session not found

---

### DELETE `/api/sessions/{session_id}`

Delete a session.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "success": true
}
```

---

## Claude Agent Chat Threads

### GET `/api/claude-agent/threads`

List Chat threads for the current user. Without search params, returns newest
threads first and supports `limit`/`offset` pagination for scroll-loaded
history panes. With `query`, searches thread titles and persisted conversation
text through the configured Chat history retriever.

**Headers:** `Authorization: Bearer <token>`

**Query params:**
- `query` (optional) - fuzzy title/message query
- `search_scope` (optional, default `all`) - `all`, `title`, or `messages`
- `retrieval_mode` (optional, default `fuzzy`) - `fuzzy`, `auto`, or `vector`
- `vector_query` (optional) - JSON object string; reserved interface only
- `min_score` (optional) - fuzzy threshold, `0` to `1`
- `limit` (optional) - max result count
- `offset` (optional, default `0`) - default-list page offset; ignored by search retrieval

**Response:**
```json
{
  "threads": [
    {
      "id": "thread-123",
      "title": "论文初筛流程",
      "created_at": "2026-06-26 10:00:00",
      "updated_at": "2026-06-27 09:00:00",
      "match": {
        "strategy": "fuzzy",
        "retriever": "fuzzy",
        "score": 1,
        "fields": ["messages"],
        "excerpt": "之前讨论过向量库先不接入，只保留接口。"
      }
    }
  ],
  "retrieval": {
    "mode": "fuzzy",
    "query": "向量库 接口",
    "search_scope": "all",
    "min_score": 0.35,
    "limit": null,
    "vector": "interface_only",
    "retriever": "fuzzy"
  }
}
```

`retrieval_mode=vector` currently returns `ok=false`,
`error="vector_retrieval_unavailable"`, and does not access a vector database.

---

## Pictures

### GET `/api/pictures`

Get recent daily pictures.

**Headers:** `Authorization: Bearer <token>`

**Query params:**
- `limit` (optional, default 30) - Max number of pictures

**Response:**
```json
{
  "pictures": [
    {
      "date": "2025-11-02",
      "image_base64": "iVBORw0KGgoAAAANSUhEUg...",
      "prompt": "A serene landscape...",
      "created_at": "2025-11-02 05:22:41"
    }
  ]
}
```

---

### POST `/api/pictures`

Save a daily picture.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "date": "2025-11-02",
  "image_base64": "iVBORw0KGgoAAAANSUhEUg...",
  "prompt": "A serene landscape..."
}
```

**Response:**
```json
{
  "success": true
}
```

**Errors:**
- `400` - date or image_base64 missing

---

## Preferences

### GET `/api/preferences`

Get user preferences.

**Headers:** `Authorization: Bearer <token>`

**Response:**
```json
{
  "voice_configs": {
    "Logic": {
      "name": "Logic",
      "tagline": "...",
      "icon": "brain",
      "color": "blue",
      "enabled": true
    }
  },
  "meta_prompt": "Be helpful",
  "state_config": {
    "states": {
      "happy": {"name": "Happy", "prompt": "..."}
    }
  },
  "selected_state": "happy",
  "updated_at": "2025-11-02 05:22:41"
}
```

Returns empty object `{}` if no preferences set.

---

### POST `/api/preferences`

Save user preferences (partial updates supported).

**Headers:** `Authorization: Bearer <token>`

**Request (any combination of fields):**
```json
{
  "voice_configs": {...},
  "meta_prompt": "Be creative",
  "state_config": {...},
  "selected_state": "happy"
}
```

**Response:**
```json
{
  "success": true
}
```

---

## Analysis Reports

### GET `/api/reports`

Get recent analysis reports.

**Headers:** `Authorization: Bearer <token>`

**Query params:**
- `limit` (optional, default 10) - Max number of reports

**Response:**
```json
{
  "reports": [
    {
      "id": 1,
      "report_type": "echoes",
      "report_data": {
        "echoes": [...]
      },
      "created_at": "2025-11-02 05:22:41"
    }
  ]
}
```

---

### POST `/api/reports`

Save an analysis report.

**Headers:** `Authorization: Bearer <token>`

**Request:**
```json
{
  "report_type": "echoes",
  "report_data": {
    "echoes": [
      {"title": "...", "description": "...", "examples": [...]}
    ]
  },
  "all_notes_text": "All the user's notes combined..."
}
```

**Response:**
```json
{
  "success": true
}
```

**Errors:**
- `400` - report_type or report_data missing

---

## Voice Analysis (PolyCLI)

### POST `/api/analyze`

Analyze text and return ONE new voice comment (sync API).

**Request:**
```json
{
  "text": "User's text to analyze",
  "session_id": "session-123",
  "voices": {...},
  "applied_comments": [],
  "meta_prompt": "",
  "state_prompt": "",
  "overlapped_phrases": []
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "voices": [
      {
        "phrase": "exact phrase",
        "voice": "Logic",
        "comment": "What the voice says",
        "icon": "brain",
        "color": "blue"
      }
    ],
    "new_voices_added": 1
  }
}
```

---

### POST `/api/chat`

Chat with a voice persona (sync API).

**Request:**
```json
{
  "voice_name": "Logic",
  "voice_config": {...},
  "conversation_history": [
    {"role": "user", "content": "Hi"},
    {"role": "assistant", "content": "Hello"}
  ],
  "user_message": "What do you think?",
  "original_text": "User's writing context",
  "meta_prompt": "",
  "state_prompt": ""
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "response": "Voice's response to the user"
  }
}
```

---

### POST `/api/generate-image`

Generate artistic image from notes (sync API, 60s timeout).

**Request:**
```json
{
  "all_notes": "All user's notes combined..."
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "image_base64": "iVBORw0KGgoAAAANSUhEUg...",
    "prompt": "Creative image description"
  }
}
```

---

### POST `/api/analyze-echoes`

Find recurring themes in notes (sync API).

**Request:**
```json
{
  "all_notes": "All user's notes combined..."
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "echoes": [
      {
        "title": "Theme title",
        "description": "Pattern description",
        "examples": ["quote1", "quote2"]
      }
    ]
  }
}
```

---

### POST `/api/analyze-traits`

Identify personality traits from notes (sync API).

**Request:**
```json
{
  "all_notes": "All user's notes combined..."
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "traits": [
      {
        "trait": "Curious",
        "strength": 4,
        "evidence": "Examples from text..."
      }
    ]
  }
}
```

---

### POST `/api/analyze-patterns`

Identify behavioral patterns from notes (sync API).

**Request:**
```json
{
  "all_notes": "All user's notes combined..."
}
```

**Response:**
```json
{
  "success": true,
  "result": {
    "patterns": [
      {
        "pattern": "Pattern name",
        "description": "Pattern description",
        "frequency": "Often/Sometimes/Rarely"
      }
    ]
  }
}
```

---

### GET `/api/default-voices`

Get default voice configurations (no auth required).

**Response:**
```json
{
  "Logic": {
    "tagline": "Wield raw intellectual power...",
    "icon": "brain",
    "color": "blue"
  },
  "Rhetoric": {...},
  ...
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message"
}
```

Common status codes:
- `400` - Bad request (missing/invalid params)
- `401` - Unauthorized (missing/invalid token)
- `404` - Not found
- `500` - Internal server error

---

## Development

**Start server:**
```bash
cd backend
source .venv/bin/activate
python server.py
```

**Run tests:**
```bash
python test_migration.py           # Test migration logic
python test_real_migration.py      # Test with real data
```

**API Docs:**
- Interactive docs: http://localhost:8765/docs
- PolyCLI control panel: http://localhost:8765/polycli

---

## Database

SQLite database at `backend/data/ink-and-memory.db`

**Initialize/reset:**
```python
from database import init_db
init_db()
```

**Tables:**
- `users` - User accounts
- `user_sessions` - Editor sessions
- `daily_pictures` - Generated images
- `user_preferences` - User settings
- `analysis_reports` - Analysis results
- `auth_sessions` - Session tokens (optional)
- `schema_version` - Migration tracking
