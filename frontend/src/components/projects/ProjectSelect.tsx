// ============================================
// TIME TRACKER - PROJECT SELECT (TYPEAHEAD)
//
// Reusable typeahead/combobox for picking a project. Replaces native
// <select> based pickers across the app. Solves the recurring
// "pagination shadow" bug class: with a native <select> backed by
// `projectsApi.getAll()` the dropdown silently truncated to the
// server's default `page_size=20`, so any project beyond the most
// recent ~20 disappeared from the picker (e.g. the May 25 timer
// dropdown losing the consolidated "Development" project, even
// though it was active).
//
// This component:
//   - fetches projects once via React Query (page_size=100 — the
//     server's `le=100` ceiling) and caches under the shared
//     ['projects', 'active'] key,
//   - filters client-side as the user types (case-insensitive
//     substring match against the project name),
//   - exposes the standard combobox affordances (↑/↓ to move
//     highlight, Enter to select, Escape to close, click-outside
//     dismiss, empty-state message).
//
// Out of scope: server-side search. If a tenant ever crosses ~100
// active projects the right fix is a dedicated `/api/projects?q=`
// endpoint, not bumping the page_size again. See PR
// fix/project-selectors-typeahead-and-pagination for the full
// rationale.
// ============================================
import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from 'react';
import { useQuery } from '@tanstack/react-query';
import { projectsApi } from '../../api/client';
import { cn } from '../../utils/helpers';
import type { Project } from '../../types';

export interface ProjectSelectProps {
  /**
   * Currently-selected project id, or null when nothing is selected.
   */
  value: number | null;
  /**
   * Called with the new project id (or null when the selection is
   * cleared via the optional "clear" affordance — not currently
   * exposed in the UI but kept in the contract for future use).
   */
  onChange: (projectId: number | null) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  /**
   * Optional dom id forwarded to the underlying input. Lets callers
   * bind a `<label htmlFor=...>` to the field.
   */
  id?: string;
  /**
   * Extra classes applied to the outer wrapper.
   */
  className?: string;
  /**
   * Extra classes applied to the input element. Use this to recolor
   * the field inside dark surfaces (e.g. the TimerWidget gradient).
   */
  inputClassName?: string;
  /**
   * Style hook for the colored dot rendered next to the selected
   * project's name. Keeps the visual identical to the previous
   * native <select> based UI in the timer card.
   */
  dotClassName?: string;
  /**
   * Aria label override for the input. Falls back to placeholder.
   */
  ariaLabel?: string;
  /**
   * Optional pre-fetched project list. When provided, the component
   * skips its own React Query fetch and renders straight from this
   * list — useful for parent pages that already hold the canonical
   * list (e.g. TimePage uses the same list for both the filter and
   * the manual-entry modal).
   */
  projects?: Project[];
  /**
   * When true, the picker supports an explicit "no selection" state:
   *   - a `null` value renders an empty input (just the placeholder),
   *   - a clear option is rendered at the top of the dropdown that
   *     calls `onChange(null)` when picked.
   * Defaults to `false` to preserve the existing required-project
   * contract across the timer / entry-modal callsites where a
   * project must always be selected.
   */
  clearable?: boolean;
  /**
   * Label for the clear option in the dropdown when `clearable` is
   * true. Defaults to "All projects" — matching the filter use case
   * on TasksPage. Has no effect when `clearable` is false.
   */
  clearLabel?: string;
}

/**
 * Shared query options for the active-project list. All ProjectSelect
 * instances mount with the same key so they hit the same React Query
 * cache entry — opening the manual-entry modal after the timer has
 * already loaded its list is free.
 */
export const ACTIVE_PROJECTS_QUERY_KEY = ['projects', 'active'] as const;

