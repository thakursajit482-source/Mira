import React, { useEffect } from 'react';
import { X, Calendar, Clock } from 'lucide-react';
import { Day } from '../../types';
import { Badge } from '../common/Badge';
import { TaskList } from '../task/TaskList';
import { formatMinutes, formatDate } from '../../utils/formatters';
import styles from './DayDetailModal.module.css';

export interface DayDetailModalProps {
  day: Day | null;
  isOpen: boolean;
  onClose: () => void;
  onToggleTask: (taskId: number, currentStatus: string) => void;
  updatingTaskIds?: number[];
}

export const DayDetailModal: React.FC<DayDetailModalProps> = ({
  day,
  isOpen,
  onClose,
  onToggleTask,
  updatingTaskIds = [],
}) => {
  // Close on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll when modal is open
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen || !day) return null;

  const tasks = day.tasks || [];
  const totalMinutes = tasks.reduce((sum, t) => sum + t.estimated_minutes, 0);

  const getStatusBadge = () => {
    switch (day.status) {
      case 'COMPLETED':
        return <Badge variant="completed" dot>Completed</Badge>;
      case 'CURRENT':
        return <Badge variant="current" dot>Current Level</Badge>;
      case 'IN_PROGRESS':
        return <Badge variant="in-progress" dot>In Progress</Badge>;
      case 'LOCKED':
        return <Badge variant="locked">Locked</Badge>;
      default:
        return null;
    }
  };

  return (
    <div className={styles.overlay} onClick={onClose} role="dialog" aria-modal="true">
      <div
        className={styles.modal}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerContent}>
            <div className={styles.tagArea}>
              <span className={styles.levelTag}>Day {day.day_number}</span>
              {getStatusBadge()}
            </div>
            <h2 className={styles.title}>{day.title || `Day ${day.day_number}`}</h2>
            <div className={styles.meta}>
              <span className={styles.metaItem}>
                <Clock size={14} />
                <span>Total: {formatMinutes(totalMinutes)}</span>
              </span>
              {day.completed_at && (
                <span className={styles.metaItem}>
                  <Calendar size={14} />
                  <span>Completed {formatDate(day.completed_at)}</span>
                </span>
              )}
            </div>
          </div>

          <button
            className={styles.closeButton}
            onClick={onClose}
            aria-label="Close modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body / Tasks */}
        <div className={styles.body}>
          <h3 className={styles.sectionTitle}>Daily Tasks</h3>
          <TaskList
            tasks={tasks}
            onToggleTask={onToggleTask}
            updatingTaskIds={updatingTaskIds}
            showSummary={true}
          />
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button className={styles.doneButton} onClick={onClose}>
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
