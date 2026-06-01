// ============================================
// TIME TRACKER - TASK SELECT (TYPEAHEAD)
//
// Reusable typeahead/combobox for picking a task. Parallels
// ProjectSelect (PR #35) and replaces the native <select> based
// task pickers across TimerWidget, EditEntryModal, the manual-entry
// modal on TimePage, and the Clock-In form on SessionWidget.
//
// Same rationale as ProjectSelect: native <select> backed by
// `tasksApi.getAll({ project_id })` silently truncated to the
// server's default `page_size=20`, so any task beyond the most
// recent ~20 in a given project disappeared from the picker.
// PR-A fixed page_size to actually reach the server; this
// component caps page_size at 100 (the backend's `le=100`) and
// filters client-side as the user types.
//
// Out of scope: server-side search. If a tenant ever crosses ~100
// tasks in a single project the right fix is a dedicated
// `/api/tasks?q=` endpoint, not bumping the page_size ceiling.
//
// Tasks are project-scoped. The picker only loads when a project is
// selected; switching projects refetches with the new project_id and
// clears the previous task selection (via onChange(null)).
//
// Task-name disambiguation: tasks imported from Basecamp can share
// the same name across different to-do lists / due dates. We
// disambiguate same-name tasks within the dropdown by suffixing the
// due date (or created month / position) — same logic that used to
// live in TimerWidget so the typeahead remains usable for tenants
// with recurring task names.
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
import { tasksApi } from '../../api/client';
import { cn } from '../../utils/helpers';
import type { Task } from '../../types';

export interface TaskSelectProps {
  /**
   * Project the task picker is scoped to. When null/undefined the
   * input is rendered disabled with a "select project first"
   * placeholder.
   */
  projectId: number | null | undefined;
  /**
   * Currently-selected task id, or null when nothing is selected.
   */
  value: number | null;
  /**
   * Called with the new task id (or null when the selection is
   * cleared — including the automatic clear when projectId changes).
   */
  onChange: (taskId: number | null, task?: Task | null) => void;
  placeholder?: string;
  required?: boolean;
  /**
   * Explicit disable. The component is also implicitly disabled when
   * projectId is null/undefined.
   */
  disabled?: boolean;
  id?: string;
  className?: string;
  inputClassName?: string;
  ariaLabel?: string;
}

/**
 * Shared query key for the active-tasks list scoped to a project.
 * Kept stable so multiple TaskSelect instances (and callers that
 * still hold a parallel `tasks` query for notifications) hit the
 * same React Query cache entry.
 */
export const TASKS_QUERY_KEY = (projectId: number | null | undefined) =>
  ['tasks', { project_id: projectId, active: true }] as const;

// ----- Label formatting / sorting (Basecamp duplicate-name aware) -----

type LabelContext = {
  nameCounts: Record<string, number>;
  collidingDueKeys: Set<string>;
};

function buildLabelContext(tasks: Task[]): LabelContext {
  const nameCounts = tasks.reduce<Record<string, number>>((acc, t) => {
    acc[t.name] = (acc[t.name] || 0) + 1;
    return acc;
  }, {});

  const counts = new Map<string, number>();
  tasks.forEach((t) => {
    if ((nameCounts[t.name] || 0) <= 1) return;
    if (!t.basecamp_due_on) return;
    const md = new Date(t.basecamp_due_on).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    });
    const key = `${t.name}|${md}`;
    counts.set(key, (counts.get(key) || 0) + 1);
  });
  const collidingDueKeys = new Set<string>();
  counts.forEach((c, k) => {
    if (c > 1) collidingDueKeys.add(k);
  });

  return { nameCounts, collidingDueKeys };
}

function formatTaskLabel(task: Task, ctx: LabelContext): string {
  const isDuplicate = (ctx.nameCounts[task.name] || 0) > 1;
  if (!isDuplicate) return task.name;

  if (task.basecamp_due_on) {
    const d = new Date(task.basecamp_due_on);
    const md = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const key = `${task.name}|${md}`;
    if (ctx.collidingDueKeys.has(key)) {
      const withYear = d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
      return `${task.name} (Due ${withYear})`;
    }
    return `${task.name} (Due ${md})`;
  }
  if (task.basecamp_todo_created_at) {
    const d = new Date(task.basecamp_todo_created_at);
    const formatted = d.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
    return `${task.name} (${formatted})`;
  }
  if (task.basecamp_todo_position != null) {
    return `${task.name} (#${task.basecamp_todo_position})`;
  }
  return task.name;
}

