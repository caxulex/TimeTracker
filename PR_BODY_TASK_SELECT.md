## Summary

Introduces `TaskSelect`, a reusable typeahead combobox for task pickers — the task-picker counterpart to `ProjectSelect` from #35. Replaces the native `<select>` task pickers in **four** places:

- `TimerWidget` (top-level task picker)
- `EditEntryModal` (edit time entry)
- `TimePage` Manual Entry modal
- `SessionWidget` Clock-In form

## Why

Native `<select>` doesn't scale well past ~30 options and gives no fuzzy lookup. With Basecamp imports producing dozens of similarly-named tasks per project, users were scrolling forever. `ProjectSelect` already fixed this for projects; this PR completes the symmetry for tasks.

## What's new

**`frontend/src/components/tasks/TaskSelect.tsx`**

- Props: `projectId`, `value`, `onChange`, `placeholder`, `required`, `disabled`, `id`, `className`, `inputClassName`, `ariaLabel`
- Fetches via `tasksApi.getAll({ project_id, page_size: 100 })`
- Query key: `['tasks', { project_id, active: true }]` (also exported as `TASKS_QUERY_KEY(projectId)` so `TimerWidget` shares the React-Query cache and the request is de-duplicated)
- Behaviors:
  - **Disabled** when `projectId` is `null`/`undefined`
  - **Type-to-filter** (case-insensitive substring match against the disambiguated label)
  - **Keyboard nav**: `↑` / `↓` / `Enter` / `Escape`
  - **Click-outside** closes the listbox
  - **Three empty states** with test-ids:
    - `task-select` not interactive → no project selected
    - `task-select-empty-project` → project has no tasks
    - `task-select-empty` → no tasks match the current query
  - **Loading state** (`task-select-loading`)
  - **Auto-clear**: when `projectId` changes and `value != null`, fires `onChange(null)`. Skips the initial mount so a pre-populated entry doesn't get cleared on first render.
- **Basecamp duplicate-name disambiguation** (`formatTaskLabel`, `sortTasksForDisplay`) moved out of `TimerWidget` and into `TaskSelect` so it now applies to all task pickers, not just the timer.

## Files

- **Added**: `frontend/src/components/tasks/TaskSelect.tsx`
- **Added**: `frontend/src/components/tasks/__tests__/TaskSelect.test.tsx` (18 tests)
- **Modified**: `frontend/src/components/time/TimerWidget.tsx` (uses `TaskSelect` + shared `TASKS_QUERY_KEY`)
- **Modified**: `frontend/src/components/time/EditEntryModal.tsx`
- **Modified**: `frontend/src/pages/TimePage.tsx` (Manual Entry)
- **Modified**: `frontend/src/components/sessions/SessionWidget.tsx` (Clock-In)
- **Modified**: `frontend/src/components/time/TimerWidget.test.tsx` (drives the new combobox via test-ids)
- **Modified**: `frontend/src/components/time/EditEntryModal.test.tsx` (asserts `page_size: 100` in the task fetch + combobox value after project change)

## Tests

- `TaskSelect.test.tsx` — 18 cases: disabled-when-no-project, fetch behavior, selection commits, type-to-filter, three empty states, keyboard nav, click-outside, loading, `page_size=100` verification, project_id refetch, projectId-change clearing (including "does NOT fire on initial mount"), Basecamp disambiguation labels.
- Updated `TimerWidget.test.tsx` "Duplicate task name disambiguation & sort" block reads option labels from the `task-select-option-{id}` listbox.
- Updated `EditEntryModal.test.tsx` "changes to project trigger a task list reload (and clear task)" asserts `tasksApi.getAll` is called with `{ project_id, page_size: 100 }` and the task input is cleared after a project change.

Full suite: **382 / 382 passing**.

## Out of scope

- The native **project** `<select>` in `SessionWidget` Clock-In is intentionally left as-is. This PR is task-pickers only.

## Related

- Parallels #35 (ProjectSelect)
- Builds on the merged `page_size` fix (PR-A) that makes `tasksApi.getAll({ project_id, page_size: 100 })` return up to 100 tasks instead of the silent 20-cap.
