import React, { useEffect, useState, useCallback } from 'react';
import {
  X,
  History,
  Sparkles,
  PlusCircle,
  RefreshCw,
  FileEdit,
  Clock,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { RoadmapChange } from '../../types';
import { getRoadmapHistory } from '../../api/roadmaps';
import {
  formatRelativeTime,
  getChangeTypeConfig,
  getStructuredChangeMetrics,
} from '../../utils/formatters';
import { Badge } from '../common/Badge';
import { EmptyState } from '../common/EmptyState';
import { ErrorBanner } from '../common/ErrorBanner';
import { HistoryTimelineSkeleton } from '../common/Skeleton';
import styles from './RoadmapHistoryModal.module.css';

export interface RoadmapHistoryModalProps {
  roadmapId: number | null;
  roadmapTitle?: string;
  isOpen: boolean;
  onClose: () => void;
}

export const RoadmapHistoryModal: React.FC<RoadmapHistoryModalProps> = ({
  roadmapId,
  roadmapTitle,
  isOpen,
  onClose,
}) => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [changes, setChanges] = useState<RoadmapChange[]>([]);
  const [expandedChangeIds, setExpandedChangeIds] = useState<number[]>([]);

  // Fetch chronological history
  const fetchHistory = useCallback(async () => {
    if (!roadmapId) return;

    try {
      setIsLoading(true);
      setError(null);
      const res = await getRoadmapHistory(roadmapId);
      setChanges(res.changes || []);
      // Expand the most recent change by default if available
      if (res.changes && res.changes.length > 0) {
        setExpandedChangeIds([res.changes[0].id]);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to load roadmap history';
      setError(msg);
    } finally {
      setIsLoading(false);
    }
  }, [roadmapId]);

  useEffect(() => {
    if (isOpen && roadmapId) {
      fetchHistory();
    }
  }, [isOpen, roadmapId, fetchHistory]);

  // Close modal on Escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // Lock body scroll while modal is open
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

  const toggleExpand = (changeId: number) => {
    setExpandedChangeIds((prev) =>
      prev.includes(changeId) ? prev.filter((id) => id !== changeId) : [...prev, changeId]
    );
  };

  const renderChangeIcon = (iconType: string) => {
    switch (iconType) {
      case 'sparkles':
        return <Sparkles size={16} />;
      case 'plus':
        return <PlusCircle size={16} />;
      case 'refresh':
        return <RefreshCw size={16} />;
      case 'edit':
        return <FileEdit size={16} />;
      case 'clock':
      default:
        return <Clock size={16} />;
    }
  };

  return (
    <div
      className={styles.overlay}
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="history-modal-title"
    >
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className={styles.header}>
          <div className={styles.headerContent}>
            <div className={styles.tagRow}>
              <span className={styles.historyTag}>Timeline</span>
              {changes.length > 0 && (
                <Badge variant="completed" dot>
                  {changes.length} {changes.length === 1 ? 'event' : 'events'}
                </Badge>
              )}
            </div>
            <h2 id="history-modal-title" className={styles.title}>
              Roadmap History
            </h2>
            {roadmapTitle && <p className={styles.subtitle}>{roadmapTitle}</p>}
          </div>

          <button
            type="button"
            className={styles.closeButton}
            onClick={onClose}
            aria-label="Close roadmap history modal"
          >
            <X size={20} />
          </button>
        </div>

        {/* Body */}
        <div className={styles.body}>
          {isLoading && <HistoryTimelineSkeleton />}

          {error && !isLoading && <ErrorBanner message={error} onRetry={fetchHistory} />}

          {!isLoading && !error && changes.length === 0 && (
            <EmptyState
              icon={<History size={32} />}
              title="No history recorded yet"
              description="Your roadmap history will appear here as you create plans, insert new topics, and reschedule tasks."
            />
          )}

          {!isLoading && !error && changes.length > 0 && (
            <div className={styles.timeline}>
              {changes.map((change, index) => {
                const config = getChangeTypeConfig(change.change_type);
                const isExpanded = expandedChangeIds.includes(change.id);
                const metrics = getStructuredChangeMetrics(change);
                const isFirst = index === 0;

                return (
                  <div key={change.id} className={styles.timelineItem}>
                    {/* Dot with appropriate change icon */}
                    <div
                      className={`${styles.timelineDot} ${
                        isFirst ? styles.active : styles.completed
                      }`}
                      aria-hidden="true"
                    >
                      {renderChangeIcon(config.iconType)}
                    </div>

                    {/* Timeline Event Card */}
                    <div className={styles.timelineCard}>
                      <div className={styles.cardTop}>
                        <div className={styles.typeBadgeGroup}>
                          <Badge variant={config.badgeVariant} dot>
                            {config.label}
                          </Badge>
                          {change.version_number && (
                            <span
                              className={styles.versionBadge}
                              title={`Roadmap snapshot version ${change.version_number}`}
                            >
                              v{change.version_number}
                            </span>
                          )}
                        </div>
                        <time className={styles.timestamp} dateTime={change.created_at}>
                          {formatRelativeTime(change.created_at)}
                        </time>
                      </div>

                      {/* Human-readable description */}
                      <p className={styles.cardDescription}>{change.description}</p>

                      {/* Detail disclosure */}
                      {metrics.length > 0 && (
                        <div>
                          <button
                            type="button"
                            className={styles.toggleDetailsButton}
                            onClick={() => toggleExpand(change.id)}
                            aria-expanded={isExpanded}
                            aria-controls={`change-details-${change.id}`}
                          >
                            <span>{isExpanded ? 'Hide details' : 'View details'}</span>
                            {isExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
                          </button>

                          {isExpanded && (
                            <div
                              id={`change-details-${change.id}`}
                              className={styles.detailsPanel}
                            >
                              <div className={styles.chipsGrid}>
                                {metrics.map((chip, chipIdx) => (
                                  <div key={chipIdx} className={styles.metricChip}>
                                    <span className={styles.chipLabel}>{chip.label}</span>
                                    <span className={styles.chipValue}>{chip.value}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className={styles.footer}>
          <button type="button" className={styles.closeFooterButton} onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
