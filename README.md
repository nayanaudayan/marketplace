# AI-Powered Multi-Vendor Marketplace

React + TypeScript + FastAPI + PostgreSQL/pgvector marketplace where shoppers describe what they need in plain
language ("lightweight laptop for programming, 16GB RAM, under ₹70,000") and get verified, explained matches.

Architecture: modular monolith. Source of truth for price, stock, orders and payments is always PostgreSQL;
the LLM only *understands* the request and *explains* results, it never decides facts.

```
frontend/   React 18, TS, Tailwind, shadcn-style UI, TanStack Query, React Router, Playwright e2e
backend/    FastAPI, SQLAlchemy 2, Alembic, Celery, pgvector
  app/core/       config, db, JWT/argon2 security, deps, Redis cache + rate limit
  app/modules/    auth users sellers categories products inventory cart wishlist orders payments reviews admin ai_search
  app/ai/         providers (gemini/ollama/offline) · agents (query understanding) · embeddings · retrieval (hybrid, verify)
                  ranking · rag (explanations) · tools (validated tool registry) · prompts
  app/workers/    Celery app + tasks (embedding indexing, expiring unpaid orders)
API_CONTRACT.md   the REST contract shared by frontend and backend
```

## Run with Docker

```bash
cp .env.example .env              # defaults work for local dev
docker compose up --build
docker compose exec backend python -m app.seed     # demo catalogue + accounts
```

Storefront (customers + sellers) http://localhost:3000 · **Admin console http://localhost:3001** · API docs http://localhost:8000/docs.
If a port is taken, set `BACKEND_PORT`, `FRONTEND_PORT`, `ADMIN_PORT` or `POSTGRES_HOST_PORT` in `.env`.

### Separate admin app
The admin console is the same frontend code built with `VITE_APP_MODE=admin`: it contains only the admin sign-in and
dashboard (no shop pages, no sign-up) and refuses non-admin logins. The storefront build has no admin pages and refuses
admin logins. Each is its own origin, so their browser sessions are separate. Both talk to the same API; the backend
still enforces roles on every `/admin` endpoint. Locally: `npm run dev:admin` (port 5184). In production serve it on its
own hostname (e.g. `admin.example.com`) and restrict who can reach it (VPN / IP allow-list) at your reverse proxy.

Seed accounts: `admin@example.com / Admin@123` · `seller@example.com / Seller@123` · `customer@example.com / Customer@123`
(`seller2@example.com` runs Gadget World and `urban@example.com` runs Urban Threads, the t-shirt store; both use `Seller@123`.)
On an existing database, re-running `python -m app.seed` adds the t-shirt range without touching other data.

## Run locally (no Docker for the app)

```bash
# database with pgvector
docker run -d --name marketplace-pg -e POSTGRES_USER=marketplace -e POSTGRES_PASSWORD=marketplace \
  -e POSTGRES_DB=marketplace -p 5433:5432 pgvector/pgvector:pg16

cd backend
python -m venv .venv && .venv/Scripts/activate        # source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000

cd ../frontend
npm install
npm run dev                                            # http://localhost:5173, proxies /api to :8000
# backend elsewhere?  VITE_PROXY_TARGET=http://localhost:8001 npm run dev
```

Without a worker, `CELERY_EAGER=true` (the default outside Docker) runs background tasks inline, so no Redis is needed.
Redis is optional everywhere: caching and rate limiting fall back to in-process behaviour.

## AI configuration

| Variable | Values | Notes |
|---|---|---|
| `LLM_PROVIDER` | `mock` (default) · `gemini` · `ollama` | `mock` = rule-based extraction + templated explanations, no network |
| `EMBEDDING_PROVIDER` | `hash` (default) · `gemini` · `ollama` | `hash` is a deterministic **dev-only** lexical embedder |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | | Gemini for both extraction/explanations (and embeddings if selected) |
| `EMBEDDING_DIM` | 768 | Must match the model **and** the `vector(768)` column; changing it needs a migration + reindex |

