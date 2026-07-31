# No Hardcoding Rule

## Mandatory

- Do not hardcode business IDs, API bases, local machine paths, model names, credentials, JWT settings, storage keys, prompt bodies, feature flags, retries, timeouts, language defaults, or UI state identifiers inside feature code.
- Before adding a new constant, search for an existing source of truth in frontend constants, backend config, environment variables, `backend/models.json`, prompt files, API docs, or shared helpers.
- If no shared definition exists, add one in the narrowest central owner and document its purpose.

## Global-First Search Order

1. Environment variables, deployment config, and `backend/models.json` / `backend/models.json.example`.
2. Backend central modules: `backend/config.py`, `backend/auth.py`, `backend/database.py`, and `backend/scheduler.py`.
3. Frontend central modules: `frontend/src/constants/storageKeys.ts`, `frontend/src/i18n.ts`, `frontend/src/api/voiceApi.ts`, and shared utils under `frontend/src/utils/`.
4. Prompt assets under `backend/prompts/`.
5. API contract documentation in `backend/API.md` and behavioral notes under `docs/`.
6. Local module constants only as the last resort, and only for values whose ownership is truly local.

## Current Examples

- localStorage keys belong in `frontend/src/constants/storageKeys.ts`; do not repeat raw key strings across components or hooks.
- UI language storage and normalization belong in `frontend/src/i18n.ts` or a shared helper that imports it.
- Frontend API URL construction belongs in `frontend/src/api/voiceApi.ts` or a central frontend config helper; do not scatter `/ink-and-memory` or endpoint paths across components.
- Auth token handling belongs in `frontend/src/contexts/AuthContext.tsx`, `frontend/src/api/voiceApi.ts`, and `backend/auth.py`.
- Model role names, provider model IDs, API keys, image retry settings, and endpoint overrides belong in `backend/models.json` loaded by `backend/config.py`.
- Voice persona prompt text belongs in `backend/prompts/*.md`; route handlers and PolyCLI sessions should load or reference prompt definitions instead of embedding long prompt strings.
- Database schema and persistence behavior belong in `backend/database.py`; avoid duplicating SQL table names or storage serialization rules in unrelated modules.
- API request/response shapes should match `backend/API.md` and the route/Pydantic contracts in `backend/server.py`; update docs when the contract changes.
