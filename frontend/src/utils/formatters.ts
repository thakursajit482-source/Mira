import { DayStatus, RoadmapStatus, TaskStatus } from '../types';

/**
 * Formats a duration in minutes into a human-friendly string (e.g. 90 -> "1h 30m", 45 -> "45m").
 */
export function formatMinutes(minutes: number): string {
  if (!minutes || minutes <= 0) return '0m';
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  if (hours > 0 && remainingMinutes > 0) {
    return `${hours}h ${remainingMinutes}m`;
  } else if (hours > 0) {
    return `${hours}h`;
  } else {
    return `${remainingMinutes}m`;
  }
}

/**
 * Formats an ISO date string into a readable format.
 */
export function formatDate(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    }).format(date);
  } catch {
    return isoString;
  }
}

/**
 * Returns human-readable status labels.
 */
export function getDayStatusLabel(status: DayStatus): string {
  switch (status) {
    case 'COMPLETED':
      return 'Completed';
    case 'CURRENT':
      return 'Current Level';
    case 'IN_PROGRESS':
      return 'In Progress';
    case 'LOCKED':
      return 'Locked';
    default:
      return status;
  }
}

export function getRoadmapStatusLabel(status: RoadmapStatus): string {
  switch (status) {
    case 'NOT_STARTED':
      return 'Not Started';
    case 'IN_PROGRESS':
      return 'Active';
    case 'COMPLETED':
      return 'Completed';
    case 'PAUSED':
      return 'Paused';
    case 'ARCHIVED':
      return 'Archived';
    default:
      return status;
  }
}

export function getTaskStatusLabel(status: TaskStatus): string {
  switch (status) {
    case 'COMPLETED':
      return 'Done';
    case 'IN_PROGRESS':
      return 'In Progress';
    case 'PENDING':
      return 'Pending';
    case 'SKIPPED':
      return 'Skipped';
    default:
      return status;
  }
}
