# Vendored repositories

This directory contains **vendored copies** of third-party repositories, imported
on 2026-06-01. Each was cloned at its then-current `HEAD` (a shallow snapshot),
and the upstream `.git` metadata was stripped — so these are plain file copies,
not submodules. They do **not** auto-update.

> ⚠️ **Licensing:** Each vendored project retains its own license (see the
> `LICENSE`/`COPYING` file inside each directory). These copies are governed by
> their respective upstream licenses, **not** by this repository's license.
> Review each before redistributing or using in production.

## Layout

| Path | Source | Notes |
|------|--------|-------|
| `superpowers/` | https://github.com/obra/superpowers | Full snapshot |
| `taste-skill/` | https://github.com/Leonxlnx/taste-skill | Full snapshot |
| `playwright/` | https://github.com/microsoft/playwright | Shallow snapshot (large monorepo) |
| `anthropics/<repo>/` | https://github.com/anthropics/`<repo>` | All 68 public org repos |

The `frontend-design` plugin referenced by
`claude plugin install frontend-design@claude-plugins-official` is **not** a
separate repo — it ships inside `anthropics/claude-plugins-official/`.

## Anthropic org repositories (68)

All public, non-fork repositories under the `anthropics` org at import time,
including the three you named explicitly: `claude-code-action`,
`claude-plugins-official`, and `financial-services`. Archived repos are included.

## Refreshing

These are point-in-time copies. To update one, re-clone upstream and replace the
directory contents (keeping the `.git` stripped).
