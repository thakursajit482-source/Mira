import React, { useEffect, useState, useCallback } from 'react';
import { X, ArrowRight, AlertTriangle, Check } from 'lucide-react';
import { ReschedulePreviewResponse } from '../../types';
import { previewReschedule, applyReschedule } from '../../api/roadmaps';
import { formatMinutes } from '../../utils/formatters';
import { Badge } from '../common/Badge';
import { Button } from '../common/Button';
import { LoadingSpinner } from '../common/LoadingSpinner';
import { ErrorBanner } from '../common/ErrorBanner';
import styles from './ReschedulePreviewModal.module.css';

export interface ReschedulePreviewModalProps {
  roadmapId: number | null;
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
}

export const ReschedulePreviewModal: React.FC<ReschedulePreviewModalProps> = ({
  roadmapId,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ReschedulePreviewResponse | null>(null);

  // Fetch preview on open
  const loadPreview = useCallback(async () => {
    if (!roadmapId) return;

    try {
      setIsLoading(true);
      setError(null);
      const res = await previewReschedule(roadmapId);
      setPreview(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to preview rescheduling';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [roadmapId]);

  useEffect(() => {
    if (isOpen && roadmapId) {
      loadPreview();
    }
  }, [isOpen, roadmapId, loadPreview]);

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll
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

  if (!isOpen) return null;

  const handleConfirmReschedule = async () => {
    if (!roadmapId) return;

    try {
      setIsApplying(true);
      setError(null);
      const result = await applyReschedule(roadmapId);
      if (result.conflict) {
        setError(result.message || 'Cannot reschedule due to fixed duration constraints.');
        return;
      }
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to apply rescheduling';
      setError(msg);
    } finally {
      setIsApplying(false);
    }
  };

  return (
    <div
      className={styles.overlay}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="reschedule-modal-title"
    >
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerContent}>
            <div className={styles.tagRow}>
              <span className={styles.rescheduleTag}>Schedule Adjustment</span>
              <Badge variant="neutral" dot>
                Preview Mode
              </Badge>
            </div>
            <h2 id="reschedule-modal-title" className={styles.title}>
              Preview Lighter Schedule
            </h2>
            <p className={styles.subtitle}>
              Rebalance future incomplete tasks within your daily available time.
            </p>
          </div>

          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label="Close reschedule preview"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {isLoading && (
            <div className={styles.loadingState}>
              <LoadingSpinner size="md" />
              <span>Simulating schedule rebalance…</span>
            </div>
          )}

          {error && !isLoading && <ErrorBanner message={error} onRetry={loadPreview} />}

          {!isLoading && !error && preview && preview.conflict && (
            <div className={styles.conflictCard}>
              <div className={styles.conflictHeader}>
                <AlertTriangle size={18} />
                <span>Capacity Limit Reached</span>
              </div>
              <p className={styles.conflictText}>{preview.message}</p>
              <p className={styles.conflictText}>
                The fixed duration of {preview.target_duration_days} days cannot accommodate shifting these tasks. Consider completing today&apos;s tasks or increasing daily available time in settings.
              </p>
            </div>
          )}

          {!isLoading && !error && preview && !preview.conflict && (
            <>
              <div className={styles.summaryCard}>
                <p className={styles.summaryText}>{preview.message}</p>
                <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                  <Badge variant="current">
                    Daily Cap: {formatMinutes(preview.daily_capacity_minutes)}
                  </Badge>
                  <Badge variant="neutral">
                    {preview.task_movements.length} tasks adjusted
                  </Badge>
                </div>
              </div>

              {preview.task_movements.length > 0 ? (
                <div className={styles.movementsSection}>
                  <h3 className={styles.sectionTitle}>Proposed Task Adjustments</h3>
                  <div className={styles.movementsList}>
                    {preview.task_movements.map((move) => (
                      <div key={move.task_id} className={styles.movementItem}>
                        <div className={styles.movementLeft}>
                          <span className={styles.movementTaskTitle}>{move.task_title}</span>
                          <span className={styles.movementTaskMinutes}>
                            {formatMinutes(move.estimated_minutes)}
                          </span>
                        </div>
                        <div className={styles.movementBadge}>
                          <span>Day {move.from_day_number}</span>
                          <ArrowRight size={12} />
                          <span>Day {move.to_day_number}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <p className={styles.summaryText}>
                  Your current schedule already fits within your daily capacity. No tasks need to be moved.
                </p>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <Button variant="secondary" size="sm" onClick={onClose} disabled={isApplying}>
            Cancel
          </Button>

          {preview && !preview.conflict && preview.task_movements.length > 0 && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleConfirmReschedule}
              isLoading={isApplying}
              leftIcon={<Check size={14} />}
            >
              Confirm & Reschedule
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};
