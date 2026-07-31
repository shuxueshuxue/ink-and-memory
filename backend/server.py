#!/usr/bin/env python3
# [Input] Consume backend/.env, HTTP requests, database/auth/config modules.
# [Output] Publish FastAPI application and REST/SSE routes.
# [Pos] backend API entrypoint
# [Sync] 2026-05-24: load backend/.env before importing config and route modules.
# [Sync] 2026-05-24: keep only current Ink Agent env keys after dotenv loading.
# [Sync] 2026-05-25: split REST API routes into backend/routers modules; keep PolyCLI session defs, root, websocket, scheduler, and mounts here.
# [Sync] 2026-06-09: allowlist INK_AGENT_EVENT_BUS_* / INK_AGENT_REDIS_URL for SSE EventBus config.
# [Sync] 2026-06-12: make CORS origin/credential policy environment-driven for cross-origin deployments.
# [Sync] 2026-06-14: expose robots.txt, sitemap.xml, and llms.txt from shared SEO content generators.
# [Sync] 2026-06-14: separate frontend public app URL from backend public API origin for SEO files.
# [Sync] 2026-06-23: register Google OAuth and Device Flow routers, initialize
#                    auth tables at startup, and add SessionMiddleware for
#                    Authlib OAuth state.
# [Sync] 2026-07-04: register the Notion resource connector router so connector
#                    auth, discovery, selection, and canonical snapshot sync
#                    endpoints are exposed alongside the rest of the backend API.
"""FastAPI-based voice analysis server with sync API support."""

import os
import time
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_ENV_FILE = Path(__file__).resolve().with_name(".env")
load_dotenv(_BACKEND_ENV_FILE, override=False)


def _drop_unsupported_agent_env() -> None:
    """Remove stale Agent env aliases that are outside this project's contract."""

    allowed_ink_names = {
        "INK_AGENT_ENABLE_MEMORY_MCP",
        "INK_AGENT_TTL_S",
        "INK_AGENT_SWEEP_INTERVAL_S",
        "INK_AGENT_SSE_KEEPALIVE_S",
        "INK_AGENT_MAX_TURNS",
        "INK_AGENT_CONTEXT_SESSIONS",
        "INK_AGENT_EVENT_BUS_BACKEND",
        "INK_AGENT_REDIS_URL",
        "INK_AGENT_EVENT_BUS_TTL_S",
        # Sandbox runtime env contract (workspace.py).  Previously dropped
        # here at startup, which silently disabled the extra sandbox read
        # paths (the apply-seccomp settings override listed here briefly was
        # removed 2026-07-26 — proven dead in production; see workspace.py).
        "INK_AGENT_SANDBOX_EXTRA_ALLOW_READ",
    }
    os.environ.pop("ANTHROPIC_API_KEY", None)
    for key in list(os.environ):
        if key.startswith("INK_AGENT_MEM0_") or key in allowed_ink_names:
            continue
        if key.startswith("INK_AGENT_"):
            os.environ.pop(key, None)
            continue
        if key.startswith("CLAUDE_CODE_") and key.endswith("_TOKEN"):
            os.environ.pop(key, None)


_drop_unsupported_agent_env()

os.environ.setdefault("TZ", "UTC")
if hasattr(time, "tzset"):
    time.tzset()

import asyncio
from datetime import datetime
import httpx
from fastapi import FastAPI, HTTPException, Depends, Header, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.sessions import SessionMiddleware
try:
    from polycli.orchestration.session_registry import session_def, get_registry
    from polycli.integrations.fastapi import mount_control_panel
    from polycli import PolyAgent
except ImportError:
    def session_def(*args, **kwargs):
        def _decorator(fn):
            return fn

        return _decorator

    def get_registry():
        return None

    def mount_control_panel(*args, **kwargs):
        return None

    class PolyAgent:
        def __init__(self, *args, **kwargs):
            self._missing_dependency_error = RuntimeError(
                "polycli is required to run PolyCLI-backed agent sessions"
            )

        def run(self, *args, **kwargs):
            raise self._missing_dependency_error
try:
    from stateless_analyzer import analyze_stateless
