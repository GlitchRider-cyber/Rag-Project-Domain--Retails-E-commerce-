# Brand RAG Assistant: Development Guide

A Retrieval-Augmented Generation (RAG) assistant for **Retail & E-commerce** that answers customer questions **only from a brand's own knowledge base** (products, FAQs, policies, size guides, care instructions), with source citations.

**Status:** MVP, deployed, not built for scale.
**Stack:** Python + FastAPI, React (Vite), PostgreSQL + pgvector, Gemini API. No LangChain or LangGraph.

---

## 1. Problem and Goals

Generic brand chatbots answer from the open internet. They hallucinate prices, return windows, stock, and policies. This project fixes that.

**Goals**

- Answer strictly from the brand's knowledge base.
- Cite sources for every claim.
- Refuse or fall back to support when the knowledge base has no answer.
- Stream responses in a clean chat UI.
- Ship a deployed, demo-ready MVP.

**Non-goals (MVP)**

- Multi-tenant brands, auth for end users, horizontal scaling.
- Order tracking or live inventory integration.
- Reranker models and fine-tuning.

---

## 2. Architecture

```
React (Vite) chat UI
   |  POST /chat  (SSE streaming)
   v
FastAPI backend
   1. Query rewrite (Gemini hydrogen): follow-up -> standalone question
   2. Embed query (mention in key decisions, query task type)
   3. Hybrid retrieval in Postgres: pgvector + full-text search, merged with RRF, top 5-6
   4. Relevance threshold: if too low, return fallback answer
   5. Prompt build: system rules + numbered context chunks + recent history
   6. Gemini Flash generates grounded answer with [1][2] citations, streamed
   v
PostgreSQL + pgvector (Supabase or Neon)
   documents | chunks | chat_sessions | messages | feedback
```

**Offline ingestion:** load -> clean -> chunk -> embed -> upsert (script, plus admin endpoint).

---

## 3. Key Decisions

| Component     | Decision                                                                                                                                          | Rationale                                                                        |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------- |
| LLM           | Gemini hydrogen free version via api otherwise ask me for model (check current model name in docs)                                                | Fast, cheap, free tier fits an MVP                                               |
| Embeddings    | sentence-transformers/all-MiniLM-L6-v2                                                                                                            | Same API key; better retrieval quality                                           |
| Database      | PostgreSQL + pgvector (Supabase/Neon)                                                                                                             | Vectors, metadata filters, keyword search, and chat history in one persistent DB |
| Retrieval     | Hybrid (vector + full-text) with Reciprocal Rank Fusion                                                                                           | SKUs, product names, and sizes need exact matching                               |
| Chunking      | Structure-aware: one chunk per product; policies split by heading; ~300-500 tokens make chunks carefully so that no data is loosed, small overlap | Never split a price or policy clause                                             |
| Orchestration | Plain Python modules                                                                                                                              | Full control, easy to explain                                                    |
| Streaming     | Server-Sent Events                                                                                                                                | Simple in FastAPI and React                                                      |
| Reranker      | Skipped for MVP                                                                                                                                   | Add later if retrieval quality demands it                                        |
| Backend       | FastAPI + Pydantic + Docker                                                                                                                       |                                                                                  |
| Frontend      | React + Vite                                                                                                                                      |                                                                                  |
| Deploy        | Backend: Render . Frontend: render. DB: Supabase                                                                                                  | Free or cheap tiers                                                              |

---

## 4. Repository Layout

