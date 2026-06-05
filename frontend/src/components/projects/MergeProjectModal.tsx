import React, { useMemo, useState } from 'react';

import { Button, Modal } from '../common';
import type { Project } from '../../types';

interface MergeProjectModalProps {
  isOpen: boolean;
  sourceProject: Project | null;
  projects: Project[];
  isMerging: boolean;
  onClose: () => void;
  onConfirm: (targetProjectId: number) => void;
}

export function MergeProjectModal({
  isOpen,
  sourceProject,
  projects,
  isMerging,
  onClose,
  onConfirm,
}: MergeProjectModalProps) {
  const [search, setSearch] = useState('');
  const [targetId, setTargetId] = useState<number | null>(null);

  const options = useMemo(() => {
    if (!sourceProject) return [];
    const normalized = search.trim().toLowerCase();
    return projects.filter((project) => {
      if (project.id === sourceProject.id) return false;
      if (project.is_archived) return false;
      if (!normalized) return true;
      return project.name.toLowerCase().includes(normalized);
    });
  }, [projects, search, sourceProject]);

  React.useEffect(() => {
    if (!isOpen) {
      setSearch('');
      setTargetId(null);
      return;
    }

    if (options.length > 0 && (targetId === null || !options.some((item) => item.id === targetId))) {
      setTargetId(options[0].id);
    }
  }, [isOpen, options, targetId]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Merge Project">
      <div className="space-y-4">
        <p className="text-sm text-gray-700">
          Merge &quot;{sourceProject?.name}&quot; into another project.
        </p>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Target project</label>
          <input
            className="mb-2 block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-orange-500 focus:outline-none focus:ring-2 focus:ring-orange-500"
            placeholder="Search projects..."
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            data-testid="merge-target-search"
          />
          <div className="max-h-48 overflow-auto rounded-lg border border-gray-200">
            {options.length === 0 ? (
              <p className="p-3 text-sm text-gray-500">No eligible target projects</p>
            ) : (
              options.map((project) => (
                <button
                  key={project.id}
                  type="button"
                  className={
                    'block w-full px-3 py-2 text-left text-sm hover:bg-orange-50 ' +
                    (targetId === project.id ? 'bg-orange-100 text-orange-800' : 'text-gray-700')
                  }
                  onClick={() => setTargetId(project.id)}
                  data-testid={`merge-target-option-${project.id}`}
                >
                  {project.name}
                </button>
              ))
            )}
          </div>
        </div>

        <div className="rounded-lg bg-orange-50 p-3 text-sm text-orange-900">
          <p>When you confirm:</p>
          <ul className="mt-1 space-y-1">
            <li>• All tasks move to the target project</li>
            <li>• Conflicting task names are suffixed with &quot;(from source)&quot;</li>
            <li>• All time entries move to the target project</li>
            <li>• The source project is archived</li>
            <li>• This action is audit logged</li>
          </ul>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            onClick={() => targetId && onConfirm(targetId)}
            disabled={!targetId || options.length === 0}
            isLoading={isMerging}
            className="bg-orange-600 text-white hover:bg-orange-700"
            data-testid="merge-project-submit"
          >
            Merge
          </Button>
        </div>
      </div>
    </Modal>
  );
}
