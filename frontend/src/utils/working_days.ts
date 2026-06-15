export type AvgDenominatorType =
  | 'working_days_completed'
  | 'working_days_all'
  | 'days_with_entries'
  | 'calendar_days';

export type WorkingDaysSource = 'user' | 'company' | 'default';

export interface AvgHoursMetadata {
  avg_denominator_days?: number;
  avg_denominator_type?: AvgDenominatorType;
  avg_includes_today?: boolean;
  avg_working_days_source?: WorkingDaysSource;
  avg_working_days_used?: number[];
}

const DAY_NAMES = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function normalizeWorkingDays(days?: number[]): number[] {
  if (!days || days.length === 0) {
    return [];
  }

  return [...new Set(days)]
    .filter((value) => Number.isInteger(value) && value >= 0 && value <= 6)
    .sort((a, b) => a - b);
}

export function formatWorkingDays(days?: number[]): string {
  const normalized = normalizeWorkingDays(days);
  if (normalized.length === 0) {
    return '(none configured)';
  }

  const segments: string[] = [];
  let start = normalized[0];
  let prev = normalized[0];

  for (let i = 1; i < normalized.length; i += 1) {
    const current = normalized[i];
    if (current === prev + 1) {
      prev = current;
      continue;
    }

    if (start === prev) {
      segments.push(DAY_NAMES[start]);
    } else {
      segments.push(`${DAY_NAMES[start]}-${DAY_NAMES[prev]}`);
    }

    start = current;
    prev = current;
  }

  if (start === prev) {
    segments.push(DAY_NAMES[start]);
  } else {
    segments.push(`${DAY_NAMES[start]}-${DAY_NAMES[prev]}`);
  }

  return segments.join(', ');
}

export function getAvgHoursSubtitle(metadata: AvgHoursMetadata, fallbackDays?: number): string {
  const denominator = metadata.avg_denominator_days;
  if (typeof denominator !== 'number' || denominator < 0) {
    if (typeof fallbackDays === 'number') {
      return `across ${fallbackDays} days`;
    }
    return 'across 0 days';
  }

  if (metadata.avg_denominator_type === 'days_with_entries') {
    return `across ${denominator} days with logged hours`;
  }

  // Show "(incl. today)" only when today is actually counted in the denominator.
  // denominator_type 'working_days_completed' means today was explicitly excluded;
  // only 'working_days_all' (and a period that contains today) includes today.
  if (
    metadata.avg_includes_today &&
    metadata.avg_denominator_type !== 'working_days_completed'
  ) {
    return `across ${denominator} working days (incl. today)`;
  }

  return `across ${denominator} completed working days`;
}

export function getAvgHoursTooltip(metadata: AvgHoursMetadata): string {
  const workingDays = formatWorkingDays(metadata.avg_working_days_used);
  const sourceNote =
    metadata.avg_working_days_source === 'user'
      ? ' (custom schedule)'
      : metadata.avg_working_days_source === 'company'
      ? ' (company schedule)'
      : '';

  const preface = metadata.avg_includes_today
    ? 'Includes today and excludes non-working days.'
    : 'Excludes today (in progress) and non-working days.';

  return `${preface} Working days for this user: ${workingDays}${sourceNote}`;
}
