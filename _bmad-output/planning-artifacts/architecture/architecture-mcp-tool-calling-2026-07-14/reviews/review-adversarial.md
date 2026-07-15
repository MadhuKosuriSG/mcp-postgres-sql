---
name: 'Adversarial Review — Architecture Spine (Secure Auth / User Registration MVP)'
type: review
target: '_bmad-output/planning-artifacts/architecture/architecture-mcp-tool-calling-2026-07-14/ARCHITECTURE-SPINE.md'
created: '2026-07-14'
---

# Adversarial Review — ARCHITECTURE-SPINE.md

## Method

Attack the spine as an adversary, not a supporter: for each AD/Convention, construct two builders (or one
builder + one future maintainer) who each obey the letter of every rule, and try to make them build something
that doesn't fit together. Grounded against the actual repo state, not hypothetical — read `main.py`,
`config.py`, `api/chat.py`, `mcp_server/client.py`, `services/chat_service.py` to see the *existing* patterns
a compliant builder would plausibly mirror, since `core/db.py`, `services/auth_service.py`, and `api/auth.py`
don't exist yet.

## Verdict

The spine is directionally sound (layering, JWT-not-sessions, async-only, 409/422 split are all real,
useful commitments) but it commits to *what* without committing to *how the parts assemble*, and the repo's
own existing code sets two competing precedents for nearly every "how" question this build needs to answer.
Five holes below; each is a place where two equally-compliant builders diverge and produce code that either
crashes, silently races, or ships an API contract the other side didn't expect.

## Holes Found

### Hole 1 — Engine lifecycle has no owner: import-time vs. lifespan-time vs. lazy

**AD/Convention implicated:** AD-5 ("`core/` holds the SQLAlchemy async engine/session... as infra"),
AD-6 (must be async), Consistency Convention ("`core/db.py` owns the single `AsyncEngine`/`async_sessionmaker`").

**The repo's existing precedent is split already.** `main.py` builds `MCPManager()` and `ChatService()` at
*module import time* (lines 13-14), but `MCPManager` is inert until `await mcp_manager.initialize()` runs
inside `lifespan()` (line 19) — an explicit two-phase construct-then-init object with its own `shutdown()`.
Meanwhile `mcp_server/client.py`'s `MCPClient.__init__` reads `os.environ.get("DATABASE_URI")` immediately
and eagerly validates nothing until `connect()`.

**Scenario:** Builder A treats `core/db.py` like `MCPManager`: a stateful object with `init_engine()` /
`dispose_engine()`, and edits `main.py`'s `lifespan()` to call them alongside `mcp_manager.initialize()`.
Builder B treats it like a typical SQLAlchemy-async cookbook module: `engine = create_async_engine(...)` and
`async_sessionmaker(engine)` as bare module-level globals, built once at import time, no init/dispose calls,
nothing added to `lifespan()` at all.

**The incompatibility:** Both comply with AD-5/AD-6 to the letter — nothing in the spine says whether engine
construction is tied to `lifespan()` or happens at import. If `services/auth_service.py` is written against
Builder A's interface (`await db.init_engine()` must run first, `db.get_session()` raises if not yet
initialized) but `core/db.py` ships in Builder B's shape (no init function exists at all), that's an
`AttributeError` at first import. If the mismatch runs the other way — auth_service calls a bare
`async_sessionmaker` directly, but a later maintainer "fixes" `core/db.py` to match the `MCPManager` pattern
and gates the sessionmaker behind an `initialize()` nobody wires into `lifespan()` — every register call fails
until someone notices the DB session is never actually initialized. Either direction is a full outage that
passes code review because each side individually matches an existing repo convention.

**Fix needed:** Add a rule stating explicitly whether `core/db.py`'s engine is constructed eagerly at import
(module-level, self-contained, no lifespan hook) or whether `main.py`'s `lifespan()` must be extended with an
explicit startup/shutdown call — and if the latter, add that edit to the Structural Seed so it isn't invented
per-builder.

### Hole 2 — Who owns the `AsyncSession`: app-lifetime service (app.state) or per-request dependency?

**AD/Convention implicated:** AD-5 (router/service split), Consistency Convention
("`services/auth_service.py` is the only writer to `users`").

**The repo's existing precedent, again, points two ways.** `api/chat.py` uses the `app.state` singleton
pattern: `get_chat_service(request) -> request.app.state.chat_service` (lines 21-22), a service built once at
startup and reused for the app's whole life, holding no per-call resource that needs closing. But an
`AsyncSession` is exactly the kind of resource that pattern is wrong for — it isn't safe to share across
concurrent requests.

