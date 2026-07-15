---
title: Secure Authentication System — User Registration MVP
status: final
created: 2026-07-14
updated: 2026-07-14
---

# PRD: Secure Authentication System — User Registration MVP

## 0. Document Purpose

This PRD scopes the first slice of authentication for the `mcp-tool-calling` FastAPI/OpenAI/MCP chat-bridge: account registration. It is written for the Architect, downstream epic/story authors, and the implementing engineer. It builds on — and was backfilled against — the already-finalized Architecture spine (`_bmad-output/planning-artifacts/architecture/architecture-mcp-tool-calling-2026-07-14/ARCHITECTURE-SPINE.md`) and the original brainstorming session (`_bmad-output/brainstorming/brainstorm-user-registration-2026-07-14/.memlog.md`); technical implementation choices already ratified there (SQLAlchemy async, Argon2id, JWT direction) are not repeated here as requirements — this document states product-level capabilities and constraints only.

## 1. Vision

`mcp-tool-calling` currently has zero authentication — any caller can hit `POST /chat` and `POST /mcp/call`, which lets an LLM run tools (including SQL execution) against Postgres on the caller's behalf. This PRD introduces the first piece of a real identity system: **user registration**. It establishes a persisted `User` account (not a shared API key or service token) as the foundation identity primitive the rest of the system — login, per-user chat history, permissioning on what a user can ask the LLM/MCP tools to do — will build on later.

This pass ships registration only. Login, token issuance, and everything gated behind an authenticated session are explicitly out of scope and deferred.

## 2. Target User

### 2.1 Jobs To Be Done

- As an operator of this service, I need a real account system so that access to the chat/tool-calling surface is tied to an identifiable person, not an open endpoint.
- As a future engineer building login/JWT/permissions on this system, I need a `User` entity and registration flow already in place to build on.
- [ASSUMPTION] Registration establishes real, individually-owned end-user accounts (not a shared secret or service token) — carried over from the Architecture spine's AD-1, not independently reconfirmed during this PRD backfill. Flagged in §8 Open Questions for explicit confirmation.

### 2.2 Key User Journeys

API-only surface, no UI in scope (confirmed) — journey is expressed as an API interaction, not a screen flow.

- **UJ-1. A new caller registers an account via the API.**
  - **Persona + context:** A client application (or direct API caller) integrating with `mcp-tool-calling` for the first time.
  - **Entry state:** Unauthenticated, no existing account.
  - **Path:** Caller submits `POST /auth/register` with email, username, full name, phone number, and password → system validates input → system checks email/username uniqueness → system hashes the password → system persists the new `User` row.
  - **Climax:** Registration succeeds; caller receives confirmation the account exists.
  - **Resolution:** Caller now has a persisted account to use once login ships (out of scope this pass).
  - **Edge case:** Caller submits an email or username that's already registered → request is rejected, no account is created or modified.

## 3. Glossary

- **User** — A persisted account record: unique email, unique username (separate identifier from email), full name, phone number, hashed password, id, created_at. The identity primitive all future auth/permissions work builds on.
- **Registration** — The act of creating a new User record via `POST /auth/register`. Does not issue a session, token, or any authenticated credential.
- **Hashed password** — The one-way, irreversible transformation of a submitted password, stored in place of the plaintext. Never logged or returned in any response.

## 4. Features

### 4.1 User Registration

**Description:** A caller creates a new account by submitting identifying information and a password. The system validates the input, enforces uniqueness on email and username independently, hashes the password, and persists the account. Realizes UJ-1.

**Functional Requirements:**

#### FR-1: Create account

A caller can submit email, username, full name, phone number, and password to `POST /auth/register` to create a new account. Realizes UJ-1.

**Consequences (testable):**
- On valid, non-duplicate input, a new `User` record is persisted and the request succeeds.
- The success response contains only non-sensitive fields (`id`, `email`) — `phone_number`, `full_name`, and the password (hashed or plaintext) are never included in any response.

#### FR-2: Enforce email uniqueness

The system rejects registration when the submitted email is already registered.

**Consequences (testable):**
- A registration attempt with a duplicate email does not create or modify any account.
- The caller receives an error response distinguishing this as a duplicate-account error, not a generic failure.

#### FR-3: Enforce username uniqueness

The system rejects registration when the submitted username is already registered, independent of email uniqueness (a duplicate username with a new email is still rejected, and vice versa).

**Consequences (testable):**
- A registration attempt with a duplicate username does not create or modify any account, even if the email is new.

#### FR-4: Validate input before storing anything

The system rejects malformed or insufficient input (invalid email format, password below the minimum length) before any hashing or storage occurs.

