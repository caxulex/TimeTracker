# Test Reliability Audit - 2026-06-15

Scope: investigation only (no test/config fixes applied).

## 1) Executive summary (ranked root causes)

1. **Tight async timing budget in page-level tests (high confidence)**
   - The flaky files rely heavily on Testing Library defaults (`findBy*`/`waitFor`), which use short async windows by default.
   - Several tests combine chained user flows + React Query re-renders + debounce or multi-phase modal rendering, creating "near-timeout" behavior that passes in isolation and fails under full-suite worker load.
   - Strong indicators:
     - `TeamsPage.test.tsx` known flake: `supports searching, selecting, confirming, and immediately showing an added project` (user-reported timeout).
     - `TimePage.test.tsx` contains comments documenting intermittent CI timing behavior for modal field availability.
     - `ProjectsPage.test.tsx` already marks one test with `{ retry: 2 }`, signaling known instability.

2. **Complex page tests render side-effect-heavy child trees (medium-high confidence)**
   - Page tests mount full pages with multiple providers and nested widgets (React Query + timer/session widgets + notifications + routing), not focused units.
   - Even with API mocks, these trees trigger extra effects/queries and increase scheduler contention during suite-wide parallel execution.

3. **Within-file shared mutable mock state patterns (medium confidence)**
   - Shared mutable objects/variables are used in module scope and mutated during tests.
   - Most files reset state in `beforeEach`, but these patterns still raise flake risk when a test misses a reset path.
   - This is more a fragility multiplier than the primary cause.

4. **Cross-file module mock leakage (low confidence as primary cause)**
   - Many module-level `vi.mock(...)` calls exist, but no direct evidence this week that they are leaking across files and causing the page flakes.
   - Current behavior is more consistent with timing pressure than mock poisoning.

5. **Fake timer leakage (low confidence)**
   - Fake timer usage appears balanced (`useFakeTimers` paired with `useRealTimers`) in scanned tests.
   - Not a leading suspect for this specific page-flake pattern.

## 2) Per-test inventory

### A) `frontend/src/pages/__tests__/TeamsPage.test.tsx`

- **Known failing case under load**
  - `supports searching, selecting, confirming, and immediately showing an added project`
- **Observed failure mode**
  - Timeout while waiting for post-interaction UI transition (`findBy`/`waitFor` chain) during add-project flow.
- **Likely cause**
  - Long interaction chain in one test:
    1) select team
    2) open add modal
    3) type search
    4) select project
    5) confirm dialog
    6) wait for mutation call
    7) wait for heading update
  - Under suite load, this chain is close to async timeout budget.

### B) `frontend/src/pages/__tests__/ProjectsPage.test.tsx`

- **Historically flaky under load**
  - User reports multiple flakes this week (file-level).
- **Most timeout-prone cases**
  - `Use this instead in create mode closes modal and focuses existing flow`
  - `renders similar warning when API returns matches`
  - `hides warning when similar matches are empty`
  - `submit-time check shows confirmation modal when matches exist`
  - `Create anyway submits despite warnings`
  - `delete modal shows counts and requires exact name before enabling delete` (already has `{ retry: 2 }`)
- **Observed failure mode pattern**
  - Timeout waiting for menu/modal/warning updates after typing/click sequences.
- **Likely cause**
  - Search/debounce + repeated modal transitions + multiple `findBy`/`waitFor` gates in single tests.

### C) `frontend/src/pages/TimePage.test.tsx`

- **Historically flaky under load**
  - User reports this file has flaked this week.
- **Most timeout-prone cases**
  - `prefills manual description from selected task when description is empty`
  - `does not overwrite manual description when user already typed text`
  - Pagination/filter tests with chained waits after state changes.
- **Observed failure mode pattern**
  - Timeout in waits around manual modal controls and subsequent state updates.
- **Likely cause**
  - Multi-phase modal rendering and chained async interactions; file itself includes comments that sync reads are intermittently unreliable without `waitFor`.

### D) `frontend/src/pages/DashboardPage.test.tsx`

- **Historically flaky under load**
  - User reports this file flaked this week.
- **Most timeout-prone cases**
  - Generic `waitFor(getByText(...))` and chart presence assertions (`bar-chart`, `pie-chart`) while rendering full dashboard composition.
- **Observed failure mode pattern**
  - Timeout waiting for expected content in full-page render path.
- **Likely cause**
  - Full dashboard includes many child widgets/providers and multiple queries; test assertions are broad and timing-sensitive under worker contention.

## 3) Systemic findings

### Module-level mocks found (selected high-relevance)

- `frontend/src/pages/__tests__/ProjectsPage.test.tsx`
  - module-level mocks for auth, notifications, AI feature hooks, API client.
- `frontend/src/pages/DashboardPage.test.tsx`
  - module-level mocks for auth, API client, websocket context, recharts, and timer store.
- `frontend/src/pages/TimePage.test.tsx`
  - module-level mocks for auth, notifications, AI feature hooks, API client.
- `frontend/src/pages/__tests__/TeamsPage.test.tsx`
  - module-level mocks for router navigation, auth store/hook, staff notifications, debounce, API client.

Assessment:
- Heavy module-level mocking is widespread in page tests.
- This raises maintenance risk, but evidence points to timing/interaction fragility as primary flake driver.

### Shared singleton / mutable state patterns

- `DashboardPage.test.tsx`: shared module-scope `mockTimerState` object reused by all tests.
- `TeamsPage.test.tsx`: module-scope mutable `teamProjects` array mutated by mocked add/remove flows (reset in `beforeEach`).
- Many page tests create new `QueryClient` per render (good), but still execute multi-query trees.

