import React from 'react';
import styles from './Badge.module.css';

export type BadgeVariant =
  | 'completed'
  | 'current'
  | 'in-progress'
  | 'locked'
  | 'neutral'
  | 'danger';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: 'sm' | 'md';
  dot?: boolean;
}

export const Badge: React.FC<BadgeProps> = ({
  children,
  variant = 'neutral',
  size = 'md',
  dot = false,
  className = '',
  ...props
}) => {
  return (
    <span
      className={`${styles.badge} ${styles[variant]} ${styles[size]} ${className}`}
      {...props}
    >
      {dot && <span className={styles.dot} aria-hidden="true" />}
      <span>{children}</span>
    </span>
  );
};
