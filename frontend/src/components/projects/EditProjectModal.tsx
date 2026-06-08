import React, { useEffect, useState } from 'react';

import { Button, Input, Modal } from '../common';
import { projectsApi } from '../../api/client';
import { useSimilarProjects } from '../../hooks/useApi';
import type { Project, SimilarProjectMatch } from '../../types';
import { SimilarProjectsWarning } from './SimilarProjectsWarning';

interface EditProjectModalProps {
  project: Project | null;
  isOpen: boolean;
  isSaving: boolean;
  onClose: () => void;
  onSave: (payload: {
    name: string;
    description?: string | null;
    color: string;
    force?: boolean;
    similar_project_ids?: number[];
  }) => void | Promise<void>;
  onViewExisting?: (project: SimilarProjectMatch) => void;
}

export function EditProjectModal({
  project,
  isOpen,
  isSaving,
  onClose,
  onSave,
  onViewExisting,
}: EditProjectModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('#3B82F6');
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [pendingSimilarMatches, setPendingSimilarMatches] = useState<SimilarProjectMatch[]>([]);
  const { matches } = useSimilarProjects(name, project?.id);

  useEffect(() => {
    if (!project) {
      setName('');
      setDescription('');
      setColor('#3B82F6');
      setConfirmOpen(false);
      setPendingSimilarMatches([]);
      return;
    }

    setName(project.name);
    setDescription(project.description || '');
    setColor(project.color || '#3B82F6');
    setConfirmOpen(false);
    setPendingSimilarMatches([]);
  }, [project]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!project) return;

    const trimmedName = name.trim();
    if (!trimmedName) return;

    const finalCheck = await projectsApi.getSimilar(trimmedName, project.id);
    if (finalCheck.matches.length > 0) {
      setPendingSimilarMatches(finalCheck.matches);
      setConfirmOpen(true);
      return;
    }

    await onSave({
      name: trimmedName,
      description: description.trim() ? description.trim() : null,
      color,
    });
  };

  const handleConfirmOverride = async () => {
    await onSave({
      name: name.trim(),
      description: description.trim() ? description.trim() : null,
      color,
      force: true,
      similar_project_ids: pendingSimilarMatches.map((item) => item.id),
    });
    setConfirmOpen(false);
    setPendingSimilarMatches([]);
  };

  const handleClose = () => {
    setConfirmOpen(false);
    setPendingSimilarMatches([]);
    onClose();
  };

  return (
    <>
    <Modal isOpen={isOpen} onClose={handleClose} title="Edit Project">
      <form className="space-y-4" onSubmit={handleSubmit}>
        <Input
          label="Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
        />

        <SimilarProjectsWarning
          matches={matches}
          mode="edit"
          onUseExisting={(match) => {
            onViewExisting?.(match);
            handleClose();
          }}
        />

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Description</label>
          <textarea
            className="block w-full rounded-lg border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
            rows={3}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Color</label>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={color}
              onChange={(event) => setColor(event.target.value)}
              className="h-10 w-10 cursor-pointer rounded border border-gray-300"
              aria-label="Project color"
            />
            <Input
              value={color}
              onChange={(event) => setColor(event.target.value)}
              pattern="^#[0-9A-Fa-f]{6}$"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="secondary" onClick={handleClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isSaving} disabled={!name.trim()}>
            Save
          </Button>
        </div>
      </form>
    </Modal>

    <Modal
      isOpen={confirmOpen}
      onClose={() => setConfirmOpen(false)}
      title="Similar projects found"
      size="sm"
    >
      <div className="space-y-4">
        <p className="text-sm text-gray-700">
          Similar projects exist. Are you sure you want to rename this project to &quot;{name.trim()}&quot;?
        </p>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button
            type="button"
            onClick={handleConfirmOverride}
            isLoading={isSaving}
            data-testid="edit-project-create-anyway"
          >
            Rename anyway
          </Button>
        </div>
      </div>
    </Modal>
    </>
  );
}
