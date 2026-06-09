import type { TaskTeam } from '../../types';

interface TeamChipProps {
  team: TaskTeam;
  onRemove?: () => void;
  size?: 'sm' | 'md';
}

export function TeamChip({ team, onRemove, size = 'md' }: TeamChipProps) {
  const sizeClasses =
    size === 'sm'
      ? 'text-[11px] px-2 py-0.5'
      : 'text-xs px-2.5 py-1';

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border border-gray-200 bg-white ${sizeClasses}`}
      title={team.name}
    >
      <span
        className="h-2 w-2 rounded-full"
        style={{ backgroundColor: team.color || '#6B7280' }}
        aria-hidden="true"
      />
      <span className="text-gray-700">{team.name}</span>
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          className="ml-0.5 text-gray-500 hover:text-red-600"
          aria-label={`Remove ${team.name}`}
        >
          ×
        </button>
      )}
    </span>
  );
}

export default TeamChip;
