import { DayStatus, RoadmapStatus, TaskStatus, RoadmapChangeType, RoadmapChange } from '../types';

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
    case 'AT_RISK':
      return 'At Risk';
    case 'SKIPPED':
      return 'Skipped';
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

/**
 * Formats a timestamp into human-friendly relative time:
 * - "Just now" (< 1 min)
 * - "12 min ago" (< 60 min)
 * - "Today · 10:42 AM"
 * - "Yesterday · 6:30 PM"
 * - "Sep 18 · 4:20 PM"
 */
export function formatRelativeTime(isoString: string | null | undefined): string {
  if (!isoString) return '—';
  try {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);

    if (diffSec < 60 && diffSec >= 0) {
      return 'Just now';
    }
    if (diffMin < 60 && diffMin > 0) {
      return `${diffMin} min ago`;
    }

    const timeStr = new Intl.DateTimeFormat('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }).format(date);

    const isToday =
      date.getDate() === now.getDate() &&
      date.getMonth() === now.getMonth() &&
      date.getFullYear() === now.getFullYear();

    if (isToday) {
      return `Today · ${timeStr}`;
    }

    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const isYesterday =
      date.getDate() === yesterday.getDate() &&
      date.getMonth() === yesterday.getMonth() &&
      date.getFullYear() === yesterday.getFullYear();

    if (isYesterday) {
      return `Yesterday · ${timeStr}`;
    }

    const isSameYear = date.getFullYear() === now.getFullYear();
    const dateStr = new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      ...(isSameYear ? {} : { year: 'numeric' }),
    }).format(date);

    return `${dateStr} · ${timeStr}`;
  } catch {
    return isoString;
  }
}

export interface ChangeTypeConfig {
  label: string;
  badgeVariant: 'current' | 'completed' | 'in-progress' | 'neutral';
  iconType: 'sparkles' | 'plus' | 'refresh' | 'edit' | 'clock';
}

/**
 * Returns human-readable label and visual styling configuration for RoadmapChangeType.
 */
export function getChangeTypeConfig(changeType: RoadmapChangeType): ChangeTypeConfig {
  switch (changeType) {
    case 'INITIAL_GENERATION':
      return {
        label: 'Roadmap Created',
        badgeVariant: 'completed',
        iconType: 'sparkles',
      };
    case 'CONTENT_INSERTION':
      return {
        label: 'Plan Added',
        badgeVariant: 'current',
        iconType: 'plus',
      };
    case 'WORKLOAD_REBALANCE':
      return {
        label: 'Tasks Rescheduled',
        badgeVariant: 'in-progress',
        iconType: 'refresh',
      };
    case 'TASK_UPDATE':
      return {
        label: 'Task Updated',
        badgeVariant: 'neutral',
        iconType: 'edit',
      };
    case 'SCHEDULE_SHIFT':
      return {
        label: 'Schedule Shifted',
        badgeVariant: 'neutral',
        iconType: 'clock',
      };
    default:
      return {
        label: changeType,
        badgeVariant: 'neutral',
        iconType: 'clock',
      };
  }
}

export interface MetricChip {
  label: string;
  value: string;
}

/**
 * Extracts clean, human-readable metric chips from RoadmapChange.metadata_info without exposing raw database JSON.
 */
export function getStructuredChangeMetrics(change: RoadmapChange): MetricChip[] {
  const meta = change.metadata_info;
  if (!meta || typeof meta !== 'object') return [];

  const chips: MetricChip[] = [];

  if (change.change_type === 'INITIAL_GENERATION') {
    if (meta.total_days || meta.target_duration_days) {
      chips.push({
        label: 'Duration',
        value: `${meta.total_days || meta.target_duration_days} days`,
      });
    }
    if (meta.total_tasks) {
      chips.push({ label: 'Tasks', value: `${meta.total_tasks} tasks` });
    }
    if (meta.daily_available_minutes || meta.daily_capacity_minutes) {
      chips.push({
        label: 'Daily Focus',
        value: `${meta.daily_available_minutes || meta.daily_capacity_minutes}m / day`,
      });
    }
  } else if (change.change_type === 'CONTENT_INSERTION') {
    if (meta.insertion_start_day || meta.start_day) {
      chips.push({
        label: 'Inserted At',
        value: `Day ${meta.insertion_start_day || meta.start_day}`,
      });
    }
    if (meta.inserted_days_count !== undefined) {
      chips.push({
        label: 'Days Added',
        value: `+${meta.inserted_days_count} days`,
      });
    }
    if (meta.shifted_days_count !== undefined) {
      chips.push({
        label: 'Future Days Shifted',
        value: `${meta.shifted_days_count} days`,
      });
    }
    if (meta.target_duration_days) {
      chips.push({
        label: 'Total Plan Limit',
        value: `${meta.target_duration_days} days`,
      });
    }
  } else if (change.change_type === 'WORKLOAD_REBALANCE') {
    if (meta.first_incomplete_day) {
      chips.push({
        label: 'Rebalanced From',
        value: `Day ${meta.first_incomplete_day}`,
      });
    }
    if (meta.moved_tasks_count !== undefined) {
      chips.push({
        label: 'Tasks Adjusted',
        value: `${meta.moved_tasks_count} tasks`,
      });
    }
    if (meta.daily_capacity_minutes) {
      chips.push({
        label: 'Target Daily Cap',
        value: `${meta.daily_capacity_minutes}m / day`,
      });
    }
    if (meta.target_duration_days) {
      chips.push({
        label: 'Fixed Duration',
        value: `${meta.target_duration_days} days`,
      });
    }
  } else {
    // Generic fallback for any other change types
    for (const [key, val] of Object.entries(meta)) {
      if (typeof val === 'string' || typeof val === 'number') {
        const cleanKey = key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
        chips.push({ label: cleanKey, value: String(val) });
      }
    }
  }

  return chips;
}
