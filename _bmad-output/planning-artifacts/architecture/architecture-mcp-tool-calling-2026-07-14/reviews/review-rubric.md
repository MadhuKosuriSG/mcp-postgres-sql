# Review — ARCHITECTURE-SPINE.md (Secure Authentication System — User Registration MVP)

Reviewed: 2026-07-14
Target: `_bmad-output/planning-artifacts/architecture/architecture-mcp-tool-calling-2026-07-14/ARCHITECTURE-SPINE.md`
Method: read the spine in full; cross-checked against the live repo (`main.py`, `api/chat.py`, `api/mcp.py`, `services/chat_service.py`, `mcp_server/client.py`, `core/` directory contents), the source docs it cites (`docs/architecture.md`, `docs/data-models.md`, `docs/development-guide.md`), the drafting `.memlog.md`, and live PyPI version listings for the four stack entries.

## Overall verdict

Solid, disciplined spine — it correctly ratifies the brownfield layering, its ADs are concrete and mostly enforceable, its stack versions are verified-current, and its Deferred list is honestly scoped. One real gap: JWT signing-key/secret handling is never acknowledged anywhere, even as a one-line deferred note, despite the checklist explicitly flagging this as an operational-envelope item to watch and despite the repo having no existing secrets-management convention to fall back on.

## Checklist walkthrough

### 1. Does it fix the real divergence points for the feature-level builder, missing none?

Covers the ones that matter: identity model vs. shared-secret gate (AD-1), which DB path owns writes (AD-2), session/token strategy direction (AD-3), scope boundary (AD-4), file/module placement (AD-5), sync-vs-async DB access (AD-6), error-code mapping (AD-7). These are exactly the axes on which two independent builders of "add registration to this app" could plausibly diverge incompatibly.

Not covered, and arguably should be at least a Deferred bullet: **JWT signing-key/secret storage and rotation**. AD-3 commits to "signed JWTs" as the future direction but says nothing about where the signing key lives, whether it's symmetric (HS256) or asymmetric (RS256), or how it's provisioned. See finding F1.

Not covered, but correctly out of scope as "seed" rather than a missed invariant: field-level validation rules (password complexity, phone number format), nullability of `full_name`/`phone_number`, and whether uniqueness is enforced via DB constraint vs. app-level pre-check. These are data-shape/data-validation concerns, not structural-divergence concerns, and the spine's own altitude framing (data shape = seed) correctly excludes them.

### 2. Is every AD's Rule enforceable and does it prevent the divergence it claims to prevent?

- AD-2, AD-4, AD-5, AD-6, AD-7: concretely checkable by inspecting code (imports used, HTTP status codes returned, which module a function lives in, sync vs. async engine calls). Each genuinely blocks the divergence it names.
- AD-3: not enforceable *in this pass* because no login code exists yet to check — but that's expected for an AD that binds *future* work; it exists to pre-empt a later builder's choice, not to gate this build. Acceptable.
- AD-1: weakest of the seven. Its Rule ("auth centers on a persisted `User` identity, not a shared secret or service token") is more a resolved product-intent statement than a code-checkable constraint — there's no single line of code a reviewer greps for to confirm compliance the way AD-6's "no sync engine" is checkable. It's still verifiable in a broader sense (does a `users` table with individual credentials exist, vs. a static API-key check?), and it does correctly resolve a real open question carried over from the brainstorm (`.memlog.md` line 11: "who is this auth for"), so it earns its place — just flagged as the softest of the seven.

### 3. Could anything under Deferred let two builders diverge incompatibly if left unresolved?

