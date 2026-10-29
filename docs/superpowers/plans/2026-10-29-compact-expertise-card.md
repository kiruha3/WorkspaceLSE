# Compact expertise card implementation plan

> **For agentic workers:** Use superpowers:executing-plans for the parent integration and test-driven-development for UI behavior. Independent preview work is delegated; final parity review is read-only.

**Goal:** Reshape the inside of an expertise card to the approved compact prototype without losing its fields, stages or live form state.

**Architecture:** Keep existing business panels, API clients, permission gates, update events and identity-based keys. Add a read-only work/documents overview with navigation to the same mounted panels; apply compact presentation only inside the card. Details remain mounted when folded.

**Tech stack:** Vue 3, TypeScript, existing Vite/Vitest and CSS; no new dependencies.

**Spec:** User instructions in this chat and `docs/mockups/expertise-card-prototype-v3/coverage.json`. Real Vue/API contracts take precedence over simulated prototype behavior.

## Global constraints

- Change the internal individual expertise card, not `ExpertisesPage.vue` or the registry.
- No backend, DB, permission grants, role changes, new business fields or automatic writes.
- No push. Work in the served checkout as requested, with checkpoint `1b20b3d` for rollback.
- Preserve all stages and real links to the archive, letter and issue-package screens.
- Preserve `v-show` panels and keys by expertise identity; navigation/folding must keep drafts, files, command attempts and dirty guards.
- Preserve restricted/accepted document versions, null versus zero, historical versus operational facts, and draft versus confirmed completion.
- Reference explanations remain under HelpTip; blocking errors stay visible.

## Review focus

1. Quick navigation from a dirty form must not issue a command, reset input or bypass the route guard.
2. Preview folding must not choose another version or automatically open an external source.
3. Access revocation must not leave focus in a removed/hidden tab.
4. A saved result date must not become completion/issuance, especially on historical work.
5. Current allowed_actions and feature flags remain the authority; simulated prototype permissions are not copied.

## Task 1 — checkpoint (complete)

- [x] Inspect working changes, run existing home/card tests: 27 pass.
- [x] Commit the current stand and all reviewed mockups: `1b20b3d`.

## Task 2 — compact overview and navigation

Files: create `frontend/src/modules/expertises/ExpertiseWorkOverview.vue`; modify `ExpertisePage.vue`, `ExpertiseSummary.vue`, `ExpertiseCardLayout.test.ts`.

Interface: overview consumes the full read-only `Expertise`, archive navigation and module availability; emits `navigate` with an existing card tab ID. Parent selects the panel and focuses it after nextTick; it does not call editor start/reset or save.

- [x] Add failing tests for work/documents overview, quick navigation, retained drafts, restricted documents and revoked-tab focus.
- [x] Implement the composition and fold registration/statistics, keeping all existing selectors and components.
- [x] Run card tests and check that navigation produces zero POSTs.

## Task 3 — compact existing panels and preview

Files: `shared/BasisPreview.vue`, its tests, new `shared/ui/compactPresentation.ts`; card-scoped styles in `ExpertisePage.vue`; optional markup-only folding in result/production histories.

Interface: `compactPresentationKey: InjectionKey<boolean>` provided only by the card; optional `BasisPreview.compact` overrides it, default outside the card remains unchanged.

- [x] Add failing tests for lazy compact preview and preserved version/error state after folding.
- [x] Preserve all preview modes and existing explicit external-view controls.
- [x] Reduce card-local spacing; keep editor and picker instances mounted.
- [x] Run preview, document-picker and all expertise tests.

## Task 4 — parity review and validation

- [x] Review the diff independently against existing child-component contracts and the coverage map.
- [x] Run the full frontend suite with at most 2 workers, typecheck/build, and inspect the live HTTP card if available.
- [x] Record real limitations, checkpoint SHA, changed files and rollback reference; leave redesign reviewable without pushing.

## Execution decisions

- User explicitly delegated design choices and requested implementation now; no additional plan-approval stop.
- Do not embed simulated mail/issue/archive forms: keep their existing real routes and guards.
- UI quick links are labelled as opening a section; they never pretend to complete or save work.

## Completion record

- Checkpoint: `1b20b3d`.
- Final frontend: 479/479 tests, 48 files; build/typecheck pass.
- Independent parity review: no blocking findings.
- Read-only live check: expertise 482/4-1-26; desktop and 760px layout; no browser saves.
- Added `expertise-card-compact.css` as the card-only scoped stylesheet to keep the page readable.
- The final UI is committed separately; no push.
