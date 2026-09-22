import React from 'react';
import styles from './ProgressBar.module.css';

export interface ProgressBarProps {
  percentage: number;
  label?: string;
  showPercentage?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'primary' | 'success';
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  percentage,
  label,
  showPercentage = true,
  size = 'md',
  variant = 'primary',
}) => {
  const clampedPercentage = Math.min(Math.max(Math.round(percentage), 0), 100);

  return (
    <div className={styles.wrapper}>
      {(label || showPercentage) && (
        <div className={styles.header}>
          {label && <span className={styles.label}>{label}</span>}
          {showPercentage && <span className={styles.percentage}>{clampedPercentage}%</span>}
        </div>
      )}
      <div
        className={`${styles.track} ${styles[size]}`}
        role="progressbar"
        aria-valuenow={clampedPercentage}
        aria-valuemin={0}
        aria-valuemax={100}
      >
        <div
          className={`${styles.fill} ${styles[variant]}`}
          style={{ width: `${clampedPercentage}%` }}
        />
      </div>
    </div>
  );
};
