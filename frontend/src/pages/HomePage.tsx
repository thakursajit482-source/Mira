import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Sparkles,
  ArrowRight,
  PlusCircle,
  CheckCircle2,
  Clock,
  Map,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { listRoadmaps, getRoadmapDetails, getRoadmapProgress } from '../api/roadmaps';
import { completeTask, uncompleteTask } from '../api/tasks';
import { Roadmap, RoadmapDetail, RoadmapProgress, Day } from '../types';
import { DEV_USER } from '../utils/devUser';
import { formatMinutes } from '../utils/formatters';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { ProgressBar } from '../components/common/ProgressBar';
import { HomeSkeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { TaskList } from '../components/task/TaskList';
import { Button } from '../components/common/Button';
import styles from './HomePage.module.css';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export const HomePage: React.FC = () => {
  const navigate = useNavigate();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeRoadmap, setActiveRoadmap] = useState<Roadmap | null>(null);
  const [roadmapDetail, setRoadmapDetail] = useState<RoadmapDetail | null>(null);
  const [progress, setProgress] = useState<RoadmapProgress | null>(null);

  const [updatingTaskIds, setUpdatingTaskIds] = useState<number[]>([]);
  const [showCompletedTasks, setShowCompletedTasks] = useState(false);

  // Fetch active roadmap, details, and progress
  const loadActiveRoadmap = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const roadmaps = await listRoadmaps(DEV_USER.id);
      if (roadmaps.length === 0) {
        setActiveRoadmap(null);
        setRoadmapDetail(null);
        setProgress(null);
        return;
      }

      // Pick the primary active roadmap
      const primaryRoadmap = roadmaps[0];
      setActiveRoadmap(primaryRoadmap);

      const [detailData, progressData] = await Promise.all([
        getRoadmapDetails(primaryRoadmap.id),
        getRoadmapProgress(primaryRoadmap.id),
      ]);

      setRoadmapDetail(detailData);
      setProgress(progressData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load roadmap data';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadActiveRoadmap();
  }, [loadActiveRoadmap]);

  // Handle task completion toggle with backend as sole source of truth
  const handleToggleTask = async (taskId: number, currentStatus: string) => {
    if (!activeRoadmap) return;

    setUpdatingTaskIds((prev) => [...prev, taskId]);

    try {
      if (currentStatus === 'COMPLETED') {
        await uncompleteTask(taskId);
      } else {
        await completeTask(taskId);
      }

      // Reload fresh authoritative details and progress from backend
      const [updatedDetail, updatedProgress] = await Promise.all([
        getRoadmapDetails(activeRoadmap.id),
        getRoadmapProgress(activeRoadmap.id),
      ]);

      setRoadmapDetail(updatedDetail);
      setProgress(updatedProgress);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update task status';
      setError(msg);
    } finally {
      setUpdatingTaskIds((prev) => prev.filter((id) => id !== taskId));
    }
  };

  // Determine current active day using backend status rules
  const currentDay: Day | null = useMemo(() => {
    if (!roadmapDetail || !roadmapDetail.days || roadmapDetail.days.length === 0) {
      return null;
    }

    const sorted = [...roadmapDetail.days].sort((a, b) => a.day_number - b.day_number);

    // 1. Explicit CURRENT or IN_PROGRESS day
    const active = sorted.find((d) => d.status === 'CURRENT' || d.status === 'IN_PROGRESS');
    if (active) return active;

    // 2. AT_RISK day needing immediate attention
    const atRisk = sorted.find((d) => d.status === 'AT_RISK');
    if (atRisk) return atRisk;

    // 3. First day with incomplete tasks
    const firstIncomplete = sorted.find((d) => d.status !== 'COMPLETED');
    if (firstIncomplete) return firstIncomplete;

    // 4. If all days are completed, return final day
    return sorted[sorted.length - 1];
  }, [roadmapDetail]);

  // Loading state with layout-stable Skeleton
  if (isLoading && !roadmapDetail) {
    return (
      <div className="container">
        <HomeSkeleton />
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="container">
        <ErrorBanner message={error} onRetry={loadActiveRoadmap} />
      </div>
    );
  }

  // Empty state when user has no roadmaps
  if (!activeRoadmap || !roadmapDetail || !currentDay) {
    return (
      <div className="container">
        <EmptyState
          icon={<Sparkles size={32} />}
          title="No Roadmap Yet"
          description="Start with a goal you've already decided to pursue. Mira will help you break it down into daily progress."
          actionLabel="Create Roadmap"
          onAction={() => navigate('/create')}
          actionIcon={<PlusCircle size={18} />}
        />
      </div>
    );
  }

  const tasks = currentDay.tasks || [];
  const completedTasksCount = tasks.filter((t) => t.status === 'COMPLETED').length;
  const isDayCompleted = currentDay.status === 'COMPLETED' || (tasks.length > 0 && completedTasksCount === tasks.length);

  const remainingMinutes = tasks
    .filter((t) => t.status !== 'COMPLETED')
    .reduce((sum, t) => sum + t.estimated_minutes, 0);

  const totalMinutes = tasks.reduce((sum, t) => sum + t.estimated_minutes, 0);

  const todayPercentage = tasks.length > 0 ? Math.round((completedTasksCount / tasks.length) * 100) : 0;

  const greeting = getGreeting();

  const getStatusBadge = () => {
    if (isDayCompleted) {
      return <Badge variant="completed" dot>Completed</Badge>;
    }
    if (currentDay.status === 'AT_RISK') {
      return <Badge variant="at-risk" dot>At Risk</Badge>;
    }
    if (currentDay.status === 'IN_PROGRESS') {
      return <Badge variant="in-progress" dot>In Progress</Badge>;
    }
    return <Badge variant="current" dot>Current Level</Badge>;
  };

  return (
    <div className="container">
      <div className={styles.dashboard}>
        {/* LEVEL 1: Calm Contextual Greeting */}
        <header className={styles.greetingHeader}>
          <h1 className={styles.greetingTitle}>{greeting}.</h1>
          <p className={styles.greetingSubtitle}>Let&apos;s make progress today.</p>
        </header>

        {/* LEVEL 2: Today's Focus (Centerpiece) */}
        <section aria-label="Today's Focus" className={styles.focusSection}>
          <Card
            variant={isDayCompleted ? 'default' : 'elevated'}
            padding="lg"
            className={`${styles.todayCard} ${isDayCompleted ? styles.todayCardCompleted : ''}`}
          >
            {/* Header: Tag + Badge */}
            <div className={styles.cardHeader}>
              <div className={styles.tagRow}>
                <span className={styles.focusLabel}>Today&apos;s Focus</span>
                {getStatusBadge()}
              </div>
              <h2 className={styles.dayTitle}>
                Day {currentDay.day_number}: {currentDay.title || `Day ${currentDay.day_number}`}
              </h2>
            </div>

            {/* Daily Task Progress Bar & Workload */}
            <div className={styles.dailyProgressBlock}>
              <div className={styles.progressStats}>
                <span className={styles.taskCounter}>
                  <strong>{completedTasksCount}</strong> of <strong>{tasks.length}</strong> tasks completed
                </span>
                {remainingMinutes > 0 ? (
                  <span className={styles.timeRemaining}>
                    <Clock size={13} />
                    <span>{formatMinutes(remainingMinutes)} remaining</span>
                  </span>
                ) : (
                  <span className={styles.timeDone}>
                    <CheckCircle2 size={13} />
                    <span>All tasks done</span>
                  </span>
                )}
              </div>

              {/* Mini Daily Progress Track */}
              <div
                className={styles.miniTrack}
                role="progressbar"
                aria-valuenow={todayPercentage}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Today's task completion progress"
              >
                <div
                  className={`${styles.miniFill} ${isDayCompleted ? styles.miniFillDone : ''}`}
                  style={{ width: `${todayPercentage}%` }}
                />
              </div>
            </div>

            {/* Task Area: Active List OR Satisfying Completed Moment */}
            {isDayCompleted ? (
              <div className={styles.dayCompleteState}>
                <div className={styles.dayCompleteIcon}>
                  <CheckCircle2 size={36} className={styles.checkDoneIcon} />
                </div>
                <div className={styles.dayCompleteMessage}>
                  <h3 className={styles.dayCompleteTitle}>Day Complete ✓</h3>
                  <p className={styles.dayCompleteDesc}>
                    You&apos;ve finished today&apos;s work. Ready to see what comes next?
                  </p>
                </div>

                <div className={styles.dayCompleteActions}>
                  <Button
                    variant="primary"
                    size="md"
                    onClick={() => navigate('/roadmap')}
                    leftIcon={<Map size={16} />}
                    rightIcon={<ArrowRight size={14} />}
                  >
                    Continue to Roadmap
                  </Button>

                  <button
                    type="button"
                    className={styles.toggleTasksBtn}
                    onClick={() => setShowCompletedTasks((prev) => !prev)}
                    aria-expanded={showCompletedTasks}
                  >
                    <span>{showCompletedTasks ? 'Hide' : 'Review'} today&apos;s tasks ({tasks.length})</span>
                    {showCompletedTasks ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                  </button>
                </div>

                {showCompletedTasks && (
                  <div className={styles.completedTasksDrawer}>
                    <TaskList
                      tasks={tasks}
                      onToggleTask={handleToggleTask}
                      updatingTaskIds={updatingTaskIds}
                      showSummary={false}
                    />
                  </div>
                )}
              </div>
            ) : (
              <div className={styles.tasksWrapper}>
                <TaskList
                  tasks={tasks}
                  onToggleTask={handleToggleTask}
                  updatingTaskIds={updatingTaskIds}
                  showSummary={false}
                />
              </div>
            )}
          </Card>
        </section>

        {/* LEVEL 3: Current Roadmap Summary Card */}
        <section aria-label="Current Roadmap Summary" className={styles.summarySection}>
          <Card padding="md" className={styles.roadmapSummaryCard}>
            <div className={styles.summaryTop}>
              <div className={styles.summaryLabelRow}>
                <span className={styles.summaryTag}>Current Roadmap</span>
                <span className={styles.roadmapDaysCount}>
                  Day {progress?.completed_days || 0} of {progress?.total_days || activeRoadmap.target_duration_days}
                </span>
              </div>
              <h3 className={styles.summaryTitle}>{activeRoadmap.title}</h3>
            </div>

            {progress && (
              <div className={styles.summaryProgressBar}>
                <ProgressBar
                  percentage={progress.progress_percentage}
                  label={`${Math.round(progress.progress_percentage)}% completed`}
                  size="md"
                  variant={progress.is_completed ? 'success' : 'primary'}
                />
              </div>
            )}

            <div className={styles.summaryBottom}>
              <span className={styles.summarySubtext}>
                {totalMinutes > 0 && `Daily pace: ~${formatMinutes(totalMinutes)}`}
              </span>

              <Button
                variant="secondary"
                size="sm"
                onClick={() => navigate('/roadmap')}
                leftIcon={<Map size={14} />}
                rightIcon={<ArrowRight size={14} />}
              >
                Continue Roadmap
              </Button>
            </div>
          </Card>
        </section>
      </div>
    </div>
  );
};
