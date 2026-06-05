import React, { useEffect, useState } from 'react';

import { Button, Input, Modal } from '../common';
import type { Project } from '../../types';

interface EditProjectModalProps {
  project: Project | null;
  isOpen: boolean;
  isSaving: boolean;
  onClose: () => void;
  onSave: (payload: { name: string; description?: string | null; color: string }) => void;
}

export function EditProjectModal({ project, isOpen, isSaving, onClose, onSave }: EditProjectModalProps) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('#3B82F6');

  useEffect(() => {
    if (!project) {
      setName('');
      setDescription('');
      setColor('#3B82F6');
      return;
    }

    setName(project.name);
    setDescription(project.description || '');
    setColor(project.color || '#3B82F6');
  }, [project]);

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!project) return;

    onSave({
      name: name.trim(),
      description: description.trim() ? description.trim() : null,
      color,
    });
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Edit Project">
      <form className="space-y-4" onSubmit={handleSubmit}>
        <Input
          label="Name"
          value={name}
          onChange={(event) => setName(event.target.value)}
          required
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
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" isLoading={isSaving} disabled={!name.trim()}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  );
}
