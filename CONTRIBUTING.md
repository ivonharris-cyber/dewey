# Contributing to Dewey

Dewey has one rule: **make memory smaller, not heavier.**

## In scope
- Anything that reduces the context an agent loads — better pointers, tighter classification, pruning stale entries.
- Safety fixes: dry-run defaults, data-loss guards, secret handling.
- Docs, examples, and tests.

## Out of scope (by design)
- Vector databases, embeddings, or heavy graph engines. Dewey is **deterministic and auditable** on purpose.
- Anything that grows the codebase past its budget. **Dewey aims to stay under 1,000 lines.**
  If a change adds lines, show what it removes or earns.
- Reading or storing secret values.

## Before a PR
- Keep functions small; keep the dependency list **empty** (standard library only).
- `dewey doctor` is security-critical — changes there need a clear rationale.
- Anything that writes or deletes must **dry-run by default**.

## Run it locally
```bash
pip install -e .
dewey sweep
```