If the LLM is down or returns invalid JSON, search transparently falls back to the rule-based extractor and templated
explanations. If embeddings fail, search degrades to keyword + hard filters.
After switching embedding provider/model, re-embed everything:
`python -c "from app.core.database import SessionLocal; from app.ai.embeddings.service import reindex_all; print(reindex_all(SessionLocal()))"`
(the content hash includes the model name, so changed models are re-embedded automatically).

### How a search works
1. **Grounding.** The app reads which spec fields the active listings really have (`ram_gb`, `storage_gb`, `weight_kg`, `battery_hours`, `noise_cancelling`, …), their type, range and categories (`app/ai/retrieval/catalog.py`, cached 60 s). That schema is given to the LLM, and the rule-based extractor uses it too, so neither can ask for a field no listing has.
2. The LLM (or rules) extracts `{category, brand, min/max price, specs[], preferences[], usage, keywords}` → validated with Pydantic, then **grounded**: unknown fields, impossible operators and unknown categorical values are dropped; category/brand are resolved against real rows; the result is merged with conversation context.
   - `specs` are hard requirements ("16GB RAM", "512GB SSD", "under 1.5 kg", "noise cancelling"; 1TB → 1024 GB).
   - `preferences` are soft wishes ("lightweight" → lowest `weight_kg`, "good battery backup" → highest battery value) used only for ranking, and only for fields the matched category has.
3. **Hard constraints in SQL**: active product, approved seller, active listing, in stock, price range, category tree, and every spec requirement. A listing that lacks a required field is excluded, never guessed.
4. Within that set: pgvector cosine search + PostgreSQL full-text search → reciprocal-rank fusion.
5. Ranking blends semantic, keyword, spec-keyword match, category match, (shrunk) rating and the preference score (percentile of the real values among the candidates). Weights are in `app/ai/ranking/ranker.py`.
6. Verification: cheapest in-stock offer per product from the database. Products with no valid offer are dropped.
7. Explanations are generated from those verified facts only, and quote the real spec values ("weight 0.99 kg (best among these)").

## Tests

```bash
cd backend && pytest                 # needs the pgvector Postgres above; uses a separate marketplace_test database
cd frontend && npm run e2e           # Playwright; needs the backend running (see e2e/ for env)
```

## Security notes
- Argon2id passwords; short-lived access JWT + rotating refresh tokens stored hashed server-side, with reuse detection.
- `ENVIRONMENT=production` refuses to start with default `JWT_SECRET` / `PAYMENT_WEBHOOK_SECRET`.
- Payment results are only trusted via the HMAC-verified webhook path (`X-Signature`); the mock gateway endpoint is disabled in production.
- LLM output is validated; the LLM cannot run SQL; tools are a fixed registry with validated arguments; prompts treat user and product text as untrusted data.
- Inventory uses row locks (`SELECT … FOR UPDATE`, ordered) with a reserve → commit/release model; covered by a concurrency test.

## Known gaps / next steps
- **Payments:** only the mock provider is implemented; Razorpay/Stripe adapters need real credentials. Refunds are simulated (status change only).
- **Image storage:** sellers upload files (JPEG/PNG/WebP/GIF, ≤5 MB, type checked by content) and they are stored on local disk (`UPLOAD_DIR`, a Docker volume in compose) and served from `/api/v1/media/`. For multiple backend replicas or production, swap this for S3-compatible storage; nothing does that yet. Images can only be added when creating a product, not edited afterwards.
- **Agent loop:** the validated tool registry (`app/ai/tools`) powers `/ai/compare`; an LLM-driven multi-step tool-calling loop (and LangGraph) is Phase 6.
- **Semantic thresholds** (`min_similarity` per embedding provider) are untuned defaults; build the benchmark set from spec §25.3 before trusting them.
- Not built: OpenTelemetry, seller reports/commission payouts, dispute handling, email notifications.
- Pre-payment cart items are not restored if an order is cancelled (the customer re-adds them).
