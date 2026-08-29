# Project instructions for Claude Code

These instructions apply to this repository (`sydney-expenses` / Receiptly) only.

## Verification before commit

After completing an implementation task:

1. Run all relevant verification for what changed:
   - Backend: `cd backend && source .venv/bin/activate && pytest`, and if models/migrations changed, verify `alembic upgrade head` on a fresh database.
   - Frontend: `cd frontend && npm run lint && npx tsc -b && npm test && npm run build`.
2. Only when all required verification passes, create a meaningful git commit and push it to the current branch's configured remote (`origin`).
3. Do not push partially completed or failing work. If verification fails, fix the issue and re-verify before committing.

## Git safety

- Never commit secrets, `.env` files, API keys, tokens, credentials, the SQLite database, uploaded receipt images, dependency directories (`node_modules`, `.venv`), caches, or generated build artifacts (`dist/`, `__pycache__/`, `.pytest_cache/`). Check `.gitignore` covers these before adding new file types.
- Never force-push (`git push --force`) or rewrite shared/remote history (`git rebase` on pushed commits, `git reset --hard` on a shared branch).
- Before any command that could discard uncommitted work, run `git status` first.
- If pushing fails because authentication or user input is required, report the exact blocker to the user and do not ask them to paste a token into the conversation — direct them to authenticate locally (e.g. `gh auth login`, or configuring a git credential helper).
- Prefer creating new commits over amending existing ones, unless explicitly asked to amend.

## After every completed task

Summarize, at minimum:
- The commit hash(es) created.
- The branch pushed to, and confirmation the push succeeded (or the exact reason it didn't).
- Any tests/checks skipped and why.
