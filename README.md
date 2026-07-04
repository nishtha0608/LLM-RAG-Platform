# RAG Platform

A production-grade Retrieval-Augmented Generation platform: FastAPI backend, PostgreSQL for
relational data, Qdrant for vector search, JWT auth, Docker/Kubernetes deployment, and CI/CD.

## Architecture

```
Client -> FastAPI (JWT auth) -> Services -> Repositories -> PostgreSQL (users, docs, chat)
                              -> RAG service -> Embeddings -> Qdrant (vector search)
                                             -> LLM provider (Anthropic Claude or local Ollama)
```

- **API layer** (`app/api/`): FastAPI routers, dependency injection, request/response schemas.
- **Service layer** (`app/services/`): auth, ingestion, embeddings, LLM generation, RAG orchestration.
- **Repository layer** (`app/repositories.py`): SQLAlchemy async data access, isolated from services.
- **Vector store** (`app/vectorstore.py`): Qdrant client wrapped behind a `Protocol`, swappable.
- **LLM provider** (`app/services/llm.py`): Anthropic Claude by default, or a local Ollama server
  for zero-cost/offline development, selected via `LLM_PROVIDER`.

## Quickstart (Docker)

```bash
cp .env.example .env          # fill in ANTHROPIC_API_KEY if using LLM_PROVIDER=anthropic
docker compose up --build
uv run alembic upgrade head    # run against the containerized Postgres
```

API docs: http://localhost:8000/docs (disabled outside `dev`/`staging`).

## Local development

```bash
uv sync --all-groups
cp .env.example .env
docker compose up -d postgres qdrant   # infra only
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

All configuration is via environment variables (see `.env.example` / `app/config.py`), including
`LLM_PROVIDER` (`anthropic` | `ollama`), chunking/retrieval tuning, and rate limits.
# LLM-RAG-Platform
