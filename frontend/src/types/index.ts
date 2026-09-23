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

export interface GeneratedTask {
  title: string;
  description: string | null;
  estimated_minutes: number;
  category: string | null;
  order_index: number;
}

export interface GeneratedDay {
  day_number: number;
  title: string | null;
  tasks: GeneratedTask[];
}

export interface GeneratedRoadmap {
  title: string;
  description: string | null;
  target_duration_days: number;
  days: GeneratedDay[];
}

export interface NewTaskDefinition {
  title: string;
  description?: string | null;
  estimated_minutes?: number | null;
  order_index?: number;
  category?: string | null;
}

export interface NewDayDefinition {
  tasks: NewTaskDefinition[];
}

export interface RoadmapInsertionRequest {
  new_days: NewDayDefinition[];
  metadata?: Record<string, unknown> | null;
}

export interface DayShiftMapping {
  day_id: number;
  old_day_number: number;
  new_day_number: number;
}

export interface InsertionPreviewResponse {
  status: string;
  conflict: boolean;
  conflict_reason?: string | null;
  first_incomplete_day?: number | null;
  insertion_start_day?: number | null;
  inserted_days_count: number;
  shifted_days_count: number;
  available_days: number;
  required_total_days: number;
  target_duration_days: number;
  shifted_days?: DayShiftMapping[];
  message: string;
}

export interface InsertionResultResponse {
  status: string;
  conflict: boolean;
  conflict_reason?: string | null;
  first_incomplete_day?: number | null;
  insertion_start_day?: number | null;
  inserted_days_count: number;
  shifted_days_count: number;
  available_days: number;
  required_total_days: number;
  target_duration_days: number;
  message: string;
  roadmap?: RoadmapDetail | null;
}

export type RoadmapChangeType =
  | 'INITIAL_GENERATION'
  | 'CONTENT_INSERTION'
  | 'WORKLOAD_REBALANCE'
  | 'TASK_UPDATE'
  | 'SCHEDULE_SHIFT';

export interface RoadmapChange {
  id: number;
  roadmap_id: number;
  version_id: number | null;
  version_number?: number | null;
  change_type: RoadmapChangeType;
  description: string;
  metadata_info?: Record<string, any> | null;
  created_at: string;
}

export interface RoadmapHistoryResponse {
  roadmap_id: number;
  total_changes: number;
  changes: RoadmapChange[];
}

export type DailyWorkloadStatus = 'ON_TRACK' | 'TIGHT' | 'OVER_CAPACITY' | 'COMPLETE';

export interface DailyWorkloadAnalysisResponse {
  roadmap_id: number;
  day_number: number;
  day_id: number;
  date?: string | null;
  status: DailyWorkloadStatus;
  remaining_task_count: number;
  completed_task_count: number;
  total_task_count: number;
  remaining_minutes: number;
  completed_minutes: number;
  total_minutes: number;
  available_minutes: number;
  remaining_capacity_minutes: number;
  overage_minutes: number;
  recommendation: string;
  tomorrow_minutes?: number | null;
  upcoming_average_minutes?: number | null;
}

export interface TaskMovement {
  task_id: number;
  task_title: string;
  from_day_number: number;
  to_day_number: number;
  estimated_minutes: number;
}

export interface DayWorkload {
  day_number: number;
  task_count: number;
  total_estimated_minutes: number;
  is_overloaded: boolean;
}

export interface WorkloadComparison {
  before: DayWorkload[];
  after: DayWorkload[];
}

export interface RoadmapRescheduleRequest {
  daily_available_minutes?: number | null;
  metadata?: Record<string, unknown> | null;
}

export interface ReschedulePreviewResponse {
  status: string;
  conflict: boolean;
  conflict_reason?: string | null;
  first_incomplete_day?: number | null;
  task_movements: TaskMovement[];
  workload_comparison?: WorkloadComparison | null;
  daily_capacity_minutes: number;
  target_duration_days: number;
  message: string;
}

export interface RescheduleResultResponse {
  status: string;
  conflict: boolean;
  conflict_reason?: string | null;
  first_incomplete_day?: number | null;
  task_movements: TaskMovement[];
  daily_capacity_minutes: number;
  target_duration_days: number;
  message: string;
  roadmap?: RoadmapDetail | null;
}

