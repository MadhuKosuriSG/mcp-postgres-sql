---
name: 'Security Review — User Registration MVP Architecture Spine'
type: review
reviewed-doc: '_bmad-output/planning-artifacts/architecture/architecture-mcp-tool-calling-2026-07-14/ARCHITECTURE-SPINE.md'
lens: security
created: '2026-07-14'
---

# Security Review — Registration Feature Architecture Spine

## Verdict

The spine gets the big structural call right — Argon2id, async SQLAlchemy off the MCP path, no server-side session store — and it explicitly names rate-limiting as a deferred gap rather than hiding it. But it has one finding severe enough to undermine AD-2's entire premise (the DB-ownership split is a code convention, not a DB-enforced boundary, so the existing unrestricted-`execute_sql` MCP chat path can still read the new `users` table's hashed passwords/PII once it exists), plus several unaddressed gaps: no enumeration-attack mitigation for the 409 duplicate-account response, no password strength/policy invariant, and PII handling (phone_number, full_name) named in the ER diagram but never discussed as a data-handling concern.

## Findings

### 1. [HIGH] AD-2's "separate DB access path" is a code convention only — not enforced at the DB level, and the existing MCP chat path can already read the future `users` table

AD-2 states: "`postgres-mcp` is never used for auth reads or writes" and frames this as preventing "password/credential writes going through a generic LLM-facing SQL-execution MCP tool (security... risk)." This framing implies the risk is solved. It is not — it is only *avoided by convention on the write path*, and not addressed at all on the read path.

Verified against the actual repo:

- `.mcp.json` explicitly launches `postgres-mcp` with `--access-mode=unrestricted`; `mcp_server/client.py` launches the same subprocess without that flag, meaning the app's runtime behavior depends on `postgres-mcp`'s undocumented default access mode — not a documented, deliberate restriction.
- `services/chat_service.py` forwards **every** MCP tool the server advertises straight into the OpenAI `tools=` list with no allowlist/denylist, and forwards **any** tool name/arguments the LLM emits straight to `call_tool` in `mcp_server/client.py`. `docs/api-contracts.md` itself notes the tool set "is not fixed in this codebase" and includes `execute_sql`-style tools.
- The new SQLAlchemy layer and the existing MCP proxy are both wired to read `DATABASE_URI` — the **same** connection string, i.e. the same DB role/credentials, per the spine's own Consistency Conventions row ("`DATABASE_URI` is the single env var for both the MCP proxy path and this direct path").
- No schema separation, no restricted DB role/grants, and no table-level allowlist exist anywhere in the repo for the MCP path.

Net effect: once the `users` table exists, an LLM-driven chat turn can call the MCP `execute_sql` tool and `SELECT * FROM users`, retrieving Argon2id hashes, emails, usernames, phone numbers, and full names — fully outside the app's own auth code, with AD-2 providing zero technical protection against it. AD-2's "Prevents" clause is aspirational, not architected.

**Recommendation the spine should adopt (or explicitly defer with a named risk owner):** either (a) provision a distinct, least-privilege Postgres role for the `postgres-mcp` connection — e.g. no `SELECT`/`INSERT`/`UPDATE`/`DELETE` grants on `users`, or a `REVOKE ALL ON users FROM <mcp_role>` — with a distinct `DATABASE_URI`-equivalent env var for the MCP subprocess, or (b) put the `users` table in a separate schema not exposed to the MCP role's search path, or (c) explicitly add this to Deferred with the risk spelled out ("the LLM tool-calling path currently has unrestricted read access to any table including `users`; mitigating this requires DB-role changes out of scope for this pass") rather than implying AD-2 already closes it.

### 2. [MEDIUM] No mitigation named for account/email enumeration via the 409 duplicate response

AD-7 and the Consistency Conventions table both specify `409` for "duplicate email/username." A registration endpoint that distinguishes "this email is taken" (409) from "registration succeeded" (2xx) is a textbook account-enumeration oracle — an attacker can probe arbitrary email addresses to learn which are registered users, which matters more here than in a typical app because this system stores phone_number and full_name (see Finding 4) alongside email. The spine should at minimum name this as a known, accepted tradeoff (common for registration UX) or note a mitigation path (generic response + async "if this email is already registered" notification email, once email-sending exists) for a future pass. Currently it is not mentioned at all.

