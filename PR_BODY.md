# fix(projects): typeahead project selectors and paginated projects list

## Summary

Three coordinated changes that together eliminate the **pagination-shadow bug class** —
the family of UI bugs caused by the projects list endpoint defaulting to `page_size=20`,
so any tenant with more than 20 projects had "missing" projects in dropdowns and on
list pages even though they exist on the server.

1. **New reusable `ProjectSelect` typeahead component** that fetches up to 100 active
   projects and lets users filter by typing. Replaces native `<select>` dropdowns that
   silently truncated at page 1.
2. **Wired into all three primary project pickers**: the Timer Widget (Dashboard + Time
   page), the Manual Entry modal (Time page), and the Edit Entry modal.
3. **Projects page** refactored from a single 20-item fetch to **`useInfiniteQuery` + "Load
   More"**, with a *"Showing X of Y projects"* indicator so the user knows how many remain.

The top-level filter `<select>` at the top of the Time page and the per-modal *task*
`<select>` are intentionally **not** converted — they are out of scope for this PR.

## The pagination-shadow bug class

Backend `/api/projects` accepts `page_size` (cap `le=100`) and defaults to 20. Any
caller that did `projectsApi.getAll({ include_archived: ... })` without passing
`page_size` would silently get **at most 20 projects**, regardless of how many existed.

This manifested as:
- Project dropdowns missing projects (Timer Widget, Manual Entry, Edit Entry).
- Projects page rendering only the first 20 projects with no indication more existed.
- Tests appearing to pass on small fixtures and silently failing for real tenants.

This PR closes off all four code paths above.

## Changes

### New
- `frontend/src/components/projects/ProjectSelect.tsx`
  - Custom combobox typeahead (no new deps; we don't have `@headlessui/react`).
  - Case-insensitive substring filter over `project.name`.
  - Keyboard: ↑/↓ cycle with wraparound, Enter commits, Esc/Tab close,
    click-outside closes.
  - Selection commits on `mouseDown` (with `preventDefault`) to beat the
    input-blur race condition.
  - Accessibility: `role="combobox"`, `aria-expanded`, `aria-controls`,
    `aria-autocomplete="list"`, `aria-required`; listbox + options with
    `aria-selected`.
  - Internally fetches `{ include_archived: false, page_size: 100 }` under the
    shared query key `['projects', 'active']`, but accepts an optional
    `projects?: Project[]` prop so callers that already maintain that query
    can pass their cached list (avoids double-fetch).
  - Exports the constant `ACTIVE_PROJECTS_QUERY_KEY` for consistent cache use.

- `frontend/src/components/projects/__tests__/ProjectSelect.test.tsx`
  - 11 tests: selected name + dot rendering, focus opens panel, substring
    filtering, case-insensitive filtering, empty state, click-to-select,
    keyboard-to-select, Esc/click-outside close, loading state,
    correct API params.

- `frontend/src/pages/__tests__/ProjectsPage.pagination.test.tsx`
  - 3 tests: "Showing 50 of 97" indicator, Load More fetches page 2 and
    completes the count, Show Archived filters the loaded pages.

### Modified
- `frontend/src/components/time/TimerWidget.tsx`
  - Project query upgraded to `page_size: 100` and standard key `['projects', 'active']`.
  - Replaces inline project `<select>` with `<ProjectSelect ... />`.
  - Task `<select>` left intact (out of scope).

- `frontend/src/pages/TimePage.tsx`
  - Project query key standardized to `['projects', 'active']` (already had
    `page_size: 100` from a prior PR).
  - In the inline `ManualEntryModal`, replaces project `<select>` with
    `<ProjectSelect ... />`. Top-level filter `<select>` left intact.

- `frontend/src/components/time/EditEntryModal.tsx`
  - Project query upgraded to `page_size: 100` and standard key `['projects', 'active']`.
  - Replaces project `<select>` with `<ProjectSelect ... />`.

- `frontend/src/pages/ProjectsPage.tsx`
  - `useQuery` → `useInfiniteQuery` keyed `['projects', 'all', 'paginated']`.
  - `PROJECTS_PAGE_SIZE = 50`, `initialPageParam: 1`,
    `getNextPageParam` returns `allPages.length + 1` until `loaded >= total`.
  - Adds `<p data-testid="projects-count">Showing X of Y projects</p>` and
    `<Button data-testid="projects-load-more">Load More</Button>` (hidden
    once everything is loaded; disabled while fetching).
  - "Show Archived" toggle continues to filter the loaded pages client-side.

### Test fixes (test-only changes for migrated UI)
- `frontend/src/components/time/TimerWidget.test.tsx` —
  test helper that selected a project via `userEvent.selectOptions` now
  drives the new combobox.
- `frontend/src/components/time/EditEntryModal.test.tsx` —
  "changes to project trigger a task list reload" now drives the
  combobox (focus + change + click on `project-select-option-2`).
- `frontend/src/pages/TimePage.test.tsx` —
  filter-row scanning of `getAllByRole('combobox')` no longer crashes on
  the new typeahead input (defends `.options` lookup with `?? []`).

## Standardized query key

All four project-list call sites now use **the same React Query key**
`['projects', 'active']` so the cache is shared:

| File | Before | After |
|---|---|---|
| `ProjectSelect.tsx` | n/a | `['projects', 'active']` |
| `TimerWidget.tsx` | `['projects', 'active']` (no `page_size`) | `['projects', 'active']`, `page_size: 100` |
| `TimePage.tsx` | `['projects']` | `['projects', 'active']` |
| `EditEntryModal.tsx` | `['projects', 'active']` (no `page_size`) | `['projects', 'active']`, `page_size: 100` |

`ProjectsPage` keeps a separate key (`['projects', 'all', 'paginated']`)
because it requests `include_archived: true` and paginates differently.

## Testing

- `npm test` — **361 tests pass** (14 new + 347 pre-existing).
- `npx tsc --noEmit` — clean.
- `npm run lint` — 0 errors, 5 warnings (all pre-existing
  `react-refresh/only-export-components` from unrelated files).

## Out of scope

- The top-level Time page filter `<select>` and the per-modal Task `<select>` are
  unchanged. These dropdowns aren't bound by the 20-project cap (tasks are paged
  separately) and converting them would expand PR scope.
- No new dependencies (deliberately did not add `@headlessui/react`).

## Risk

- Low. The query key standardization shares cache across pickers, which
  reduces fetches; no breaking semantics. All existing tests pass.
- The Projects page transition from a single fetch to paged fetch is the
  only behavioral change for an end user — they now see "Showing 20 of 97
  projects" with a Load More button instead of silently seeing only 20.