export function ProjectSelect({
  value,
  onChange,
  placeholder = 'Select project',
  required = false,
  disabled = false,
  id,
  className,
  inputClassName,
  dotClassName,
  ariaLabel,
  projects: projectsProp,
  clearable = false,
  clearLabel = 'All projects',
}: ProjectSelectProps) {
  const reactId = useId();
  const inputId = id ?? `project-select-${reactId}`;
  const listboxId = `${inputId}-listbox`;

  const { data: projectsData, isLoading } = useQuery({
    queryKey: ACTIVE_PROJECTS_QUERY_KEY,
    queryFn: () =>
      projectsApi.getAll({ include_archived: false, page_size: 100 }),
    // When the caller passed `projects` directly, we still mount the
    // query (so subsequent uses without the prop hit a warm cache)
    // but we don't need its result. Leaving it enabled is also fine
    // because React Query dedupes by key.
    enabled: !projectsProp,
  });

  const projects: Project[] = useMemo(
    () => projectsProp ?? projectsData?.items ?? [],
    [projectsProp, projectsData]
  );

  // ------------ Open/close + query state ------------
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState<number>(-1);

  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => projects.find((p) => p.id === value) ?? null,
    [projects, value]
  );

  // The text shown in the input. When the panel is closed we show the
  // selected project's name; while the panel is open the user is
  // free-typing a search query.
  const displayValue = open ? query : selected?.name ?? '';

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return projects;
    return projects.filter((p) => p.name.toLowerCase().includes(q));
  }, [projects, query]);

  // When `clearable` is true the dropdown carries an extra synthetic
  // option at index 0 (the "All projects" / clear affordance). All
  // keyboard-navigation math has to account for this offset so
  // arrows + Enter address the right entry.
  const clearOffset = clearable ? 1 : 0;
  const totalOptions = clearOffset + filtered.length;

  // Keep the highlight inside the option range. When the option list
  // shrinks past the current highlight, clamp to the last available
  // option (or -1 when there are no options at all).
  useEffect(() => {
    if (!open) {
      setHighlight(-1);
      return;
    }
    if (totalOptions === 0) {
      setHighlight(-1);
    } else if (highlight >= totalOptions) {
      setHighlight(totalOptions - 1);
    } else if (highlight < 0) {
      // Pre-select the currently-selected project when present, else
      // the clear option (when present), else the first project, so
      // Enter immediately commits something sensible.
      if (selected) {
        const idx = filtered.findIndex((p) => p.id === selected.id);
        setHighlight(idx >= 0 ? idx + clearOffset : 0);
      } else {
        setHighlight(0);
      }
    }
  }, [open, totalOptions, filtered, highlight, selected, clearOffset]);

  const openPanel = useCallback(() => {
    if (disabled) return;
    setOpen(true);
    setQuery('');
  }, [disabled]);

  const closePanel = useCallback(() => {
    setOpen(false);
    setQuery('');
    setHighlight(-1);
  }, []);

  const commitSelection = useCallback(
    (project: Project) => {
      onChange(project.id);
      closePanel();
      // Drop focus from the input so the displayed value (the new
      // project name) is visible without the cursor.
      inputRef.current?.blur();
    },
    [onChange, closePanel]
  );

  const commitClear = useCallback(() => {
    onChange(null);
    closePanel();
    inputRef.current?.blur();
  }, [onChange, closePanel]);

  const commitHighlight = useCallback(() => {
    if (highlight < 0) return;
    if (clearable && highlight === 0) {
      commitClear();
      return;
    }
    const project = filtered[highlight - clearOffset];
    if (project) commitSelection(project);
  }, [highlight, clearable, clearOffset, filtered, commitClear, commitSelection]);

  // ------------ Click-outside ------------
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const wrapper = wrapperRef.current;
      if (wrapper && !wrapper.contains(e.target as Node)) {
        closePanel();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, closePanel]);

  // ------------ Keyboard nav ------------
  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!open) {
        openPanel();
        return;
      }
      if (totalOptions === 0) return;
      setHighlight((h) => (h + 1) % totalOptions);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) {
        openPanel();
        return;
      }
      if (totalOptions === 0) return;
      setHighlight((h) => (h <= 0 ? totalOptions - 1 : h - 1));
    } else if (e.key === 'Enter') {
      if (open && highlight >= 0) {
        e.preventDefault();
        commitHighlight();
      }
    } else if (e.key === 'Escape') {
      if (open) {
        e.preventDefault();
        closePanel();
      }
    } else if (e.key === 'Tab') {
      if (open) closePanel();
    }
  };

  // ------------ Render ------------
  const hasSelected = !!selected && !open;
  const showLoading = isLoading && projects.length === 0;

  return (
    <div
      ref={wrapperRef}
      className={cn('relative', className)}
      data-testid="project-select"
    >
      {/* Colored dot — only when a project is selected and the panel
          is closed. Mirrors the visual used elsewhere (TimerWidget,
          ProjectsPage cards). */}
      {hasSelected && (
        <span
          aria-hidden="true"
          className={cn(
            'pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full',
            dotClassName
          )}
          style={{ backgroundColor: selected!.color }}
          data-testid="project-select-dot"
        />
      )}

      <input
        ref={inputRef}
        id={inputId}
        type="text"
        role="combobox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-label={ariaLabel ?? placeholder}
        aria-required={required || undefined}
        autoComplete="off"
        spellCheck={false}
        disabled={disabled}
        placeholder={placeholder}
        value={displayValue}
        onChange={(e) => {
          if (!open) setOpen(true);
          setQuery(e.target.value);
        }}
        onFocus={openPanel}
        onClick={openPanel}
        onKeyDown={onKeyDown}
        className={cn(
          'block w-full rounded-lg border border-gray-300 bg-white shadow-sm text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed',
          // Reserve space on the left for the colored dot when one is
          // showing.
          hasSelected ? 'pl-7 pr-3 py-2' : 'px-3 py-2',
          inputClassName
        )}
      />

      {open && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-gray-200 bg-white py-1 text-sm shadow-lg"
          data-testid="project-select-listbox"
        >
          {showLoading ? (
            <li
              role="option"
              aria-selected="false"
              aria-disabled="true"
              className="px-3 py-2 text-gray-500"
              data-testid="project-select-loading"
            >
              Loading projects…
            </li>
          ) : (
            <>
              {clearable && (
                <li
                  role="option"
                  aria-selected={value === null}
                  data-testid="project-select-clear"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    commitClear();
                  }}
                  onMouseEnter={() => setHighlight(0)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 cursor-pointer border-b border-gray-100',
                    highlight === 0
                      ? 'bg-blue-50 text-blue-900'
                      : 'text-gray-700',
                    value === null && highlight !== 0 && 'font-medium'
                  )}
                >
                  <span
                    aria-hidden="true"
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0 border border-gray-300 bg-white"
                  />
                  <span className="truncate">{clearLabel}</span>
                </li>
              )}
              {filtered.length === 0 ? (
                <li
                  role="option"
                  aria-selected="false"
                  aria-disabled="true"
                  className="px-3 py-2 text-gray-500"
                  data-testid="project-select-empty"
                >
                  No projects match &lsquo;{query.trim()}&rsquo;
                </li>
              ) : (
                filtered.map((project, idx) => {
                  const optionIdx = idx + clearOffset;
                  const isHighlighted = optionIdx === highlight;
                  const isSelected = selected?.id === project.id;
                  return (
                    <li
                      key={project.id}
                      role="option"
                      aria-selected={isSelected}
                      data-testid={`project-select-option-${project.id}`}
                      // `onMouseDown` (not `onClick`) so the blur from
                      // mousedown doesn't beat us to the close-panel
                      // race.
                      onMouseDown={(e) => {
                        e.preventDefault();
                        commitSelection(project);
                      }}
                      onMouseEnter={() => setHighlight(optionIdx)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2 cursor-pointer',
                        isHighlighted ? 'bg-blue-50 text-blue-900' : 'text-gray-900',
                        isSelected && !isHighlighted && 'font-medium'
                      )}
                    >
                      <span
                        aria-hidden="true"
                        className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: project.color }}
                      />
                      <span className="truncate">{project.name}</span>
                    </li>
                  );
                })
              )}
            </>
          )}
        </ul>
      )}
    </div>
  );
}

export default ProjectSelect;
