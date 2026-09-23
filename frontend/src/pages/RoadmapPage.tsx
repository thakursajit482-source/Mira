import React, { useEffect, useState, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, PlusCircle, Calendar, RefreshCw, Compass, History, CheckCircle2 } from 'lucide-react';
import { listRoadmaps, getRoadmapDetails, getRoadmapProgress, getRoadmapMomentum } from '../api/roadmaps';
import { completeTask, uncompleteTask } from '../api/tasks';
import { Roadmap, RoadmapDetail, RoadmapProgress, RoadmapMomentum, Day } from '../types';
import { DEV_USER } from '../utils/devUser';
import { formatDate } from '../utils/formatters';
import { useToast } from '../context/ToastContext';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { ProgressBar } from '../components/common/ProgressBar';
import { RoadmapSkeleton } from '../components/common/Skeleton';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { RoadmapNode } from '../components/roadmap/RoadmapNode';
import { RoadmapPath } from '../components/roadmap/RoadmapPath';
import { DayDetailModal } from '../components/roadmap/DayDetailModal';
import { RoadmapHistoryModal } from '../components/roadmap/RoadmapHistoryModal';
import { RoadmapMomentumSection } from '../components/roadmap/RoadmapMomentumSection';
import styles from './RoadmapPage.module.css';

