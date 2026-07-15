---
name: 'Web-Verification Review — Architecture Spine (Secure Auth / User Registration MVP)'
type: review
target: '_bmad-output/planning-artifacts/architecture/architecture-mcp-tool-calling-2026-07-14/ARCHITECTURE-SPINE.md'
created: '2026-07-14'
---

# Web-Verification Review — ARCHITECTURE-SPINE.md

## Scope

Check whether the technical decisions committed in the spine (Stack table versions, AD-3 JWT-vs-sessions,
Argon2id-vs-passlib rationale, asyncpg/SQLAlchemy async pairing) are grounded in verifiable current reality
(as of July 2026) rather than asserted from stale training data.

## What was searched

1. `SQLAlchemy 2.0.51 release changelog`
2. `asyncpg 0.31.0 release pypi`
3. `alembic 1.18.5 release pypi`
4. `argon2-cffi 25.1.0 release pypi`
5. `OWASP password storage cheat sheet 2026 Argon2id recommendation`
6. `SQLAlchemy async engine asyncpg driver create_async_engine postgresql+asyncpg`
7. `SQLAlchemy 2.1 release status 2026 stable`
8. `FastAPI JWT vs server-side sessions single process best practice 2026`
9. `alembic 1.18.5 SQLAlchemy 2.0.51 compatibility requires`
10. `passlib unmaintained bcrypt 4.0 compatibility issue 2025 2026`

## Findings

### 1. Stack table versions — all real, current, mutually compatible

| Package | Claimed | Verified |
| --- | --- | --- |
| SQLAlchemy (async) | 2.0.51 | Real release, dated 2026-06-15 per the SQLAlchemy project blog (`sqlalchemy.org/blog/2026/06/15/sqlalchemy-2.0.51-released`). This is the current 2.0.x line — **not** superseded by a stable newer major: SQLAlchemy 2.1 exists only as a beta (2.1.0b3, 2026-06-27) with no announced stable release date, so pinning 2.0.51 rather than a 2.1 pre-release is the correct, conservative call for a production auth feature. |
| asyncpg | 0.31.0 | Real release, dated 2025-11-24 (PyPI/GitHub). Current latest at review time. No newer stable release supersedes it. |
| alembic | 1.18.5 | Real release, dated 2026-06-25 (alembic docs "Front Matter" page confirms 1.18.5 is the current doc version). Alembic requires SQLAlchemy ≥1.4, and its 1.18.x line's autogenerate work explicitly targets SQLAlchemy 2.0's bulk-reflection APIs — confirms it's designed to pair with the 2.0.x line pinned here, not just tolerating it. |
| argon2-cffi | 25.1.0 | Real release, dated 2025-06-03 (PyPI/GitHub). Adds official Python 3.13/3.14 support, drops Python 3.7. Current latest; no newer release found. |

No hallucinated version numbers, no dates that don't line up, no version skew between SQLAlchemy and Alembic.
Verdict: **Stack table is well-grounded.**

### 2. Argon2id via argon2-cffi over passlib/bcrypt — claim holds, and the case is stronger than the spine states

OWASP's Password Storage Cheat Sheet (2024+ update) does list Argon2id as the top recommendation, with bcrypt
and scrypt as fallbacks only when Argon2id is unavailable — this matches the spine's citation.

Additionally (not mentioned in the spine, but worth noting as reinforcing evidence): `passlib` — the other
common Python password-hashing wrapper — is unmaintained (last release 2020) and has open, actively-reported
2025–2026 compatibility breakage with modern `bcrypt` releases (bcrypt 5.0 removed an attribute passlib's
backend detection depended on, breaking `passlib[bcrypt]` with a misleading "password too long" error).
This makes `argon2-cffi` (actively released, June 2025) the clearly safer current choice over `passlib`
independent of the algorithm argument. The spine's rationale is accurate but could have cited this as an
additional, concrete reason.

Verdict: **Correctly grounded; even more strongly justified than stated.**

### 3. JWT (stateless) over server-side sessions (AD-3) — directionally reasonable, but one real gap not addressed

Current (2026) discourse is more divided than the spine implies. Multiple 2026 sources explicitly push back on
JWT-as-default for browser-facing session state, precisely because of the revocation problem: JWTs can't be
invalidated server-side without adding a blocklist/store, at which point you've reintroduced server-side state
anyway and lost the main advantage of statelessness. The emerging "best practice" framing in several 2026
pieces is a hybrid — server-side sessions for browser-facing login, JWTs for service-to-service/internal use —
rather than JWT-for-everything.

This doesn't make AD-3 wrong for this project: a single-process FastAPI app with no other services to talk to
gains little from statelessness but also isn't harmed by it, and JWT is still a defensible, common choice here.
But the spine's rationale is silent on revocation (logout / password-change / compromise invalidation), which
is exactly the gap current sources flag as the recurring practical failure mode of "just use JWT." Since AD-3
is explicitly deferred (login isn't built this pass), this is a planning note rather than a blocking objection:
**when login is actually implemented, the future builder should decide how logout/invalidation is handled
(short-lived access token + refresh rotation, or an explicit denylist) rather than assume plain stateless JWTs
solve session management with no further design.**

Verdict: **Not wrong, but under-justified — flag as a gap to close before login ships, not as an error in the spine today.**

### 4. asyncpg + SQLAlchemy 2.0 async engine — confirmed standard, no gotchas

Confirmed via SQLAlchemy's own asyncio documentation and multiple independent tutorials: the async engine is
created via `create_async_engine()` from `sqlalchemy.ext.asyncio` using the `postgresql+asyncpg://` URL scheme
(dialect+driver naming, standard SQLAlchemy convention — no unusual driver name or extra config required).
`asyncpg` is explicitly the dialect SQLAlchemy documents and recommends for async Postgres access. This is the
standard, unsurprising combination; a builder following the spine won't hit a driver-name or config trap.

Verdict: **Confirmed correct, no hidden compatibility trap.**

## Overall Verdict

The spine's technical decisions are grounded in real, current, mutually compatible facts — not hallucinated or
stale. Every pinned version exists, is current, and is not superseded by a stable newer alternative. The
Argon2id choice is not just correct but understates its own case. The one soft spot is AD-3: the JWT rationale
doesn't engage with the revocation/logout problem that 2026 sources treat as the central practical weakness of
stateless JWT for browser sessions — worth a follow-up note when login is actually designed, but not a defect
in what's committed today (registration only, login deferred).
