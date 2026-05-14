# AGENTS.md

## Repository Expectations
- Treat `C:\develop\MonoRepoIdeas` as the git root for active product work.
- Keep this file short and repo-wide; put domain rules in the closest project-level `AGENTS.md`.
- Every product lives in `projects/<ascii-slug>/`.
- Every product should have its own `README.md`, `AGENTS.md`, `docs/`, `src/`, and `tests/`.
- Keep generated outputs in `artifacts/` or `outputs/`, not in the project root.
- Avoid absolute local paths in scripts and launchers.
- When behavior changes, update the nearest project docs and any relevant repo docs.
- Commit completed changes before ending a work session so another Codex session can continue from a clean, auditable state.

## Navigation
- Start with `README.md` in the repo root for the monorepo map.
- Use `docs/` for process, conventions, and decisions.
- Use `knowledge/` for reusable domain knowledge that may help multiple projects.
- Use the nearest project `AGENTS.md` for domain and workflow rules.

## Current Validation Commands
- For `projects/scanner/`, run `py -m unittest discover -s tests` from `projects/scanner/`.
- Prefer project-local commands documented in each project's `README.md` over inventing new ones.
