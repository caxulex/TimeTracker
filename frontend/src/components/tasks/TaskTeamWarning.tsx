interface TaskTeamWarningProps {
  offProjectTeamNames: string[];
}

export function TaskTeamWarning({ offProjectTeamNames }: TaskTeamWarningProps) {
  if (offProjectTeamNames.length === 0) {
    return null;
  }

  return (
    <div
      className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900"
      role="alert"
      data-testid="task-team-warning"
    >
      Selected team(s) are not assigned to this project: {offProjectTeamNames.join(', ')}
    </div>
  );
}

export default TaskTeamWarning;
