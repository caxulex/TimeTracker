// ============================================
// TIME TRACKER - TEAM SELECT (TYPEAHEAD)
//
// Reusable typeahead/combobox for picking a team. Parallels
// ProjectSelect (PR #35) / TaskSelect (PR #38) / UserSelect (this
// PR) and replaces the remaining native <select> team pickers on
// admin pages (AdminTimeEntriesPage filter, ProjectsPage modal,
// IntegrationsPage Basecamp sync target, …).
//
// Same rationale as the rest of the family: native <select> sourced
// from `teamsApi.getAll()` silently truncated to the server's
// default page_size, dropping teams from the bottom of the list
// once a tenant grew past ~20. PR-A made `teamsApi.getAll(1, 100)`
// honor the page_size param; this component caps the dropdown at
// 100 (backend ceiling) and filters client-side.
//
// Teams don't have a color attribute — unlike ProjectSelect there
// is no leading dot, just the team name. If a tenant ever crosses
// ~100 teams the right fix is `/api/teams?q=`, not bumping the
// page_size.
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
import { teamsApi } from '../../api/client';
import { useDebounce } from '../../hooks/useDebounce';
import { cn } from '../../utils/helpers';
import type { Team } from '../../types';

/** Minimal team shape this picker reads. */
export type TeamSelectOption = Pick<Team, 'id' | 'name'>;

export interface TeamSelectProps {
  /** Currently-selected team id, or null when nothing is selected. */
  value: number | null;
  /**
   * Called with the new team id (or null when the selection is
   * cleared via the clear option, when `clearable` is on).
   */
  onChange: (teamId: number | null) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  id?: string;
  className?: string;
  inputClassName?: string;
  ariaLabel?: string;
  /**
   * Optional pre-fetched team list. When provided the component
   * skips its own React Query fetch and renders straight from this
   * list — useful for parent pages that already hold the canonical
   * list (e.g. ProjectsPage's ProjectModal receives `teams`).
   */
  teams?: TeamSelectOption[];
  /**
   * When true the picker supports an explicit "no selection" state.
   * Used for filter callsites (AdminTimeEntriesPage) and the
   * IntegrationsPage Basecamp sync default-team semantics.
   */
  clearable?: boolean;
  /** Label for the clear option. Defaults to "All teams". */
  clearLabel?: string;
}

/** Shared query options for the team list. See ProjectSelect for the rationale. */
export const TEAMS_QUERY_KEY = ['teams'] as const;

export function TeamSelect({
  value,
  onChange,
  placeholder = 'Select team',
  required = false,
  disabled = false,
  id,
  className,
  inputClassName,
  ariaLabel,
  teams: teamsProp,
  clearable = false,
  clearLabel = 'All teams',
}: TeamSelectProps) {
  const reactId = useId();
  const inputId = id ?? `team-select-${reactId}`;
  const listboxId = `${inputId}-listbox`;

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState<number>(-1);

  const debouncedSearch = useDebounce(query, 250);
  const search = debouncedSearch.trim() || undefined;

  const { data: teamsData, isFetching: isFetchingTeams } = useQuery({
    queryKey: ['teams', 'search', search ?? ''],
    queryFn: () =>
      teamsApi.getAll({
        page: 1,
        page_size: 20,
        search,
      }),
    enabled: open && !teamsProp,
    staleTime: 30_000,
  });

  const { data: selectedTeamData } = useQuery({
    queryKey: ['teams', value],
    queryFn: () => teamsApi.getById(value as number),
    enabled: value !== null && value !== undefined,
    staleTime: 60_000,
  });

  const teams: TeamSelectOption[] = useMemo(
    () => teamsProp ?? teamsData?.items ?? [],
    [teamsProp, teamsData]
  );

  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(() => {
    const fromList = teams.find((t) => t.id === value) ?? null;
    if (fromList) return fromList;
    if (selectedTeamData && selectedTeamData.id === value) {
      return selectedTeamData;
    }
    return null;
  }, [teams, value, selectedTeamData]);

  const displayValue = open ? query : selected?.name ?? '';

  const filtered = useMemo(() => {
    if (!teamsProp) return teams;
    const q = query.trim().toLowerCase();
    if (!q) return teams;
    return teams.filter((t) => t.name.toLowerCase().includes(q));
  }, [teams, teamsProp, query]);

  const clearOffset = clearable ? 1 : 0;
  const totalOptions = clearOffset + filtered.length;

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
      if (selected) {
        const idx = filtered.findIndex((t) => t.id === selected.id);
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
    (team: TeamSelectOption) => {
      onChange(team.id);
      closePanel();
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
    const team = filtered[highlight - clearOffset];
    if (team) commitSelection(team);
  }, [highlight, clearable, clearOffset, filtered, commitClear, commitSelection]);

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

  const showLoading = isFetchingTeams && teams.length === 0 && !teamsProp;

  return (
    <div
      ref={wrapperRef}
      className={cn('relative', className)}
      data-testid="team-select"
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
          'block w-full rounded-lg border border-gray-300 bg-white shadow-sm text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:opacity-50 disabled:cursor-not-allowed',
          inputClassName
        )}
      />

      {open && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-60 w-full overflow-auto rounded-lg border border-gray-200 bg-white py-1 text-sm shadow-lg"
          data-testid="team-select-listbox"
        >
          {showLoading ? (
            <li
              role="option"
              aria-selected="false"
              aria-disabled="true"
              className="px-3 py-2 text-gray-500"
              data-testid="team-select-loading"
            >
              Loading teams…
            </li>
          ) : (
            <>
              {clearable && (
                <li
                  role="option"
                  aria-selected={value === null}
                  data-testid="team-select-clear"
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
                  <span className="truncate">{clearLabel}</span>
                </li>
              )}
              {filtered.length === 0 ? (
                <li
                  role="option"
                  aria-selected="false"
                  aria-disabled="true"
                  className="px-3 py-2 text-gray-500"
                  data-testid="team-select-empty"
                >
                  {query.trim()
                    ? `No teams match '${query.trim()}'`
                    : 'No teams found'}
                </li>
              ) : (
                filtered.map((team, idx) => {
                  const optionIdx = idx + clearOffset;
                  const isHighlighted = optionIdx === highlight;
                  const isSelected = selected?.id === team.id;
                  return (
                    <li
                      key={team.id}
                      role="option"
                      aria-selected={isSelected}
                      data-testid={`team-select-option-${team.id}`}
                      onMouseDown={(e) => {
                        e.preventDefault();
                        commitSelection(team);
                      }}
                      onMouseEnter={() => setHighlight(optionIdx)}
                      className={cn(
                        'flex items-center gap-2 px-3 py-2 cursor-pointer',
                        isHighlighted ? 'bg-blue-50 text-blue-900' : 'text-gray-900',
                        isSelected && !isHighlighted && 'font-medium'
                      )}
                    >
                      <span className="truncate">{team.name}</span>
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

export default TeamSelect;