Assessment:
- Mutable shared state exists and can amplify brittleness if resets are incomplete.
- No direct smoking gun of cross-file singleton contamination in this audit run.

### Fake timer usage patterns

- Scanned fake timer usage is generally paired with `useRealTimers` in cleanup.
- No strong evidence of fake-timer leakage causing this week's page flakes.

### Global test setup findings

- `frontend/src/test/setup.ts` includes:
  - `cleanup()` in `afterEach`
  - browser API mocks (`matchMedia`, `IntersectionObserver`, `ResizeObserver`, `localStorage`)
- Missing global hygiene that commonly reduces flake risk:
  - no global `vi.restoreAllMocks()`
  - no global `vi.clearAllMocks()`
  - no explicit global store reset hook for Zustand stores

Assessment:
- Current setup is functional, but not strict enough for high-volume page-level async tests.

### Vitest config analysis

- `frontend/vitest.config.ts`:
  - no explicit `isolate`, `pool`, `threads`, `maxWorkers`, `sequence`, or custom timeouts
  - uses default jsdom + setup file
- Practical impact:
  - relies on Vitest defaults for concurrency/isolation behavior
  - no project-level tuning for known slow/interaction-heavy page tests

Assessment:
- Config is not obviously incorrect, but not tuned for reliability under loaded full-suite conditions.

## 4) Recommended fixes (ranked)

### Fix 1 (highest impact / lowest risk)
**Increase async stability budget for page tests and normalize waiting patterns.**

- Scope:
  - Introduce explicit timeout budget for page-level async assertions (either global async util timeout or per-test helper wrappers).
  - Replace brittle immediate `findBy` chains in critical page tests with deterministic wait points tied to clear UI milestones.
- Effort: **S** (0.5-1 day)
- Risk: **Low**
- Expected flake coverage: **High** (likely addresses majority of 7+ observed flakes)

### Fix 2
**Add strict global test cleanup hygiene.**

- Scope:
  - Add global `afterEach` cleanup for mocks and known shared state (including store reset registry for Zustand stores used by page tests).
- Effort: **S-M** (1 day)
- Risk: **Low-Medium** (may expose hidden coupling in some tests)
- Expected flake coverage: **Medium-High**

### Fix 3
**Reduce page-test complexity by isolating expensive child widgets in page tests.**

- Scope:
  - Keep page contract assertions, but mock/stub non-essential heavy widgets (charts, timer/session blocks, AI panels) in page-level tests.
- Effort: **M** (1-2 days)
- Risk: **Medium** (must avoid over-mocking behavior under test)
- Expected flake coverage: **Medium**

### Fix 4
**Targeted reliability mode for known slow files.**

- Scope:
  - For specific page files, run serially or in a constrained worker mode in CI reliability gate.
- Effort: **S**
- Risk: **Low**
- Expected flake coverage: **Medium** (mitigates load-induced timing variance, does not improve intrinsic test robustness)

### Fix 5
**Longer-term test architecture shift to unified request mocking strategy (e.g., MSW) for page flows.**

- Effort: **L**
- Risk: **Medium**
- Expected flake coverage: **Medium-High** over time

## 5) Implementation plan for chosen fix shape

Recommended rollout: **Fix 1 + Fix 2 first**, then reassess before deeper refactors.

1. **Baseline and target list**
   - Freeze current known flaky page tests list (Projects, Dashboard, Time, Teams).
   - Add a reproducibility runner in CI/local (N repeated full-suite or targeted worker-stress pass).

2. **Async budget hardening (page tests first)**
   - Introduce a shared page-test helper for `findBy`/`waitFor` with reliability timeout budget.
   - Update only the known flaky cases first; avoid broad mechanical churn.
   - Prefer waiting on stable semantic milestones (dialog open/close, heading count change, mutation observable completion).

3. **Global cleanup hardening**
   - Add global post-test hygiene for mocks and registered store resets.
   - Ensure each page test starts from clean singleton/store state.

4. **Re-run reliability gate**
   - Execute repeated full-suite reliability run (same method used in PR gate).
   - Confirm reduction in page-level timeouts before additional changes.

5. **Optional second pass (if needed)**
   - Apply constrained concurrency for the small set of known slow/flaky page files.
   - Evaluate whether heavier page decomposition/mocking is still required.

## Investigation evidence captured in this session

- Examined:
  - `frontend/src/pages/__tests__/ProjectsPage.test.tsx`
  - `frontend/src/pages/DashboardPage.test.tsx`
  - `frontend/src/pages/TimePage.test.tsx`
  - `frontend/src/pages/__tests__/TeamsPage.test.tsx`
  - `frontend/vitest.config.ts`
  - `frontend/src/test/setup.ts`
  - `frontend/src/pages/ProjectsPage.tsx`
  - `frontend/src/pages/TimePage.tsx`
  - `frontend/src/pages/TeamsPage.tsx`
  - `frontend/src/components/teams/TeamProjectsSection.tsx`
  - `frontend/src/hooks/useDebounce.ts`

- Runtime checks performed:
  - Targeted 4-file grouped run: pass
  - 10x repeated grouped stress run of the 4 files: 0 failed runs
  - 1x full suite run: 58/58 files, 537/537 tests passed

Interpretation:
- The intermittency is real (user-reported multi-day gate impact), but did not reproduce in this single local audit session.
- Code patterns still show clear reliability risk concentrated in async timing fragility under load.
