import React from 'react';
import styles from './RoadmapPath.module.css';

export interface RoadmapPathProps {
  isCompleted?: boolean;
  isActive?: boolean;
}

export const RoadmapPath: React.FC<RoadmapPathProps> = ({
  isCompleted = false,
  isActive = false,
}) => {
  return (
    <div className={styles.container} aria-hidden="true">
      <div
        className={`${styles.line} ${
          isCompleted
            ? styles.lineCompleted
            : isActive
            ? styles.lineActive
            : ''
        }`}
      />
    </div>
  );
};
