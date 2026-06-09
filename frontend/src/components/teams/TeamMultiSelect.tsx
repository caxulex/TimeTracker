import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { teamsApi } from '../../api/client';
import { TeamChip } from './TeamChip';
import type { Team } from '../../types';

interface TeamMultiSelectProps {
  selectedIds: number[];
  onChange: (teamIds: number[]) => void;
}

export function TeamMultiSelect({ selectedIds, onChange }: TeamMultiSelectProps) {
  const { data } = useQuery({
    queryKey: ['teams', 'task-picker'],
    queryFn: () => teamsApi.getAll({ page: 1, page_size: 100 }),
  });

  const teams = data?.items ?? [];

  const selected = useMemo(
    () => teams.filter((team) => selectedIds.includes(team.id)),
    [teams, selectedIds]
  );

  const available = useMemo(
    () => teams.filter((team) => !selectedIds.includes(team.id)),
    [teams, selectedIds]
  );

  const addTeam = (team: Team) => {
    onChange([...selectedIds, team.id]);
  };

  const removeTeam = (teamId: number) => {
    onChange(selectedIds.filter((id) => id !== teamId));
  };

  return (
    <div className="space-y-2" data-testid="team-multiselect">
      <div className="flex flex-wrap gap-1.5" data-testid="selected-teams">
        {selected.map((team) => (
          <TeamChip
            key={team.id}
            team={{ id: team.id, name: team.name, color: team.color }}
            onRemove={() => removeTeam(team.id)}
          />
        ))}
        {selected.length === 0 && <p className="text-xs text-gray-500">No teams selected</p>}
      </div>

      <select
        value=""
        onChange={(e) => {
          const value = Number(e.target.value);
          if (!value) return;
          const team = available.find((item) => item.id === value);
          if (team) addTeam(team);
        }}
        className="block w-full px-3 py-2 border border-gray-300 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        aria-label="Add team"
      >
        <option value="">Add team...</option>
        {available.map((team) => (
          <option key={team.id} value={team.id}>
            {team.name}
          </option>
        ))}
      </select>
    </div>
  );
}

export default TeamMultiSelect;