**Scenario:** Builder A mirrors `api/chat.py` exactly: `auth_service = AuthService()` built once in `main.py`,
stashed on `app.state.auth_service`, and `AuthService` opens-and-closes its own `AsyncSession` from the shared
sessionmaker inside each method call. Builder B follows the standard FastAPI/SQLAlchemy-async idiom instead:
`api/auth.py` has a `get_db_session()` generator dependency yielding a fresh `AsyncSession` per request
(closed in `finally`), and constructs `AuthService(session)` fresh inside the route handler every call —
never touching `app.state`.

**The incompatibility:** Both comply with AD-5's "router in `api/auth.py`, business logic in
`services/auth_service.py`" literally. Nothing in the spine says whether `AuthService` is a singleton or a
per-request object, or who is responsible for opening/closing the session. A future maintainer who has only
read the spine and sees `app.state.chat_service` as the established pattern in this codebase will build
`AuthService` as a singleton with an internally cached session (or, worse, patches an existing per-request
`AuthService(session)` to also work as a singleton by making `session` an optional constructor arg that falls
back to a module-global session when omitted). That module-global session, shared across concurrent
`/auth/register` requests, is not safe for concurrent use — two simultaneous registrations interleaving
statements on the same `AsyncSession` corrupts transaction state non-deterministically. This is the worst
kind of hole: it doesn't fail at merge time, it fails under concurrent load in production.

**Fix needed:** State explicitly: is `AuthService` per-request (constructed with an injected session, request
lifetime) or app-lifetime (singleton, session opened/closed per call internally)? State who calls
`session.close()`/`commit()`/`rollback()` — the service, or a FastAPI dependency wrapper.

### Hole 3 — "409 for duplicate email/username" doesn't say check-then-insert vs. insert-then-catch, or the response shape

