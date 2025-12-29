// ============================================
// PASSWORD STRENGTH INDICATOR COMPONENT
// Visual feedback for password strength
// ============================================

import { useMemo } from 'react';
import { checkPasswordStrength } from '../../utils/helpers';

interface PasswordStrengthIndicatorProps {
  password: string;
  showFeedback?: boolean;
}

export function PasswordStrengthIndicator({
  password,
  showFeedback = true,
}: PasswordStrengthIndicatorProps) {
  const strength = useMemo(() => checkPasswordStrength(password), [password]);

  if (!password) return null;

  return (
    <div className="mt-2 space-y-2">
      {/* Strength Bar */}
      <div className="flex items-center gap-2">
        <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${strength.color}`}
            style={{ width: `${(strength.score / 5) * 100}%` }}
          />
        </div>
        <span
          className={`text-xs font-medium ${
            strength.score <= 1
              ? 'text-red-600'
              : strength.score <= 2
              ? 'text-orange-600'
              : strength.score <= 3
              ? 'text-yellow-600'
              : strength.score <= 4
              ? 'text-green-600'
              : 'text-emerald-700'
          }`}
        >
          {strength.label}
        </span>
      </div>

      {/* Feedback */}
      {showFeedback && strength.feedback.length > 0 && (
        <ul className="text-xs text-gray-500 space-y-0.5">
          {strength.feedback.map((item, index) => (
            <li key={index} className="flex items-center gap-1">
              <svg
                className="w-3 h-3 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