except ImportError:
    def analyze_stateless(*args, **kwargs):
        raise RuntimeError(
            "stateless_analyzer dependencies are required for stateless analysis"
        )

try:
    from speech_recognition import init_speech_recognition
except ImportError:
    async def init_speech_recognition(*args, **kwargs):
        raise RuntimeError(
            "speech recognition dependencies are required for websocket recognition"
        )

import config
from seo_content import build_llms_txt, build_robots_txt, build_sitemap_xml
from picture_service import _generate_picture_for_date, _today_in_tz
from typing import Optional, List, Any
from pydantic import BaseModel

# Import database and auth modules
import database
import auth

SUPPORTED_LANGUAGES = {"en", "zh"}
DEFAULT_LANGUAGE = "en"
BACKEND_VERSION = os.environ.get("BACKEND_VERSION", "unknown")
PUBLIC_BASE_URL = os.environ.get("INK_PUBLIC_BASE_URL", "/")
BACKEND_PUBLIC_BASE_URL = os.environ.get("INK_BACKEND_PUBLIC_BASE_URL", PUBLIC_BASE_URL)


def _split_csv_env(name: str, default: str) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        raw = default
    values = [value.strip() for value in raw.split(",") if value.strip()]
    return values


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


DEFAULT_CORS_ALLOW_ORIGINS = (
    "http://localhost,"
    "http://localhost:5173,"
    "http://127.0.0.1,"
    "http://127.0.0.1:5173"
)
CORS_ALLOW_ORIGINS = _split_csv_env("INK_CORS_ALLOW_ORIGINS", DEFAULT_CORS_ALLOW_ORIGINS)
CORS_ALLOW_CREDENTIALS = _bool_env("INK_CORS_ALLOW_CREDENTIALS", False)
SESSION_SECRET_KEY = (
    os.environ.get("SESSION_SECRET_KEY")
    or os.environ.get("JWT_SECRET")
    or os.environ.get("JWT_SECRET_KEY")
    or "dev-session-secret-change-in-production"
)
COOKIE_SECURE = _bool_env("COOKIE_SECURE", False)
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "lax").strip().lower()
if COOKIE_SAMESITE not in {"lax", "strict", "none"}:
    COOKIE_SAMESITE = "lax"


def normalize_language_code(language: Optional[str]) -> str:
    if not language:
        return DEFAULT_LANGUAGE
    language = language.lower()
    if language.startswith("zh"):
        return "zh"
    return "en"


def _count_mixed_words(text: str) -> int:
    """
    Count words in mixed Chinese/English text.
    - CJK characters count as 1 each
    - English is counted by whitespace-separated tokens
    """
    word_count = 0
    for ch in text:
        code = ord(ch)
        if (0x4E00 <= code <= 0x9FFF or 0x3400 <= code <= 0x4DBF or 0x3040 <= code <= 0x309F or 0x30A0 <= code <= 0x30FF):
            word_count += 1
    import re
    english_words = re.sub(r"[\u4E00-\u9FFF\u3400-\u4DBF\u3040-\u309F\u30A0-\u30FF]", " ", text)
    word_count += len([w for w in english_words.split() if w])
    return word_count




def _load_all_notes_text(user_id: int) -> str:
    sessions = database.get_all_sessions_with_text(user_id)
    texts = [s.get("text", "") for s in sessions if (s.get("text") or "").strip()]
    return "\n\n".join(texts)

def resolve_language(_user_id: int, requested_language: Optional[str] = None) -> str:
    """Return a supported language code, falling back to default."""
    if requested_language:
        code = normalize_language_code(requested_language)
        if code in SUPPORTED_LANGUAGES:
            return code
    return DEFAULT_LANGUAGE


def language_instruction(language_code: str, detail: str = "") -> str:
    if language_code == "zh":
        base = "请使用简体中文输出所有内容。"
    else:
        base = "Respond in English."
    if detail:
        return f"{base} {detail}".strip()
    return base


# ========== Session Definitions (PolyCLI) ==========


