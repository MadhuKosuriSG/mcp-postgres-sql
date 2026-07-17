## Deferred from: code review of story-1-1-register-a-new-account (2026-07-15)

- **`mcp_manager.initialize()` raising before `yield` leaves `shutdown()`/`dispose_engine()` unreached** — pre-existing lifespan structure (no `try`/`finally`) predates this story; this story's `dispose_engine()` call just inherited the existing pattern. Fixing this means wrapping the whole lifespan in `try`/`finally`, which touches pre-existing `MCPManager` behavior outside this story's scope.
- **No case normalization on email/username uniqueness** (`Foo@x.com` vs `foo@x.com` currently treated as distinct) — this is a product decision for Story 1.2 (which owns uniqueness enforcement), not something Story 1.1's raw DB `UNIQUE` constraint needs to resolve.
