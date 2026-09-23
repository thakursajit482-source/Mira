import React from 'react';
import { Check, Lock, Play, Sparkles, AlertTriangle, SkipForward, Clock, ExternalLink } from 'lucide-react';
import { Day } from '../../types';
import { Badge } from '../common/Badge';
import { TaskList } from '../task/TaskList';
import { formatMinutes } from '../../utils/formatters';
import styles from './RoadmapNode.module.css';

export interface RoadmapNodeProps {
  day: Day;
  onClick: () => void;
  isCurrent?: boolean;
  onToggleTask?: (taskId: number, currentStatus: string) => void;
  updatingTaskIds?: number[];
  nodeRef?: React.Ref<HTMLDivElement>;
}

export const RoadmapNode: React.FC<RoadmapNodeProps> = ({
  day,
  onClick,
  isCurrent = false,
  onToggleTask,
  updatingTaskIds = [],
  nodeRef,
}) => {
  const isCompleted = day.status === 'COMPLETED';
  const isInProgress = day.status === 'IN_PROGRESS';
  const isAtRisk = day.status === 'AT_RISK';
  const isSkipped = day.status === 'SKIPPED';
  const isLocked = day.status === 'LOCKED';
  const isEffectivelyCurrent = isCurrent || day.status === 'CURRENT';

  const tasks = day.tasks || [];
  const completedTasksCount = tasks.filter((t) => t.status === 'COMPLETED').length;
  const totalMinutes = tasks.reduce((acc, t) => acc + t.estimated_minutes, 0);

  // Status-specific node marker icon
  const renderMarkerIcon = () => {
    if (isCompleted) {
      return <Check size={18} className={styles.iconCheck} />;
    }
    if (isEffectivelyCurrent) {
      return <Sparkles size={18} className={styles.iconSparkle} />;
    }
    if (isAtRisk) {
      return <AlertTriangle size={16} className={styles.iconAtRisk} />;
    }
    if (isSkipped) {
      return <SkipForward size={16} className={styles.iconSkipped} />;
    }
    if (isInProgress) {
      return <Play size={16} className={styles.iconPlay} />;
    }
    return <Lock size={16} className={styles.iconLock} />;
  };

  const getStatusBadge = () => {
    if (isCompleted) {
      return <Badge variant="completed" size="sm" dot>Completed</Badge>;
    }
    if (isEffectivelyCurrent) {
      return <Badge variant="current" size="sm" dot>Current Level</Badge>;
    }
    if (isAtRisk) {
      return <Badge variant="at-risk" size="sm" dot>At Risk</Badge>;
    }
    if (isSkipped) {
      return <Badge variant="skipped" size="sm">Skipped</Badge>;
    }
    if (isInProgress) {
      return <Badge variant="in-progress" size="sm" dot>In Progress</Badge>;
    }
    return <Badge variant="locked" size="sm">Locked</Badge>;
  };

  const getMarkerStatusClass = () => {
    if (isCompleted) return styles.markerCompleted;
    if (isEffectivelyCurrent) return styles.markerCurrent;
    if (isAtRisk) return styles.markerAtRisk;
    if (isSkipped) return styles.markerSkipped;
    if (isInProgress) return styles.markerInProgress;
    return styles.markerLocked;
  };

  // If this is the CURRENT day, render the featured active card with inline tasks!
  if (isEffectivelyCurrent) {
    return (
      <div
        ref={nodeRef}
        className={`${styles.container} ${styles.currentContainer}`}
        id={`day-node-${day.day_number}`}
      >
        {/* Visual Level Marker */}
        <div className={`${styles.marker} ${getMarkerStatusClass()}`} aria-hidden="true">
          {renderMarkerIcon()}
        </div>

        {/* Featured Active Card */}
        <div className={`${styles.card} ${styles.cardCurrent}`}>
          <div className={styles.activeHeader}>
            <div className={styles.titleArea}>
              <div className={styles.tagRow}>
                <span className={styles.levelTag}>Day {day.day_number}</span>
                {getStatusBadge()}
              </div>
              <h3 className={styles.activeDayTitle}>{day.title || `Day ${day.day_number}`}</h3>
            </div>

            <button
              type="button"
              className={styles.inspectButton}
              onClick={onClick}
              title="Open full day details"
              aria-label={`View details for Day ${day.day_number}`}
            >
              <span>Details</span>
              <ExternalLink size={14} />
            </button>
          </div>

          <div className={styles.activeMeta}>
            {totalMinutes > 0 && (
              <span className={styles.activeMetaItem}>
                <Clock size={13} />
                <span>Estimated: {formatMinutes(totalMinutes)}</span>
              </span>
            )}
            <span className={styles.activeMetaItem}>
              <strong>{completedTasksCount}</strong> of <strong>{tasks.length}</strong> tasks completed
            </span>
          </div>

          {/* Inline Active Task List */}
          <div className={styles.activeTasksWrapper}>
            {tasks.length > 0 && onToggleTask ? (
              <TaskList
                tasks={tasks}
                onToggleTask={onToggleTask}
                updatingTaskIds={updatingTaskIds}
                showSummary={false}
              />
            ) : (
              <p className={styles.noTasks}>No tasks assigned for today.</p>
            )}
          </div>
        </div>
      </div>
    );
  }

  // Compact Level Node for Completed, Locked, or other days
  return (
    <div
      ref={nodeRef}
      className={`${styles.container} ${isCompleted ? styles.completedContainer : ''} ${
        isLocked ? styles.lockedContainer : ''
      }`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      id={`day-node-${day.day_number}`}
      aria-label={`Day ${day.day_number}: ${day.title || `Day ${day.day_number}`}, ${day.status}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
    >
      {/* Visual Level Marker */}
      <div className={`${styles.marker} ${getMarkerStatusClass()}`} aria-hidden="true">
        {renderMarkerIcon()}
      </div>

      {/* Compact Content Card */}
      <div
        className={`${styles.card} ${
          isCompleted
            ? styles.cardCompleted
            : isAtRisk
            ? styles.cardAtRisk
            : isSkipped
            ? styles.cardSkipped
            : isInProgress
            ? styles.cardInProgress
            : styles.cardLocked
        }`}
      >
        <div className={styles.compactHeader}>
          <div className={styles.compactTitleArea}>
            <span className={styles.compactLevelTag}>Day {day.day_number}</span>
            <h4 className={styles.compactDayTitle}>{day.title || `Day ${day.day_number}`}</h4>
          </div>
          <div className={styles.compactBadgeArea}>{getStatusBadge()}</div>
        </div>

        <div className={styles.compactFooter}>
          <span className={styles.compactTaskCount}>
            {tasks.length > 0 ? (
              <>
                <strong>{completedTasksCount}</strong>/{tasks.length} tasks
              </>
            ) : (
              '0 tasks'
            )}
          </span>
          {totalMinutes > 0 && (
            <span className={styles.compactDuration}>{formatMinutes(totalMinutes)}</span>
          )}
        </div>
      </div>
    </div>
  );
};
