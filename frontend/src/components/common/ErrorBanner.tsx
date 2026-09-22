import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';
import styles from './ErrorBanner.module.css';
import { Button } from './Button';

export interface ErrorBannerProps {
  message: string;
  onRetry?: () => void;
  className?: string;
}

export const ErrorBanner: React.FC<ErrorBannerProps> = ({
  message,
  onRetry,
  className = '',
}) => {
  return (
    <div className={`${styles.banner} ${className}`} role="alert">
      <div className={styles.icon}>
        <AlertCircle size={20} />
      </div>
      <div className={styles.content}>
        <p className={styles.message}>{message}</p>
      </div>
      {onRetry && (
        <Button
          size="sm"
          variant="secondary"
          onClick={onRetry}
          leftIcon={<RefreshCw size={14} />}
        >
          Retry
        </Button>
      )}
    </div>
  );
};
