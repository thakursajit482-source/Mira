import React, { useEffect, useRef, useState } from 'react';
import {
  Flame,
  CheckCircle2,
  Circle,
  Sparkles,
  CheckCheck,
} from 'lucide-react';
import { RoadmapMomentum, Milestone, RecentProgressActivity } from '../../types';
import { Badge } from '../common/Badge';
import { formatMinutes, formatDate, formatRelativeTime } from '../../utils/formatters';
import { useToast } from '../../context/ToastContext';
import styles from './RoadmapMomentumSection.module.css';

interface RoadmapMomentumSectionProps {
  momentum: RoadmapMomentum;
}

export const RoadmapMomentumSection: React.FC<RoadmapMomentumSectionProps> = ({ momentum }) => {
  const { completion, tasks, time, streak, momentum: momMetrics, milestones, recent_activity } = momentum;
  const toast = useToast();
  const isInitialMount = useRef(true);
  const [newlyAchievedIds, setNewlyAchievedIds] = useState<string[]>([]);

  // Safe milestone celebration tracking (Part 4)
  useEffect(() => {
    if (!momentum.roadmap_id) return;
    const storageKey = `mira_seen_milestones_${momentum.roadmap_id}`;

    let seenIds: Set<string>;
    try {
      const stored = localStorage.getItem(storageKey);
      seenIds = stored ? new Set(JSON.parse(stored)) : new Set();
    } catch {
      seenIds = new Set();
    }

    if (isInitialMount.current) {
      isInitialMount.current = false;
      // On initial load, record currently achieved milestones into seenIds
      // so we don't spam celebrations for historic achievements
      let changed = false;
      milestones.forEach((m) => {
        if (m.achieved && !seenIds.has(m.id)) {
          seenIds.add(m.id);
          changed = true;
        }
      });
      if (changed) {
        try {
          localStorage.setItem(storageKey, JSON.stringify(Array.from(seenIds)));
        } catch {
          // ignore localStorage write errors
        }
      }
      return;
    }

    // Subsequent updates: detect new unachieved -> achieved transitions during this session!
    const newlyAchieved: Milestone[] = [];
    milestones.forEach((m) => {
      if (m.achieved && !seenIds.has(m.id)) {
        newlyAchieved.push(m);
        seenIds.add(m.id);
      }
    });

    if (newlyAchieved.length > 0) {
      newlyAchieved.forEach((m) => {
        toast.success(`Milestone Reached: ${m.title}`, m.description);
      });
      setNewlyAchievedIds((prev) => [...prev, ...newlyAchieved.map((m) => m.id)]);
      try {
        localStorage.setItem(storageKey, JSON.stringify(Array.from(seenIds)));
      } catch {
        // ignore localStorage write errors
      }
    }
  }, [momentum.roadmap_id, milestones, toast]);

  // Determine momentum badge variant
  const getMomentumBadgeVariant = (status: string) => {
    switch (status) {
      case 'COMPLETE':
        return 'completed';
      case 'BUILDING':
        return 'completed';
      case 'STEADY':
        return 'current';
      case 'SLOWING':
        return 'at-risk';
      case 'PAUSED':
      default:
        return 'neutral';
    }
  };

  const getMomentumBoxClass = (status: string) => {
    switch (status) {
      case 'COMPLETE':
        return styles.momentumStatusBoxComplete;
      case 'BUILDING':
        return styles.momentumStatusBoxBuilding;
      case 'STEADY':
        return styles.momentumStatusBoxSteady;
      case 'SLOWING':
        return styles.momentumStatusBoxSlowing;
      case 'PAUSED':
      default:
        return styles.momentumStatusBoxPaused;
    }
  };

  const getActivityIcon = (eventType: string) => {
    switch (eventType) {
      case 'DAY_COMPLETED':
        return <CheckCheck size={16} className={styles.activityIcon} />;
      case 'MILESTONE_REACHED':
        return <Sparkles size={16} className={styles.activityIcon} />;
      case 'TASK_COMPLETED':
      default:
        return <CheckCircle2 size={16} className={styles.activityIcon} />;
    }
  };

  return (
    <section aria-label="Progress and Momentum" className={styles.momentumContainer}>
      {/* Top 2-Column Grid: Progress Overview & Streak / Momentum */}
      <div className={styles.topGrid}>
        {/* Card 1: Progress Overview */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <span className={styles.cardLabel}>Roadmap Progress</span>
            <Badge variant={completion.percentage === 100 ? 'completed' : 'current'} dot>
              {completion.percentage === 100 ? 'Completed' : 'In Progress'}
            </Badge>
          </div>

          <div className={styles.progressOverviewMain}>
            <span className={styles.percentBig}>{Math.round(completion.percentage)}%</span>
            <span className={styles.percentSub}>
              {completion.completed_days} of {completion.total_days} days completed
            </span>
          </div>

          {/* Accessible horizontal progress track */}
          <div
            className={styles.progressTrack}
            role="progressbar"
            aria-valuenow={Math.round(completion.percentage)}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label="Overall roadmap completion progress"
          >
            <div
              className={styles.progressFill}
              style={{ width: `${Math.min(100, Math.max(0, completion.percentage))}%` }}
            />
          </div>

          {/* Quick Metrics Pills */}
          <div className={styles.metricsPills}>
            <div className={styles.metricPill}>
              <span className={styles.metricPillLabel}>Days</span>
              <span className={styles.metricPillVal}>
                {completion.completed_days} / {completion.total_days}
              </span>
            </div>
            <div className={styles.metricPill}>
              <span className={styles.metricPillLabel}>Tasks</span>
              <span className={styles.metricPillVal}>
                {tasks.completed_tasks} / {tasks.total_tasks}
              </span>
            </div>
            {time.total_planned_minutes !== null && (
              <div className={styles.metricPill}>
                <span className={styles.metricPillLabel}>Time</span>
                <span className={styles.metricPillVal}>
                  {formatMinutes(time.completed_minutes || 0)} / {formatMinutes(time.total_planned_minutes || 0)}
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Card 2: Momentum & Consistency */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <span className={styles.cardLabel}>Consistency & Momentum</span>
            <span className={styles.sectionSubtitle}>
              {streak.last_productive_date
                ? `Last active ${formatDate(streak.last_productive_date)}`
                : 'No activity yet'}
            </span>
          </div>

          {/* Streak highlight */}
          <div className={styles.streakBlock}>
            <div className={styles.streakIconWrapper}>
              <Flame size={22} />
            </div>
            <div className={styles.streakValueGroup}>
              <span className={styles.streakDays}>
                {streak.current_days} {streak.current_days === 1 ? 'day' : 'days'} streak
              </span>
              <span className={styles.streakBest}>
                Best streak: {streak.best_days} {streak.best_days === 1 ? 'day' : 'days'}
              </span>
            </div>
          </div>

          {/* Momentum Status Box */}
          <div className={`${styles.momentumStatusBox} ${getMomentumBoxClass(momMetrics.status)}`}>
            <div className={styles.momentumHeaderRow}>
              <span className={styles.momentumLabel}>{momMetrics.label}</span>
              <Badge variant={getMomentumBadgeVariant(momMetrics.status)} dot>
                {momMetrics.status}
              </Badge>
            </div>
            <p className={styles.momentumDesc}>{momMetrics.description}</p>
          </div>
        </div>
      </div>

      {/* Milestones Card */}
      <div className={styles.milestonesCard}>
        <div className={styles.cardHeader}>
          <span className={styles.cardLabel}>Key Milestones</span>
          <span className={styles.sectionSubtitle}>
            {milestones.filter((m) => m.achieved).length > 0
              ? `${milestones.filter((m) => m.achieved).length} of ${milestones.length} reached`
              : 'Milestones will appear as you complete your roadmap.'}
          </span>
        </div>

        <div className={styles.milestonesList}>
          {milestones.map((m: Milestone) => (
            <div
              key={m.id}
              className={`${styles.milestoneItem} ${m.achieved ? styles.milestoneItemAchieved : ''}`}
            >
              {m.achieved ? (
                <CheckCircle2 size={18} className={styles.milestoneIconAchieved} />
              ) : (
                <Circle size={18} className={styles.milestoneIconPending} />
              )}
              <div className={styles.milestoneDetails}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span className={styles.milestoneTitle}>{m.title}</span>
                  {newlyAchievedIds.includes(m.id) && (
                    <Badge variant="completed" size="sm">New</Badge>
                  )}
                </div>
                <span className={styles.milestoneDesc}>{m.description}</span>
                {m.achieved && m.achieved_at && (
                  <span className={styles.milestoneDate}>Achieved {formatDate(m.achieved_at)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Progress Activity */}
      <div className={styles.activityCard}>
        <div className={styles.cardHeader}>
          <span className={styles.cardLabel}>Recent Progress</span>
          <span className={styles.sectionSubtitle}>Latest actions</span>
        </div>

        {recent_activity.length > 0 ? (
          <div className={styles.activityList}>
            {recent_activity.map((act: RecentProgressActivity) => (
              <div key={act.id} className={styles.activityItem}>
                <div className={styles.activityLeft}>
                  {getActivityIcon(act.event_type)}
                  <span className={styles.activityTitle}>{act.title}</span>
                  {act.description && (
                    <span className={styles.activitySub}>· {act.description}</span>
                  )}
                </div>
                <span className={styles.activityTime}>{formatRelativeTime(act.timestamp)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className={styles.emptyActivity}>No progress activity yet.</p>
        )}
      </div>
    </section>
  );
};