```
rag-brand-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI app, CORS, routers
│   │   ├── config.py          # env settings (pydantic-settings)
│   │   ├── db.py              # connection pool, schema helpers
│   │   ├── schemas.py         # request/response models
│   │   ├── ingest/
│   │   │   ├── loaders.py     # read products.json, md policies, faqs
│   │   │   ├── chunker.py     # structure-aware chunking
│   │   │   └── pipeline.py    # embed + idempotent upsert
│   │   ├── retrieval/
│   │   │   ├── embed.py       # Gemini embedding calls
│   │   │   ├── search.py      # vector + FTS + RRF
│   │   │   └── rewrite.py     # query rewriting
│   │   ├── llm/
│   │   │   ├── prompts.py     # system prompt, templates
│   │   │   └── generate.py    # Gemini streaming generation
│   │   └── routes/
│   │       ├── chat.py
│   │       ├── ingest.py
│   │       ├── sources.py
│   │       ├── feedback.py
│   │       └── health.py
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── components/        # ChatWindow, MessageBubble, CitationChip, SourcePanel, ProductCard
│       ├── hooks/useChat.js   # SSE streaming state
│       ├── api.js
│       └── App.jsx
├── data/
│   ├── products.json
│   ├── policies/*.md          # returns, shipping, warranty, privacy
│   └── faqs.md
├── eval/
│   ├── golden_set.json
│   └── run_eval.py
├── .env.example
└── README.md
```

---

## 5. Data Model

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (
  id            SERIAL PRIMARY KEY,
  doc_type      TEXT NOT NULL,          -- product | policy | faq | guide
  title         TEXT NOT NULL,
  source_url    TEXT,
  content_hash  TEXT NOT NULL,          -- for idempotent re-ingestion
  metadata      JSONB DEFAULT '{}',
  updated_at    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE chunks (
  id            SERIAL PRIMARY KEY,
  document_id   INT REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index   INT NOT NULL,
  content       TEXT NOT NULL,
  section       TEXT,
  metadata      JSONB DEFAULT '{}',     -- category, price, sku, etc.
  embedding     VECTOR(768),
  tsv           TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
);

CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);

CREATE TABLE chat_sessions (id UUID PRIMARY KEY, created_at TIMESTAMPTZ DEFAULT now());

