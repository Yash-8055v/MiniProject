# TruthCrew — AI-Powered Misinformation Detection

> रुकें। सोचें। जाँचें। — Stop. Think. Verify.

TruthCrew is an agentic AI framework for multimodal misinformation detection, verification, and awareness — built for India's linguistic diversity. It supports **English, Hindi, and Marathi** and can verify text claims, images, and videos.

- **Live Demo:** <https://truthcrew.vercel.app>
- **Telegram Bot:** <https://t.me/Truth_Crew_Bot>
- **GitHub:** <https://github.com/Yash-8055v/MiniProject>

---

## Features

- **Text Claim Verification** — Analyze any news headline or claim using a 4-agent AI pipeline
- **Media Verification** — Detect AI-generated images and videos using Groq Vision (Llama 4 Scout)
- **Multilingual Output** — Explanations in English, Hindi, and Marathi via Sarvam AI
- **Trending Misinformation** — Auto-refreshed daily pipeline tracks viral false claims across India
- **5-Layer Credibility Scoring** — Source tier, count, alignment, verifiability, and cross-agreement
- **Telegram Bot** — Full fact-checking via Telegram with voice input (STT) and voice reply (TTS)
- **MongoDB Caching** — Analysis results cached to avoid redundant API calls
- **Google Trends Heatmap** — Regional spread of misinformation across Indian states

---

## Architecture

```text
User Input (Text / Image / Video / Voice)
              ↓
    FastAPI Backend (Python)
              ↓
    ┌─────────────────────────────────────┐
    │         CrewAI Agent Pipeline        │
    │                                     │
    │  1. Search Agent                    │
    │     └─ 3-layer web search           │
    │        (trusted → open → merge)     │
    │                                     │
    │  2. Analyst Agent                   │
    │     └─ Evidence evaluation          │
    │                                     │
    │  3. Writer Agent                    │
    │     └─ Verdict + explanation (EN)   │
    │                                     │
    │  4. Sarvam Language Agent           │
    │     └─ Hindi + Marathi translation  │
    └─────────────────────────────────────┘
              ↓
    5-Layer Credibility Scorer
              ↓
    MongoDB Cache + Response
```

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| Backend | FastAPI + Python 3.11 |
| AI Agents | CrewAI |
| LLM | Groq (Llama 3.3 70B) |
| Vision AI | Groq Vision (Llama 4 Scout) |
| Voice AI | Sarvam AI (STT + TTS) |
| Database | MongoDB Atlas |
| Scheduler | APScheduler |
| Telegram Bot | python-telegram-bot v20 |
| Deployment | Vercel (frontend) + Render (backend) |

---

## Project Structure

```text
MiniProject/
├── backend/
│   ├── config/
│   │   ├── agents.yaml              # CrewAI agent definitions
│   │   └── tasks.yaml               # CrewAI task definitions
│   ├── crew/
│   │   ├── crew.py                  # Main pipeline (run_crew)
│   │   └── llm.py                   # Groq LLM config
│   ├── database/
│   │   └── db.py                    # MongoDB connection + caching
│   ├── server/
│   │   ├── api.py                   # FastAPI routes
│   │   ├── media_verification.py    # Image/video AI detection
│   │   ├── credibility_scorer.py    # 5-layer credibility scoring
│   │   └── heatmap.py               # Google Trends regional data
│   ├── telegram_bot/
│   │   ├── bot.py                   # Bot builder + handler registration
│   │   ├── handlers.py              # Command + message handlers (STT/TTS)
│   │   ├── formatter.py             # MarkdownV2 message formatting
│   │   ├── rate_limiter.py          # Per-user rate limiting
│   │   └── user_prefs.py            # Language preference store
│   ├── tools/
│   │   └── web_search.py            # 3-layer search (trusted + open)
│   ├── trending/
│   │   └── pipeline.py              # Daily trending claim refresh
│   ├── .envExample                  # Environment variable template
│   ├── main.py                      # Uvicorn entrypoint
│   └── pyproject.toml
│
└── frontend/TruthCrew/
    ├── src/
    │   ├── components/
    │   │   ├── Navigation.tsx
    │   │   ├── Footer.tsx
    │   │   ├── ScoreBreakdown.tsx    # 5-layer credibility UI
    │   │   ├── VoiceInput.tsx        # Mic recording + STT
    │   │   └── LanguageSelector.tsx
    │   ├── pages/
    │   │   ├── Home.tsx
    │   │   ├── Analyze.tsx           # Text claim verification
    │   │   ├── MediaVerification.tsx # Image + video detection
    │   │   ├── Trending.tsx
    │   │   └── About.tsx
    │   └── services/
    │       └── api.ts                # All API calls (fetch-based)
    └── package.json
```

---

## Environment Variables

Create `backend/.env` from `backend/.envExample`:

```env
# MongoDB
MONGO_URI=mongodb+srv://...

# Groq (LLM + Vision)
GROQ_API_KEY=gsk_...

# Sarvam AI (STT + TTS)
SARVAM_API_KEY=sk_...

# Telegram Bot
TELEGRAM_BOT_TOKEN=...

# HuggingFace (optional)
HUGGING_FACE_API_TOKEN=hf_...

# Deployment
WEBSITE_URL=https://truthcrew.vercel.app
BACKEND_URL=http://localhost:8000
```

---

## Local Setup

### Backend

```bash
cd backend
pip install uv
uv sync
cp .envExample .env   # fill in your keys
uv run python main.py
```

Server runs at: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

### Frontend

```bash
cd frontend/TruthCrew
npm install
npm run dev
```

App runs at: `http://localhost:5173`

---

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | `/verify` | Verify a text claim (full pipeline) |
| POST | `/api/detect-image` | Detect AI-generated image |
| POST | `/api/detect-video` | Detect AI-generated video |
| POST | `/api/agents/stt` | Speech-to-text (Sarvam AI) |
| POST | `/api/agents/tts` | Text-to-speech (Sarvam AI) |
| GET | `/api/trending-claims` | Get top trending misinformation |
| GET | `/health` | Health check + last refresh time |

---

## 5-Layer Credibility Scoring

| Layer | Weight | Description |
| --- | --- | --- |
| Source Tier | 35% | Government > International > National > Regional |
| Source Count | 20% | More sources = higher confidence |
| Evidence Alignment | 25% | % of results from trusted domains |
| Claim Verifiability | 10% | Specificity (numbers, dates, names) |
| Cross Agreement | 10% | Multiple trusted sources corroborating |

---

## Telegram Bot Commands

| Command | Description |
| --- | --- |
| `/start` | Welcome message |
| `/check <claim>` | Fact-check a claim |
| `/trending` | Top 5 trending misinformation |
| `/language` | Switch response language (EN/HI/MR) |
| Voice message | Auto STT → fact-check → TTS voice reply |

---

## Deployment

- **Frontend** → Vercel (auto-deploy from `main` branch)
- **Backend** → Render (Web Service, `python main.py`)

---

## Disclaimer

TruthCrew assists in evaluating the credibility of claims but does not guarantee absolute truth. Results depend on publicly available information and AI interpretation. Always verify with primary sources.

---

## License

Built for educational and research purposes — B.Tech AI & Data Science, National Level Project Showcase.
