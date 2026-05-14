# MonoRepoIdeas

`MonoRepoIdeas` is the working monorepo at `C:\develop\MonoRepoIdeas` and is linked to:

- [AionTechAGI/MonoRepoIdeas](https://github.com/AionTechAGI/MonoRepoIdeas)

## What lives here

- `projects/` contains each product in its own folder.
- `docs/` contains repo-wide process and operating docs.
- `knowledge/` contains reusable research notes and domain knowledge.
- `templates/project-template/` is the starting point for a new project.
- `.github/` contains review and CI metadata.

## Current projects

- `projects/scanner/` is the current valuation and market research app migrated from `stock_valuation_lab`.

See also:

- [projects/README.md](./projects/README.md)

## How to work in this repo

1. Put each new idea in `projects/<ascii-slug>/`.
2. Add a local `README.md` and `AGENTS.md` inside that project.
3. Keep generated files in `artifacts/` or `outputs/`, not in the project root.
4. Keep long-lived conventions in `docs/` and long-lived knowledge in `knowledge/`.

## Quick start for scanner

```powershell
cd C:\develop\MonoRepoIdeas\projects\scanner
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Run tests from the project root:

```powershell
cd C:\develop\MonoRepoIdeas\projects\scanner
py -m unittest discover -s tests
```

## Creating a new project

1. Copy `templates/project-template/` into `projects/<ascii-slug>/`.
2. Rename the placeholders in the new project's `README.md` and `AGENTS.md`.
3. Add project-specific docs and tests before pushing the first branch.
