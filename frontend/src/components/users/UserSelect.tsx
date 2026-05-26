// ============================================
// TIME TRACKER - USER SELECT (TYPEAHEAD)
//
// Reusable typeahead/combobox for picking a user. Parallels
// ProjectSelect (PR #35) / TaskSelect (PR #38) and replaces the
// remaining native <select> based user pickers on admin pages
// (AdminTimeEntriesPage filter, TeamsPage AddMember modal,
// PayRatesPage assignment, AdminAISettings per-user override, …).
//
// Same rationale as ProjectSelect: native <select> backed by
// `usersApi.getAll()` silently truncated to the server's default
// `page_size=20`, so for tenants approaching SaaS scale (hundreds
// of staff) any user beyond the most recent ~20 disappeared from
// the picker. PR-A made `usersApi.getAll(1, 100)` actually reach
// the server; this component caps at 100 (the backend's `le=100`)
// and filters client-side as the user types.
//
// Differences vs ProjectSelect:
//   - no colored dot — users don't have a color attribute. We show
//     a small initials avatar instead (matches the pattern already
//     in use on PayRatesPage / StaffPage cards).
//   - the selected user shows just the name in the closed input;
//     while the dropdown is open each option also shows the email
//     as a smaller subtitle, so admins can disambiguate same-name
//     staff without expanding the row.
//
// Out of scope: server-side search. If a tenant ever crosses ~100
// users the right fix is a dedicated `/api/users?q=` endpoint, not
// bumping the page_size ceiling.
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
import { usersApi } from '../../api/client';
import { cn, getInitials } from '../../utils/helpers';
import type { User } from '../../types';

/**
 * The minimal user shape this picker reads. Most callsites pass
 * full `User` objects; AdminAISettings happens to hold a slimmer
 * `{id, name, email}` shape, so we accept the structural subset to
 * avoid forcing callers to over-specify.
 */
export type UserSelectOption = Pick<User, 'id' | 'name' | 'email'>;

export interface UserSelectProps {
  /** Currently-selected user id, or null when nothing is selected. */
  value: number | null;
  /**
   * Called with the new user id (or null when the selection is
   * cleared via the "All users" affordance, when `clearable` is on).
   */
  onChange: (userId: number | null) => void;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  /** Forwarded to the underlying input; lets callers bind a label. */
  id?: string;
  className?: string;
  inputClassName?: string;
  ariaLabel?: string;
  /**
   * Optional pre-fetched user list. When provided the component
   * skips its own React Query fetch and renders straight from this
   * list — useful for parent pages that already hold the canonical
   * list (e.g. AdminAISettings receives `users` as a prop).
   */
  users?: UserSelectOption[];
  /**
   * When true, the picker supports an explicit "no selection" state:
   *   - a `null` value renders an empty input (just the placeholder),
   *   - a clear option is rendered at the top of the dropdown that
   *     calls `onChange(null)` when picked.
   * Defaults to `false` to preserve the existing required-user
   * contract across modal pickers (TeamsPage AddMember, etc).
   */
  clearable?: boolean;
  /**
   * Label for the clear option in the dropdown when `clearable` is
   * true. Defaults to "All users" — matching the filter use case on
   * AdminTimeEntriesPage. Has no effect when `clearable` is false.
   */
  clearLabel?: string;
}

/**
 * Shared query options for the user list. All UserSelect instances
 * mount with the same key so they hit the same React Query cache
 * entry. We don't have a backend `is_active` filter today so the
 * `{ active: true }` part of the key is purely descriptive — it
 * exists to keep this cache separate from any future deactivated-
 * user query we might add, and to communicate intent at callsites.
 */
export const USERS_QUERY_KEY = ['users', { active: true }] as const;

export function UserSelect({
  value,
  onChange,
  placeholder = 'Select user',
  required = false,
  disabled = false,
  id,
  className,
  inputClassName,
  ariaLabel,
  users: usersProp,
  clearable = false,
  clearLabel = 'All users',
}: UserSelectProps) {
  const reactId = useId();
  const inputId = id ?? `user-select-${reactId}`;
  const listboxId = `${inputId}-listbox`;

  const { data: usersData, isLoading } = useQuery({
    queryKey: USERS_QUERY_KEY,
    // page=1, size=100 — backend's `le=100` ceiling.
    queryFn: () => usersApi.getAll(1, 100),
    enabled: !usersProp,
  });

  const users: UserSelectOption[] = useMemo(
    () => usersProp ?? usersData?.items ?? [],
    [usersProp, usersData]
  );

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [highlight, setHighlight] = useState<number>(-1);

  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const selected = useMemo(
    () => users.find((u) => u.id === value) ?? null,
    [users, value]
  );

  const displayValue = open ? query : selected?.name ?? '';

  // Filter against both name and email — admins commonly know a
  // user by email-prefix when there are name collisions.
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return users;
    return users.filter(
      (u) =>
        u.name.toLowerCase().includes(q) ||
        u.email.toLowerCase().includes(q)
    );
  }, [users, query]);

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
        const idx = filtered.findIndex((u) => u.id === selected.id);
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
    (user: UserSelectOption) => {
      onChange(user.id);
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
    const user = filtered[highlight - clearOffset];
    if (user) commitSelection(user);
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

  const showLoading = isLoading && users.length === 0 && !usersProp;

  return (
    <div
      ref={wrapperRef}
      className={cn('relative', className)}
      data-testid="user-select"
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
          data-testid="user-select-listbox"
        >
          {showLoading ? (
            <li
              role="option"
              aria-selected="false"
              aria-disabled="true"
              className="px-3 py-2 text-gray-500"
              data-testid="user-select-loading"
            >
              Loading users…
            </li>
          ) : (
            <>
              {clearable && (
                <li
                  role="option"
                  aria-selected={value === null}
                  data-testid="user-select-clear"
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
                    className="w-6 h-6 rounded-full flex-shrink-0 border border-gray-300 bg-white"
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
                  data-testid="user-select-empty"
                >
                  No users match &lsquo;{query.trim()}&rsquo;
                </li>
              ) : (
                filtered.map((user, idx) => {
                  const optionIdx = idx + clearOffset;
                  const isHighlighted = optionIdx === highlight;
                  const isSelected = selected?.id === user.id;
                  return (
                    <li
                      key={user.id}
                      role="option"
                      aria-selected={isSelected}
                      data-testid={`user-select-option-${user.id}`}
                      // `onMouseDown` (not `onClick`) so the blur from
                      // mousedown doesn't beat us to the close-panel
                      // race.
                      onMouseDown={(e) => {
                        e.preventDefault();
                        commitSelection(user);
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
                        className="w-6 h-6 rounded-full flex-shrink-0 bg-blue-100 text-blue-700 text-xs font-medium flex items-center justify-center"
                      >
                        {getInitials(user.name || user.email)}
                      </span>
                      <span className="flex-1 min-w-0">
                        <span className="block truncate">{user.name || user.email}</span>
                        {user.name && (
                          <span className="block truncate text-xs text-gray-500">
                            {user.email}
                          </span>
                        )}
                      </span>
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

export default UserSelect;