function sortTasksForDisplay(tasks: Task[]): Task[] {
  if (tasks.length === 0) return tasks;

  type Group = { firstIndex: number; items: Task[] };
  const groups = new Map<string, Group>();
  tasks.forEach((t, i) => {
    const existing = groups.get(t.name);
    if (existing) {
      existing.items.push(t);
    } else {
      groups.set(t.name, { firstIndex: i, items: [t] });
    }
  });

  const cmpStrDesc = (a: string | null | undefined, b: string | null | undefined): number => {
    const av = a || '';
    const bv = b || '';
    if (av && bv) {
      if (av === bv) return 0;
      return av < bv ? 1 : -1;
    }
    if (av) return -1;
    if (bv) return 1;
    return 0;
  };

  for (const g of groups.values()) {
    if (g.items.length <= 1) continue;
    g.items.sort((a, b) => {
      const dueCmp = cmpStrDesc(a.basecamp_due_on, b.basecamp_due_on);
      if (dueCmp !== 0) return dueCmp;
      const createdCmp = cmpStrDesc(a.basecamp_todo_created_at, b.basecamp_todo_created_at);
      if (createdCmp !== 0) return createdCmp;
      const aPos = a.basecamp_todo_position;
      const bPos = b.basecamp_todo_position;
      if (aPos != null && bPos != null) return aPos - bPos;
      if (aPos != null) return -1;
      if (bPos != null) return 1;
      return 0;
    });
  }

  return Array.from(groups.values())
    .sort((a, b) => a.firstIndex - b.firstIndex)
    .flatMap((g) => g.items);
}

