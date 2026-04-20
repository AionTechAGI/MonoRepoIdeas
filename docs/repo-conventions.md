# Repo conventions

## Layout

- Put active products in `projects/<ascii-slug>/`.
- Keep repo-wide process docs in `docs/`.
- Keep reusable domain references in `knowledge/`.
- Keep starter scaffolding in `templates/`.

## Project naming

- Use ASCII slugs for project folders.
- Use human-readable names inside each project's `README.md`.
- Avoid spaces in project directory names.

## Project minimums

Each project should include:

- `README.md`
- `AGENTS.md`
- `docs/`
- `src/`
- `tests/`

## Outputs

- Generated reports do not belong in a project root.
- Store deliverables in `artifacts/`.
- Store disposable outputs in `outputs/` or `artifacts/generated/`.

## Scripts and paths

- Prefer relative commands and paths.
- Do not hard-code local user directories in launch scripts.
- Document run commands in the project `README.md`.
