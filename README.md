# Ink & Memory

<p align="center">
  <img src="assets/banner.png" alt="Ink & Memory Banner" width="700"/>
</p>

<p align="center">
  <a href="README.zh.md">中文</a> · English
</p>

> *Write. Reflect. Listen to the voices within.*

**Ink & Memory** is a journaling studio inspired by the inner monologues of *Disco Elysium*. As you write, a council of distinct personas chimes in—offering perspective, asking questions, or pointing out the absurdity of it all.

This isn't just another notes app. It's a daily writing companion that saves your work, organizes your thoughts, and helps you notice patterns in your own thinking. It speaks both English and Chinese, switching seamlessly as you write.

---

## What Makes It Different

<p align="center">
  <img src="assets/writing-area.png" alt="Writing with inner voices" width="700"/>
</p>

**A clean writing space.** No toolbar clutter. Just a calm surface for your thoughts, with automatic saving so nothing gets lost.

**A council of inner voices.** As you type, different personas highlight phrases and offer their takes—from the pattern-spotting Mirror to the darkly funny Absurdist. They appear as gentle watercolor highlights in the margins, never interrupting your flow.

**Your timeline, visualized.** Every session is saved to a calendar. Each day generates a unique image from your writing—a visual diary that grows with you.

**Fully customizable.** Don't like a voice? Edit it. Want new perspectives? Create your own deck. Share your creations with the community or discover what others have made.

---

## The Voices

The voices are organized into three decks. Enable the ones that resonate; disable the rest.

### Introspection Deck
*For processing emotions and understanding yourself*

| | Voice | What it does |
|---|---|---|
| ❤️ | **Holder** | Offers gentle validation and support |
| 👁️ | **Mirror** | Reflects patterns you might not notice |
| 👊 | **Starter** | Breaks paralysis with tiny first steps |
| 🧭 | **Weaver** | Finds hidden threads connecting your thoughts |
| 🎭 | **Absurdist** | Lightens heaviness with dark humor |

### Scholar Deck
*For intellectual and academic perspectives*

| | Voice | What it does |
|---|---|---|
| 🧭 | **Linguist** | Analyzes structure, semantics, meaning |
| 👁️ | **Painter** | Focuses on imagery, aesthetics, mood |
| 💡 | **Physicist** | Applies principles of energy and systems |
| 🧠 | **Computer Scientist** | Thinks in algorithms and complexity |
| ❤️ | **Doctor** | Offers health and psychological angles |
| 🧭 | **Historian** | Provides context and historical patterns |

### Philosophy Deck
*For examining life through different lenses*

| | Voice | What it does |
|---|---|---|
| 🛡️ | **Stoic** | Emphasizes what you can and can't control |
| 💨 | **Taoist** | Points toward effortless action and flow |
| 🤔 | **Existentialist** | Asks about choice, freedom, meaning |
| 👊 | **Pragmatist** | Focuses on what actually works |

### Making Your Own

Each voice is just a system prompt, an icon, and a color. Fork any deck to customize it. Create voices that channel your favorite thinker, focus on specific aspects of your life, or just make you laugh. Share them in the community store.

---

## Getting Started

### You'll Need
- Python 3.11+ with [uv](https://github.com/astral-sh/uv)
- Node.js 18+

### Backend Setup

```bash
cd backend
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -r requirements.txt
```

Create a `models.json` file for your LLM:

```json
{
  "models": {
    "gemini-3-flash-preview": {
      "endpoint": "https://openrouter.ai/api/v1",
      "api_key": "your-key-here",
      "model": "google/gemini-3-flash-preview"
    }
  },
  "roles": {
    "voice_analysis": "gemini-3-flash-preview",
    "voice_chat": "gemini-3-flash-preview"
  }
}
```

See `backend/models.json.example` for the full set of roles and image settings.

Then start the server:

```bash
python server.py  # Runs on http://localhost:8765
```

### Manual database initialization

You need to create the SQLite tables before first launch:

```bash
cd backend
python database.py
```

### Frontend Setup

```bash
cd frontend
npm install
npm run dev  # Runs on http://localhost:5173
```

---

## How It Works

The voice system uses a **trace-based energy model**:

1. **Energy builds** as you write
2. **Threshold triggers** analysis of recent text
3. **Voices scan** for phrases that match their personality
4. **Comments appear** as watercolor highlights in the margin

This creates an organic rhythm—voices chime in naturally rather than constantly interrupting.

---

## Technical Stack

**Frontend:** React 19 + TypeScript, Vite, TipTap editor with custom extensions

**Backend:** FastAPI + Python, PolyCLI for LLM orchestration, SQLite with WAL mode

**AI:** Multi-model support (GPT-4, Claude, DeepSeek, Gemini), structured outputs via Pydantic

**Architecture:** Deck-based voice system with parent-child relationships, community store for sharing

---

## Roadmap

- More voices and community-created decks
- Richer visualizations of your writing patterns
- Mobile app for writing on the go
- Collaborative features

---

## Deployment

To deploy Ink & Memory to **Google Cloud Run** (frontend + backend as separate services, with Cloud Storage FUSE persistence for SQLite):

```bash
export GCP_PROJECT_ID=your-project-id
./deploy/google-cloud/deploy.sh setup-storage  # one-time: GCS bucket + service account
./deploy/google-cloud/deploy.sh setup-env      # one-time: secrets + env vars
./deploy/google-cloud/deploy.sh deploy         # every release
```

See [docs/deploy/overview.md](docs/deploy/overview.md) for the full guide.

---

## Contributing

This is open source. We'd love your help.

- **Found a bug?** Open an issue
- **Have an idea?** Let's discuss it
- **Want to code?** PRs welcome
- **Created a cool deck?** Share it with the community

---

<p align="center">
  <i>Your thoughts deserve to be heard—even by yourself.</i>
</p>