export function TaskSelect({
  projectId,
  value,
  onChange,
  placeholder = 'Select task',
  required = false,
  disabled = false,
  id,
  className,
  inputClassName,
  ariaLabel,
}: TaskSelectProps) {
  const reactId = useId();
  const inputId = id ?? `task-select-${reactId}`;
  const listboxId = `${inputId}-listbox`;

  const hasProject = projectId != null;
  const effectiveDisabled = disabled || !hasProject;

  // ------------ Data fetch ------------
  const { data: tasksData, isLoading } = useQuery({
    queryKey: TASKS_QUERY_KEY(projectId ?? null),
    queryFn: () =>
      tasksApi.getAll({ project_id: projectId as number, page_size: 100 }),
    enabled: hasProject,
  });

  const tasks: Task[] = useMemo(
    () => (hasProject ? tasksData?.items ?? [] : []),
    [tasksData, hasProject]
  );

  const sortedTasks = useMemo(() => sortTasksForDisplay(tasks), [tasks]);
  const labelCtx = useMemo(() => buildLabelContext(tasks), [tasks]);

  // ------------ Auto-clear on project change ------------
  // When the parent swaps to a different project, the previously-
  // selected task is no longer meaningful — fire onChange(null) so
  // the form state matches. We skip the very first render (the
  // initial projectId arriving alongside an initial value is fine).
  const prevProjectIdRef = useRef<number | null | undefined>(projectId);
  useEffect(() => {
    if (prevProjectIdRef.current !== projectId) {
      // Only clear when there was a previous (non-undefined-on-mount)
      // project and a task was actually selected.
      if (value != null) {
        onChange(null, null);
      }
      prevProjectIdRef.current = projectId;
    }
    // We intentionally exclude `value` and `onChange` from the
    // dependency list — we only want to react to a real projectId
    // transition, not to the cascade that our own onChange triggers.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // ------------ Open/close + query state ------------
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState<number>(-1);

  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => tasks.find((t) => t.id === value) ?? null,
    [tasks, value]
  );

  const selectedLabel = selected ? formatTaskLabel(selected, labelCtx) : '';

  const displayValue = open ? query : selectedLabel;

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return sortedTasks;
    return sortedTasks.filter((t) => t.name.toLowerCase().includes(q));
  }, [sortedTasks, query]);

  useEffect(() => {
    if (!open) {
      setHighlight(-1);
      return;
    }
    if (filtered.length === 0) {
      setHighlight(-1);
    } else if (highlight >= filtered.length) {
      setHighlight(filtered.length - 1);
    } else if (highlight < 0) {
      const idx = selected
        ? filtered.findIndex((t) => t.id === selected.id)
        : 0;
      setHighlight(idx >= 0 ? idx : 0);
    }
  }, [open, filtered, highlight, selected]);

  const openPanel = useCallback(() => {
    if (effectiveDisabled) return;
    setOpen(true);
    setQuery('');
  }, [effectiveDisabled]);

  const closePanel = useCallback(() => {
    setOpen(false);
    setQuery('');
    setHighlight(-1);
  }, []);

  const commitSelection = useCallback(
    (task: Task) => {
      onChange(task.id, task);
      closePanel();
      inputRef.current?.blur();
    },
    [onChange, closePanel]
  );

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
    if (effectiveDisabled) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (!open) {
        openPanel();
        return;
      }
      if (filtered.length === 0) return;
      setHighlight((h) => (h + 1) % filtered.length);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (!open) {
        openPanel();
        return;
      }
      if (filtered.length === 0) return;
      setHighlight((h) => (h <= 0 ? filtered.length - 1 : h - 1));
    } else if (e.key === 'Enter') {
      if (open && highlight >= 0 && filtered[highlight]) {
        e.preventDefault();
        commitSelection(filtered[highlight]);
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

  // ------------ Placeholder text by state ------------
  const effectivePlaceholder = !hasProject
    ? 'Select project first'
    : placeholder;

  const showLoading = hasProject && isLoading && tasks.length === 0;
  const noTasksInProject = hasProject && !isLoading && tasks.length === 0;

  return (
    <div
      ref={wrapperRef}
      className={cn('relative', className)}
      data-testid="task-select"
    >
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
        disabled={effectiveDisabled}
        placeholder={effectivePlaceholder}
        value={displayValue}
        onChange={(e) => {
          if (!open) setOpen(true);
          setQuery(e.target.value);
        }}
        onFocus={openPanel}
        onClick={openPanel}
        onKeyDown={onKeyDown}
        className={cn(
          'block w-full rounded-lg border border-gray-300 bg-white shadow-sm text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed',
          inputClassName
        )}
      />

      {open && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-gray-200 bg-white py-1 text-sm shadow-lg"
          data-testid="task-select-listbox"
        >
          {showLoading ? (
            <li
              role="option"
              aria-selected="false"
              aria-disabled="true"
              className="px-3 py-2 text-gray-500"
              data-testid="task-select-loading"
            >
              Loading tasks…
            </li>
          ) : noTasksInProject ? (
            <li
              role="option"
              aria-selected="false"
              aria-disabled="true"
              className="px-3 py-2 text-gray-500"
              data-testid="task-select-empty-project"
            >
              This project has no tasks yet
            </li>
          ) : filtered.length === 0 ? (
            <li
              role="option"
              aria-selected="false"
              aria-disabled="true"
              className="px-3 py-2 text-gray-500"
              data-testid="task-select-empty"
            >
              No tasks match &lsquo;{query.trim()}&rsquo;
            </li>
          ) : (
            filtered.map((task, idx) => {
              const isHighlighted = idx === highlight;
              const isSelected = selected?.id === task.id;
              return (
                <li
                  key={task.id}
                  role="option"
                  aria-selected={isSelected}
                  data-testid={`task-select-option-${task.id}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    commitSelection(task);
                  }}
                  onMouseEnter={() => setHighlight(idx)}
                  className={cn(
                    'flex items-center gap-2 px-3 py-2 cursor-pointer',
                    isHighlighted ? 'bg-blue-50 text-blue-900' : 'text-gray-900',
                    isSelected && !isHighlighted && 'font-medium'
                  )}
                >
                  <span className="truncate">{formatTaskLabel(task, labelCtx)}</span>
                </li>
              );
            })
          )}
        </ul>
      )}
    </div>
  );
}

export default TaskSelect;
