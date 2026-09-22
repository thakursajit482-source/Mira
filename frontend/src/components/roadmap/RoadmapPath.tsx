import React from 'react';
import styles from './RoadmapPath.module.css';

export interface RoadmapPathProps {
  isCompleted?: boolean;
}

export const RoadmapPath: React.FC<RoadmapPathProps> = ({ isCompleted = false }) => {
  return (
    <div className={styles.container}>
      <div className={`${styles.line} ${isCompleted ? styles.lineCompleted : ''}`} />
    </div>
  );
};
