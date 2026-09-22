import React, { useState } from 'react';
import { Check, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { Task } from '../../types';
import { formatMinutes } from '../../utils/formatters';
import styles from './TaskItem.module.css';

export interface TaskItemProps {
  task: Task;
  onToggle: (taskId: number, currentStatus: string) => void;
  isUpdating?: boolean;
}

export const TaskItem: React.FC<TaskItemProps> = ({
  task,
  onToggle,
  isUpdating = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const isCompleted = task.status === 'COMPLETED';

  const handleCheckboxClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isUpdating) return;
    onToggle(task.id, task.status);
  };

  const toggleExpand = () => {
    if (task.description) {
      setIsExpanded((prev) => !prev);
    }
  };

  return (
    <div
      className={`${styles.container} ${isCompleted ? styles.completed : ''} ${
        isUpdating ? styles.updating : ''
      }`}
      onClick={toggleExpand}
    >
      <div className={styles.mainRow}>
        {/* Custom Checkbox */}
        <button
          type="button"
          className={`${styles.checkbox} ${isCompleted ? styles.checkboxChecked : ''}`}
          onClick={handleCheckboxClick}
          disabled={isUpdating}
          aria-label={isCompleted ? `Mark ${task.title} as incomplete` : `Mark ${task.title} as complete`}
          aria-checked={isCompleted}
          role="checkbox"
        >
          {isCompleted && <Check size={14} className={styles.checkIcon} />}
        </button>

        {/* Task Title & Details */}
        <div className={styles.content}>
          <div className={styles.header}>
            <span className={`${styles.title} ${isCompleted ? styles.titleCompleted : ''}`}>
              {task.title}
            </span>
          </div>

          <div className={styles.meta}>
            <span className={styles.timeBadge}>
              <Clock size={12} />
              <span>{formatMinutes(task.estimated_minutes)}</span>
            </span>

            {task.description && (
              <span className={styles.expandHint}>
                {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                <span>{isExpanded ? 'Hide info' : 'Details'}</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Expanded Description */}
      {isExpanded && task.description && (
        <div className={styles.descriptionRow}>
          <p className={styles.descriptionText}>{task.description}</p>
        </div>
      )}
    </div>
  );
};
