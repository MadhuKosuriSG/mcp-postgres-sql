---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-mcp-tool-calling-2026-07-14/prd.md
  - _bmad-output/planning-artifacts/architecture/architecture-mcp-tool-calling-2026-07-14/ARCHITECTURE-SPINE.md
  - docs/architecture.md
  - docs/data-models.md
  - docs/api-contracts.md
  - docs/development-guide.md
  - docs/source-tree-analysis.md
  - docs/project-overview.md
---

# mcp-tool-calling - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for mcp-tool-calling, decomposing the requirements from the PRD and Architecture spine into implementable stories. This pass covers a single feature: user registration (`POST /auth/register`). No UX design contract exists or is needed — this is an API-only surface with no UI in scope.

## Requirements Inventory

### Functional Requirements

FR1: A caller can submit email, username, full name, phone number, and password to `POST /auth/register` to create a new account. On valid, non-duplicate input, a new `User` record is persisted and the request succeeds. The success response contains only non-sensitive fields (`id`, `email`) — `phone_number`, `full_name`, and the password (hashed or plaintext) are never included in any response.

FR2: The system rejects registration when the submitted email is already registered. A registration attempt with a duplicate email does not create or modify any account. The caller receives an error response distinguishing this as a duplicate-account error, not a generic failure.

FR3: The system rejects registration when the submitted username is already registered, independent of email uniqueness (a duplicate username with a new email is still rejected, and vice versa). A registration attempt with a duplicate username does not create or modify any account, even if the email is new.

FR4: The system rejects malformed or insufficient input (invalid email format, password below the minimum length) before any hashing or storage occurs. A registration attempt with invalid input creates no account and stores nothing, including no partial record. The caller receives an error response distinguishing this as an invalid-input error from a duplicate-account error and from an upstream/service failure.

FR5: The submitted password is transformed into a one-way hash before storage; the plaintext value is never persisted, logged, or returned in any response, and no stored field can be reversed to recover it.

### NonFunctional Requirements

NFR1: Duplicate-detection (FR2, FR3) must be race-safe under concurrent registration attempts for the same email/username — no window where two concurrent requests both succeed and create conflicting accounts.

NFR2: Error responses must let a caller reliably distinguish "duplicate account" (FR2/FR3) from "invalid input" (FR4) from "service/upstream failure" — three distinguishable outcomes, not one generic error shape.

NFR3: Passwords are stored only as one-way hashes using a modern, industry-current algorithm (Argon2id) — no reversible encryption, no unsalted or outdated hashing.

NFR4: [ASSUMPTION] No abuse-rate protection (rate limiting, bot/spam mitigation) is required for this MVP pass — flagged as a known, accepted gap rather than a hard requirement.

### Additional Requirements

**Starter template:** None. This is a brownfield repo with an existing FastAPI/services/mcp_server layered structure — there is no starter/greenfield template to apply. Epic 1 Story 1 introduces new infra (SQLAlchemy async engine, Alembic) into the existing structure rather than scaffolding a new project.

**Architectural decisions (binding, from Architecture spine):**
- Auth centers on a persisted `User` identity, not a shared secret or service token (AD-1).
- Auth owns direct Postgres access via the app's own SQLAlchemy layer (`core/db.py`); `postgres-mcp` is never used for auth reads or writes (AD-2). Accepted risk, not fixed this pass: `postgres-mcp` connects with the same DB role and can already run `execute_sql` against the `users` table once it exists — no DB-level role restriction is being added in this pass.
- Session strategy will be stateless JWT when login ships later; no session table/store is introduced now, and this pass ships no `/auth/login` endpoint or token issuance (AD-3, AD-4).
- File/module placement: router in `api/auth.py`, business logic in `services/auth_service.py`; `core/db.py` holds the SQLAlchemy async engine/session, `core/models.py` holds the `User` ORM model (AD-5).
- All auth DB access uses SQLAlchemy `AsyncSession`/`asyncpg` — no sync DB engine is introduced (AD-6).
- Auth errors map to real 4xx codes: `409` for duplicate email/username, `422` for validation failures (rejected pre-hash); `502` stays reserved for genuine MCP/LLM upstream failures. Duplicate detection is insert-then-catch against the DB unique constraint (`IntegrityError`), never check-then-insert. Error `detail` stays a flat string, not a structured/field-keyed object (AD-7).
- Engine lifecycle: `AsyncEngine` is constructed and disposed via FastAPI's `lifespan` hook, same pattern as the existing `MCPManager`. `services/auth_service.py` obtains a new `AsyncSession` per request via `Depends` — no session is ever shared across requests (AD-8).

**Naming & consistency conventions:**
- `users` table (snake_case columns), `User` ORM class; routes under the `/auth` prefix (e.g. `POST /auth/register`).
- Error body stays `{"detail": "..."}`, matching the existing `/chat` and `/mcp/call` endpoints, which keep their own `502` pattern unchanged.
- `DATABASE_URI` is read in exactly one place — `config.py`'s existing env-loading pattern (currently loads `OPENAI_API_KEY`/`OPENAI_MODEL`), extended — not a second `os.environ.get()` call inside `core/db.py`.

**Dependency & tooling setup (from Architecture Stack + Structural Seed, and confirmed against the existing `requirements.txt`):**
- New dependencies to add to the existing `requirements.txt` (no new `pyproject.toml`/poetry manifest): SQLAlchemy (async) 2.0.51, asyncpg 0.31.0, alembic 1.18.5, argon2-cffi 25.1.0.
- Alembic migration tooling must be introduced (`alembic/versions/`, `alembic.ini`) — no migration folder exists in the repo today.

