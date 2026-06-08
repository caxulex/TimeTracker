import { useState } from 'react';
import { Card, CardHeader, Button, Input, Modal } from '../components/common';
import {
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from '../hooks/useApi';
import type { Category } from '../types';

const PRESET_COLORS = ['#DC2626', '#10B981', '#3B82F6', '#F59E0B', '#8B5CF6', '#6B7280'];

export function CategoriesSettingsPage() {
  const { data: categories = [], isLoading } = useCategories();
  const createCategory = useCreateCategory();
  const updateCategory = useUpdateCategory();
  const deleteCategory = useDeleteCategory();

  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [color, setColor] = useState('#6B7280');

  const [deleteTarget, setDeleteTarget] = useState<Category | null>(null);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    await createCategory.mutateAsync({
      name: name.trim(),
      color,
      description: description.trim() || undefined,
    });
    setName('');
    setDescription('');
    setColor('#6B7280');
    setShowCreate(false);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Task Categories</h1>
          <p className="text-gray-500">Manage categories used to organize tasks.</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>New Category</Button>
      </div>

      <Card>
        <CardHeader title="Categories" subtitle="Shared across your company" />
        {isLoading ? (
          <p className="text-sm text-gray-500">Loading categories...</p>
        ) : (
          <div className="space-y-3" data-testid="categories-settings-list">
            {categories.map((category) => (
              <div
                key={category.id}
                className="rounded-lg border border-gray-200 p-3"
                data-testid={`category-row-${category.id}`}
              >
                <div className="grid grid-cols-1 gap-3 md:grid-cols-[auto_1fr_1fr_auto_auto] md:items-center">
                  <input
                    type="color"
                    value={category.color}
                    onChange={(e) => {
                      updateCategory.mutate({ id: category.id, data: { color: e.target.value } });
                    }}
                    className="h-9 w-12 cursor-pointer rounded border border-gray-300 bg-white"
                    aria-label={`Color for ${category.name}`}
                  />

                  <Input
                    label=""
                    value={category.name}
                    onChange={(e) => {
                      updateCategory.mutate({ id: category.id, data: { name: e.target.value } });
                    }}
                    placeholder="Name"
                  />

                  <Input
                    label=""
                    value={category.description || ''}
                    onChange={(e) => {
                      updateCategory.mutate({ id: category.id, data: { description: e.target.value } });
                    }}
                    placeholder="Description"
                  />

                  <div className="text-sm text-gray-600" data-testid={`category-task-count-${category.id}`}>
                    {category.task_count} tasks
                  </div>

                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => setDeleteTarget(category)}
                    data-testid={`category-delete-${category.id}`}
                  >
                    Delete
                  </Button>
                </div>
              </div>
            ))}
            {categories.length === 0 && (
              <p className="text-sm text-gray-500">No categories yet.</p>
            )}
          </div>
        )}
      </Card>

      <Modal isOpen={showCreate} onClose={() => setShowCreate(false)} title="Create Category">
        <form className="space-y-4" onSubmit={handleCreate}>
          <Input
            label="Name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Category name"
            required
          />

          <div>
            <p className="mb-2 text-sm font-medium text-gray-700">Color</p>
            <div className="flex flex-wrap gap-2">
              {PRESET_COLORS.map((preset) => (
                <button
                  key={preset}
                  type="button"
                  aria-label={`Select ${preset}`}
                  data-testid={`categories-create-color-${preset}`}
                  onClick={() => setColor(preset)}
                  className={`h-7 w-7 rounded-full border-2 ${
                    color === preset ? 'border-gray-900' : 'border-transparent'
                  }`}
                  style={{ backgroundColor: preset }}
                />
              ))}
            </div>
          </div>

          <Input
            label="Description (optional)"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What does this category track?"
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

      <Modal
        isOpen={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        title="Delete Category"
      >
        {deleteTarget && (
          <div className="space-y-4" data-testid="category-delete-confirmation">
            <p className="text-sm text-gray-700">
              This category is currently applied to {deleteTarget.task_count} tasks. Deleting it will remove
              the category tag from those tasks.
            </p>
            <div className="flex justify-end gap-2">
              <Button type="button" variant="secondary" onClick={() => setDeleteTarget(null)}>
                Cancel
              </Button>
              <Button
                variant="danger"
                onClick={async () => {
                  await deleteCategory.mutateAsync(deleteTarget.id);
                  setDeleteTarget(null);
                }}
              >
                Delete Category
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}

export default CategoriesSettingsPage;
