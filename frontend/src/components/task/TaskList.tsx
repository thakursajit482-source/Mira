import React from 'react';
import { Task } from '../../types';
import { TaskItem } from './TaskItem';
import { formatMinutes } from '../../utils/formatters';
import styles from './TaskList.module.css';

export interface TaskListProps {
  tasks: Task[];
  onToggleTask: (taskId: number, currentStatus: string) => void;
  updatingTaskIds?: number[];
  showSummary?: boolean;
}

export const TaskList: React.FC<TaskListProps> = ({
  tasks,
  onToggleTask,
  updatingTaskIds = [],
  showSummary = true,
}) => {
  if (tasks.length === 0) {
    return (
      <div className={styles.emptyList}>
        <p>No tasks assigned for this day.</p>
      </div>
    );
  }

  const completedCount = tasks.filter((t) => t.status === 'COMPLETED').length;
  const remainingMinutes = tasks
    .filter((t) => t.status !== 'COMPLETED')
    .reduce((sum, t) => sum + t.estimated_minutes, 0);

  return (
    <div className={styles.container}>
      {showSummary && (
        <div className={styles.summaryBar}>
          <span className={styles.countText}>
            <strong>{completedCount}</strong> of <strong>{tasks.length}</strong> tasks completed
          </span>
          <span className={`${styles.remainingText} ${remainingMinutes === 0 ? styles.remainingDone : ''}`}>
            {remainingMinutes > 0 ? `${formatMinutes(remainingMinutes)} remaining` : 'All tasks done ✓'}
          </span>
        </div>
      )}

      <div className={styles.list}>
        {tasks.map((task) => (
          <TaskItem
            key={task.id}
            task={task}
            onToggle={onToggleTask}
            isUpdating={updatingTaskIds.includes(task.id)}
          />
        ))}
      </div>
    </div>
  );
};
