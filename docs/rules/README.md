# Rules Reference

## Scope

These rule notes are the human-readable companion to the workspace guardrails in `.cursor/rules/`.
They are adapted for the current Ink & Memory app:

- `frontend/`: React 19 + Vite + TypeScript writing UI, editor engine, stateful hooks, localStorage constants, auth context, and API client.
- `backend/`: FastAPI + PolyCLI Python service for auth, session storage, voice/deck analysis, scheduled jobs, speech recognition, prompt loading, and model configuration.
- `docs/`: architecture, design, API, and rule notes. Keep docs aligned with source ownership when behavior changes.

## Rules Index

- `docs/rules/no-hardcoding.md`: config-first policy for envs, routes, model roles, storage keys, prompt files, thresholds, and API bases.
- `docs/rules/component-reuse.md`: reuse-first policy for React components/hooks, editor/engine modules, backend services, PolyCLI sessions, prompts, and database helpers.
- `.cursor/rules/vibe-engineering.mdc`: architecture, hardcoding, and overlap guardrails.
- `.cursor/rules/vibe-loading.mdc`: load only the docs needed for the task.
- `.cursor/rules/vibe-doc-sync.mdc`: update folder docs and file headers when source behavior changes.
- `.cursor/rules/vibe-component-reuse.mdc`: search before adding parallel implementations.

## Golden Rules

1. Keep source-of-truth values centralized: frontend storage keys in `frontend/src/constants/storageKeys.ts`, UI language key in `frontend/src/i18n.ts`, backend model roles and credentials in `backend/models.json`, runtime settings in `backend/config.py` and environment variables.
2. Reuse existing React components, hooks, API helpers, backend auth/database/config modules, PolyCLI session definitions, prompt files, and tests before adding new code paths.
3. Preserve the frontend/backend boundary: React calls typed helpers in `frontend/src/api/voiceApi.ts`; backend route behavior is owned by `backend/server.py` plus focused helpers such as `auth.py`, `database.py`, `scheduler.py`, and `stateless_analyzer.py`.
4. Do not copy Pawkeyland-specific paths, pet-domain names, Claude Agent layers, or prompt-policy locations into this project unless an active Ink & Memory feature explicitly introduces them.
5. Update the nearest `**/.folder.md` and related docs when a changed folder already participates in the workspace documentation contract.
