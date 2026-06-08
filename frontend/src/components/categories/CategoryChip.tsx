import type { TaskCategory } from '../../types';

interface CategoryChipProps {
  category: Pick<TaskCategory, 'name' | 'color'>;
  onRemove?: () => void;
  size?: 'sm' | 'md';
}

export function CategoryChip({ category, onRemove, size = 'md' }: CategoryChipProps) {
  const isSmall = size === 'sm';

  return (
    <span
      className={`inline-flex items-center rounded-full border text-xs font-medium ${
        isSmall ? 'px-2 py-0.5' : 'px-2.5 py-1'
      }`}
      style={{
        borderColor: category.color,
        backgroundColor: `${category.color}22`,
        color: category.color,
      }}
      data-testid={`category-chip-${category.name}`}
    >
      {category.name}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="ml-1 rounded-full p-0.5 hover:bg-black/10"
          aria-label={`Remove ${category.name}`}
          data-testid={`category-chip-remove-${category.name}`}
        >
          x
        </button>
      )}
    </span>
  );
}

export default CategoryChip;
