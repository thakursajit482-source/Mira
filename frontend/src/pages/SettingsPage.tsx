import React, { useState, useEffect } from 'react';
import {
  User,
  Server,
  Shield,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Bell,
  Globe,
  Check,
} from 'lucide-react';
import { DEV_USER } from '../utils/devUser';
import { apiClient } from '../api/client';
import { notificationApi } from '../api/notifications';
import {
  getBrowserNotificationPermission,
  requestBrowserNotificationPermission,
  type BrowserNotificationPermission,
} from '../services/notifications';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { formatMinutes } from '../utils/formatters';
import type { NotificationPreferences } from '../types';
import styles from './SettingsPage.module.css';

interface HealthStatus {
  status: string;
  app_name: string;
  environment: string;
  version: string;
}

export const SettingsPage: React.FC = () => {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isChecking, setIsChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Notification Preferences State
  const [prefs, setPrefs] = useState<NotificationPreferences | null>(null);
  const [isSavingPrefs, setIsSavingPrefs] = useState(false);
  const [showSavedNotice, setShowSavedNotice] = useState(false);
  const [browserPermission, setBrowserPermission] = useState<BrowserNotificationPermission>(
    getBrowserNotificationPermission()
  );

  const checkBackendHealth = async () => {
    setIsChecking(true);
    setError(null);
    try {
      const data = await apiClient<HealthStatus>('/health');
      setHealth(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Backend unreachable';
      setError(msg);
      setHealth(null);
    } finally {
      setIsChecking(false);
    }
  };

  const loadPreferences = async () => {
    try {
      const data = await notificationApi.getPreferences(1);
      setPrefs(data);
    } catch (err) {
      console.warn('Failed to fetch notification preferences:', err);
    }
  };

  useEffect(() => {
    checkBackendHealth();
    loadPreferences();
  }, []);

  const updatePreferences = async (patch: Partial<NotificationPreferences>) => {
    if (!prefs) return;
    setIsSavingPrefs(true);
    try {
      const updated = await notificationApi.updatePreferences(patch, 1);
      setPrefs(updated);
      setShowSavedNotice(true);
      setTimeout(() => setShowSavedNotice(false), 2500);
    } catch (err) {
      console.warn('Failed to update notification preferences:', err);
    } finally {
      setIsSavingPrefs(false);
    }
  };

  const handleRequestBrowserPermission = async () => {
    const permission = await requestBrowserNotificationPermission();
    setBrowserPermission(permission);
  };

  const handleDetectTimezone = () => {
    try {
      const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (detected) {
        updatePreferences({ timezone: detected });
      }
    } catch (err) {
      console.warn('Failed to detect browser timezone:', err);
    }
  };

  return (
    <div className="container">
      <div className={styles.wrapper}>
        <div className={styles.header}>
          <span className={styles.category}>Configuration</span>
          <h1 className={styles.title}>Settings & Environment</h1>
          <p className={styles.subtitle}>
            Manage development profile, review backend connectivity, and configure notifications.
          </p>
        </div>

        <div className={styles.grid}>
          {/* User Profile Card */}
          <Card padding="lg" className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <User size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>Development Profile</h3>
                <p className={styles.cardSubtitle}>Active local user context</p>
              </div>
            </div>

            <div className={styles.detailsList}>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>User ID</span>
                <span className={styles.detailValue}>{DEV_USER.id}</span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>Username</span>
                <span className={styles.detailValue}>{DEV_USER.username}</span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>Email</span>
                <span className={styles.detailValue}>{DEV_USER.email}</span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>Daily Capacity</span>
                <span className={styles.detailValue}>
                  {formatMinutes(DEV_USER.dailyAvailableMinutes)} ({DEV_USER.dailyAvailableMinutes} mins)
                </span>
              </div>
            </div>
          </Card>

          {/* Backend Status Card */}
          <Card padding="lg" className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Server size={20} />
              </div>
              <div className={styles.serverTitleArea}>
                <div>
                  <h3 className={styles.cardTitle}>Backend Connection</h3>
                  <p className={styles.cardSubtitle}>FastAPI Engine at /api/v1</p>
                </div>
                {health ? (
                  <Badge variant="completed" size="sm" dot>Connected</Badge>
                ) : (
                  <Badge variant="danger" size="sm" dot>Disconnected</Badge>
                )}
              </div>
            </div>

            <div className={styles.detailsList}>
              {health ? (
                <>
                  <div className={styles.detailItem}>
                    <span className={styles.detailKey}>App Name</span>
                    <span className={styles.detailValue}>{health.app_name}</span>
                  </div>
                  <div className={styles.detailItem}>
                    <span className={styles.detailKey}>Environment</span>
                    <span className={styles.detailValue}>{health.environment}</span>
                  </div>
                  <div className={styles.detailItem}>
                    <span className={styles.detailKey}>Version</span>
                    <span className={styles.detailValue}>{health.version}</span>
                  </div>
                  <div className={styles.detailItem}>
                    <span className={styles.detailKey}>Health</span>
                    <span className={styles.statusOk}>
                      <CheckCircle2 size={14} /> OK
                    </span>
                  </div>
                </>
              ) : (
                <div className={styles.errorNotice}>
                  <AlertCircle size={16} />
                  <span>{error || 'Cannot connect to backend server at /api/v1'}</span>
                </div>
              )}
            </div>

            <div className={styles.cardFooter}>
              <Button
                variant="secondary"
                size="sm"
                onClick={checkBackendHealth}
                isLoading={isChecking}
                leftIcon={<RefreshCw size={14} />}
              >
                Recheck Connection
              </Button>
            </div>
          </Card>

          {/* Notifications & Reminders Card */}
          <Card padding="lg" className={`${styles.card} ${styles.fullWidthCard}`}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Bell size={20} />
              </div>
              <div className={styles.serverTitleArea}>
                <div>
                  <h3 className={styles.cardTitle}>Notifications & Reminders</h3>
                  <p className={styles.cardSubtitle}>
                    Deterministic daily alerts, completion reminders, and timezone settings
                  </p>
                </div>
                {showSavedNotice && (
                  <span className={styles.savedBadge}>
                    <Check size={14} /> Saved
                  </span>
                )}
              </div>
            </div>

            {prefs ? (
              <div className={styles.preferenceGroup}>
                {/* Master Toggle */}
                <div className={styles.preferenceRow}>
                  <div className={styles.preferenceInfo}>
                    <span className={styles.preferenceLabel}>Enable Notifications</span>
                    <span className={styles.preferenceDesc}>
                      Receive deterministic notifications for today&apos;s focus, over-capacity warnings, and milestones.
                    </span>
                  </div>
                  <label className={styles.toggle} aria-label="Toggle all notifications">
                    <input
                      type="checkbox"
                      checked={prefs.notifications_enabled}
                      disabled={isSavingPrefs}
                      onChange={(e) => updatePreferences({ notifications_enabled: e.target.checked })}
                    />
                    <span className={styles.toggleSlider} />
                  </label>
                </div>

                {/* Daily Reminder Toggle */}
                <div className={styles.preferenceRow}>
                  <div className={styles.preferenceInfo}>
                    <span className={styles.preferenceLabel}>Daily Evening Reminder</span>
                    <span className={styles.preferenceDesc}>
                      Remind me if today&apos;s planned roadmap tasks are still incomplete at the scheduled time.
                    </span>
                  </div>
                  <label className={styles.toggle} aria-label="Toggle daily reminder">
                    <input
                      type="checkbox"
                      checked={prefs.daily_reminder_enabled}
                      disabled={!prefs.notifications_enabled || isSavingPrefs}
                      onChange={(e) => updatePreferences({ daily_reminder_enabled: e.target.checked })}
                    />
                    <span className={styles.toggleSlider} />
                  </label>
                </div>

                {/* Reminder Time */}
                <div className={styles.preferenceRow}>
                  <div className={styles.preferenceInfo}>
                    <span className={styles.preferenceLabel}>Reminder Time</span>
                    <span className={styles.preferenceDesc}>
                      Time of day in your local timezone to evaluate remaining tasks.
                    </span>
                  </div>
                  <input
                    type="time"
                    className={styles.inputField}
                    value={prefs.daily_reminder_time}
                    disabled={!prefs.notifications_enabled || !prefs.daily_reminder_enabled || isSavingPrefs}
                    onChange={(e) => updatePreferences({ daily_reminder_time: e.target.value })}
                    aria-label="Daily reminder time"
                  />
                </div>

                {/* Timezone */}
                <div className={styles.preferenceRow}>
                  <div className={styles.preferenceInfo}>
                    <span className={styles.preferenceLabel}>Timezone</span>
                    <span className={styles.preferenceDesc}>
                      Configured IANA timezone for accurate daily schedule calculation.
                    </span>
                  </div>
                  <div className={styles.timezoneControl}>
                    <span className={styles.detailValue}>{prefs.timezone}</span>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={handleDetectTimezone}
                      disabled={isSavingPrefs}
                      leftIcon={<Globe size={13} />}
                    >
                      Use Device Timezone
                    </Button>
                  </div>
                </div>

                {/* Browser Web Notifications */}
                <div className={styles.preferenceRow}>
                  <div className={styles.preferenceInfo}>
                    <span className={styles.preferenceLabel}>Browser Notifications</span>
                    <span className={styles.preferenceDesc}>
                      Receive non-intrusive desktop notifications when Mira is open in your browser.
                    </span>
                  </div>
                  <div className={styles.browserNotificationArea}>
                    {browserPermission === 'granted' ? (
                      <Badge variant="completed" size="sm" dot>Allowed</Badge>
                    ) : browserPermission === 'denied' ? (
                      <Badge variant="danger" size="sm" dot>Blocked</Badge>
                    ) : browserPermission === 'unsupported' ? (
                      <Badge variant="neutral" size="sm">Unsupported</Badge>
                    ) : (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleRequestBrowserPermission}
                        leftIcon={<Bell size={13} />}
                      >
                        Enable in Browser
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className={styles.detailsList}>
                <span className={styles.detailKey}>Loading notification settings...</span>
              </div>
            )}
          </Card>

          {/* Philosophy & Architecture Card */}
          <Card padding="lg" className={`${styles.card} ${styles.fullWidthCard}`}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Shield size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>Mira Philosophy & Invariants</h3>
                <p className={styles.cardSubtitle}>Deterministic architecture</p>
              </div>
            </div>

            <div className={styles.philosophyContent}>
              <p>
                <strong>&ldquo;Mira — Turn your plans into progress.&rdquo;</strong>
              </p>
              <p>
                AI doesn&apos;t decide what you should learn. It helps you actually finish what you&apos;ve already decided to learn.
              </p>
              <ul>
                <li><strong>Authoritative Backend:</strong> All day and task progression states are strictly calculated by the backend.</li>
                <li><strong>Deterministic Notifications:</strong> Reminders evaluate your actual plan data, never speculative AI prompts.</li>
                <li><strong>History Protection:</strong> Completed days and tasks are immutable to prevent loss of progress.</li>
                <li><strong>Fixed Duration:</strong> Total target duration remains fixed unless explicitly changed.</li>
              </ul>
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
};
