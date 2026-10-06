---
name: project-status-tracking
description: Use when starting new feature/phase work on this project, finishing a phase or sub-feature, discovering a deviation from the original plan, when asked for a status update / "what's implemented so far", or when asked about the project's folder structure / architecture layout -- tracking/IMPLEMENTATION_STATUS.md is the authoritative, maintained record of what's actually built vs. planned, and this skill also carries the current, confirmed folder structure.
---

# Project Status Tracking

`tracking/IMPLEMENTATION_STATUS.md` is the authoritative "what's done vs. planned"
document for this repo. It exists because `PROJECT_PLAN.md` (the architecture/history
doc) goes stale on status fast and has already been caught contradicting itself once
(see that file's own notes). This skill keeps one document as the current source of
truth instead of letting status drift across `PROJECT_PLAN.md`, `README.md`, and
whatever a given session happens to remember.

## When to read it

- Before starting work on any new phase or feature, to know what's actually built
  (not what a stale doc claims) and avoid re-doing or contradicting existing work.
- When the user asks "what's implemented," "what's left," "did you finish X," or
  similar status questions -- read this file first rather than re-deriving status from
  scratch every time, though always spot-check against the real code before relying on
  an old claim (see "Keeping it accurate" below).

## When to update it

Update `tracking/IMPLEMENTATION_STATUS.md` immediately whenever:
- A phase's status changes (stub -> real, in-progress -> done).
- A new deviation from the original planned architecture happens (a file moved, a
  planned component was replaced/consolidated, a planned abstraction was dropped in
  favor of something simpler).
- A gap/risk listed in its "Known gaps / risks" section gets closed, or a new one is
  discovered.
- Significant uncommitted work lands or gets committed (the "durable?" column is
  load-bearing -- don't let it go stale silently).

Edit the existing phase tables/sections in place -- this document describes *current
state*, not a changelog. Don't append dated entries; git history is the changelog.

## Keeping it accurate

Before trusting an existing claim in the document for anything consequential (deciding
what to build next, telling the user something is "done"), spot-check it against the
real repo state:
- `git status`/`git log` for what's actually committed vs. still working-tree-only.
- A quick `Read`/`Grep` of the file(s) the claim is about -- a "1-line stub" claim is
  checked by actually opening the file, not assumed from last time.

If a claim turns out stale, fix it as part of the same turn you noticed it, don't just
work around it.

## Doing a full re-audit

If the document looks significantly out of date (e.g. after a long gap, or after a big
refactor landed), re-audit properly rather than patching piecemeal: read the current
plan/architecture doc, list the real directory tree, check each planned phase's files
for stub-vs-real content, check git status for durability, and rewrite the affected
sections. For a repo this size, delegating the read-everything-and-report step to an
Explore agent (one prompt covering: plan doc, directory tree, phase-by-phase file reads,
git status, deviations) works well and keeps the main session's context clean -- then
turn its report directly into the document's sections yourself.

## Current folder structure (as of 2026-10-06)

Confirmed by listing the real repo, not copied from the original plan doc (several
things moved/were renamed/dropped since then -- see "Deviations" in
`tracking/IMPLEMENTATION_STATUS.md`). Dependency direction is strictly one-way:
`orchestration` -> `flows` -> `components` -> `factory`. Nothing in `flows/` or below
ever imports from `orchestration/`.

```
dell-automation/
├── orchestration/        # THE real entry point. RoleRunner.run(role, run_id) wires
│                         # each role's flows together in order (sign-in -> pairing ->
│                         # ...). Nothing else calls into or out of this layer.
├── flows/                # Individual flow classes, one responsibility each (SignInFlow,
│   ├── target/           # TargetPairingFlow, SourcePairingFlow, ...). Target-only vs
│   └── source/           # Source-only split -- confirmed no shared/parameterized-by-
│                         # role flow exists or is planned (Source has no auth step).
├── components/           # Page Objects flows compose -- no business logic, just
│   ├── shared/           # screen/dialog interactions. Same target/source split, plus
│   ├── target/           # a thin shared/ for genuinely cross-role chrome (nav bar).
│   └── source/
├── locators/              # Locator tuples only (by, value) -- one module per
│   ├── target/            # screen/component, imported by the matching components/ file.
│   └── source/             # Same target/source split as components/.
├── factory/              # Infrastructure: Session (app+browser+WinAppDriver lifecycle),
│                         # config.py (env-var driven constants), coordination_client.py,
│                         # ocr.py, retry.py, logger_factory.py, prerequisites.py.
├── coordination_service/ # The FastAPI relay itself (app.py) + its own README. Runs
│                         # standalone (see utils/run_coordination_service.py), not
│                         # imported by orchestration/flows -- they talk to it over HTTP
│                         # via factory/coordination_client.py only.
├── utils/                # Operational helper SCRIPTS (not business logic) meant to run
│                         # unattended/standalone -- starting the Coordination Service,
│                         # the app-crash watchdog. Confirmed distinction from tools/
│                         # (2026-10-06): utils/ is for things you'd run in a real
│                         # workflow; tools/ is for testing/diagnosing during development.
├── tools/                # Dev/debug/testing entry points ONLY -- never imported by
│                         # orchestration/flows/components/factory, and never the
│                         # reverse. Includes permanent regression tests (_test_*.py),
│                         # one-off diagnostics (_peek_*.py), interactive CLI launchers
│                         # (run_sign_in_flow.py, launch_target_app.py), and planning
│                         # docs. See its own docstrings for what's permanent vs
│                         # disposable -- don't assume everything here is throwaway.
├── tests/                # pytest suite (Session-based fixtures in conftest.py) --
│                         # mostly stubs still (Phase 3+ test files not yet real).
├── assertions/           # Narrow, currently just assertions/target/error_banner.py
│                         # (string constants). Planned common/pairing/transfer
│                         # assertion modules from the original plan were never built --
│                         # see Deviations in tracking/IMPLEMENTATION_STATUS.md.
├── reports/              # Screenshots land in reports/output/screenshots/ (written
│                         # directly by components/base_component.py). No
│                         # ActionReporter/report.html pipeline exists yet -- stubs only.
└── tracking/             # IMPLEMENTATION_STATUS.md -- see this skill's own purpose.
```

When this drifts (a folder gets added/renamed/removed), fix this section in the same
turn you notice it -- don't let it join `PROJECT_PLAN.md` in going stale.

## Format conventions

- Phase-by-phase table at the top (`Phase | Scope | Status | Durable?`) for a one-glance
  view, then a detail section per phase with file paths and justifications.
- A numbered "Deviations from the original planned architecture" list -- append new
  deviations here, don't bury them in prose elsewhere.
- A "Known gaps / risks" section carried forward until each item is actually closed.
- Cite real file paths and class/function names wherever possible so a claim can be
  re-verified later with a plain Grep, not just trusted.
