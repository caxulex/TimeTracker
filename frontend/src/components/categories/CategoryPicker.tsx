import { useMemo, useState } from 'react';
import { Button, Input, Modal } from '../common';
import { useCategories, useCreateCategory } from '../../hooks/useApi';
import type { Category } from '../../types';
import { CategoryChip } from './CategoryChip';

interface CategoryPickerProps {
  selectedIds: number[];
  onChange: (ids: number[]) => void;
}

const PRESET_COLORS = ['#DC2626', '#10B981', '#3B82F6', '#F59E0B', '#8B5CF6', '#6B7280'];

export function CategoryPicker({ selectedIds, onChange }: CategoryPickerProps) {
  const { data: categories = [] } = useCategories();
  const createCategory = useCreateCategory();

  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState('');
  const [newDescription, setNewDescription] = useState('');
  const [newColor, setNewColor] = useState('#6B7280');

  const selected = useMemo(
    () => categories.filter((category) => selectedIds.includes(category.id)),
    [categories, selectedIds]
  );

  const available = useMemo(
    () => categories.filter((category) => !selectedIds.includes(category.id)),
    [categories, selectedIds]
  );

  const addCategory = (id: number) => {
    if (selectedIds.includes(id)) return;
    onChange([...selectedIds, id]);
  };

  const removeCategory = (id: number) => {
    onChange(selectedIds.filter((selectedId) => selectedId !== id));
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const created = await createCategory.mutateAsync({
      name: newName.trim(),
      color: newColor,
      description: newDescription.trim() || undefined,
    });
    onChange([...selectedIds, created.id]);
    setNewName('');
    setNewDescription('');
    setNewColor('#6B7280');
    setShowCreate(false);
  };

  return (
    <div className="space-y-2" data-testid="category-picker">
      <div className="flex flex-wrap gap-2" data-testid="category-picker-selected">
        {selected.map((category) => (
          <CategoryChip
            key={category.id}
            category={category}
            onRemove={() => removeCategory(category.id)}
          />
        ))}
        {selected.length === 0 && <p className="text-xs text-gray-500">No categories selected</p>}
      </div>

      <div className="flex items-center gap-2">
        <select
          className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
          aria-label="Add category"
          data-testid="category-picker-select"
          value=""
          onChange={(e) => {
            const value = e.target.value;
            if (value === '__create__') {
              setShowCreate(true);
              return;
            }
            if (!value) return;
            addCategory(Number(value));
          }}
        >
          <option value="">Add category...</option>
          {available.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
          <option value="__create__">+ Create new</option>
        </select>
      </div>

      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="Create Category">
        <form className="space-y-4" onSubmit={handleCreate}>
          <Input
            label="Name"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Category name"
            required
          />

          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Color</p>
            <div className="flex flex-wrap gap-2">
              {PRESET_COLORS.map((color) => (
                <button
                  key={color}
                  type="button"
                  onClick={() => setNewColor(color)}
                  aria-label={`Select ${color}`}
                  className={`h-7 w-7 rounded-full border-2 ${newColor === color ? 'border-gray-900' : 'border-transparent'}`}
                  style={{ backgroundColor: color }}
                  data-testid={`category-color-${color}`}
                />
              ))}
            </div>
          </div>

          <Input
            label="Description (optional)"
            value={newDescription}
            onChange={(e) => setNewDescription(e.target.value)}
            placeholder="What is this category for?"
          />

          <div className="flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={() => setShowCreate(false)}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createCategory.isPending}>
              Create
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default CategoryPicker;