### 3. [MEDIUM] No password strength/policy invariant

The spine specifies the hashing algorithm (Argon2id — a correct, current choice) but names no invariant for input-side password policy (minimum length, rejection of trivially weak passwords, max length to bound Argon2id CPU cost per request). Argon2id without a minimum-length or max-length rule creates two distinct risks: weak passwords hashed just as strongly as strong ones, and a trivial DoS vector (very long password strings inflating per-request Argon2id CPU time, since Argon2id cost scales with input in some configurations and at minimum wastes CPU on hashing attacker-controlled arbitrary-length input). A one-line rule ("passwords are length-bounded — e.g. 8–128 chars — before hashing") belongs in Invariants or Consistency Conventions, not left to whoever writes `services/auth_service.py`.

### 4. [MEDIUM] `phone_number` and `full_name` are named in the ER diagram but never discussed as PII / data-handling concerns

The `USER` entity in the Structural Seed ER diagram includes `phone_number` and `full_name` as plaintext columns with no companion invariant about: (a) whether either field is optional or required, (b) whether phone_number needs format validation/normalization (raising a minor injection/consistency concern if used later for SMS-based verification or MFA), (c) any note that this is PII subject to data-protection obligations (access logging, deletion-on-request, breach-notification scope) beyond the password-specific "never logged, never returned" rule. The existing "never logged, never returned in any response" rule in Consistency Conventions is scoped explicitly to *passwords* — it's ambiguous whether `full_name`/`phone_number` are meant to be returned in the registration response (e.g., as a confirmation echo) or withheld. Given Finding 1 (MCP path can read this data too), the PII surface here is larger than the spine currently acknowledges. At minimum, the spine should state whether the registration response returns any user fields at all, and which ones.

### 5. [LOW] Deferred section correctly flags rate-limiting/bot-protection as a real gap — no change needed, noted as a positive

Unlike Findings 1–4, this is not a gap: "Registration abuse protection (rate limiting, bot/spam mitigation on `POST /auth/register`)" is explicitly called out in Deferred as "a real gap for a security-facing endpoint rather than silently assumed away." This is the correct treatment for an architecture-altitude document — name the gap, don't pretend it's solved, don't silently omit it. Flagging this because the review brief asked whether Deferred adequately surfaces this risk, and it does.

### 6. [LOW] No invariant on transport-layer enforcement (HTTPS) or on request logging elsewhere in the app that could incidentally capture the registration payload

Checked `services/chat_service.py`, `api/chat.py`, and `main.py` directly — there is no request/response body logging middleware in the current codebase, so there is no existing log-leak vector for the plaintext password in transit through app logs today. This is a genuine non-finding, included so the review isn't read as having missed it. However, the spine has no invariant preventing a *future* contributor from adding blanket request-logging middleware (common when someone adds observability) that would then capture the plaintext password in `POST /auth/register` request bodies before it reaches the hashing step. Given "Deployment/environment envelope" is already Deferred, this could be folded into that deferred item with one added sentence: "any future request-logging/observability middleware must exclude request bodies for `/auth/*` routes."

## Summary Table

| # | Severity | Area | One-line issue |
| --- | --- | --- | --- |
| 1 | HIGH | DB-ownership split / AD-2 | Convention-only separation; unrestricted MCP `execute_sql` path can already read future `users` table (hashes, email, phone, name) — same `DATABASE_URI`/role, no schema or grant separation |
| 2 | MEDIUM | Registration endpoint | 409 duplicate-email/username response is an email-enumeration oracle; unaddressed |
| 3 | MEDIUM | Password handling | No length/complexity bound named before Argon2id hashing — weak-password and CPU-DoS exposure |
| 4 | MEDIUM | PII handling | `phone_number`/`full_name` named in schema but not discussed as PII; unclear if returned in registration response |
| 5 | LOW (positive) | Deferred section | Rate-limiting/bot-protection gap is correctly and explicitly named, not silently omitted |
| 6 | LOW | Logging | No current log-leak vector, but no invariant guards against future request-logging middleware capturing plaintext passwords on `/auth/*` |