@session_def(
    name="Get Writing Suggestion",
    description="Get AI-powered writing inspiration from a voice persona",
    params={
        "text": {"type": "str"},
        "user_id": {"type": "int"},
        "meta_prompt": {"type": "str"},
        "state_prompt": {"type": "str"},
    },
    category="Writing",
)
def get_writing_suggestion(
    text: str, user_id: int, meta_prompt: str = "", state_prompt: str = ""
):
    """Generate writing inspiration from a random voice persona."""
    print(f"\n{'=' * 60}")
    print(f"✍️  get_writing_suggestion() called")
    print(f"   Text length: {len(text)} chars")
    print(f"{'=' * 60}\n")

    if not text or len(text.strip()) < 10:
        return {"success": False, "error": "Text too short"}

    # @@@ Load voices from user's enabled decks (deck system)
    import random

    voices = database.load_voices_from_user_decks(user_id)

    if not voices:
        return {"success": False, "error": "No enabled voices found in your decks"}

    # Pick a random enabled voice
    voice_key = random.choice(list(voices.keys()))
    voice_info = voices[voice_key]

    print(f"🎭 Selected voice: {voice_info['name']} ({voice_key})")
    print(f"📚 Selected from {len(voices)} enabled voices")

    agent = PolyAgent(id="writing-suggester")

    # Build system prompt - voice gives inspiration, not continuation
    system_prompt = f"""You are {voice_info["name"]}, an inner voice persona.
Your role: {voice_info.get("systemPrompt", "")}

Read what the user just wrote and offer a VERY SHORT, gentle nudge about what to write next.

IMPORTANT STYLE:
- Keep it EXTREMELY brief (1 short sentence, max 15 words)
- Be warm, conversational, and friendly
- Focus on inspiration and possibility, not criticism
- Suggest what to explore next, don't analyze what was written
- Use casual, everyday language
- Think: "What if you..." or "Maybe explore..." or "How about..."

DO NOT:
- Analyze or critique their writing
- Summarize what they wrote
- Give formal feedback
- Be verbose or explanatory

Examples of GOOD suggestions:
- "What if you describe how that made you feel?"
- "Maybe explore what happened next?"
- "I'm curious about the details..."
- "How did that moment change things?"

Speak in {voice_info["name"]}'s characteristic style, but keep it brief and inspiring."""

    if state_prompt:
        system_prompt += f"\n\nEmotional context: {state_prompt}"

    if meta_prompt:
        system_prompt += f"\n\nWriter's style: {meta_prompt}"

    user_prompt = f"""The user just wrote:

{text}

Give them ONE very short, gentle nudge about what to write next (max 15 words)."""

    # Generate inspiration
    print(f"📤 Calling agent.run() with model='{config.VOICE_INSPIRATION_MODEL}'...")
    result = agent.run(
        user_prompt,
        system_prompt=system_prompt,
        model=config.VOICE_INSPIRATION_MODEL,
        cli="no-tools",
        tracked=True,
    )

    if not result.is_success or not result.content:
        print(f"⚠️  Failed to generate inspiration")
        inspiration = None
    else:
        inspiration = result.content.strip()
        print(f"✅ Got inspiration: {inspiration[:100]}...")

    print(f"\n📦 Returning voice inspiration\n")

    return {
        "success": True,
        "inspiration": inspiration,
        "voice": voice_info["name"],
        "voice_key": voice_key,
        "icon": voice_info["icon"],
        "color": voice_info["color"],
    }


