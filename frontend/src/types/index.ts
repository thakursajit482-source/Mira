// TypeScript types matching FastAPI backend Pydantic schemas

export type RoadmapStatus = 'NOT_STARTED' | 'IN_PROGRESS' | 'COMPLETED' | 'PAUSED' | 'ARCHIVED';

export type DayStatus = 'LOCKED' | 'CURRENT' | 'IN_PROGRESS' | 'COMPLETED' | 'AT_RISK' | 'SKIPPED';

export type TaskStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'SKIPPED';

export interface Task {
  id: number;
  day_id: number;
  title: string;
  description: string | null;
  order_index: number;
  estimated_minutes: number;
  status: TaskStatus;
  is_completed?: boolean;
  category?: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface Day {
  id: number;
  roadmap_id: number;
  day_number: number;
  title: string | null;
  status: DayStatus;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  tasks?: Task[];
}

export interface Roadmap {
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  target_duration_days: number;
  status: RoadmapStatus;
  start_date: string | null;
  target_completion_date: string | null;
  current_version: number;
  created_at: string;
  updated_at: string;
}

export interface RoadmapDetail extends Roadmap {
  days: Day[];
}

export interface RoadmapProgress {
  roadmap_id: number;
  total_days: number;
  completed_days: number;
  progress_percentage: number;
  total_tasks?: number;
  completed_tasks?: number;
  first_incomplete_day?: number | null;
  status?: RoadmapStatus;
  is_completed?: boolean;
}

export interface RoadmapGenerationRequest {
  user_id: number;
  goal: string;
  target_duration_days: number;
  daily_available_minutes: number;
  context?: string | null;
}

export interface ApiError {
  detail: string | { msg: string; type: string }[];
  status?: number;
}