**AD/Convention implicated:** AD-7 ("duplicate email/username → `409`"), Consistency Convention
("Error body stays `{"detail": "..."}"`, matching existing endpoints").

**Scenario:** Builder A implements uniqueness as two sequential pre-check `SELECT`s (check email exists,
then check username exists) before the `INSERT`, and returns whichever failed first as a plain string:
`{"detail": "email already registered"}`. Builder B implements it as a single `INSERT`, relying on the two DB
unique constraints (per the ERD, both `email` and `username` are `UK`) and catching `IntegrityError`,
returning a generic `{"detail": "duplicate email or username"}` regardless of which column collided.

**The incompatibility, part A (race):** Builder A's check-then-insert has a TOCTOU race: two concurrent
registration requests with the same email both pass the pre-check (neither sees the other's uncommitted row),
both proceed to `INSERT`, and the DB throws `IntegrityError` on both — a path Builder A's code never
anticipated, since their design assumes the pre-check is authoritative. Depending on which `except` clauses
exist, this either 500s, or falls through to the generic `HTTPException(502)` pattern that AD-7 explicitly
says must *not* catch client-caused errors — silently violating the AD that was supposedly satisfied.

**The incompatibility, part B (shape):** the spine says `detail` matches "existing endpoints," but the only
existing precedent (`api/chat.py` line 33) is `detail=str(exc)` — a flat string. That's compatible with both
Builder A's field-specific string and Builder B's generic string, but neither is compatible with a plausible
third reading: a maintainer building a registration frontend that needs to highlight *which* field collided
(email vs. username) reasonably expects `detail` to carry structure (e.g. `{"field": "email", "message":
"..."}`) — which no longer "stays `{"detail": "..."}"` as a string, yet arguably still satisfies the
convention's literal JSON shape (a `detail` key exists). Whichever of these two shapes ships first, the other
side's client code (or docs, or tests) written against the other shape breaks.

**Fix needed:** Pin down (a) uniqueness enforcement mechanism (DB unique constraint + catch `IntegrityError`
is the only race-safe option — the spine should say so explicitly, not leave it inferable from "should be
obvious"), (b) precedence when both columns collide (one combined query producing one deterministic answer,
not two sequential existence checks), and (c) the exact `detail` value type (string vs. object) for the 409
case specifically, since "matches existing endpoints" under-specifies it.

### Hole 4 — `DATABASE_URI` has "one env var," not "one reader" — config.py vs. direct `os.environ` access

**AD/Convention implicated:** Consistency Convention ("`DATABASE_URI` is the single env var for both the MCP
proxy path and this direct path").

**Scenario, grounded in existing code:** `config.py` (the repo's one existing config module) only holds
`OPENAI_API_KEY`/`OPENAI_MODEL`, read via `os.getenv` at import time — no `DATABASE_URI` there. Meanwhile
`mcp_server/client.py` reads `DATABASE_URI` directly via `os.environ.get("DATABASE_URI")` inside
`MCPClient.__init__` (line 38), bypassing `config.py` entirely, with no eager validation (empty string/`None`
is accepted at construction and only raises inside `connect()`). Builder A, extending the existing config
module's convention, adds `DATABASE_URI = os.getenv("DATABASE_URI")` to `config.py` and has `core/db.py`
import it from there, raising at import time if unset (fail-fast). Builder B copies the `MCPClient` precedent
literally — `core/db.py` reads `os.environ.get("DATABASE_URI")` directly, deferring the missing-var failure
until first connection attempt (fail-late).

**The incompatibility:** Both are "the single env var." But now there are two different failure semantics for
the exact same misconfiguration (missing `DATABASE_URI` in the environment): the app either refuses to start
at all (Builder A) or starts fine and only 500s on the first `/auth/register` call, possibly minutes or hours
later in production (Builder B) — while the MCP proxy path, per the existing `mcp_server/client.py` code,
already exhibits the fail-late behavior. A maintainer who assumes "one env var" means "one validation
behavior across both paths" (reasonable reading of the convention's intent) will be surprised when auth and
the MCP path disagree on when/how they surface a missing var.

**Fix needed:** State whether `DATABASE_URI` is read via `config.py` (single source, validated once) or
independently by each consumer (as `mcp_server/client.py` already does) — and if independently, state the
required failure semantics (fail-fast at import vs. fail-late at first use) so the two paths behave the same
way under the same misconfiguration.

### Hole 5 — AD-2's "auth reads or writes" scope boundary around the `users` table is not the same as "the `users` table"

**AD/Convention implicated:** AD-2 ("`postgres-mcp` is never used for auth reads or writes"), Consistency
Convention ("`services/auth_service.py` is the only writer to `users`" — writer only, not reader).

**Scenario:** A future maintainer (post-MVP, building an admin/reporting feature not covered by this spine,
e.g. "list registered users this week") reasons: AD-2 forbids `postgres-mcp` for *auth* reads/writes, and this
new feature isn't authentication — it's reporting. They wire an LLM-facing MCP tool call (`execute_sql`
through the existing `postgres-mcp` path already used by `/chat`) to `SELECT` from `users` directly for a
dashboard, never touching `services/auth_service.py`. A second maintainer, reading the same AD-2, assumes it
means "the `users` table is entirely off-limits to the generic SQL MCP path," full stop, and blocks that PR in
review — but has no rule text to point to, since AD-2's own words say "auth reads or writes," and this read
is neither part of "auth" nor a "write." Both maintainers can defend their reading of AD-2 to the letter.

**The incompatibility:** One codebase path now has the LLM-facing, prompt-injectable `execute_sql` MCP tool
capable of reading `hashed_password` and other `users` columns directly (defeating the entire security
rationale AD-2 states — "credential storage" risk — since a read of `hashed_password` via a generic
SQL-execution tool is exactly the exposure AD-2 was written to prevent, even though the literal rule text only
names "reads or writes" in the context of the *auth flow*, not the table itself).

**Fix needed:** Reword AD-2's scope from "auth reads or writes" to name the actual boundary: no MCP/LLM-facing
SQL tool may ever touch the `users` table (or at minimum, the `hashed_password` column) for any purpose, not
just the registration/login flow — table-scoped, not feature-scoped.

## Secondary / Lower-Severity Notes

- **Request/response payload shape is entirely unspecified.** The ERD defines `full_name` and `phone_number`
  as columns but the spine never says whether they're required or optional in the `POST /auth/register`
  request body, nor whether the `201`/success response returns the created user (and if so, which fields —
  presumably excluding `hashed_password`, but that's inferred, not stated). Two builders could ship
  incompatible request/response Pydantic models for the one shared endpoint.
- **Migration vs. auto-create-schema drift.** Alembic is in the Stack/Structural Seed, but nothing forbids a
  builder from also adding a `Base.metadata.create_all()` convenience call in `core/db.py`'s init path (a
  common shortcut). If one environment's schema comes from `create_all` (whatever the current `models.py`
  looks like at that moment) and another's comes from replaying `alembic/versions/*`, the two can drift
  (e.g. a unique constraint added in a later migration that `create_all` — run against an earlier version of
  `models.py` — never produced). Deferred section already flags the deployment envelope as unresolved; this
  is a sharper edge of that same gap worth naming.