export const RoadmapPage: React.FC = () => {
  const navigate = useNavigate();
  const toast = useToast();
  const currentDayRef = useRef<HTMLDivElement | null>(null);

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [roadmaps, setRoadmaps] = useState<Roadmap[]>([]);
  const [selectedRoadmapId, setSelectedRoadmapId] = useState<number | null>(null);
  const [roadmapDetail, setRoadmapDetail] = useState<RoadmapDetail | null>(null);
  const [progress, setProgress] = useState<RoadmapProgress | null>(null);
  const [momentum, setMomentum] = useState<RoadmapMomentum | null>(null);

  const [selectedDay, setSelectedDay] = useState<Day | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isHistoryModalOpen, setIsHistoryModalOpen] = useState(false);
  const [updatingTaskIds, setUpdatingTaskIds] = useState<number[]>([]);

  // Load all roadmaps and initial selected roadmap
  const loadRoadmaps = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      const data = await listRoadmaps(DEV_USER.id);
      setRoadmaps(data);

      if (data.length > 0) {
        const primaryId = data[0].id;
        setSelectedRoadmapId(primaryId);

        const [detailData, progressData, momentumData] = await Promise.all([
          getRoadmapDetails(primaryId),
          getRoadmapProgress(primaryId),
          getRoadmapMomentum(primaryId).catch(() => null),
        ]);

        setRoadmapDetail(detailData);
        setProgress(progressData);
        setMomentum(momentumData);
      } else {
        setSelectedRoadmapId(null);
        setRoadmapDetail(null);
        setProgress(null);
        setMomentum(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load roadmap';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadRoadmaps();
  }, [loadRoadmaps]);

  // Load details when switching roadmap
  const handleSelectRoadmap = async (id: number) => {
    try {
      setSelectedRoadmapId(id);
      setIsLoading(true);
      const [detailData, progressData, momentumData] = await Promise.all([
        getRoadmapDetails(id),
        getRoadmapProgress(id),
        getRoadmapMomentum(id).catch(() => null),
      ]);
      setRoadmapDetail(detailData);
      setProgress(progressData);
      setMomentum(momentumData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load roadmap details';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  };

  // Jump smoothly to current day
  const handleJumpToCurrentDay = () => {
    if (currentDayRef.current) {
      currentDayRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  // Open day detail modal
  const handleOpenDayModal = (day: Day) => {
    setSelectedDay(day);
    setIsModalOpen(true);
  };

  const handleCloseDayModal = () => {
    setIsModalOpen(false);
    setSelectedDay(null);
  };

  // Toggle task completion (used by both inline current day card and modal)
  const handleToggleTask = async (taskId: number, currentStatus: string) => {
    if (!selectedRoadmapId) return;

    setUpdatingTaskIds((prev) => [...prev, taskId]);

    try {
      if (currentStatus === 'COMPLETED') {
        await uncompleteTask(taskId);
        toast.info('Task marked incomplete.');
      } else {
        await completeTask(taskId);
      }

      // Reload fresh authoritative details, progress, and momentum from backend
      const [updatedDetail, updatedProgress, updatedMomentum] = await Promise.all([
        getRoadmapDetails(selectedRoadmapId),
        getRoadmapProgress(selectedRoadmapId),
        getRoadmapMomentum(selectedRoadmapId).catch(() => null),
      ]);

      setRoadmapDetail(updatedDetail);
      setProgress(updatedProgress);
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

      // Also update currently inspected day inside modal if open
      if (selectedDay) {
        const freshDay = updatedDetail.days.find((d) => d.id === selectedDay.id);
        if (freshDay) {
          setSelectedDay(freshDay);
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

  // Layout-stable skeleton loading state
  if (isLoading && !roadmapDetail) {
    return (
      <div className="container">
        <RoadmapSkeleton />
      </div>
    );
  }

  if (error) {
    return (
      <div className="container">
        <ErrorBanner message={error} onRetry={loadRoadmaps} />
      </div>
    );
  }

  // Empty state when user has no roadmaps (Part 6)
  if (!roadmapDetail || roadmaps.length === 0) {
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

  const days = [...roadmapDetail.days].sort((a, b) => a.day_number - b.day_number);
  const remainingDays = progress ? Math.max(0, progress.total_days - progress.completed_days) : 0;

  return (
    <div className="container">
      {/* Top Header Card */}
      <Card padding="lg" className={styles.headerCard}>
        <div className={styles.headerTop}>
          <div className={styles.titleGroup}>
            <div className={styles.tagRow}>
              <span className={styles.roadmapTag}>Level Map</span>
              <Badge
                variant={progress?.is_completed ? 'completed' : 'current'}
                dot
              >
                {progress?.is_completed ? 'Completed' : 'Active Plan'}
              </Badge>
            </div>
            <h1 className={styles.roadmapTitle}>{roadmapDetail.title}</h1>
            {roadmapDetail.description && (
              <p className={styles.roadmapDesc}>{roadmapDetail.description}</p>
            )}
          </div>

          {/* Action & Switcher Controls */}
          <div className={styles.headerActions}>
            {roadmaps.length > 1 && (
              <div className={styles.switcher}>
                <label htmlFor="roadmap-select" className={styles.switcherLabel}>
                  Switch Plan:
                </label>
                <select
                  id="roadmap-select"
                  className={styles.selectInput}
                  value={selectedRoadmapId || ''}
                  onChange={(e) => handleSelectRoadmap(Number(e.target.value))}
                >
                  {roadmaps.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.title} ({r.target_duration_days}d)
                    </option>
                  ))}
                </select>
              </div>
            )}

            <Button
              variant="secondary"
              size="sm"
              onClick={handleJumpToCurrentDay}
              leftIcon={<Compass size={14} />}
              title="Scroll directly to today's active level"
            >
              Jump to Current Day
            </Button>

            <Button
              variant="secondary"
              size="sm"
              onClick={() => setIsHistoryModalOpen(true)}
              leftIcon={<History size={14} />}
              title="View chronological roadmap change timeline"
            >
              History
            </Button>
          </div>
        </div>

        {/* Big Motivating Progress Section */}
        <div className={styles.progressCard}>
          <div className={styles.progressMetrics}>
            <div className={styles.percentDisplay}>
              <span className={styles.percentNumber}>
                {progress ? Math.round(progress.progress_percentage) : 0}%
              </span>
              <span className={styles.percentLabel}>Completed</span>
            </div>

            <div className={styles.statCounters}>
              <div className={styles.statBox}>
                <span className={styles.statValue}>
                  {progress ? progress.completed_days : 0} / {progress ? progress.total_days : 0}
                </span>
                <span className={styles.statLabel}>Days Finished</span>
              </div>
              <div className={styles.statBox}>
                <span className={styles.statValue}>{remainingDays}</span>
                <span className={styles.statLabel}>Days Remaining</span>
              </div>
            </div>
          </div>

          <div className={styles.progressBarWrapper}>
            <ProgressBar
              percentage={progress ? progress.progress_percentage : 0}
              size="lg"
              variant={progress?.is_completed ? 'success' : 'primary'}
            />
          </div>

          <div className={styles.metaRow}>
            <span className={styles.metaItem}>
              <Calendar size={13} />
              <span>Created {formatDate(roadmapDetail.created_at)}</span>
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadRoadmaps}
              leftIcon={<RefreshCw size={13} />}
            >
              Refresh
            </Button>
          </div>
        </div>
      </Card>

      {/* Roadmap Completion Experience (Part 14) */}
      {progress?.is_completed && (
        <section aria-label="Roadmap Complete" className={styles.roadmapCompletionHero}>
          <div className={styles.completionLeft}>
            <CheckCircle2 size={28} className={styles.completionIcon} />
            <div className={styles.completionText}>
              <h2 className={styles.completionTitle}>Roadmap complete</h2>
              <p className={styles.completionDesc}>You finished everything you planned.</p>
            </div>
          </div>

          <div className={styles.completionActions}>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                document.getElementById('progression-section')?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              Review Roadmap
            </Button>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                document.getElementById('momentum-section')?.scrollIntoView({ behavior: 'smooth' });
              }}
            >
              View Progress
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={() => navigate('/create')}
              leftIcon={<PlusCircle size={14} />}
            >
              Start a New Roadmap
            </Button>
          </div>
        </section>
      )}

      {/* Progress & Momentum Section */}
      <div id="momentum-section">
        {momentum && <RoadmapMomentumSection momentum={momentum} />}
      </div>

      {/* Progression Section */}
      <div id="progression-section" className={styles.progressionSection}>
        <div className={styles.progressionHeader}>
          <h2 className={styles.progressionTitle}>Level Progression</h2>
          <p className={styles.progressionSub}>
            Complete today’s active tasks below to advance to your next milestone.
          </p>
        </div>

        {/* Vertical Level Progression Path */}
        <div className={styles.nodesList}>
          {days.map((day, index) => {
            const isLast = index === days.length - 1;
            const isCurrent =
              progress?.first_incomplete_day === day.day_number || day.status === 'CURRENT';

            const nextDay = !isLast ? days[index + 1] : null;
            const nextIsCurrent =
              nextDay &&
              (progress?.first_incomplete_day === nextDay.day_number || nextDay.status === 'CURRENT');

            return (
              <React.Fragment key={day.id}>
                <RoadmapNode
                  day={day}
                  onClick={() => handleOpenDayModal(day)}
                  isCurrent={isCurrent}
                  onToggleTask={handleToggleTask}
                  updatingTaskIds={updatingTaskIds}
                  nodeRef={isCurrent ? currentDayRef : undefined}
                />
                {!isLast && (
                  <RoadmapPath
                    isCompleted={day.status === 'COMPLETED'}
                    isActive={day.status === 'COMPLETED' && Boolean(nextIsCurrent)}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Day Detail Modal */}
      <DayDetailModal
        day={selectedDay}
        isOpen={isModalOpen}
        onClose={handleCloseDayModal}
        onToggleTask={handleToggleTask}
        updatingTaskIds={updatingTaskIds}
      />

      {/* Roadmap History Timeline Modal */}
      <RoadmapHistoryModal
        roadmapId={selectedRoadmapId}
        roadmapTitle={roadmapDetail.title}
        isOpen={isHistoryModalOpen}
        onClose={() => setIsHistoryModalOpen(false)}
      />
    </div>
  );
};
