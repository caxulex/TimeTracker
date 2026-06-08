import React from 'react';

import { Button } from '../common';
import type { SimilarProjectMatch } from '../../types';

interface SimilarProjectsWarningProps {
  matches: SimilarProjectMatch[];
  mode: 'create' | 'edit';
  onUseExisting?: (project: SimilarProjectMatch) => void;
}

function getMatchDescription(match: SimilarProjectMatch): string {
  if (match.match_type === 'exact') {
    return `matches "${match.name.toLowerCase()}" exactly`;
  }
  if (match.match_type === 'substring') {
    return 'one name contains the other';
  }
  return 'close typo/variation detected';
}

export function SimilarProjectsWarning({ matches, mode, onUseExisting }: SimilarProjectsWarningProps) {
  if (matches.length === 0) {
    return null;
  }

  return (
    <div
      className="rounded-lg border border-amber-300 bg-amber-50 p-4"
      role="status"
      data-testid="similar-projects-warning"
    >
      <p className="text-sm font-semibold text-amber-900">Similar projects already exist</p>
      <div className="mt-3 space-y-3">
        {matches.map((match) => (
          <div
            key={match.id}
            className="rounded-md border border-amber-200 bg-white p-3"
            data-testid={`similar-project-match-${match.id}`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-amber-900">
                  {match.name} ({match.team_name})
                </p>
                <p className="mt-1 text-xs text-amber-700">{getMatchDescription(match)}</p>
              </div>
              {onUseExisting && (
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  onClick={() => onUseExisting(match)}
                  data-testid={`similar-project-action-${match.id}`}
                >
                  {mode === 'create' ? 'Use this instead' : 'View this project'}
                </Button>
              )}
            </div>
          </div>
        ))}
      </div>
      <p className="mt-3 text-xs text-amber-800">You can still continue if this is intentional.</p>
    </div>
  );
}
