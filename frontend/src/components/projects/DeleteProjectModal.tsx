import React, { useEffect, useState } from 'react';

import { Button, Modal } from '../common';
import type { Project, ProjectDeletePreview } from '../../types';

interface DeleteProjectModalProps {
  isOpen: boolean;
  project: Project | null;
  preview: ProjectDeletePreview | null;
  isLoadingPreview: boolean;
  isDeleting: boolean;
  onClose: () => void;
  onConfirm: () => void;
}

export function DeleteProjectModal({
  isOpen,
  project,
  preview,
  isLoadingPreview,
  isDeleting,
  onClose,
  onConfirm,
}: DeleteProjectModalProps) {
  const [typedName, setTypedName] = useState('');

  useEffect(() => {
    if (isOpen) {
      setTypedName('');
    }
  }, [isOpen, project?.id]);

  const nameMatches = typedName === (project?.name || '');

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Delete Project">
      <div className="space-y-4">
        <p className="text-sm font-medium text-gray-800" data-testid="delete-project-modal-title">
          Delete &quot;{project?.name}&quot;
        </p>
        <p className="text-sm font-semibold text-red-700">This permanently deletes:</p>
        <ul className="space-y-1 text-sm text-gray-700">
          <li>• The project &quot;{project?.name}&quot;</li>
          <li>• {isLoadingPreview ? '...' : (preview?.tasks ?? 0)} tasks</li>
          <li>• {isLoadingPreview ? '...' : (preview?.entries ?? 0)} time entries</li>
          <li>• All team associations</li>
        </ul>

        <p className="text-sm font-semibold text-red-700">This action cannot be undone.</p>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">
            Type the project name to confirm
          </label>
          <input
            value={typedName}
            onChange={(event) => setTypedName(event.target.value)}
            className="block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-red-500 focus:outline-none focus:ring-2 focus:ring-red-500"
            data-testid="delete-project-confirm-name"
          />
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="danger"
            onClick={onConfirm}
            isLoading={isDeleting}
            disabled={!nameMatches || isLoadingPreview}
            data-testid="delete-project-submit"
          >
            Delete
          </Button>
        </div>
      </div>
    </Modal>
  );
}
