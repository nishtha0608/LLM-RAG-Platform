# RAG Platform

A production-grade Retrieval-Augmented Generation platform: FastAPI backend, PostgreSQL for
relational data, Qdrant for vector search, JWT auth, a built-in web UI, Docker/Kubernetes
deployment, and CI/CD.

Upload documents, ask questions in a chat interface, and get answers grounded in your own
content with citations back to the source file — running fully locally (Ollama) or against
Anthropic Claude.

## Features

- **JWT auth** — register/login, access + refresh tokens
- **Document ingestion** — upload PDF/text files, automatic chunking and embedding
- **RAG chat** — multi-turn chat sessions with streaming responses and per-answer source citations
- **Pluggable LLM provider** — local Ollama (free, offline) or Anthropic Claude (`LLM_PROVIDER`)
- **Built-in web UI** — a single-page frontend served directly by the API, no separate build step
- **Production tooling** — rate limiting, structured logging, OpenTelemetry tracing, health checks
- **Deployable** — Docker Compose for local dev, Kustomize overlays for dev/staging/prod on Kubernetes

## Architecture

```
Browser (built-in UI) ─┐
                        ▼
                 FastAPI (JWT auth)
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
   Auth service   Document service   RAG service
        │               │               │
        ▼               ▼               ▼
   PostgreSQL     Embeddings ──────► Qdrant (vector search)
   (users, docs,        │
    chat history)        ▼
                  LLM provider
              (Ollama, local — or
               Anthropic Claude)
```

- **API layer** (`app/api/`): FastAPI routers, dependency injection, request/response schemas.
- **Service layer** (`app/services/`): auth, ingestion, embeddings, LLM generation, RAG orchestration.
- **Repository layer** (`app/repositories.py`): SQLAlchemy async data access, isolated from services.
- **Vector store** (`app/vectorstore.py`): Qdrant client wrapped behind a `Protocol`, swappable.
- **LLM provider** (`app/services/llm.py`): local Ollama by default (zero-cost/offline), or
  Anthropic Claude, selected via `LLM_PROVIDER`.
- **Frontend** (`app/static/index.html`): a dependency-free HTML/JS page served by FastAPI itself
  at `/` — no separate frontend build or dev server needed.

## Quickstart (Docker)

```bash
cp .env.example .env              # fill in ANTHROPIC_API_KEY if using LLM_PROVIDER=anthropic
docker compose up -d --build
docker compose exec api alembic upgrade head
```

If running the default local `LLM_PROVIDER=ollama`, pull a model into the Ollama container once:

```bash
docker compose exec ollama ollama pull llama3.2:1b   # or a larger model if you have the hardware
```

Then open:

- **Web UI**: http://localhost:8000/
- **API docs**: http://localhost:8000/docs (disabled outside `dev`/`staging`)

## Local development

```bash
uv sync --all-groups
cp .env.example .env
docker compose up -d postgres qdrant ollama   # infra only
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Testing

```bash
uv run pytest                 # unit + integration (spins up Postgres via testcontainers)
uv run ruff check .
uv run mypy app
```

## Deployment

- `k8s/base/` holds the Kustomize base (Deployment, Service, HPA, Ingress, PDB).
- `k8s/overlays/{dev,staging,prod}/` patch replicas, namespace, and image tag per environment.
- `.github/workflows/ci.yaml` runs lint, typecheck, tests, a Trivy security scan, and builds/pushes
  the image on `main`.
- `.github/workflows/cd.yaml` deploys to prod via `kubectl apply -k` with automatic rollback on
  failed rollout.

Copy `k8s/base/secret.yaml.example` to a real Secret (or, preferably, use External Secrets
Operator / Sealed Secrets in production instead of committing rendered Secrets to Git).

## Configuration

All configuration is via environment variables (see `.env.example` / `app/config.py`).

| Variable | Default | Description |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama` (local, free) or `anthropic` (hosted, needs API key) |
| `ANTHROPIC_API_KEY` | — | Required if `LLM_PROVIDER=anthropic` |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL (use `http://ollama:11434` in Docker) |
| `OLLAMA_MODEL` | `llama3.2:1b` | Model tag to use; must be pulled into Ollama first |
| `OLLAMA_NUM_CTX` | `8192` | Context window passed to Ollama, so retrieved chunks aren't truncated |
| `EMBEDDING_MODEL` | `BAAI/bge-small-en-v1.5` | Sentence-transformers model for chunk/query embeddings |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `200` | Document chunking parameters |
| `RETRIEVAL_TOP_K` | `5` | Number of chunks retrieved per query |
| `RATE_LIMIT_PER_MINUTE` | see `app/config.py` | Per-client request rate limit |

### Choosing a local model

`llama3.2:1b` is fast (CPU-friendly, ~seconds per reply) but has limited reasoning ability.
`llama3.1` (8B) is noticeably more accurate but can take minutes per reply on CPU-only Docker.
Pick based on your hardware: `docker compose exec ollama ollama pull <model>`, then set
`OLLAMA_MODEL` to match.

## Troubleshooting

- **Chat requests hang or return `ERR_INCOMPLETE_CHUNKED_ENCODING`**: the Ollama model is still
  generating and hit the client timeout, or no model has been pulled yet — run
  `docker compose exec ollama ollama list` to check, and pull one if empty.
- **`GET /` returns 404**: make sure you're on a build that includes `app/static/index.html` and
  that `app/main.py` mounts it; rebuild the image if you pulled an older commit.
- **Port already in use**: `docker-compose.yml` binds `8000` (API), `5432` (Postgres), `6333`
  (Qdrant), and `11434` (Ollama) on the host. If another project is using one of these, change the
  host-side port mapping in `docker-compose.yml`.