**Consequences (testable):**
- A registration attempt with invalid input creates no account and stores nothing, including no partial record.
- The caller receives an error response distinguishing this as an invalid-input error from a duplicate-account error and from an upstream/service failure.

#### FR-5: Never store or expose the plaintext password

The submitted password is transformed into a one-way hash before storage; the plaintext value is never persisted, logged, or returned in any response, and no stored field can be reversed to recover it.

**Out of Scope:**
- Password strength/complexity rules beyond a minimum length are not specified in this pass.

**Feature-specific NFRs:**
- Duplicate-detection (FR-2, FR-3) must be race-safe under concurrent registration attempts for the same email/username — no window where two concurrent requests both succeed and create conflicting accounts.
- Error responses must let a caller reliably distinguish "duplicate account" (FR-2/FR-3) from "invalid input" (FR-4) from "service/upstream failure" — three distinguishable outcomes, not one generic error shape.

## 5. Non-Goals (Explicit)

- This system does not implement login, session issuance, or token-based authentication in this pass — registration only creates the account, it does not let the caller use it yet.
- This system does not implement password reset, email verification, or role-based access control (RBAC) in this pass.
- This system does not restrict which existing internal components (e.g. the MCP/Postgres tool-calling path) can read the new `users` table at the database level — see §8 Open Questions for the accepted risk this creates.

## 6. MVP Scope

### 6.1 In Scope

- `POST /auth/register` endpoint accepting email, username, full name, phone number, password.
- Email uniqueness enforcement.
- Username uniqueness enforcement (independent of email).
- Input validation (email format, minimum password length) prior to storage.
- One-way password hashing; plaintext never persisted, logged, or returned.
- Success response returning only non-sensitive account fields.

### 6.2 Out of Scope for MVP

- Login / JWT issuance / token refresh — deferred to a future pass (Architecture spine AD-3 already sets the direction: stateless JWTs, no server-side session store).
- Password reset, email verification, RBAC — named in the original brainstorm as later extensions.
- Rate limiting / abuse protection on the registration endpoint — not decided in this pass; flagged as a real gap for a security-facing, publicly-reachable endpoint, not silently assumed away. `[NOTE FOR PM]` revisit before this endpoint is internet-facing at any real scale.
- Automated test coverage — no pytest/test-DB suite is introduced for this pass; the repo has none today.
- Deployment/environment envelope (Dockerfile, CI/CD, migration-execution strategy) — no deployment tooling exists in this repo yet; unresolved, not blocking this pass.

## 7. Cross-Cutting NFRs

- **Security:** Passwords are stored only as one-way hashes using a modern, industry-current algorithm — no reversible encryption, no unsalted or outdated hashing. [ASSUMPTION] No abuse-rate protection (rate limiting, bot/spam mitigation) is required for this MVP pass — flagged in §6.2 as a known, accepted gap rather than a hard requirement.
- **Reliability:** Duplicate-account handling must not race under concurrent load (see §4.1 feature-specific NFRs).
- **Error clarity:** Client-caused errors (duplicate account, invalid input) must be distinguishable from service/upstream failures in the response, so callers and operators can tell them apart without inspecting logs.

## 8. Open Questions

1. **[ASSUMPTION — needs confirmation]** Is registration meant to build real, individually-owned user identity (per §2.1), or is the underlying goal narrower — just gating `/chat` and `/mcp/call` against open access? The Architecture spine already committed to the former (AD-1); this PRD backfill carries that forward without an independent product confirmation. If the narrower goal is actually correct, the architecture and this PRD both need revisiting.
2. **Accepted risk, carried from Architecture:** the existing `postgres-mcp` MCP path connects with the same database role the new registration code will use, and — once the `users` table exists — can already run `execute_sql` against it, exposing hashed passwords and PII to the LLM chat path. This was explicitly accepted as a risk for this MVP rather than fixed (no DB-level role restriction added). **Revisit before production use or before this app handles real user data at scale.**
3. No quantitative success metric is defined for this MVP (see §9 Assumptions Index) — is that acceptable, or should a signup-oriented metric (e.g. registration success rate) be added before this ships?

## 9. Assumptions Index

- From §2.1 / §8.1 — Registration builds real end-user identity, not a shared-secret/service gate. Carried over from Architecture AD-1, not independently reconfirmed with the user during this PRD backfill.
- From §7 — No abuse-rate protection (rate limiting) is required for this MVP pass; treated as an accepted, flagged gap rather than a requirement.
- No Success Metrics section is included in this PRD — the user did not provide a metric when asked during backfill; functional correctness (FR-1 through FR-5 hold true) is being used as the de facto acceptance bar for this pass. Confirm or add a real metric before this is considered fully closed (see §8, item 3).
