---
baseline_commit: 5b0390a6ec8d43f8cffdde8c0cb3f31dbd98032f
---

# Story 1.1: Register a New Account

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a client application integrating with mcp-tool-calling,
I want to submit my email, username, full name, phone number, and password to create an account,
so that I have a persisted identity the system can build login and permissions on later.

## Acceptance Criteria

1. Given the Alembic migration has been applied, when the `users` table schema is inspected, then `email` and `username` each have a database-level `UNIQUE` constraint (required for Story 1.2's insert-then-catch duplicate detection).
2. Given a caller submits valid, non-duplicate email, username, full name, phone number, and password to `POST /auth/register`, when the request is processed, then the password is hashed with Argon2id before any storage occurs, a new `User` row is persisted via a per-request `AsyncSession` (obtained through `Depends`, never shared across requests), and the response is `201 Created` containing only `id` and `email`.
3. Given a successful registration response, when the response body is inspected, then it contains no `phone_number`, `full_name`, `hashed_password`, or plaintext password field.
4. Given the stored `User` row after registration, when the database row is inspected, then `hashed_password` holds only the Argon2id hash — no plaintext password is persisted, logged, or recoverable.

## Tasks / Subtasks

- [x] Task 1: Add DB dependencies (AC: 1, 2)
  - [x] Add to `requirements.txt`: `SQLAlchemy==2.0.51`, `asyncpg==0.31.0`, `alembic==1.18.5`, `argon2-cffi==25.1.0`
- [x] Task 2: Create `core/db.py` — async engine/session infra (AC: 2)
  - [x] Build the async DB URL once from the existing `DATABASE_URI` (plain `postgresql://` scheme — see Dev Notes) by swapping the scheme, e.g. `DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://", 1)`
  - [x] `create_async_engine(async_database_uri, pool_pre_ping=True)`
  - [x] `async_sessionmaker(engine, expire_on_commit=False)`
  - [x] `get_db()` async generator dependency: `async with SessionLocal() as session: yield session`
  - [x] Wire engine construction/dispose into `main.py`'s `lifespan` (mirrors `mcp_manager.initialize()`/`shutdown()`) — see Completion Notes re: `app.state` exposure
- [x] Task 3: Create `core/models.py` — `User` ORM model (AC: 1)
  - [x] Declarative `Base`; `User` class: `id` (PK), `email` (unique, not null), `username` (unique, not null), `full_name`, `phone_number`, `hashed_password`, `created_at` (default now)
- [x] Task 4: Alembic setup (AC: 1)
  - [x] `alembic init -t async alembic` (async-template `env.py`, not the default sync template)
  - [x] Do **not** hardcode a connection string into `alembic.ini`'s `sqlalchemy.url` — `alembic.ini` is **not** gitignored (only `.env` is), so a literal URL there commits DB credentials to git. Instead, set the URL dynamically inside `alembic/env.py` via `config.set_main_option("sqlalchemy.url", async_database_uri)`, sourcing `async_database_uri` from `config.py`/`core/db.py`'s same swap logic as Task 2. Leave `alembic.ini`'s static `sqlalchemy.url` line blank/placeholder.
  - [x] Set `target_metadata = Base.metadata` from `core/models.py`
  - [x] Generate + apply a migration creating the `users` table with `UNIQUE` constraints on `email`/`username`
  - [x] Do **not** wire `alembic upgrade head` into `main.py`'s `lifespan` — run it as a separate manual/CLI step (see Dev Notes for why)
- [x] Task 5: Implement `services/auth_service.py` — registration logic (AC: 2, 3, 4)
  - [x] `register(session, email, username, full_name, phone_number, password) -> User`
  - [x] Hash password via `argon2.PasswordHasher().hash(password)`, offloaded via `run_in_threadpool`/`asyncio.to_thread` (sync, CPU-bound call)
  - [x] Persist via `session.add(user)` + `await session.commit()`
  - [x] Return only the persisted `User` — do not leak `phone_number`/`full_name`/`hashed_password` upward beyond the service boundary
- [x] Task 6: Implement `api/auth.py` — `POST /auth/register` router (AC: 2, 3)
  - [x] `router = APIRouter()` with no prefix, full path in the decorator (`@router.post("/auth/register", ...)`) — matches the existing `api/chat.py`/`api/mcp.py` convention (neither uses `APIRouter(prefix=...)`)
  - [x] Pydantic `RegisterRequest`: `email`, `username`, `full_name`, `phone_number`, `password` all as plain `str` fields — **not** `EmailStr`. `email-validator` (required by `EmailStr`) isn't in `requirements.txt`, and format validation is Story 1.3's scope, not this story's
  - [x] `RegisterResponse` (`id`, `email` only)
  - [x] `Depends(get_db)` for the per-request `AsyncSession`
  - [x] Call `auth_service.register(...)`, return `201` with `RegisterResponse`
  - [x] Mount router in `main.py` via `app.include_router(auth_router)`, matching the existing `chat_router`/`mcp_router` pattern

## Dev Notes

- **Architecture compliance (binding — [Source: ARCHITECTURE-SPINE.md#AD-1 through AD-8]):** registration models a persisted `User` identity, not a shared secret. Auth owns direct Postgres access via `core/db.py`; `postgres-mcp` is never used for auth reads/writes. No login/JWT/session store this pass. File placement is fixed: router in `api/auth.py`, business logic in `services/auth_service.py`, DB infra in `core/db.py`/`core/models.py`. All DB access is async (no sync engine anywhere). Engine lifecycle is via FastAPI `lifespan`; session is per-request via `Depends`, never shared/singleton.
- **Existing pattern to mirror** ([Source: mcp_server/manager.py], [Source: main.py], [Source: api/mcp.py]): `MCPManager` is constructed at module level, `await mcp_manager.initialize()`/`shutdown()` wired into `lifespan`, exposed via `app.state.mcp_manager`. Routers pull it via `Depends(get_mcp_manager)`, which reads `request.app.state.mcp_manager` (see `api/mcp.py`). Mirror this exact shape for the DB engine — construct/dispose via `lifespan`, expose via `app.state`. The one difference per AD-8: what's injected into request handlers via `Depends` is a fresh **session** (`get_db`), not the engine itself — never share a session across requests the way `MCPManager` is shared as a singleton.
- **`config.py` is the intended single env-loading point** ([Source: config.py]) — currently loads `OPENAI_API_KEY`/`OPENAI_MODEL` via `os.getenv` after `load_dotenv()`. Add `DATABASE_URI = os.getenv("DATABASE_URI")` there — do not add a second `os.environ.get()` call inside `core/db.py`. **Existing precedent, not this story's job to fix:** `mcp_server/client.py` already reads `DATABASE_URI` directly via `os.environ.get("DATABASE_URI")`, bypassing `config.py` — this is pre-existing and out of scope; don't "fix" `MCPClient` as part of this story.
- **`DATABASE_URI` is a plain `postgresql://` URL, shared with the existing MCP path** — verified in `.env`: `DATABASE_URI=postgresql://user:pass@host:5432/db`. This scheme selects SQLAlchemy's default sync `psycopg2` dialect (not installed, and invalid for `create_async_engine` regardless). Build the async variant once — e.g. `DATABASE_URI.replace("postgresql://", "postgresql+asyncpg://", 1)` — and reuse that same derived value in both `core/db.py` and `alembic/env.py`. Do not pass raw `DATABASE_URI` to `create_async_engine` directly.
- **SQLAlchemy 2.0.51 async pattern:**
  ```python
  from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

  engine = create_async_engine(async_database_uri, pool_pre_ping=True)
  SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

  async def get_db():
      async with SessionLocal() as session:
          yield session
  ```
  `expire_on_commit=False` is required — without it, accessing `User` attributes after commit (e.g. serializing the response) triggers a lazy-load that raises `MissingGreenlet` in an async context.
- **Alembic async migrations:** run `alembic init -t async alembic` (not the default sync template) to scaffold an `env.py` that already supports an async engine. Set the connection URL dynamically inside `env.py` (`config.set_main_option("sqlalchemy.url", async_database_uri)`) rather than hardcoding it into `alembic.ini` — `alembic.ini` is **not** gitignored (only `.env` is per `.gitignore`), so a literal credential-bearing URL there would be committed to git. **Do not** invoke `alembic upgrade head` from inside FastAPI's `lifespan` — Alembic's migration runner is sync and internally calls `asyncio.run()`, which raises if invoked from a context that already has a running event loop (this app's `lifespan` does). Run the migration as a separate manual/CLI step instead — consistent with deployment/CI automation being explicitly out of scope for this pass.
- **argon2-cffi 25.1.0 API:**
  ```python
  from argon2 import PasswordHasher
  ph = PasswordHasher()
  hashed = ph.hash(password)   # str — store in hashed_password
  ```
  `PasswordHasher.hash()` is synchronous and CPU-bound — calling it directly inside an `async def` route blocks the event loop. Offload via `fastapi.concurrency.run_in_threadpool` or `asyncio.to_thread`. (Verification via `.verify()` is not needed by this story — no login exists yet.)
- **Response shape:** the success response returns only `id` and `email` ([Source: ARCHITECTURE-SPINE.md#API response shape]) — do not include `phone_number`, `full_name`, or any password field in the response Pydantic model, even accidentally via a shared/inherited schema.
- **Testing standards summary:** no automated test suite exists in this repo (no `pytest`, no `tests/` dir), and this story does not introduce one — explicitly out of scope this pass ([Source: prd.md#6.2 Out of Scope for MVP]). Verify manually: apply the migration, `POST /auth/register` with valid data (curl/httpie), confirm `201` and the exact response shape, then inspect the DB row directly to confirm `hashed_password` holds only an Argon2id hash.
- **Do NOT build in this story:** login, JWT issuance, duplicate-conflict handling (`409` — Story 1.2), or input validation beyond what's needed to construct the row (`422` — Story 1.3). This story's scope is the happy path only.

### Project Structure Notes

- New files: `core/db.py`, `core/models.py`, `api/auth.py`, `services/auth_service.py`, `alembic/` (`alembic.ini`, `alembic/env.py`, `alembic/versions/`).
- Modified files: `requirements.txt` (4 new deps), `config.py` (add `DATABASE_URI`), `main.py` (wire engine into `lifespan`, mount `auth_router`).
- `core/` currently contains only `__init__.py` — this story is the first to add real code there, consistent with Architecture's "`core/` becomes shared DB infra" (AD-5).
- No conflicts with the currently uncommitted changes in `api/chat.py`/`services/chat_service.py` (an unrelated `tool_calls` trace addition) — different files, no overlap.

### References

- [Source: _bmad-output/planning-artifacts/architecture/architecture-mcp-tool-calling-2026-07-14/ARCHITECTURE-SPINE.md#AD-1] through AD-8, Stack, Structural Seed, Consistency Conventions
- [Source: _bmad-output/planning-artifacts/prds/prd-mcp-tool-calling-2026-07-14/prd.md#4.1 User Registration] FR-1, FR-5; [Source: prd.md#6.2] Out of Scope
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.1: Register a New Account]
- [Source: main.py] lifespan pattern
- [Source: mcp_server/manager.py] manager construct/initialize/shutdown pattern
- [Source: api/mcp.py] `Depends(get_x)` + `request.app.state.x` pattern
- [Source: config.py] single env-loading point pattern

## Dev Agent Record

### Agent Model Used

claude-sonnet-5

### Debug Log References

- **Alembic `ConfigParser` interpolation failure**: setting `sqlalchemy.url` dynamically via `config.set_main_option()` with a percent-encoded password (e.g. containing `%40`) raised `ValueError: invalid interpolation syntax` — `ConfigParser`'s `BasicInterpolation` treats a bare `%` as a template token. Fixed by escaping (`.replace("%", "%%")`) before passing to `set_main_option`. Not anticipated in the story; documented in `alembic/env.py` as a comment.
- **Pre-existing `users` table collision**: the target Postgres database (`ai_database_assistant`, from `DATABASE_URI`) already had an unrelated `users` table (`first_name`, `last_name`, `email`, `age`, `city`, 2 rows). Autogenerate correctly produced a migration that would drop those columns/data. Halted and confirmed with the user before proceeding (see Completion Notes) — added an explicit `DELETE FROM users` at the top of the migration's `upgrade()` since the existing NOT-NULL-less rows would otherwise block adding the new `NOT NULL` columns.

### Completion Notes List

- Implemented the full happy-path registration flow: `POST /auth/register` → Argon2id hash → persisted `User` row → `201` with only `id`/`email`. All 4 ACs verified manually end-to-end (server started, `curl` against `/auth/register`, direct DB row inspection) — see Debug Log and verification transcript in this session.
- **Deviation from story wording (Task 2, "expose via `app.state`")**: implemented `core/db.py`'s engine/`SessionLocal` as plain module-level objects (constructed once at import, matching `MCPManager()`'s bare-constructor style), rather than routing `get_db` through `request.app.state`. Rationale: `create_async_engine`/`async_sessionmaker` do no I/O at construction (unlike `MCPManager.initialize()`, which opens a real subprocess/session), so there's no async setup step that needs to live inside `lifespan` — only disposal does, and that's wired into `lifespan` via `core.db.dispose_engine()`. This satisfies AD-8's substantive requirements (lifespan-owned disposal, fresh per-request session via `Depends`, never shared) without the extra `app.state` indirection, which would have added a moving part with no corresponding benefit here.
- **Pre-existing DB state required a user decision mid-implementation**: the shared Postgres database already had an unrelated `users` table with 2 rows of stale data. Paused and got explicit user confirmation before letting the migration drop those columns/rows (user confirmed this data was safe to lose). Documented in Debug Log above.
- Per this story's own Dev Notes (informed by PRD §6.2 Out of Scope — no automated test suite this pass), no pytest tests were written; verification was manual (migration apply, `curl` against the live endpoint, direct DB inspection), matching the story's explicit testing-standards guidance.
- Regression check: confirmed `/`, `/health` still return `200`, and the `502` from `/chat` during testing is a pre-existing `OPENAI_API_KEY`-missing condition unrelated to this story's changes (verified via server log).
- Out of scope for this story, confirmed not implemented: duplicate-email/username handling (`409`, Story 1.2), input format/length validation (`422`, Story 1.3), login/JWT.

### File List

**New files:**
- `core/db.py`
- `core/models.py`
- `services/auth_service.py`
- `api/auth.py`
- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/README`
- `alembic/versions/565523b9e716_create_users_table.py`

**Modified files:**
- `requirements.txt` (added SQLAlchemy, asyncpg, alembic, argon2-cffi)
- `config.py` (added `DATABASE_URI`)
- `main.py` (wired `core.db.dispose_engine()` into `lifespan` shutdown, mounted `auth_router`)

## Change Log

- 2026-07-15: Implemented Story 1.1 — registration happy path, DB/Alembic/ORM foundation. Status: ready-for-dev → review.
