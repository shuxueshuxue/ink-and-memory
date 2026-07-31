# Component Reuse Rule

## Mandatory

- Search the active workspace before adding a React component, hook, API helper, backend endpoint, PolyCLI session, database helper, prompt file, or script.
- Prefer extending existing Ink & Memory ownership boundaries over creating parallel implementations.
- Do not import Pawkeyland-specific modules, pet-domain paths, Claude Agent services, or prompt policy assumptions into this app as a shortcut.

## Frontend Search Order

1. Nearest feature component under `frontend/src/components/`.
2. Shared stateful logic under `frontend/src/hooks/`.
3. Editor and chat behavior in `frontend/src/engine/`.
4. API integration in `frontend/src/api/voiceApi.ts`.
5. Shared constants and utilities in `frontend/src/constants/`, `frontend/src/utils/`, `frontend/src/i18n.ts`, and `frontend/src/contexts/`.
6. New component or hook only when reuse would create incorrect ownership, unclear props, or cross-feature coupling.

## Backend Search Order

1. Existing FastAPI route or PolyCLI session in `backend/server.py`.
2. Auth, persistence, and runtime helpers in `backend/auth.py`, `backend/database.py`, `backend/config.py`, `backend/scheduler.py`, `backend/stateless_analyzer.py`, and `backend/speech_recognition.py`.
3. Existing prompt assets in `backend/prompts/`.
4. Existing tooling and tests in `backend/tools/` and `backend/tests/`.
5. New module only when the behavior has a stable owner and would otherwise make `server.py` or `database.py` harder to maintain.

## Practical Examples

- Add editor UI by extending existing components such as `App.tsx`, `ChatWidgetUI.tsx`, `DeckManager.tsx`, or smaller components nearby before introducing a new screen.
- Add reusable client state through a hook in `frontend/src/hooks/` when multiple components need the same lifecycle, persistence, or API orchestration.
- Add backend voice/deck behavior by reusing the existing `database.py` access patterns and PolyCLI session definitions before adding another route shape.
- Add prompt behavior by creating or editing a file in `backend/prompts/` and loading it through `backend/config.py` patterns, not by embedding prompt bodies in request handlers.

## Documentation Requirement

- If a change alters ownership between frontend, backend, prompts, or persistence, update the nearest existing `.folder.md` and the relevant docs.
- When you choose not to reuse an existing unit, record the concrete reason in code review notes or nearby docs: wrong abstraction, wrong lifecycle, incompatible data contract, or unacceptable coupling.