**Deferred — explicitly do NOT create stories for these in this pass:**
- Login, JWT issuance, token refresh.
- JWT signing-secret storage and rotation.
- Token revocation / logout strategy.
- Password reset, email verification, RBAC.
- Automated test coverage (no pytest/test-DB suite exists today; this pass does not start one).
- Deployment/environment envelope (Dockerfile, CI/CD, IaC, migration-execution strategy in a deployed environment).
- Registration abuse protection (rate limiting, bot/spam mitigation on `POST /auth/register`).
- Email/username-enumeration hardening (softening the `409` duplicate-account signal).
- DB-level role restriction separating `postgres-mcp`'s connection from the `users` table — accepted risk, revisit before production.

### UX Design Requirements

None. Confirmed API-only surface, no UI in scope for this pass — no UX design contract exists or is needed.

### FR Coverage Map

FR1: Epic 1 - Create account via POST /auth/register
FR2: Epic 1 - Enforce email uniqueness
FR3: Epic 1 - Enforce username uniqueness
FR4: Epic 1 - Validate input before storing anything
FR5: Epic 1 - Never store or expose plaintext password

## Epic List

### Epic 1: Account Registration
A caller can register a new account via `POST /auth/register` — submitting email, username, full name, phone number, and password — with the system enforcing uniqueness, validating input, and securely hashing the password before persisting the account.
**FRs covered:** FR1, FR2, FR3, FR4, FR5

## Epic 1: Account Registration

A caller can register a new account via `POST /auth/register` — submitting email, username, full name, phone number, and password — with the system enforcing uniqueness, validating input, and securely hashing the password before persisting the account.

### Story 1.1: Register a New Account

As a client application integrating with mcp-tool-calling,
I want to submit my email, username, full name, phone number, and password to create an account,
So that I have a persisted identity the system can build login and permissions on later.

**Technical Notes:** Adds `core/db.py` (`AsyncEngine`/`async_sessionmaker` via FastAPI `lifespan`, matching the existing `MCPManager` pattern), `core/models.py` (`User` ORM model), an Alembic migration for the `users` table, and new deps in `requirements.txt` (SQLAlchemy async 2.0.51, asyncpg 0.31.0, alembic 1.18.5, argon2-cffi 25.1.0). `DATABASE_URI` continues to be read only via `config.py`'s existing loader.

**Acceptance Criteria:**

**Given** the Alembic migration has been applied
**When** the `users` table schema is inspected
**Then** `email` and `username` each have a database-level `UNIQUE` constraint (required for Story 1.2's insert-then-catch duplicate detection)

**Given** a caller submits valid, non-duplicate email, username, full name, phone number, and password to `POST /auth/register`
**When** the request is processed
**Then** the password is hashed with Argon2id before any storage occurs, a new `User` row is persisted via a per-request `AsyncSession` (obtained through `Depends`, never shared across requests), and the response is `201 Created` containing only `id` and `email`

**Given** a successful registration response
**When** the response body is inspected
**Then** it contains no `phone_number`, `full_name`, `hashed_password`, or plaintext password field

**Given** the stored `User` row after registration
**When** the database row is inspected
**Then** `hashed_password` holds only the Argon2id hash — no plaintext password is persisted, logged, or recoverable

### Story 1.2: Reject Duplicate Registrations

As a client application integrating with mcp-tool-calling,
I want registration to fail cleanly when my email or username is already taken,
So that I never end up with two conflicting accounts or an ambiguous error.

**Acceptance Criteria:**

**Given** an existing `User` account with a given email
**When** a new registration request submits that same email (with any username)
**Then** the request is rejected with `409 Conflict`, no new account is created, and the existing account is not modified

**Given** an existing `User` account with a given username
**When** a new registration request submits that same username (with any new email)
**Then** the request is rejected with `409 Conflict`, no new account is created, and the existing account is not modified

**Given** two concurrent registration requests submitting the same email or username
**When** both are processed at the same time
**Then** exactly one succeeds and one fails with `409 Conflict` — duplicate detection relies on insert-then-catch against the database's `UNIQUE` constraint (`IntegrityError`) established in Story 1.1, never a check-then-insert pattern that could race

**Given** a `409 Conflict` response for a duplicate email or username
**When** the response body is inspected
**Then** `detail` is a flat string distinguishing this as a duplicate-account error, not the same shape as a `422` validation error or a `502` upstream failure

### Story 1.3: Validate Registration Input

As a client application integrating with mcp-tool-calling,
I want malformed registration data rejected before anything is stored,
So that I get a clear, actionable error instead of a silently broken or partial account.

**Acceptance Criteria:**

**Given** a registration request with a malformed email (not a valid email format)
**When** the request is processed
**Then** it is rejected with `422 Unprocessable Entity` before any password hashing or database write occurs, and no `User` row (partial or complete) is created

**Given** a registration request with a password below the minimum length
**When** the request is processed
**Then** it is rejected with `422 Unprocessable Entity` before any hashing or database write occurs, and no `User` row is created

**Given** a `422` validation-error response
**When** the response body is inspected
**Then** `detail` is a flat string distinguishing this as an invalid-input error, distinct in shape from the `409` duplicate-account error (Story 1.2) and the `502` upstream-failure error used by `/chat` and `/mcp/call`

**Given** a registration request missing one or more required fields (email, username, full name, phone number, password)
**When** the request is processed
**Then** it is rejected with `422 Unprocessable Entity` and no `User` row is created
