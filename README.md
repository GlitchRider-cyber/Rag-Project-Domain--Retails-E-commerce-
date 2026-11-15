# Aurelia & Co. — Brand RAG Assistant

> An AI-powered shopping assistant that uses Retrieval-Augmented Generation to answer customer questions about products, policies, and FAQs for the fictional premium lifestyle brand **Aurelia & Co.**

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.11+-green.svg)
![Node](https://img.shields.io/badge/node-18+-green.svg)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Frontend (React)                         │
│               Vite · Tailwind CSS · SSE Streaming               │
│                     http://localhost:5173                        │
└──────────────────────────┬──────────────────────────────────────┘
                           │  HTTP / SSE
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│                     http://localhost:8000                        │
│                                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌───────────┐  ┌───────────┐  │
│  │  /chat   │  │  /ingest     │  │ /feedback  │  │  /health  │  │
│  │  (SSE)   │  │  (admin)     │  │            │  │           │  │
│  └────┬─────┘  └──────┬───────┘  └───────────┘  └───────────┘  │
│       │               │                                         │
│  ┌────▼───────────────▼────────────────────────────────────┐    │
│  │                  RAG Pipeline                            │    │
│  │                                                          │    │
│  │  1. Embed query (MiniLM-L6-v2, 384-dim)                 │    │
│  │  2. Vector search + full-text search (pgvector + GIN)    │    │
│  │  3. Re-rank & filter by relevance threshold              │    │
│  │  4. Build prompt with retrieved context                   │    │
│  │  5. Stream response via Gemini LLM                       │    │
│  └──────────────────────┬───────────────────────────────────┘    │
│                         │                                        │
└─────────────────────────┼────────────────────────────────────────┘
                          │
              ┌───────────▼───────────┐
              │   PostgreSQL + pgvector│
              │                       │
              │  documents  │ chunks  │
              │  (metadata) │ (text + │
              │             │  embed) │
              │  ───────────┼──────── │
              │  chat_sessions       │
              │  messages            │
              │  feedback            │
              └───────────────────────┘
```

---

## Features

- **Conversational RAG** — Ask natural-language questions about products, policies, sizing, and more
- **SSE Streaming** — Token-by-token streaming for a responsive chat experience
- **Hybrid Search** — Combines vector similarity (pgvector HNSW) with PostgreSQL full-text search
- **Inline Citations** — Clickable `[1]`, `[2]` references linking to source passages
- **Source Panel** — Slide-in panel showing the full source context for any citation
- **Session Memory** — Multi-turn conversations with chat history stored in PostgreSQL
- **Feedback System** — Thumbs-up / thumbs-down ratings on assistant responses
- **Evaluation Suite** — 35-question golden set with automated scoring (retrieval hit rate, phrase coverage, refusal accuracy, latency)
- **Graceful Refusal** — Politely declines unanswerable or off-topic questions
- **Admin Ingestion** — Password-protected endpoint to re-ingest data files on demand

---

## Tech Stack

| Layer      | Technology                                                |
| ---------- | --------------------------------------------------------- |
| Frontend   | React 18, Vite, Tailwind CSS                              |
| Backend    | FastAPI, Uvicorn, Pydantic v2                             |
| LLM        | Google Gemini (`gemini-4-hydrogen` via `google-genai`)    |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, local) |
| Database   | PostgreSQL 16 + pgvector                                  |
| Async DB   | asyncpg                                                   |
| Streaming  | Server-Sent Events (sse-starlette)                        |

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** and **npm**
- **PostgreSQL 16** with the **pgvector** extension installed
- A **Google Gemini API key** ([Get one here](https://aistudio.google.com/apikey))

---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/your-username/E-commerce-RAG.git
cd E-commerce-RAG
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in your values:

```env
GEMINI_API_KEY=your-actual-api-key
DATABASE_URL=postgresql://postgres:password@localhost:5432/aurelia_rag
ADMIN_PASSWORD=your-secure-admin-password
```

### 3. Set Up the Database

```bash
# Create the database
psql -U postgres -c "CREATE DATABASE aurelia_rag;"

# Enable pgvector extension
psql -U postgres -d aurelia_rag -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

The application will create all tables automatically on first run.

### 4. Install Backend Dependencies

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 5. Run Data Ingestion

```bash
# From the project root, with the backend venv activated
python -m backend.app.ingest.runner
```

This loads products, policies, and FAQs from `data/` into the database with embeddings.

### 6. Start the Backend

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 7. Install Frontend Dependencies & Start

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at **http://localhost:5173**.

---

## API Documentation

Once the backend is running, interactive docs are available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints

| Method | Endpoint    | Description                        | Auth  |
| ------ | ----------- | ---------------------------------- | ----- |
| POST   | `/chat`     | Send a message, receive SSE stream | —     |
| POST   | `/ingest`   | Re-ingest data files               | Admin |
| POST   | `/feedback` | Submit feedback on a response      | —     |
| GET    | `/health`   | Health check                       | —     |

### POST `/chat`

**Request:**

```json
{
  "message": "What cashmere products do you have?",
  "session_id": "optional-session-uuid"
}
```

**Response (SSE stream):**

```
data: {"type": "token", "content": "We"}
data: {"type": "token", "content": " have"}
data: {"type": "token", "content": " several"}
...
data: {"type": "sources", "sources": [{"title": "...", "content": "...", "doc_type": "product"}]}
data: {"type": "done", "session_id": "uuid", "message_id": 42}
```

### POST `/feedback`

```json
{
  "message_id": 42,
  "rating": 1,
  "comment": "Very helpful!"
}
```

### POST `/ingest`

```json
{
  "password": "your-admin-password"
}
```

---

## Evaluation

The `eval/` directory contains a golden evaluation set and an automated runner.

### Golden Set

[`eval/golden_set.json`](eval/golden_set.json) contains 35 test cases across 8 categories:

| Category           | Count | Description                           |
| ------------------ | ----- | ------------------------------------- |
| product_lookup     | 10    | Single product questions              |
| product_comparison | 5     | Comparing two or more products        |
| policy_question    | 5     | Shipping, returns, warranty, privacy  |
| sizing             | 3     | Size availability and recommendations |
| sku_lookup         | 3     | Exact SKU match queries               |
| unanswerable       | 4     | Questions outside the knowledge base  |
| off_topic          | 5     | Completely unrelated questions        |

### Running the Evaluation

```bash
# Make sure the backend is running first
python eval/run_eval.py

# Or specify a different backend URL
python eval/run_eval.py --base-url http://localhost:8000
```

### Metrics

| Metric             | Description                                                              |
| ------------------ | ------------------------------------------------------------------------ |
| Retrieval Hit Rate | % of answerable questions where the correct doc type appeared in sources |
| Phrase Coverage    | % of expected key phrases found in the answer                            |
| Refusal Accuracy   | % of unanswerable/off-topic questions correctly refused                  |
| Avg Latency        | Mean response time in milliseconds                                       |
| P95 Latency        | 95th percentile response time                                            |

Results are saved to `eval/results.json`.

---

## Project Structure

```
E-commerce-RAG/
├── .env.example            # Environment variable template
├── README.md               # This file
├── data/
│   ├── products.json       # 40 product entries
│   ├── faqs.md             # 25+ Q&A pairs
│   └── policies/
│       ├── returns.md      # 30-day return policy
│       ├── shipping.md     # Shipping options & rates
│       ├── warranty.md     # 1-year craftsmanship warranty
│       └── privacy.md      # Privacy policy
├── backend/
│   ├── requirements.txt
│   └── app/
│       ├── main.py         # FastAPI app & routes
│       ├── config.py       # Pydantic settings
│       ├── db.py           # Database pool & schema
│       ├── schemas.py      # Request/response models
│       ├── ingest/
│       │   ├── loaders.py  # Data file loaders
│       │   ├── chunker.py  # Text chunking logic
│       │   └── runner.py   # Ingestion orchestrator
│       ├── retrieval/
│       │   ├── embedder.py # MiniLM-L6-v2 wrapper
│       │   └── search.py   # Hybrid vector + FTS search
│       └── chat/
│           ├── prompt.py   # System prompt builder
│           └── engine.py   # Gemini streaming engine
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── index.html
│   └── src/
│       ├── App.jsx
│       ├── App.css
│       ├── index.css
│       ├── main.jsx
│       ├── api/
│       │   └── chat.js     # SSE client
│       └── components/
│           ├── ChatWindow.jsx
│           ├── MessageBubble.jsx
│           ├── CitationChip.jsx
│           ├── SourcePanel.jsx
│           └── ProductCard.jsx
└── eval/
    ├── golden_set.json     # 35 test Q&A pairs
    └── run_eval.py         # Automated evaluation runner
```

---

## Deployment

### Backend — Render

1. Create a new **Web Service** on [Render](https://render.com)
2. Connect your GitHub repository
3. Configure:
   - **Root Directory**: `backend`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables from `.env.example`

### Database — Supabase

1. Create a new project on [Supabase](https://supabase.com)
2. Enable the pgvector extension:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
3. Copy the connection string to your `DATABASE_URL` env var
4. Run the ingestion script against the remote database

### Frontend — Vercel

1. Import the project on [Vercel](https://vercel.com)
2. Configure:
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. Add an environment variable:
   - `VITE_API_URL` = your Render backend URL (e.g., `https://aurelia-rag.onrender.com`)
4. Update `ALLOWED_ORIGINS` on Render to include your Vercel domain

---

## Screenshots

> _Screenshots will be added after initial deployment._

| Screen                                        | Description                                  |
| --------------------------------------------- | -------------------------------------------- |
| ![Chat Interface](docs/screenshots/chat.png)  | Main chat interface with streaming responses |
| ![Source Panel](docs/screenshots/sources.png) | Citation source panel with full context      |
| ![Product Card](docs/screenshots/product.png) | Product information card                     |
| ![Mobile View](docs/screenshots/mobile.png)   | Responsive mobile layout                     |

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ for <strong>Aurelia & Co.</strong>
</p>
