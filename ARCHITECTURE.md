# Chitiyu Architecture Constraints

## Domain Boundary Rule — Non-Negotiable

Each domain in `backend/domains/` is treated as a separately deployed
microservice. These rules apply to every PR:

1. No domain may import from another domain
2. No domain may query another domain's DB tables
3. All cross-domain communication routes through `orchestrator/` only
4. Each domain owns its own DB tables and migrations

Violation check:
  grep -r "from domains\." backend/domains/
Should return only same-domain imports (e.g. health importing health.db).
