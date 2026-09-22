import React from 'react';
import { Check, Lock, Play, Sparkles } from 'lucide-react';
import { Day } from '../../types';
import { Badge } from '../common/Badge';
import { formatMinutes } from '../../utils/formatters';
import styles from './RoadmapNode.module.css';

export interface RoadmapNodeProps {
  day: Day;
  onClick: () => void;
  isCurrent?: boolean;
}

export const RoadmapNode: React.FC<RoadmapNodeProps> = ({
  day,
  onClick,
  isCurrent = false,
}) => {
  const isCompleted = day.status === 'COMPLETED';
  const isInProgress = day.status === 'IN_PROGRESS';
  const isEffectivelyCurrent = isCurrent || day.status === 'CURRENT';

  const tasks = day.tasks || [];
  const completedTasksCount = tasks.filter((t) => t.status === 'COMPLETED').length;
  const totalMinutes = tasks.reduce((acc, t) => acc + t.estimated_minutes, 0);

  // Status-specific node icon
  const renderIcon = () => {
    if (isCompleted) {
      return <Check size={18} className={styles.iconCheck} />;
    }
    if (isEffectivelyCurrent) {
      return <Sparkles size={18} className={styles.iconSparkle} />;
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
    if (isInProgress) {
      return <Badge variant="in-progress" size="sm" dot>In Progress</Badge>;
    }
    return <Badge variant="locked" size="sm">Locked</Badge>;
  };

  return (
    <div
      className={`${styles.container} ${isEffectivelyCurrent ? styles.currentContainer : ''}`}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick();
        }
      }}
    >
      {/* Visual Level Marker */}
      <div
        className={`${styles.marker} ${
          isCompleted
            ? styles.markerCompleted
            : isEffectivelyCurrent
            ? styles.markerCurrent
            : isInProgress
            ? styles.markerInProgress
            : styles.markerLocked
        }`}
      >
        {renderIcon()}
      </div>

      {/* Content Card */}
      <div
        className={`${styles.card} ${
          isCompleted
            ? styles.cardCompleted
            : isEffectivelyCurrent
            ? styles.cardCurrent
            : isInProgress
            ? styles.cardInProgress
            : styles.cardLocked
        }`}
      >
        <div className={styles.header}>
          <div className={styles.titleArea}>
            <span className={styles.levelTag}>Day {day.day_number}</span>
            <h4 className={styles.dayTitle}>{day.title || `Day ${day.day_number}`}</h4>
          </div>
          <div className={styles.badgeArea}>{getStatusBadge()}</div>
        </div>

        {/* Task summary */}
        <div className={styles.footer}>
          <span className={styles.taskCount}>
            {tasks.length > 0 ? (
              <>
                <strong>{completedTasksCount}</strong>/{tasks.length} tasks
              </>
            ) : (
              '0 tasks'
            )}
          </span>
          {totalMinutes > 0 && (
            <span className={styles.duration}>{formatMinutes(totalMinutes)}</span>
          )}
        </div>
      </div>
    </div>
  );
};
