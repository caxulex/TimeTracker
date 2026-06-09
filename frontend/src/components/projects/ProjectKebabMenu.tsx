import React, { useEffect, useRef, useState } from 'react';

interface ProjectKebabTopAction {
  label: string;
  onClick: () => void;
  className?: string;
  testId?: string;
}

interface ProjectKebabMenuProps {
  isArchived: boolean;
  canMerge: boolean;
  onEdit: () => void;
  onArchiveToggle: () => void;
  onMerge: () => void;
  onDelete: () => void;
  mergeLabel?: string;
  topAction?: ProjectKebabTopAction;
}

export function ProjectKebabMenu({
  isArchived,
  canMerge,
  onEdit,
  onArchiveToggle,
  onMerge,
  onDelete,
  mergeLabel = 'Merge with...',
  topAction,
}: ProjectKebabMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };

    document.addEventListener('mousedown', handleOutside);
    return () => document.removeEventListener('mousedown', handleOutside);
  }, []);

  const run = (action: () => void) => {
    setOpen(false);
    action();
  };

  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className="h-8 w-8 rounded-md text-gray-500 hover:bg-gray-100 hover:text-gray-700"
        aria-label="Project actions"
        data-testid="project-kebab-button"
        onClick={(event) => {
          event.stopPropagation();
          setOpen((prev) => !prev);
        }}
      >
        <span aria-hidden="true">⋮</span>
      </button>

      {open && (
        <div
          className="absolute right-0 z-20 mt-2 w-44 rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
          role="menu"
          data-testid="project-kebab-menu"
        >
          {topAction && (
            <>
              <button
                type="button"
                className={topAction.className ?? 'w-full px-3 py-2 text-left text-sm font-semibold text-gray-900 hover:bg-gray-50'}
                onClick={() => run(topAction.onClick)}
                data-testid={topAction.testId ?? 'project-kebab-action-top'}
              >
                {topAction.label}
              </button>
              <div className="my-1 border-t border-gray-100" />
            </>
          )}
          <button
            type="button"
            className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
            onClick={() => run(onEdit)}
            data-testid="project-kebab-action-edit"
          >
            Edit
          </button>
          <button
            type="button"
            className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
            onClick={() => run(onArchiveToggle)}
            data-testid="project-kebab-action-archive"
          >
            {isArchived ? 'Unarchive' : 'Archive'}
          </button>
          {canMerge && (
            <button
              type="button"
              className="w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50"
              onClick={() => run(onMerge)}
              data-testid="project-kebab-action-merge"
            >
              {mergeLabel}
            </button>
          )}
          <div className="my-1 border-t border-gray-100" />
          <button
            type="button"
            className="w-full px-3 py-2 text-left text-sm text-red-600 hover:bg-red-50"
            onClick={() => run(onDelete)}
            data-testid="project-kebab-action-delete"
          >
            Delete
          </button>
        </div>
      )}
    </div>
  );
}
