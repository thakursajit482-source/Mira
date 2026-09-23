import React from 'react';
import styles from './Skeleton.module.css';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: string | number;
  height?: string | number;
  borderRadius?: string | number;
  circle?: boolean;
}

export const Skeleton: React.FC<SkeletonProps> = ({
  width,
  height = '1rem',
  borderRadius,
  circle = false,
  className = '',
  style,
  ...props
}) => {
  const customStyle: React.CSSProperties = {
    width: typeof width === 'number' ? `${width}px` : width,
    height: typeof height === 'number' ? `${height}px` : height,
    borderRadius: circle ? '50%' : typeof borderRadius === 'number' ? `${borderRadius}px` : borderRadius,
    ...style,
  };

  return (
    <div
      className={`${styles.skeleton} ${circle ? styles.circle : ''} ${className}`}
      style={customStyle}
      aria-hidden="true"
      {...props}
    />
  );
};

export const RoadmapSkeleton: React.FC = () => {
  return (
    <div className={styles.roadmapSkeleton} aria-label="Loading roadmap content" role="status">
      {/* Header Skeleton */}
      <div className={styles.headerSkeleton}>
        <Skeleton width="180px" height="14px" />
        <Skeleton width="65%" height="32px" />
        <Skeleton width="45%" height="18px" />
      </div>

      {/* Progress Card Skeleton */}
      <div className={styles.progressCardSkeleton}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Skeleton width="120px" height="16px" />
          <Skeleton width="45px" height="24px" />
        </div>
        <Skeleton width="100%" height="10px" borderRadius="999px" />
        <Skeleton width="140px" height="14px" />
      </div>

      {/* Nodes Container Skeleton */}
      <div className={styles.nodesContainerSkeleton}>
        {/* Completed node skeleton */}
        <div className={styles.nodeSkeletonItem}>
          <Skeleton width="48px" height="48px" circle />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Skeleton width="160px" height="18px" />
            <Skeleton width="90px" height="12px" />
          </div>
          <Skeleton width="80px" height="24px" borderRadius="12px" />
        </div>

        {/* Featured CURRENT node skeleton */}
        <div className={styles.featuredNodeSkeleton}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <Skeleton width="48px" height="48px" circle />
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <Skeleton width="180px" height="20px" />
                <Skeleton width="100px" height="14px" />
              </div>
            </div>
            <Skeleton width="110px" height="26px" borderRadius="14px" />
          </div>

          <div className={styles.taskPlaceholders}>
            <Skeleton width="100%" height="44px" borderRadius="8px" />
            <Skeleton width="100%" height="44px" borderRadius="8px" />
            <Skeleton width="100%" height="44px" borderRadius="8px" />
          </div>
        </div>

        {/* Locked node skeleton */}
        <div className={styles.nodeSkeletonItem}>
          <Skeleton width="48px" height="48px" circle />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Skeleton width="150px" height="18px" />
            <Skeleton width="80px" height="12px" />
          </div>
          <Skeleton width="70px" height="24px" borderRadius="12px" />
        </div>

        {/* Locked node skeleton 2 */}
        <div className={styles.nodeSkeletonItem}>
          <Skeleton width="48px" height="48px" circle />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
            <Skeleton width="170px" height="18px" />
            <Skeleton width="85px" height="12px" />
          </div>
          <Skeleton width="70px" height="24px" borderRadius="12px" />
        </div>
      </div>
    </div>
  );
};
