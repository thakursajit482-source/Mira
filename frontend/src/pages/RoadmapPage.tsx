import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sparkles, PlusCircle, Calendar, RefreshCw } from 'lucide-react';
import { listRoadmaps, getRoadmapDetails, getRoadmapProgress } from '../api/roadmaps';
import { completeTask, uncompleteTask } from '../api/tasks';
import { Roadmap, RoadmapDetail, RoadmapProgress, Day } from '../types';
import { DEV_USER } from '../utils/devUser';
import { formatDate } from '../utils/formatters';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { ProgressBar } from '../components/common/ProgressBar';
import { LoadingSpinner } from '../components/common/LoadingSpinner';
import { EmptyState } from '../components/common/EmptyState';
import { ErrorBanner } from '../components/common/ErrorBanner';
import { RoadmapNode } from '../components/roadmap/RoadmapNode';
import { RoadmapPath } from '../components/roadmap/RoadmapPath';
import { DayDetailModal } from '../components/roadmap/DayDetailModal';
import styles from './RoadmapPage.module.css';

export const RoadmapPage: React.FC = () => {
  const navigate = useNavigate();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [roadmaps, setRoadmaps] = useState<Roadmap[]>([]);
  const [selectedRoadmapId, setSelectedRoadmapId] = useState<number | null>(null);
  const [roadmapDetail, setRoadmapDetail] = useState<RoadmapDetail | null>(null);
  const [progress, setProgress] = useState<RoadmapProgress | null>(null);

  const [selectedDay, setSelectedDay] = useState<Day | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
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

        const [detailData, progressData] = await Promise.all([
          getRoadmapDetails(primaryId),
          getRoadmapProgress(primaryId),
        ]);

        setRoadmapDetail(detailData);
        setProgress(progressData);
      } else {
        setSelectedRoadmapId(null);
        setRoadmapDetail(null);
        setProgress(null);
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
      const [detailData, progressData] = await Promise.all([
        getRoadmapDetails(id),
        getRoadmapProgress(id),
      ]);
      setRoadmapDetail(detailData);
      setProgress(progressData);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load roadmap details';
      setError(msg);
    } finally {
      setIsLoading(false);
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

  // Toggle task completion
  const handleToggleTask = async (taskId: number, currentStatus: string) => {
    if (!selectedRoadmapId) return;

    setUpdatingTaskIds((prev) => [...prev, taskId]);

    try {
      if (currentStatus === 'COMPLETED') {
        await uncompleteTask(taskId);
      } else {
        await completeTask(taskId);
      }

      // Reload fresh authoritative details and progress from backend
      const [updatedDetail, updatedProgress] = await Promise.all([
        getRoadmapDetails(selectedRoadmapId),
        getRoadmapProgress(selectedRoadmapId),
      ]);

      setRoadmapDetail(updatedDetail);
      setProgress(updatedProgress);

      // Also update currently inspected day inside modal
      if (selectedDay) {
        const freshDay = updatedDetail.days.find((d) => d.id === selectedDay.id);
        if (freshDay) {
          setSelectedDay(freshDay);
        }
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update task status';
      setError(msg);
    } finally {
      setUpdatingTaskIds((prev) => prev.filter((id) => id !== taskId));
    }
  };

  if (isLoading && !roadmapDetail) {
    return <LoadingSpinner label="Loading roadmap progression..." fullPage />;
  }

  if (error) {
    return (
      <div className="container">
        <ErrorBanner message={error} onRetry={loadRoadmaps} />
      </div>
    );
  }

  if (!roadmapDetail || roadmaps.length === 0) {
    return (
      <div className="container">
        <EmptyState
          icon={<Sparkles size={28} />}
          title="No Roadmaps Found"
          description="You do not have any learning roadmaps yet. Generate your first structured roadmap to begin your journey."
          actionLabel="Generate Roadmap"
          onAction={() => navigate('/create')}
          actionIcon={<PlusCircle size={18} />}
        />
      </div>
    );
  }

  const days = [...roadmapDetail.days].sort((a, b) => a.day_number - b.day_number);

  return (
    <div className="container">
      {/* Top Header Card */}
      <Card padding="lg" className={styles.headerCard}>
        <div className={styles.headerTop}>
          <div className={styles.titleGroup}>
            <div className={styles.tagRow}>
              <span className={styles.roadmapTag}>Level Map</span>
              <Badge variant="current" dot>
                {progress?.is_completed ? 'Finished' : 'In Progress'}
              </Badge>
            </div>
            <h1 className={styles.roadmapTitle}>{roadmapDetail.title}</h1>
            <p className={styles.roadmapDesc}>{roadmapDetail.description}</p>
          </div>

          {/* Roadmap switcher if user has multiple */}
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
        </div>

        {/* Progress & Meta */}
        <div className={styles.headerBottom}>
          <div className={styles.progressArea}>
            {progress && (
              <ProgressBar
                percentage={progress.progress_percentage}
                label={`${progress.completed_days} of ${progress.total_days} Days Completed`}
                size="md"
                variant={progress.is_completed ? 'success' : 'primary'}
              />
            )}
          </div>

          <div className={styles.metaRow}>
            <span className={styles.metaItem}>
              <Calendar size={14} />
              <span>Created {formatDate(roadmapDetail.created_at)}</span>
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadRoadmaps}
              leftIcon={<RefreshCw size={14} />}
            >
              Refresh
            </Button>
          </div>
        </div>
      </Card>

      {/* Progression Section */}
      <div className={styles.progressionSection}>
        <div className={styles.progressionHeader}>
          <h2 className={styles.progressionTitle}>Level Progression</h2>
          <p className={styles.progressionSub}>
            Click any level node to view daily tasks and track progress.
          </p>
        </div>

        {/* Vertical Nodes List */}
        <div className={styles.nodesList}>
          {days.map((day, index) => {
            const isLast = index === days.length - 1;
            const isCurrent =
              progress?.first_incomplete_day === day.day_number || day.status === 'CURRENT';

            return (
              <React.Fragment key={day.id}>
                <RoadmapNode
                  day={day}
                  onClick={() => handleOpenDayModal(day)}
                  isCurrent={isCurrent}
                />
                {!isLast && (
                  <RoadmapPath
                    isCompleted={day.status === 'COMPLETED'}
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
    </div>
  );
};