@session_def(
    name="Chat with Voice",
    description="Have a conversation with a specific inner voice persona",
    params={
        "voice_id": {"type": "str"},
        "user_id": {"type": "int"},
        "conversation_history": {"type": "list"},
        "user_message": {"type": "str"},
        "original_text": {"type": "str"},
        "meta_prompt": {"type": "str"},
        "state_prompt": {"type": "str"},
    },
    category="Chat",
)
def chat_with_voice(
    voice_id: str,
    user_id: int,
    conversation_history: list,
    user_message: str,
    original_text: str = "",
    meta_prompt: str = "",
    state_prompt: str = "",
):
    """Chat with a specific voice persona."""
    print(f"\n{'=' * 60}")
    print(f"💬 chat_with_voice() called")
    print(f"   Voice ID: {voice_id}")
    print(f"   User ID: {user_id}")
    print(f"   User message: {user_message}")
    print(f"   History length: {len(conversation_history)}")
    print(f"   Meta prompt: {repr(meta_prompt)[:100]}")
    print(f"   State prompt: {repr(state_prompt)[:100]}")
    print(f"{'=' * 60}\n")

    # @@@ Load voices from user's enabled decks (deck system)
    voices = database.load_voices_from_user_decks(user_id)

    # @@@ Get voice config for this specific voice
    if voice_id in voices:
        voice_config = voices[voice_id]
        voice_name = voice_config.get("name", voice_id)
        print(f"📚 Loaded voice from deck system: {voice_id} ({voice_name})")
    else:
        # Fallback: voice might be disabled or not in user's decks
        return {
            "success": False,
            "error": f"Voice {voice_id} not found in your enabled decks. Please enable it in the Decks tab.",
        }

    agent = PolyAgent(id=f"voice-chat-{voice_name.lower()}")

    # Build system prompt for this voice
    system_prompt = f"""You are {voice_name}, an inner voice archetype from Disco Elysium.

Your character: {voice_config.get("systemPrompt", "")}

Respond in character as {voice_name}. Be concise (1-3 sentences). Stay true to your archetype.
Use the conversation context but focus on your unique perspective."""

    # Add original writing area text if available
    if original_text and original_text.strip():
        system_prompt += f"""

Context: The user is writing this text:
---
{original_text.strip()}
---

Your initial comment was about this text. Keep this context in mind when responding to the user's questions."""

    # Add meta prompt if available
    if meta_prompt and meta_prompt.strip():
        system_prompt += f"""

Additional instructions:
{meta_prompt.strip()}"""

    # Add state prompt if available
    if state_prompt and state_prompt.strip():
        system_prompt += f"""

User's current state:
{state_prompt.strip()}"""

    # Build full prompt with conversation history
    prompt = system_prompt + "\n\nConversation history:\n"

    # Add conversation history
    for msg in conversation_history:
        role_label = "User" if msg["role"] == "user" else voice_name
        prompt += f"\n{role_label}: {msg['content']}"

    # Add user's new message
    prompt += f"\n\nUser: {user_message}\n\n{voice_name}:"

    # Get response from LLM
    result = agent.run(prompt, model=config.VOICE_CHAT_MODEL, cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        response = "..."
    else:
        response = result.content

    print(f"✅ Got response: {response[:100]}...")

    return {"response": response, "voice_name": voice_name}


@session_def(
    name="Analyze Voices",
    description="Get one new voice comment for text",
    params={
        "text": {"type": "str"},
        "editor_session_id": {"type": "str"},
        "user_id": {"type": "int"},
        "applied_comments": {"type": "list"},
        "meta_prompt": {"type": "str"},
        "state_prompt": {"type": "str"},
        "overlapped_phrases": {"type": "list"},
        "not_found_phrases": {"type": "list"},
    },
    category="Analysis",
)
def analyze_text(
    text: str,
    editor_session_id: str,
    user_id: int,
    applied_comments: list = None,
    meta_prompt: str = "",
    state_prompt: str = "",
    overlapped_phrases: list = None,
    not_found_phrases: list = None,
):
    """Stateless analysis - returns ONE new comment based on text and applied comments."""
    print(f"\n{'=' * 60}")
    print(f"🎯 Stateless analyze_text() called")
    print(f"   User ID: {user_id}")
    print(f"   Text: {text[:100]}...")
    print(f"   Applied comments: {len(applied_comments or [])}")
    print(f"   Overlapped phrases: {len(overlapped_phrases or [])}")
    print(f"   Not found phrases: {len(not_found_phrases or [])}")
    print(f"   Meta prompt: {repr(meta_prompt)[:100]}")
    print(f"   State prompt: {repr(state_prompt)[:100]}")
    print(f"{'=' * 60}\n")

    # @@@ Load voices from user's enabled decks (deck system)
    voices = database.load_voices_from_user_decks(user_id)
    print(
        f"📚 Loaded {len(voices)} enabled voices from deck system: {list(voices.keys()) if voices else 'None (will use defaults)'}"
    )

    agent = PolyAgent(id="voice-analyzer")

    # Get voices from stateless analyzer
    result = analyze_stateless(
        agent,
        text,
        applied_comments or [],
        voices,
        meta_prompt,
        state_prompt,
        overlapped_phrases or [],
        not_found_phrases or [],
    )

    print(f"✅ Returning {result['new_voices_added']} new voice(s)")

    return {
        "voices": result["voices"],
        "new_voices_added": result["new_voices_added"],
        "status": "completed",
    }


@session_def(
    name="Analyze Echoes",
    description="Find recurring themes and topics in all user notes",
    params={
        "user_id": {"type": "int"},
        "language": {"type": "str"},
    },
    category="Analysis",
)
def analyze_echoes(user_id: int, language: str = "en"):
    """Analyze recurring themes and topics across all notes."""
    notes = _load_all_notes_text(user_id)
    if not notes.strip():
        return {"echoes": []}
    print(f"\n{'=' * 60}")
    print(f"🔄 analyze_echoes() called")
    language_code = normalize_language_code(language)
    print(f"   Language: {language_code}")
    print(f"{'=' * 60}\n")

    agent = PolyAgent(id="echoes-analyzer")

    prompt = f"""Analyze these personal notes and identify recurring themes, topics, or concerns that keep appearing.

Notes:
---
{notes}
---

Find 3-5 echoes (recurring themes) that appear across different entries. For each echo:
- Give it a short title (2-4 words)
- Explain what pattern you see
- Quote 2-3 specific examples from the notes

Format as a JSON array:
[
  {{"title": "...", "description": "...", "examples": ["quote1", "quote2", "quote3"]}},
  ...
]

Return ONLY the JSON array, no other text."""
    prompt += f"\n\n{language_instruction(language_code, 'All titles, descriptions, and examples should use this language. Keep the JSON keys the same.')}"

    result = agent.run(prompt, model=config.ECHO_ANALYSIS_MODEL, cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"echoes": []}

    try:
        import json

        echoes = json.loads(result.content.strip())
        return {"echoes": echoes}
    except:
        return {"echoes": []}


@session_def(
    name="Analyze Traits",
    description="Identify personality traits and characteristics from user notes",
    params={
        "user_id": {"type": "int"},
        "language": {"type": "str"},
    },
    category="Analysis",
)
def analyze_traits(user_id: int, language: str = "en"):
    """Analyze personality traits from all notes."""
    notes = _load_all_notes_text(user_id)
    if not notes.strip():
        return {"traits": []}
    print(f"\n{'=' * 60}")
    print(f"👤 analyze_traits() called")
    language_code = normalize_language_code(language)
    print(f"   Language: {language_code}")
    print(f"{'=' * 60}\n")

    agent = PolyAgent(id="traits-analyzer")

    prompt = f"""Analyze these personal notes and identify personality traits and characteristics.

Notes:
---
{notes}
---

Identify 4-6 personality traits that are evident from the writing. For each trait:
- Give it a name (1-2 words)
- Rate the strength (1-5)
- Explain why you see this trait with specific examples

Format as a JSON array:
[
  {{"trait": "...", "strength": 4, "evidence": "..."}},
  ...
]

Return ONLY the JSON array, no other text."""
    prompt += f"\n\n{language_instruction(language_code, 'Use this language for trait names, explanations, and evidence (JSON keys stay in English).')}"

    result = agent.run(prompt, model=config.TRAIT_ANALYSIS_MODEL, cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"traits": []}

    try:
        import json

        traits = json.loads(result.content.strip())
        return {"traits": traits}
    except:
        return {"traits": []}


@session_def(
    name="Analyze Patterns",
    description="Identify behavioral patterns and habits from user notes",
    params={
        "user_id": {"type": "int"},
        "language": {"type": "str"},
    },
    category="Analysis",
)
def analyze_patterns(
    user_id: int, language: str = "en"
):
    """Analyze behavioral patterns from all notes."""
    notes = _load_all_notes_text(user_id)
    if not notes.strip():
        return {"patterns": []}
    print(f"\n{'=' * 60}")
    print(f"🔍 analyze_patterns() called")
    language_code = normalize_language_code(language)
    print(f"   Language: {language_code}")
    print(f"{'=' * 60}\n")

    agent = PolyAgent(id="patterns-analyzer")

    prompt = f"""Analyze these personal notes and identify behavioral patterns or habits.

Notes:
---
{notes}
---

Identify 3-5 behavioral patterns or habits. For each pattern:
- Give it a descriptive name
- Describe the pattern
- Note the frequency/context when it appears

Format as a JSON array:
[
  {{"pattern": "...", "description": "...", "frequency": "..."}},
  ...
]

Return ONLY the JSON array, no other text."""
    prompt += f"\n\n{language_instruction(language_code, 'Use this language for pattern names, descriptions, and frequency notes (JSON keys stay in English).')}"

    result = agent.run(prompt, model=config.PATTERN_ANALYSIS_MODEL, cli="no-tools", tracked=True)

    if not result.is_success or not result.content:
        return {"patterns": []}

    try:
        import json

        patterns = json.loads(result.content.strip())
        return {"patterns": patterns}
    except:
        return {"patterns": []}


@session_def(
    name="Generate Daily Picture",
    description="Generate an artistic image based on user's daily notes",
    params={
        "user_id": {"type": "int"},
        "target_date": {"type": "str"},  # Optional: YYYY-MM-DD format
        "notes_override": {"type": "str"},
        "dry_run": {"type": "bool"},
        "skip_if_exists": {"type": "bool"},
    },
    category="Creative",
)
def generate_daily_picture(
    user_id: int,
    target_date: str = None,
    notes_override: str = None,
    dry_run: bool = True,
    skip_if_exists: bool = False,
    timezone: str = "Asia/Shanghai",
):
    """
    Generate an image for a specific date.

    Defaults to dry_run=True so the caller decides whether to persist.
    """
    result = _generate_picture_for_date(
        user_id=user_id,
        target_date=target_date,
        timezone=timezone,
        notes_override=notes_override,
        skip_if_exists=skip_if_exists,
        dry_run=dry_run,
    )
    # PolyCLI sessions should fail loudly if no image produced
    if result.get("skipped"):
        raise ValueError(result.get("reason") or "Generation skipped")
    if not result.get("image_base64"):
        raise ValueError(result.get("error") or "Generation returned no image")
    return result


# ========== FastAPI Application ==========

app = FastAPI(
    title="Ink & Memory API",
    description="Voice analysis and creative generation API",
    version="2.0.0",
)

print(f"🧾 Backend version: {BACKEND_VERSION}")

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    same_site=COOKIE_SAMESITE,
    https_only=COOKIE_SECURE,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========== Timeline Auto-Generation Scheduler ==========

from apscheduler.schedulers.asyncio import AsyncIOScheduler
import scheduler as timeline_scheduler

# Create scheduler instance
timeline_gen_scheduler = AsyncIOScheduler()


@app.on_event("startup")
async def startup_database():
    """Initialize SQLite schema and idempotent auth migrations."""
    database.init_db()


@app.on_event("startup")
async def startup_scheduler():
    """Start the timeline auto-generation scheduler on app startup."""
    print("\n" + "=" * 60)
    print("📅 Starting Timeline Auto-Generation Scheduler")
    print("   Schedule: Daily at 00:00 (midnight, Asia/Shanghai timezone)")
    print("   Generates timeline images for previous day")
    print("=" * 60 + "\n")

    # @@@ asyncio.run() creates new event loop for scheduler thread
    timeline_gen_scheduler.add_job(
        lambda: asyncio.run(timeline_scheduler.daily_generation_job()),
        "cron",
        hour=0,
        minute=0,
        timezone="Asia/Shanghai",
        id="daily_timeline_generation",
        name="Generate timeline images for yesterday",
        replace_existing=True,
    )

    timeline_gen_scheduler.start()
    print("✅ Scheduler started - next run at midnight (00:00 Asia/Shanghai)\n")


@app.on_event("shutdown")
async def shutdown_scheduler():
    """Shutdown the scheduler gracefully."""
    print("\n📅 Shutting down timeline scheduler...")
    timeline_gen_scheduler.shutdown(wait=False)
    print("✅ Scheduler shutdown complete\n")


# ========== Claude Agent Factory ==========

from agent_factory import claude_agent_thread_factory
from routers import admin as admin_router_module
from routers.admin import router as admin_router
from routers.auth import (
    ImportDataRequest,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    router as auth_router,
)
from routers.claude_agent import (
    ClaudeAgentRequestBody,
    CreateThreadResponseBody,
    ToolConfirmRequestBody,
    router as claude_agent_router,
)
from routers.device_oauth import OAuthProtocolError, router as device_oauth_router
from routers.friends import (
    FriendRequestActionRequest,
    UseInviteCodeRequest,
    router as friends_router,
)
from routers.oauth import router as oauth_router
from routers.pictures import GeneratePictureRequest, router as pictures_router
from routers.preferences import router as preferences_router
from routers.notion import router as notion_router
from routers.reports import router as reports_router
from routers.sessions import SessionBatchRequest, router as sessions_router
from routers.storage import UploadUrlRequest, router as storage_router
from routers.system_config import router as system_config_router
from routers.workspace import router as workspace_router
from routers.reflections import router as reflections_router
from routers.voices import (
    DeckCreateRequest,
    DeckUpdateRequest,
    VoiceCreateRequest,
    VoiceForkRequest,
    VoiceUpdateRequest,
    router as voices_router,
)

admin_router_module.set_timeline_gen_scheduler(timeline_gen_scheduler)


@app.exception_handler(OAuthProtocolError)
async def oauth_protocol_error_handler(request, exc: OAuthProtocolError):
    """Return Device Flow token errors in RFC-style top-level JSON shape."""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error,
            "error_description": exc.description,
        },
        headers={"Cache-Control": "no-store", "Pragma": "no-cache"},
    )


