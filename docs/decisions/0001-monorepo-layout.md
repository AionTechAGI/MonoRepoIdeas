# ADR 0001: MonoRepoIdeas layout for C:\develop\MonoRepoIdeas

## Status

Accepted on 2026-04-20.

## Decision

`C:\develop\MonoRepoIdeas` becomes the git root for active product work and is linked to the `AionTechAGI/MonoRepoIdeas` GitHub repository.

The repository uses a lightweight monorepo structure:

- `projects/` for products
- `docs/` for repo process
- `knowledge/` for reusable domain material
- `templates/` for project bootstrapping

Each product owns its local docs and local `AGENTS.md`.

## Why

- The current setup needs shared rules without mixing all project files together.
- A lightweight structure is easier to adopt now than a full shared-package workspace.
- It keeps future GitHub pushes clean and predictable.

## Consequences

- Product-specific rules must stay close to the product.
- Generated reports move out of product roots into `artifacts/`.
- Shared Python packaging can be revisited later if several projects begin sharing code.
