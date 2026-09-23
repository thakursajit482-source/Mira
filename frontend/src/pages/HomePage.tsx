import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, ArrowRight, PlusCircle, CheckCircle, Calendar, Clock, Map } from 'lucide-react';
import { listRoadmaps, getRoadmapDetails, getRoadmapProgress } from '../api/roadmaps';
import { completeTask, uncompleteTask } from '../api/tasks';
import { Roadmap, RoadmapDetail, RoadmapProgress, Day } from '../types';
import { DEV_USER } from '../utils/devUser';
import { formatMinutes } from '../utils/formatters';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { ProgressBar } from '../components/common/ProgressBar';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { TaskList } from '../components/task/TaskList';
import { Button } from '../components/common/Button';
import styles from './HomePage.module.css';

export const HomePage: React.FC = () => {
  const navigate = useNavigate();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeRoadmap, setActiveRoadmap] = useState<Roadmap | null>(null);
  const [roadmapDetail, setRoadmapDetail] = useState<RoadmapDetail | null>(null);
  const [progress, setProgress] = useState<RoadmapProgress | null>(null);

  const [updatingTaskIds, setUpdatingTaskIds] = useState<number[]>([]);

  // Fetch active roadmap and details
  const loadActiveRoadmap = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const roadmaps = await listRoadmaps(DEV_USER.id);
      if (roadmaps.length === 0) {
        setActiveRoadmap(null);
        setRoadmapDetail(null);
        setProgress(null);
        setIsLoading(false);
        return;
      }

      // Pick the first active or latest roadmap
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

  // Handle task completion toggle
  const handleToggleTask = async (taskId: number, currentStatus: string) => {
    if (!activeRoadmap) return;

    setUpdatingTaskIds((prev) => [...prev, taskId]);

    try {
      if (currentStatus === 'COMPLETED') {
        await uncompleteTask(taskId);
      } else {
        await completeTask(taskId);
      }

      // Reload authoritative details and progress from backend
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

  if (isLoading) {
    return <LoadingSpinner label="Loading your daily focus..." fullPage />;
  }

  if (error) {
    return (
      <div className="container">
        <ErrorBanner message={error} onRetry={loadActiveRoadmap} />
      </div>
    );
  }

  if (!activeRoadmap || !roadmapDetail) {
    return (
      <div className="container">
        <EmptyState
          icon={<Sparkles size={28} />}
          title="No Active Roadmap"
          description="You haven't started a roadmap yet. Generate or create your first roadmap to turn your learning plans into daily progress."
          actionLabel="Create Your First Roadmap"
          onAction={() => navigate('/create')}
          actionIcon={<PlusCircle size={18} />}
        />
      </div>
    );
  }

  // Determine current day from progress or detail
  const days = roadmapDetail.days || [];
  let currentDay: Day | undefined = undefined;

  if (progress && progress.first_incomplete_day) {
    currentDay = days.find((d) => d.day_number === progress.first_incomplete_day);
  }

  if (!currentDay) {
    currentDay = days.find((d) => d.status === 'CURRENT' || d.status === 'IN_PROGRESS');
  }

  if (!currentDay && days.length > 0) {
    currentDay = days[0];
  }

  // Find next upcoming day
  const nextDay = currentDay
    ? days.find((d) => d.day_number === currentDay!.day_number + 1)
    : undefined;

  const currentTasks = currentDay?.tasks || [];
  const totalDayMinutes = currentTasks.reduce((sum, t) => sum + t.estimated_minutes, 0);

  return (
    <div className="container">
      {/* Top Banner / Roadmap Summary */}
      <div className={styles.topSection}>
        <div className={styles.roadmapInfo}>
          <div className={styles.titleRow}>
            <h1 className={styles.roadmapTitle}>{activeRoadmap.title}</h1>
            <Badge variant="current" dot>
              {progress?.is_completed ? 'Completed' : 'Active Plan'}
            </Badge>
          </div>
          <p className={styles.roadmapDescription}>
            {activeRoadmap.description || 'Follow your daily plan and complete tasks to advance.'}
          </p>
        </div>

        <Button
          variant="primary"
          size="md"
          onClick={() => navigate('/roadmap')}
          leftIcon={<Map size={16} />}
          rightIcon={<ArrowRight size={14} />}
        >
          Continue Roadmap
        </Button>
      </div>

      {/* Progress Bar Card */}
      {progress && (
        <Card className={styles.progressCard} padding="md">
          <ProgressBar
            percentage={progress.progress_percentage}
            label={`Day ${progress.completed_days} of ${progress.total_days} Completed`}
            size="md"
            variant={progress.is_completed ? 'success' : 'primary'}
          />
        </Card>
      )}

      {/* Main Grid: Today's Focus & Side Cards */}
      <div className={styles.contentGrid}>
        {/* Left Column: Today's Focus Card */}
        <div className={styles.mainColumn}>
          <Card variant="elevated" padding="lg" className={styles.todayCard}>
            <div className={styles.cardHeader}>
              <div className={styles.levelBadgeRow}>
                <span className={styles.levelLabel}>
                  {currentDay ? `Day ${currentDay.day_number}` : 'Daily Focus'}
                </span>
                {currentDay?.status === 'COMPLETED' ? (
                  <Badge variant="completed" dot>Completed</Badge>
                ) : currentDay?.status === 'AT_RISK' ? (
                  <Badge variant="at-risk" dot>At Risk</Badge>
                ) : (
                  <Badge variant="current" dot>Current Level</Badge>
                )}
              </div>
              <h2 className={styles.cardTitle}>
                {currentDay?.title || "Today's Work"}
              </h2>
              <div className={styles.cardMeta}>
                <span className={styles.metaItem}>
                  <Clock size={14} />
                  <span>{formatMinutes(totalDayMinutes)}</span>
                </span>
                <span className={styles.metaItem}>
                  <CheckCircle size={14} />
                  <span>{currentTasks.length} tasks</span>
                </span>
              </div>
            </div>

            {/* Task list for current day */}
            <div className={styles.cardBody}>
              <TaskList
                tasks={currentTasks}
                onToggleTask={handleToggleTask}
                updatingTaskIds={updatingTaskIds}
                showSummary={true}
              />
            </div>
          </Card>
        </div>

        {/* Right Column: Upcoming & Tips */}
        <div className={styles.sideColumn}>
          {/* Next Level Preview */}
          {nextDay ? (
            <Card padding="md" className={styles.nextCard}>
              <div className={styles.nextHeader}>
                <span className={styles.nextTag}>Upcoming Next</span>
                <Badge variant="locked" size="sm">Locked</Badge>
              </div>
              <h4 className={styles.nextTitle}>Day {nextDay.day_number}: {nextDay.title || 'Next Level'}</h4>
              <p className={styles.nextMeta}>
                {nextDay.tasks?.length || 0} tasks • {formatMinutes(nextDay.tasks?.reduce((sum, t) => sum + t.estimated_minutes, 0) || 0)}
              </p>
              <Button
                variant="ghost"
                size="sm"
                className={styles.viewRoadmapBtn}
                onClick={() => navigate('/roadmap')}
                rightIcon={<ArrowRight size={14} />}
              >
                Inspect on Roadmap
              </Button>
            </Card>
          ) : (
            <Card padding="md" className={styles.nextCard}>
              <div className={styles.nextHeader}>
                <span className={styles.nextTag}>Milestone</span>
                <Badge variant="completed" size="sm">Final Day</Badge>
              </div>
              <h4 className={styles.nextTitle}>Final Level</h4>
              <p className={styles.nextMeta}>
                You are on the final stretch of this roadmap! Complete today&apos;s tasks to finish the entire plan.
              </p>
            </Card>
          )}

          {/* Quick Info Card */}
          <Card padding="md" className={styles.infoCard}>
            <div className={styles.infoItem}>
              <Calendar size={16} className={styles.infoIcon} />
              <div>
                <span className={styles.infoLabel}>Target Duration</span>
                <p className={styles.infoValue}>{activeRoadmap.target_duration_days} Days</p>
              </div>
            </div>
            <div className={styles.infoItem}>
              <Clock size={16} className={styles.infoIcon} />
              <div>
                <span className={styles.infoLabel}>Daily Capacity</span>
                <p className={styles.infoValue}>{formatMinutes(DEV_USER.dailyAvailableMinutes)}</p>
              </div>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