No. Each Deferred item is either (a) not yet triggered by this build (login/JWT/refresh, password reset/email verification/RBAC — and the one truly divergence-prone piece of that bucket, session strategy, is already pinned by AD-3so what's left to defer is genuinely inert), or (b) doesn't have a "two builders" scenario in this single-feature pass (test coverage, deployment envelope, abuse protection). The deployment/migration-execution bullet is honestly labeled "unresolved" rather than silently assumed, which is the right call for a repo with zero deployment tooling today.

The one item that *should* have at least a Deferred bullet but has none anywhere in the document is JWT secret/key handling — see F1.

### 4. Is every named technology's version plausible as "verified current"?

Checked live against PyPI (`pip index versions`) on review date:

| Package | Spine version | Latest on PyPI | Verdict |
| --- | --- | --- | --- |
| SQLAlchemy | 2.0.51 | 2.0.51 (2.1 still pre-1.0/beta line) | Correct, latest 2.0.x |
| asyncpg | 0.31.0 | 0.31.0 | Correct, latest |
| alembic | 1.18.5 | 1.18.5 | Correct, latest |
| argon2-cffi | 25.1.0 | 25.1.0 | Correct, latest |

No stale or hallucinated versions. Argon2id via `argon2-cffi` is also the right call per current OWASP guidance, and the spine correctly notes there's no prior hashing convention in the repo to preserve.

### 5. Does it ratify rather than contradict the brownfield codebase?

Yes, on every point checked:

- "Zero auth today" — confirmed; `main.py` wires no auth middleware/dependency anywhere.
- "No in-repo DB layer" — confirmed; `core/` exists only as an empty `__init__.py` stub today, and `docs/architecture.md` independently states "no in-repo data layer... Data access to PostgreSQL happens entirely through the external postgres-mcp server."
- Layering `api/ → services/ → mcp_server/` — confirmed live in `services/chat_service.py` (imports `mcp_server.manager.MCPManager`) and `api/chat.py`/`api/mcp.py` (both route through `services`/`mcp_server` via `Depends`). The spine's addition of `core/` as a new sibling leaf under `services/` doesn't rename or restructure anything existing.
- `DATABASE_URI` reuse (Consistency Conventions row) — confirmed grounded: `mcp_server/client.py:38` reads `os.environ.get("DATABASE_URI")` today; the spine's plan for `core/db.py` to read the same var is a real single-source-of-config decision, not an invented claim.
- AD-7's carve-out from the existing blanket `502` pattern — confirmed the existing pattern first: both `api/chat.py` and `api/mcp.py` today raise `HTTPException(status_code=502, ...)` on service errors. AD-7 correctly narrows `502` to "MCP/LLM upstream failures" and gives auth its own `409`/`422`, without silently overriding the existing convention for the two endpoints that already rely on it.

### 6. Is every feature-level structural dimension decided/deferred/flagged — nothing silently unaddressed?

Mostly yes. Design paradigm, layering, DB-access ownership, sync/async, error mapping, session strategy direction, and scope are all explicit. The deployment/migration-execution envelope is explicitly named as unresolved in Deferred, which satisfies the "at least acknowledged" bar from the checklist.

The one silent gap: **JWT signing-key/secret handling** is not mentioned anywhere — not as an AD, not as a Deferred bullet, not even as a caveat under AD-3. This matters because (a) the checklist explicitly calls it out as an operational-envelope item to verify, and (b) the repo's only existing precedent for secret-like config (`OPENAI_API_KEY`) is a plain `.env` var with no rotation/vaulting story, so a future login-builder has no signal here at all — they could pick a hardcoded dev secret, an unrotated env var, or a KMS-backed key, each with materially different operational consequences, and nothing in this spine or its Deferred list would have prevented or even anticipated the divergence.

### 7. Any placeholder text, template artifacts, or vague/unenforceable language?

None found. `binds: []` and `companions: []` in the frontmatter are empty but legitimate (this is the first spine for this scope; no prior spine to bind to, no companion docs generated yet) — not template leftovers. All seven ADs have concrete Binds/Prevents/Rule triads with specific file paths, status codes, and package names rather than generic filler. The one soft spot is AD-1's Rule reading more like a resolved product decision than a hard enforceable constraint (see finding 2 above), but it's not vague/placeholder text — it's a legitimate, if softer, invariant.

## Findings (ranked)

**F1 — Moderate — JWT signing-key/secret handling is completely unaddressed.**
Nowhere in the document — not AD-3, not Deferred — is there any acknowledgment of how the future JWT signing key will be stored, whether it's symmetric or asymmetric, or how it differs from the repo's existing plain-`.env` secret convention (`OPENAI_API_KEY`). A future login-implementer has zero guidance and could pick an approach that's operationally incompatible with whatever deployment story eventually gets built (also still unresolved). Recommend adding one line to Deferred, e.g.: "JWT signing-key storage/rotation strategy — not decided; will need to be resolved before AD-3's direction is implemented, likely alongside the deployment/environment envelope."

**F2 — Minor — AD-1's Rule is softer/less code-checkable than its six siblings.**
"Auth centers on a persisted `User` identity, not a shared secret or service token" is a resolved product decision (correctly closing an open question from the brainstorm) but isn't grep-able the way AD-2/AD-6/AD-7 are. Not a defect requiring a rewrite, just the weakest link in an otherwise consistently enforceable set — worth a reviewer's eye when checking compliance later rather than assuming it's automatically checkable.

**F3 — Cosmetic — Design Paradigm section doesn't note that `core/` already exists (as an empty stub).**
The prose reads as if `core/` is being introduced fresh; in reality it's an existing empty `__init__.py`-only package (confirmed on disk) that this build will be the first to populate. No functional impact — the spine's plan is consistent with the actual state — but a reader relying solely on the spine (without checking the repo) would get a slightly inaccurate mental model of "what already exists."

## Passes worth noting (not findings, but verified good)

- All four stack versions verified as the current latest release on PyPI as of the review date — no staleness or hallucination.
- Brownfield ratification is accurate on every checkable point: zero existing auth, no in-repo DB layer, correct existing layering, correct `DATABASE_URI` reuse, and a correctly-scoped carve-out from the existing `502` error pattern rather than a silent override.
- The Deferred list is honest rather than evasive — it explicitly says migration-execution strategy is "unresolved" instead of assuming an answer, and it doesn't bury any item that would actually cause two builders to diverge incompatibly within this pass's scope.