CREATE TABLE messages (
  id          SERIAL PRIMARY KEY,
  session_id  UUID REFERENCES chat_sessions(id),
  role        TEXT NOT NULL,            -- user | assistant
  content     TEXT NOT NULL,
  sources     JSONB,                    -- chunk ids cited
  created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE feedback (
  id          SERIAL PRIMARY KEY,
  message_id  INT REFERENCES messages(id),
  rating      SMALLINT NOT NULL,        -- 1 up, -1 down
  comment     TEXT,
  created_at  TIMESTAMPTZ DEFAULT now()
);
```

---

## 6. API Contract

| Method | Endpoint              | Purpose                                                                                  |
| ------ | --------------------- | ---------------------------------------------------------------------------------------- |
| POST   | `/chat`               | Body: `{session_id, message}`. Streams SSE: `token` events, then a final `sources` event |
| POST   | `/ingest`             | Admin-only (password header). Runs ingestion pipeline                                    |
| GET    | `/sources/{chunk_id}` | Returns the source passage for a citation chip                                           |
| POST   | `/feedback`           | Thumbs up/down on a message                                                              |
| GET    | `/health`             | Liveness and DB check                                                                    |

---

## 7. RAG Pipeline Details

### 7.1 Ingestion

1. Load products (JSON), policies and FAQs (Markdown).
2. Clean text, normalize whitespace.
3. Chunk: one chunk per product (name, price, description, specs, care); policies split by heading; FAQs one Q&A per chunk.
4. Embed with the **document** task type, in batches.
5. Upsert by `content_hash`; skip unchanged documents. Re-runnable and idempotent.

### 7.2 Query-time retrieval

1. Rewrite the question using the last few turns.
2. Embed with the **query** task type.
3. Run vector search (cosine) and full-text search; take top ~20 from each.
4. Merge with Reciprocal Rank Fusion; keep top 5-6.
5. Optional metadata filter by `doc_type` when the intent is obvious (returns, shipping).
6. If the best score is below the threshold, skip generation and return the fallback message.

### 7.3 Generation prompt rules

- Answer only from the numbered context. Do not use outside knowledge.
- Cite with `[n]` after each claim.
- Never invent prices, stock status, discounts, or delivery dates.
- If the context lacks the answer, say so and point to support.
- Keep answers short, friendly, and on-brand.
- Refuse out-of-scope requests politely.

---

## 8. Frontend Requirements

- Chat widget style layout with streaming responses.
- Citation chips under each answer; clicking opens the source passage panel.
- Suggested starter questions.
- Thumbs up/down per answer.
- Loading, error, and empty states.
- Responsive for mobile.
- Optional: product cards when an answer references a product.

---

## 9. Environment Variables

```
GEMINI_API_KEY=
GEMINI_CHAT_MODEL=
GEMINI_EMBED_MODEL=
DATABASE_URL=
ADMIN_PASSWORD=
ALLOWED_ORIGINS=http://localhost:5173
RETRIEVAL_TOP_K=6
RELEVANCE_THRESHOLD=
```

---

## 10. Development Phases

### Phase 1: Foundation

- [ ] Choose brand (real with scraped public pages, or fictional with generated data)
- [ ] Create `data/` with 30-50 products, policies, FAQs
- [ ] Set up Supabase/Neon, enable pgvector, run schema
- [ ] Scaffold FastAPI app, config, DB connection

### Phase 2: Ingestion

- [ ] Loaders and chunker
- [ ] Embedding client with batching and retry
- [ ] Idempotent upsert; CLI command and `/ingest` endpoint

### Phase 3: Retrieval

- [ ] Vector search, FTS, RRF merge
- [ ] Threshold tuning with sample queries
- [ ] Query rewrite step

### Phase 4: Chat API

- [ ] Prompt templates and guardrails
- [ ] Streaming `/chat` over SSE
- [ ] Persist messages and cited sources
- [ ] `/sources`, `/feedback`, `/health`

### Phase 5: Frontend

- [ ] Vite + React setup, `useChat` SSE hook
- [ ] Chat UI, citation chips, source panel
- [ ] Starter questions, feedback buttons

### Phase 6: Evaluation

- [ ] Golden set of 30-50 Q&A pairs (include unanswerable and out-of-scope questions)
- [ ] Measure retrieval hit rate@k
- [ ] Check faithfulness (manual or LLM-judged)
- [ ] Tune chunking, threshold, and prompt

### Phase 7: Deployment

- [ ] Dockerize backend; deploy to Render/Railway/Cloud Run
- [ ] Deploy frontend to Vercel; set CORS and API URL
- [ ] Run ingestion against production DB
- [ ] Rate limiting and admin password on `/ingest`
- [ ] README with architecture diagram, setup steps, demo link

---

## 11. Evaluation Plan

| Metric               | How                                                            |
| -------------------- | -------------------------------------------------------------- |
| Retrieval hit rate@k | Does the expected source chunk appear in the top k?            |
| Faithfulness         | Are all claims supported by retrieved context?                 |
| Answer correctness   | Compare to golden answer                                       |
| Refusal accuracy     | Out-of-scope and unanswerable questions get a correct fallback |
| Latency              | Time to first token and total time                             |

Golden set mix: product lookups, comparisons, policy questions, multi-turn follow-ups, SKU or size exact-match queries, unanswerable questions, and off-topic questions.

---

## 12. Risks and Mitigations

| Risk                                | Mitigation                                                                            |
| ----------------------------------- | ------------------------------------------------------------------------------------- |
| Hallucinated prices or policies     | Strict grounded prompt, threshold fallback, eval checks                               |
| Poor retrieval on SKUs and sizes    | Hybrid search with full-text                                                          |
| Gemini free-tier rate limits        | Batch embeddings, retry with backoff, cache embeddings                                |
| Free-tier DB or host sleeping       | Health check, keep-alive ping, note cold start in README                              |
| Prompt injection through user input | Treat context and user text as data; fixed system rules; refuse instruction overrides |
| Stale knowledge base                | Content-hash re-ingestion, `updated_at` shown in sources                              |

---

## 13. Definition of Done (MVP)

- Deployed frontend and backend reachable by a public link.
- Answers are grounded with working citations.
- Unanswerable and out-of-scope questions get a graceful fallback.
- Ingestion is re-runnable without duplicates.
- Evaluation results are documented in the README.
- README includes setup, architecture diagram, and screenshots.

---

## 14. Stretch Goals

- Product cards and image display.
- Analytics on thumbs-down and unanswered questions to find knowledge-base gaps.
- Reranker for better precision.
- Multi-brand support through a `brand_id` column.
- Embeddable widget script for any storefront.
