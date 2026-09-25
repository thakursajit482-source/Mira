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
  CalendarClock,
  Info,
  AlertCircle,
  Flame,
  TrendingUp,
} from 'lucide-react';
import {
  listRoadmaps,
  getRoadmapDetails,
  getRoadmapProgress,
  getDailyWorkloadAnalysis,
  getRoadmapMomentum,
} from '../api/roadmaps';
import { completeTask, uncompleteTask } from '../api/tasks';
import {
  Roadmap,
  RoadmapDetail,
  RoadmapProgress,
  Day,
  DailyWorkloadAnalysisResponse,
  RoadmapMomentum,
} from '../types';
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
import { ReschedulePreviewModal } from '../components/roadmap/ReschedulePreviewModal';
import { useToast } from '../context/ToastContext';
import styles from './HomePage.module.css';

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return 'Good morning';
  if (hour < 18) return 'Good afternoon';
  return 'Good evening';
}

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToast();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeRoadmap, setActiveRoadmap] = useState<Roadmap | null>(null);
  const [roadmapDetail, setRoadmapDetail] = useState<RoadmapDetail | null>(null);
  const [progress, setProgress] = useState<RoadmapProgress | null>(null);
  const [dailyAnalysis, setDailyAnalysis] = useState<DailyWorkloadAnalysisResponse | null>(null);
  const [momentum, setMomentum] = useState<RoadmapMomentum | null>(null);
  const [isRescheduleModalOpen, setIsRescheduleModalOpen] = useState(false);

  const [updatingTaskIds, setUpdatingTaskIds] = useState<number[]>([]);
  const [showCompletedTasks, setShowCompletedTasks] = useState(false);

  // Fetch active roadmap, details, progress, daily analysis, and momentum
  const loadActiveRoadmap = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const roadmaps = await listRoadmaps(DEV_USER.id);
      if (roadmaps.length === 0) {
        setActiveRoadmap(null);
        setRoadmapDetail(null);
        setProgress(null);
        setDailyAnalysis(null);
        setMomentum(null);
        return;
      }

      // Pick the primary active roadmap
      const primaryRoadmap = roadmaps[0];
      setActiveRoadmap(primaryRoadmap);

      const [detailData, progressData, analysisData, momentumData] = await Promise.all([
        getRoadmapDetails(primaryRoadmap.id),
        getRoadmapProgress(primaryRoadmap.id),
        getDailyWorkloadAnalysis(primaryRoadmap.id),
        getRoadmapMomentum(primaryRoadmap.id).catch(() => null),
      ]);

      setRoadmapDetail(detailData);
      setProgress(progressData);
      setDailyAnalysis(analysisData);
      setMomentum(momentumData);
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
        toast.info('Task marked incomplete.');
      } else {
        await completeTask(taskId);
      }

      // Reload fresh authoritative details, progress, analysis, and momentum from backend
      const [updatedDetail, updatedProgress, updatedAnalysis, updatedMomentum] = await Promise.all([
        getRoadmapDetails(activeRoadmap.id),
        getRoadmapProgress(activeRoadmap.id),
        getDailyWorkloadAnalysis(activeRoadmap.id),
        getRoadmapMomentum(activeRoadmap.id).catch(() => null),
      ]);

      setRoadmapDetail(updatedDetail);
      setProgress(updatedProgress);
      setDailyAnalysis(updatedAnalysis);
      if (updatedMomentum) {
        setMomentum(updatedMomentum);
      }

      // Day / Roadmap completion feedback when completing a task
      if (currentStatus !== 'COMPLETED') {
        if (updatedProgress.is_completed) {
          toast.success('Roadmap complete', 'You finished everything you planned.');
        } else {
          const targetDay = updatedDetail.days.find((d) => d.tasks?.some((t) => t.id === taskId));
          if (targetDay && targetDay.tasks && targetDay.tasks.length > 0 && targetDay.tasks.every((t) => t.status === 'COMPLETED')) {
            toast.success(`Day ${targetDay.day_number} complete`, 'Nice work. Your roadmap is moving forward.');
          } else {
            toast.success('Task completed.');
          }
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Couldn't update the task. Try again.";
      setError(msg);
      toast.error("Couldn't update the task. Try again.");
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

  // Empty state when user has no roadmaps (Part 6)
  if (!activeRoadmap || !roadmapDetail || !currentDay) {
    return (
      <div className="container">
        <EmptyState
          icon={<Sparkles size={32} />}
          title="Nothing planned yet."
          description="Add a roadmap and Mira will help you turn it into daily progress."
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

  const isRoadmapCompleted = Boolean(
    progress?.is_completed ||
      (progress && progress.completed_days >= progress.total_days && progress.total_days > 0)
  );

  const remainingMinutes = tasks
    .filter((t) => t.status !== 'COMPLETED')
    .reduce((sum, t) => sum + t.estimated_minutes, 0);

  const totalMinutes = tasks.reduce((sum, t) => sum + t.estimated_minutes, 0);

  const todayPercentage = tasks.length > 0 ? Math.round((completedTasksCount / tasks.length) * 100) : 0;

  const greeting = getGreeting();

  const getStatusBadge = () => {
    if (dailyAnalysis) {
      switch (dailyAnalysis.status) {
        case 'COMPLETE':
          return <Badge variant="completed" dot>Completed</Badge>;
        case 'OVER_CAPACITY':
          return <Badge variant="at-risk" dot>Over Capacity</Badge>;
        case 'TIGHT':
          return <Badge variant="current" dot>Tight Schedule</Badge>;
        case 'ON_TRACK':
          return <Badge variant="completed" dot>On Track</Badge>;
      }
    }
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

  const capacityPercent =
    dailyAnalysis && dailyAnalysis.available_minutes > 0
      ? Math.min(100, Math.round((dailyAnalysis.remaining_minutes / dailyAnalysis.available_minutes) * 100))
      : 0;

  return (
    <div className="container">
      <div className={styles.dashboard}>
        {/* LEVEL 1: Calm Contextual Greeting with Motivational Context */}
        <header className={styles.greetingHeader}>
          <h1 className={styles.greetingTitle}>{greeting}.</h1>
          <p className={styles.greetingSubtitle}>
            {isRoadmapCompleted
              ? 'Roadmap complete.'
              : momentum?.streak && momentum.streak.current_days > 1
              ? `Your streak is ${momentum.streak.current_days} days.`
              : isDayCompleted
              ? `Day ${currentDay.day_number} is complete.`
              : progress && progress.progress_percentage > 0
              ? `You’ve completed ${Math.round(progress.progress_percentage)}% of this roadmap.`
              : "Let's make progress today."}
          </p>
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
                Day {currentDay.day_number}
                {currentDay.title && (
                  <span className={styles.dayDateLabel}>{currentDay.title}</span>
                )}
              </h2>
            </div>

            {/* Smart Workload Budget Grid */}
            <div className={styles.budgetGrid}>
              <div className={styles.budgetItem}>
                <span className={styles.budgetLabel}>Estimated Time</span>
                <span className={styles.budgetValue}>
                  {dailyAnalysis ? formatMinutes(dailyAnalysis.remaining_minutes) : formatMinutes(remainingMinutes)}
                </span>
              </div>
              <div className={styles.budgetItem}>
                <span className={styles.budgetLabel}>Available Today</span>
                <span className={styles.budgetValue}>
                  {dailyAnalysis ? formatMinutes(dailyAnalysis.available_minutes) : '2h'}
                </span>
              </div>
              <div className={styles.budgetItem}>
                <span className={styles.budgetLabel}>Capacity Margin</span>
                <span
                  className={`${styles.budgetValue} ${
                    dailyAnalysis?.status === 'OVER_CAPACITY'
                      ? styles.budgetOverage
                      : styles.budgetRemaining
                  }`}
                >
                  {dailyAnalysis?.status === 'OVER_CAPACITY'
                    ? `+${dailyAnalysis.overage_minutes}m over`
                    : dailyAnalysis?.status === 'COMPLETE'
                    ? 'Complete'
                    : `${dailyAnalysis?.remaining_capacity_minutes ?? 0}m left`}
                </span>
              </div>
            </div>

            {/* Daily Task Progress Bar & Capacity Track */}
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

              {/* Task Completion Progress Track */}
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

              {/* Capacity Usage Track */}
              {dailyAnalysis && !isDayCompleted && (
                <div className={styles.capacityTrackWrapper}>
                  <div className={styles.capacityTrackHeader}>
                    <span>Workload Capacity Usage</span>
                    <span>{capacityPercent}%</span>
                  </div>
                  <div
                    className={styles.capacityTrack}
                    role="progressbar"
                    aria-valuenow={capacityPercent}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-label="Today's workload capacity usage"
                  >
                    <div
                      className={`${styles.capacityFill} ${
                        dailyAnalysis.status === 'OVER_CAPACITY'
                          ? styles.capacityFillOver
                          : dailyAnalysis.status === 'TIGHT'
                          ? styles.capacityFillTight
                          : styles.capacityFillOnTrack
                      }`}
                      style={{ width: `${capacityPercent}%` }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Smart Recommendation Card */}
            {dailyAnalysis && !isDayCompleted && (
              <div
                className={`${styles.recommendationCard} ${
                  dailyAnalysis.status === 'OVER_CAPACITY'
                    ? styles.recommendationCardOver
                    : dailyAnalysis.status === 'TIGHT'
                    ? styles.recommendationCardTight
                    : ''
                }`}
              >
                <div className={styles.recommendationContent}>
                  {dailyAnalysis.status === 'OVER_CAPACITY' ? (
                    <AlertCircle size={18} className={styles.recommendationIconOver} />
                  ) : dailyAnalysis.status === 'TIGHT' ? (
                    <CalendarClock size={18} className={styles.recommendationIcon} />
                  ) : (
                    <Info size={18} className={styles.recommendationIcon} />
                  )}
                  <p className={styles.recommendationText}>{dailyAnalysis.recommendation}</p>
                </div>

                {dailyAnalysis.status === 'OVER_CAPACITY' && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => setIsRescheduleModalOpen(true)}
                    leftIcon={<CalendarClock size={13} />}
                  >
                    Preview Lighter Schedule
                  </Button>
                )}
              </div>
            )}

            {/* Task Area: Active List OR Satisfying Completed Moment */}
            {isDayCompleted ? (
              <div className={styles.dayCompleteState}>
                <div className={styles.dayCompleteIcon}>
                  <CheckCircle2 size={36} className={styles.checkDoneIcon} />
                </div>
                {isRoadmapCompleted ? (
                  <>
                    <div className={styles.dayCompleteMessage}>
                      <h3 className={styles.dayCompleteTitle}>Roadmap complete</h3>
                      <p className={styles.dayCompleteDesc}>
                        You finished everything you planned.
                      </p>
                    </div>

                    <div className={styles.dayCompleteActions}>
                      <Button
                        variant="primary"
                        size="md"
                        onClick={() => navigate('/roadmap')}
                        leftIcon={<Map size={16} />}
                      >
                        Review Roadmap
                      </Button>

                      <Button
                        variant="secondary"
                        size="md"
                        onClick={() => navigate('/create')}
                        leftIcon={<PlusCircle size={16} />}
                      >
                        Start a New Roadmap
                      </Button>

                      <button
                        type="button"
                        className={styles.toggleTasksBtn}
                        onClick={() => setShowCompletedTasks((prev) => !prev)}
                        aria-expanded={showCompletedTasks}
                      >
                        <span>{showCompletedTasks ? 'Hide' : 'Review'} tasks ({tasks.length})</span>
                        {showCompletedTasks ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <div className={styles.dayCompleteMessage}>
                      <h3 className={styles.dayCompleteTitle}>Day {currentDay.day_number} complete</h3>
                      <p className={styles.dayCompleteDesc}>
                        Nice work. Your roadmap is moving forward.
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
                  </>
                )}

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

            {/* Secondary Upcoming Workload Insight */}
            {dailyAnalysis && (dailyAnalysis.tomorrow_minutes || dailyAnalysis.upcoming_average_minutes) && (
              <div className={styles.upcomingInsight}>
                <Clock size={12} />
                <span>
                  {dailyAnalysis.tomorrow_minutes ? `Tomorrow: ${formatMinutes(dailyAnalysis.tomorrow_minutes)} planned` : ''}
                  {dailyAnalysis.tomorrow_minutes && dailyAnalysis.upcoming_average_minutes ? ' · ' : ''}
                  {dailyAnalysis.upcoming_average_minutes ? `Next days avg: ~${formatMinutes(dailyAnalysis.upcoming_average_minutes)}/day` : ''}
                </span>
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

            {/* Phase 10.6: Compact Progress & Momentum summary row */}
            {momentum && (
              <div className={styles.homeMomentumRow}>
                <div className={styles.homeMomentumChips}>
                  <span className={styles.homeMomentumChip} title="Current consistency streak">
                    <Flame size={13} className={styles.homeFlameIcon} />
                    <span>{momentum.streak.current_days}d streak</span>
                  </span>
                  <span className={styles.homeMomentumChip} title={momentum.momentum.description}>
                    <TrendingUp size={13} />
                    <span>{momentum.momentum.label}</span>
                  </span>
                </div>
                <button
                  type="button"
                  className={styles.viewProgressLink}
                  onClick={() => navigate('/roadmap')}
                >
                  View Progress &rarr;
                </button>
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

        {/* Reschedule Preview Modal */}
        <ReschedulePreviewModal
          roadmapId={activeRoadmap.id}
          isOpen={isRescheduleModalOpen}
          onClose={() => setIsRescheduleModalOpen(false)}
          onSuccess={loadActiveRoadmap}
        />
      </div>
    </div>
  );
};