@app.on_event("startup")
async def startup_claude_agent():
    """Start the Claude Agent session pool sweeper."""
    claude_agent_thread_factory.start()
    print("✅ Claude Agent factory started\n")


@app.on_event("shutdown")
async def shutdown_claude_agent():
    """Gracefully close all Claude Agent sessions."""
    await claude_agent_thread_factory.aclose()
    print("✅ Claude Agent factory closed\n")



# ========== Custom API Endpoints (Clean Interface) ==========


@app.get("/")
def root():
    """Root endpoint"""
    base = BACKEND_PUBLIC_BASE_URL.rstrip("/") + "/"
    return PlainTextResponse(
        f"The server is configured with a public base URL of {base}"
        f" - did you mean to visit {base}api/claude-agent/threads instead?"
    )


@app.get("/robots.txt", include_in_schema=False)
def robots_txt():
    """Machine-readable crawler access policy for the public app."""
    return PlainTextResponse(
        build_robots_txt(PUBLIC_BASE_URL),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml():
    """XML sitemap for the public app surface."""
    return Response(
        build_sitemap_xml(PUBLIC_BASE_URL),
        media_type="application/xml; charset=utf-8",
    )


@app.get("/llms.txt", include_in_schema=False)
def llms_txt():
    """Structured app summary for AI search and LLM crawlers."""
    return PlainTextResponse(
        build_llms_txt(PUBLIC_BASE_URL, BACKEND_PUBLIC_BASE_URL),
        media_type="text/plain; charset=utf-8",
    )


@app.get("/api/health")
def health():
    """Health endpoint for deploy scripts, Compose healthchecks, and Cloud Run probes."""
    return {
        "status": "ok",
        "version": BACKEND_VERSION,
        "cors_allow_origins": CORS_ALLOW_ORIGINS,
    }


# ========== Router Registration ==========

app.include_router(auth_router)
app.include_router(oauth_router)
app.include_router(device_oauth_router)
app.include_router(sessions_router)
app.include_router(pictures_router)
app.include_router(preferences_router)
app.include_router(notion_router)
app.include_router(reports_router)
app.include_router(admin_router)
app.include_router(voices_router)
app.include_router(friends_router)
app.include_router(claude_agent_router)
app.include_router(storage_router)
app.include_router(system_config_router)
app.include_router(workspace_router)
app.include_router(reflections_router)


@app.websocket("/ws/speech-recognition")
async def speech_recognition(websocket: WebSocket):
    # TODO: find a way of authentication for websocket
    await websocket.accept()
    await init_speech_recognition(websocket)


registry = get_registry()
# @@@ Pass auth_callback to enable authentication for /polycli/api/trigger-sync
mount_control_panel(
    app, registry, prefix="/polycli", auth_callback=auth.verify_access_token
)

# ========== Main ==========

if __name__ == "__main__":
    import uvicorn

    print("\n" + "=" * 60)
    print("🎭 Ink & Memory FastAPI Server")
    print(f"🧾 Version: {BACKEND_VERSION}")
    print("=" * 60)
    print("\n📚 API Endpoints:")
    print("    GET  /api/health         - Health check")
    print("  Auth & User:")
    print("    POST /api/register        - Register new user")
    print("    POST /api/login           - Login")
    print("    GET  /api/me              - Get current user")
    print("  Data Storage:")
    print("    POST /api/sessions        - Save session")
    print("    GET  /api/sessions        - List sessions")
    print("    GET  /api/sessions/{id}   - Get session")
    print("    DELETE /api/sessions/{id} - Delete session")
    print("    POST /api/pictures        - Save daily picture")
    print("    GET  /api/pictures        - List pictures")
    print("    GET  /api/pictures/{date}/full - Get full picture by date")
    print("    GET  /api/preferences     - Get user preferences")
    print("    POST /api/preferences     - Save preferences")
    print("    GET  /api/reports         - Get analysis reports")
    print("    POST /api/reports         - Save report")
    print("  Configuration:")
    print("    GET  /api/default-voices  - Get default voice configs")
    print("  Deck & Voice Management:")
    print("    GET  /api/decks           - List all decks")
    print("    GET  /api/decks/{id}      - Get deck with voices")
    print("    POST /api/decks           - Create deck")
    print("    PUT  /api/decks/{id}      - Update deck")
    print("    DELETE /api/decks/{id}    - Delete deck")
    print("    POST /api/decks/{id}/fork - Fork deck")
    print("    POST /api/voices          - Create voice")
    print("    PUT  /api/voices/{id}     - Update voice")
    print("    DELETE /api/voices/{id}   - Delete voice")
    print("    POST /api/voices/{id}/fork - Fork voice")
    print("  Friend System:")
    print("    POST /api/friends/invite/generate - Generate invite code")
    print("    POST /api/friends/invite/use      - Use invite code")
    print("    GET  /api/friends/requests        - Get friend requests")
    print("    POST /api/friends/requests/{id}/accept - Accept request")
    print("    POST /api/friends/requests/{id}/reject - Reject request")
    print("    GET  /api/friends                 - Get friends list")
    print("    DELETE /api/friends/{id}          - Remove friend")
    print("    GET  /api/friends/{id}/timeline   - Get friend's timeline")
    print("    GET  /api/friends/{id}/pictures/{date}/full - Get friend's full picture")
    print("\n  Claude Agent:")
    print("    POST /api/claude-agent                 - Stream agent response (SSE)")
    print("    GET  /api/claude-agent/chat-history    - Get recent sessions for context")
    print("    POST /api/claude-agent/message-latency - Record message latency metrics")
    print("    GET  /api/claude-agent/session         - Get active session snapshot")
    print("    DELETE /api/claude-agent/session       - Close active session")
    print("    POST /api/claude-agent/tool-confirm    - Resolve pending tool confirmation")
    print("\n  PolyCLI (AI Functions):")
    print("    /polycli                  - Control panel UI")
    print("    /polycli/api/trigger-sync - Direct sync API")
    print("       Sessions: analyze_text, chat_with_voice,")
    print("                 get_writing_suggestion, analyze_echoes,")
    print("                 analyze_traits, analyze_patterns,")
    print("                 generate_daily_picture")
    print("\n  Documentation:")
    print("    /docs                     - Auto-generated API docs")
    print("=" * 60 + "\n")

    uvicorn.run(app, host="127.0.0.1", port=8765)
