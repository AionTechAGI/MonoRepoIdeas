# Git workflow

## Branches

- Use `main` as the default branch.
- Create short-lived branches per task or feature.
- Keep unrelated experiments outside this repo or in clearly isolated branches.

## Commits

- Keep commits focused on one change or one cohesive migration.
- Avoid mixing structural moves with unrelated feature work when possible.
- Update docs in the same change when behavior or repo layout changes.

## Pull requests

- Explain what changed and what was verified.
- Call out any follow-up work left on purpose.
- Keep generated outputs out of project roots before opening the PR.

## Reviews

- Use `.github/CODEOWNERS` once the placeholder owner is replaced with the real GitHub username or team.
- Keep project-specific review expectations in the nearest `AGENTS.md`.
