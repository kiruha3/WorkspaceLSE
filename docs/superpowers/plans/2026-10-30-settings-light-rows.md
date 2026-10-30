# Settings light rows implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this small presentation change inline. Steps use checkbox syntax for tracking.

**Goal:** Apply approved settings mockup 6 with compact navigation rows in two groups.

**Architecture:** Keep the seven existing routes and permission predicates. Render visible entries in two semantic navigation groups, using the shared outline icon component and local responsive styles. No API, data, or schema changes.

**Tech Stack:** Vue 3, TypeScript, existing CSS and UiIcon.

**Spec:** User approved generated variant 6 on 2026-10-30: “Команда и доступ” and “Данные и документы”, white compact rows, outline icons and chevrons. All existing destinations remain available under the same conditions. On narrow screens stack the groups. Hide empty groups so partial access does not leave blank columns.

## Global constraints

- Preserve data-setting selectors, route targets and access conditions.
- Preserve the existing storage-permission information message.
- No new business features, dependencies, database writes or migrations.
- Reuse the current checkout and running preview.

## Review focus

- All seven destinations must remain distinct and reachable.
- Permission-limited sessions must retain the same visible links.
- Empty groups must not leave headings or a blank column.
- Long Russian text must wrap on mobile; links must support keyboard focus.
- Local styling must not change other settings pages or the shared app density.

## Task 1: Settings presentation

**Files:** Modify `frontend/src/modules/settings/SettingsPage.vue`, `frontend/src/shared/ui/UiIcon.vue`; remove obsolete settings-tile rules from `frontend/src/shared/styles/workspace-compact.css`.

- [x] Group visible existing destinations; retain route targets and predicates.
- [x] Apply compact row styling and accessible focus/hover states with a one-column breakpoint.
- [x] Run existing settings/navigation tests and production build. No new tests for this reversible presentation-only change.
- [x] Check the actual page visually, including narrow width and all seven route targets.

## Verification

- 26 focused tests passed in StorageSettingsPage, GoogleSourceSettingsPage and router suites; the final full frontend run passed all 518 tests.
- Updated two existing App navigation test selectors to distinguish the primary sidebar navigation from settings navigation and to stop relying on the removed grid class. The focused App suite passed all 16 tests.
- Production build and TypeScript check passed. The existing bundle-size warning remains.
- Actual setup session shows all seven links with the original route targets.
- Desktop 1280px: two groups, rows 76px high. At 390px: one column, all seven links remain and none overflows the viewport. Temporary viewport reset after the check.
- Keyboard Tab from the staff link reaches accounts with a visible solid focus outline.
- Google source settings opens through its row; back navigation returns to settings.
- Screenshot: `.runtime/settings-light-rows.png` (local, ignored).
- `git diff --check` passed.
