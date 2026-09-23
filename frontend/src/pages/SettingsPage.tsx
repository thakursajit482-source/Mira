import React, { useState, useEffect, useCallback } from 'react';
import {
  User as UserIcon,
  Server,
  Shield,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Bell,
  Globe,
  Check,
  Clock,
  Palette,
  Sun,
  Moon,
  Monitor,
  Download,
  AlertTriangle,
  X,
  Compass,
} from 'lucide-react';
import { apiClient } from '../api/client';
import { userApi } from '../api/users';
import { listRoadmaps, exportRoadmap, deleteRoadmap } from '../api/roadmaps';
import {
  getBrowserNotificationPermission,
  requestBrowserNotificationPermission,
  type BrowserNotificationPermission,
} from '../services/notifications';
import { useToast } from '../context/ToastContext';
import { useTheme } from '../context/ThemeContext';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { formatMinutes } from '../utils/formatters';
import type { UserPreferences, ThemeOption, Roadmap } from '../types';
import styles from './SettingsPage.module.css';

interface HealthStatus {
  status: string;
  app_name: string;
  environment: string;
  version: string;
}

export const SettingsPage: React.FC = () => {
  const { toast } = { toast: useToast() };
  const { theme, setTheme } = useTheme();

  // Backend Health
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isCheckingHealth, setIsCheckingHealth] = useState(false);
  const [healthError, setHealthError] = useState<string | null>(null);

  // User Preferences
  const [prefs, setPrefs] = useState<UserPreferences | null>(null);
  const [isSavingPrefs, setIsSavingPrefs] = useState(false);
  const [showSavedNotice, setShowSavedNotice] = useState(false);

  // Daily Capacity Input
  const [capacityInput, setCapacityInput] = useState<string>('120');
  const [capacityError, setCapacityError] = useState<string | null>(null);
  const [isSavingCapacity, setIsSavingCapacity] = useState(false);

  // Active Roadmap & Export/Delete
  const [activeRoadmap, setActiveRoadmap] = useState<Roadmap | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  // Browser Notification Permission
  const [browserPermission, setBrowserPermission] = useState<BrowserNotificationPermission>(
    getBrowserNotificationPermission()
  );

  const checkBackendHealth = async () => {
    setIsCheckingHealth(true);
    setHealthError(null);
    try {
      const data = await apiClient<HealthStatus>('/health');
      setHealth(data);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Backend unreachable';
      setHealthError(msg);
      setHealth(null);
    } finally {
      setIsCheckingHealth(false);
    }
  };

  const loadPreferencesAndRoadmap = useCallback(async () => {
    try {
      const userPrefs = await userApi.getUserPreferences(1);
      setPrefs(userPrefs);
      setCapacityInput(String(userPrefs.daily_available_minutes));
    } catch (err) {
      console.warn('Failed to load user preferences:', err);
    }

    try {
      const roadmaps = await listRoadmaps(1);
      const active = roadmaps.find((r) => r.status === 'IN_PROGRESS' || r.status === 'NOT_STARTED') || roadmaps[0] || null;
      setActiveRoadmap(active);
    } catch (err) {
      console.warn('Failed to load roadmaps:', err);
    }
  }, []);

  useEffect(() => {
    checkBackendHealth();
    loadPreferencesAndRoadmap();
  }, [loadPreferencesAndRoadmap]);

  const updatePreference = async (patch: Partial<UserPreferences>) => {
    if (!prefs) return;
    setIsSavingPrefs(true);
    try {
      const updated = await userApi.updateUserPreferences(patch, 1);
      setPrefs(updated);
      setShowSavedNotice(true);
      setTimeout(() => setShowSavedNotice(false), 2000);
      toast.success('Preferences updated');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to update preferences';
      toast.error('Save failed', msg);
    } finally {
      setIsSavingPrefs(false);
    }
  };

  const handleSaveCapacity = async () => {
    const parsed = parseInt(capacityInput, 10);
    if (isNaN(parsed) || parsed < 15 || parsed > 1440) {
      setCapacityError('Capacity must be between 15 and 1440 minutes (24 hours).');
      return;
    }
    setCapacityError(null);
    setIsSavingCapacity(true);
    try {
      const updated = await userApi.updateUserPreferences({ daily_available_minutes: parsed }, 1);
      setPrefs(updated);
      setCapacityInput(String(updated.daily_available_minutes));
      toast.success('Daily study capacity saved', `${formatMinutes(parsed)} per day`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Could not save capacity';
      setCapacityError(msg);
      toast.error('Save failed', msg);
    } finally {
      setIsSavingCapacity(false);
    }
  };

  const handleResetCapacity = () => {
    if (prefs) {
      setCapacityInput(String(prefs.daily_available_minutes));
      setCapacityError(null);
    }
  };

  const handleThemeChange = async (newTheme: ThemeOption) => {
    setTheme(newTheme);
    try {
      await userApi.updateUserPreferences({ theme: newTheme }, 1);
      setPrefs((prev) => (prev ? { ...prev, theme: newTheme } : prev));
      toast.success('Theme preference saved');
    } catch (err) {
      console.warn('Failed to sync theme with server:', err);
    }
  };

  const handleDetectTimezone = () => {
    try {
      const detected = Intl.DateTimeFormat().resolvedOptions().timeZone;
      if (detected) {
        updatePreference({ timezone: detected });
      }
    } catch (err) {
      console.warn('Failed to detect browser timezone:', err);
    }
  };

  const handleRequestBrowserPermission = async () => {
    const permission = await requestBrowserNotificationPermission();
    setBrowserPermission(permission);
  };

  const handleExportRoadmap = async () => {
    if (!activeRoadmap) {
      toast.info('No active roadmap to export');
      return;
    }
    setIsExporting(true);
    try {
      const exportData = await exportRoadmap(activeRoadmap.id);
      const jsonString = JSON.stringify(exportData, null, 2);
      const blob = new Blob([jsonString], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `mira-roadmap-${activeRoadmap.id}-export.json`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);
      toast.success('Roadmap exported', 'Download started');
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to export roadmap';
      toast.error('Export failed', msg);
    } finally {
      setIsExporting(false);
    }
  };

  const handleDeleteRoadmap = async () => {
    if (!activeRoadmap) return;
    setIsDeleting(true);
    try {
      await deleteRoadmap(activeRoadmap.id);
      toast.success('Roadmap deleted', `"${activeRoadmap.title}" was permanently removed.`);
      setActiveRoadmap(null);
      setIsDeleteModalOpen(false);
      // Reload roadmaps
      const roadmaps = await listRoadmaps(1);
      setActiveRoadmap(roadmaps[0] || null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to delete roadmap';
      toast.error('Deletion failed', msg);
    } finally {
      setIsDeleting(false);
    }
  };

  // Keyboard Escape listener for delete modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isDeleteModalOpen) {
        setIsDeleteModalOpen(false);
      }
    };
    if (isDeleteModalOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isDeleteModalOpen]);

  const hasCapacityChanged =
    prefs && parseInt(capacityInput, 10) !== prefs.daily_available_minutes;

  return (
    <div className="container">
      <div className={styles.wrapper}>
        <div className={styles.header}>
          <span className={styles.category}>Configuration</span>
          <h1 className={styles.title}>Settings & Preferences</h1>
          <p className={styles.subtitle}>
            Manage profile context, study capacity, roadmap behavior, appearance, and notifications.
          </p>
        </div>

        <div className={styles.grid}>
          {/* 1. Profile Section */}
          <Card padding="lg" className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <UserIcon size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>Profile</h3>
                <p className={styles.cardSubtitle}>Your personal information used by Mira</p>
              </div>
            </div>

            <div className={styles.detailsList}>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>Username</span>
                <span className={styles.detailValue}>{prefs?.username || 'dev_user'}</span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>Email</span>
                <span className={styles.detailValue}>{prefs?.email || 'dev@mira.local'}</span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>Configured Timezone</span>
                <span className={styles.detailValue}>{prefs?.timezone || 'UTC'}</span>
              </div>
              <div className={styles.detailItem}>
                <span className={styles.detailKey}>Account Status</span>
                <Badge variant="completed" size="sm" dot>Active</Badge>
              </div>
            </div>
          </Card>

          {/* 2. Personalization & Daily Available Time */}
          <Card padding="lg" className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Clock size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>Daily Study Time</h3>
                <p className={styles.cardSubtitle}>Capacity used by Daily Planning & Roadmap Engine</p>
              </div>
            </div>

            <div className={styles.capacityControl}>
              <div className={styles.capacityInputRow}>
                <input
                  type="number"
                  min={15}
                  max={1440}
                  className={`${styles.inputField} ${styles.capacityInput}`}
                  value={capacityInput}
                  onChange={(e) => {
                    setCapacityInput(e.target.value);
                    setCapacityError(null);
                  }}
                  aria-label="Daily available minutes"
                />
                <span className={styles.detailKey}>
                  minutes / day ({formatMinutes(parseInt(capacityInput, 10) || 0)})
                </span>
              </div>

              {capacityError && <span className={styles.fieldError}>{capacityError}</span>}

              <p className={styles.preferenceDesc}>
                Updating daily capacity recalculates your daily workload analysis. It will not silently mutate or reschedule existing roadmap tasks.
              </p>

              {hasCapacityChanged && (
                <div className={styles.capacityActions}>
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={handleSaveCapacity}
                    isLoading={isSavingCapacity}
                  >
                    Save Capacity
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleResetCapacity}
                    disabled={isSavingCapacity}
                  >
                    Cancel
                  </Button>
                </div>
              )}
            </div>
          </Card>

          {/* 3. Roadmap Preferences */}
          <Card padding="lg" className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Compass size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>Roadmap Preferences</h3>
                <p className={styles.cardSubtitle}>Planning behavior and schedule adjustments</p>
              </div>
            </div>

            <div className={styles.preferenceGroup}>
              <div className={styles.infoCallout}>
                <strong>Planning Invariant:</strong> Mira preserves completed work and only adjusts future incomplete work when you explicitly ask it to reschedule.
              </div>

              <div className={styles.preferenceRow}>
                <div className={styles.preferenceInfo}>
                  <span className={styles.preferenceLabel}>Ask Before Rescheduling</span>
                  <span className={styles.preferenceDesc}>
                    Display a visual diff preview of proposed day shifts before modifying your roadmap.
                  </span>
                </div>
                <label className={styles.toggle} aria-label="Toggle confirmation before rescheduling">
                  <input
                    type="checkbox"
                    checked={prefs?.ask_before_reschedule ?? true}
                    disabled={isSavingPrefs}
                    onChange={(e) => updatePreference({ ask_before_reschedule: e.target.checked })}
                  />
                  <span className={styles.toggleSlider} />
                </label>
              </div>
            </div>
          </Card>

          {/* 4. Appearance Section */}
          <Card padding="lg" className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Palette size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>Appearance</h3>
                <p className={styles.cardSubtitle}>Interface theme and color mode</p>
              </div>
            </div>

            <div className={styles.themeGrid}>
              <button
                type="button"
                className={`${styles.themeCard} ${theme === 'system' ? styles.themeCardActive : ''}`}
                onClick={() => handleThemeChange('system')}
                aria-label="System default theme"
              >
                <div className={styles.themeCardIcon}>
                  <Monitor size={22} />
                </div>
                <span className={styles.themeCardLabel}>System</span>
              </button>

              <button
                type="button"
                className={`${styles.themeCard} ${theme === 'light' ? styles.themeCardActive : ''}`}
                onClick={() => handleThemeChange('light')}
                aria-label="Light theme"
              >
                <div className={styles.themeCardIcon}>
                  <Sun size={22} />
                </div>
                <span className={styles.themeCardLabel}>Light</span>
              </button>

              <button
                type="button"
                className={`${styles.themeCard} ${theme === 'dark' ? styles.themeCardActive : ''}`}
                onClick={() => handleThemeChange('dark')}
                aria-label="Dark theme"
              >
                <div className={styles.themeCardIcon}>
                  <Moon size={22} />
                </div>
                <span className={styles.themeCardLabel}>Dark</span>
              </button>
            </div>
          </Card>

          {/* 5. Notifications & Reminders (Phase 10.8 Reused) */}
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
                      onChange={(e) => updatePreference({ notifications_enabled: e.target.checked })}
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
                      onChange={(e) => updatePreference({ daily_reminder_enabled: e.target.checked })}
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
                    onChange={(e) => updatePreference({ daily_reminder_time: e.target.value })}
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

          {/* 6. Data & Privacy */}
          <Card padding="lg" className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Shield size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>Data & Privacy</h3>
                <p className={styles.cardSubtitle}>Export and control your roadmap data</p>
              </div>
            </div>

            <div className={styles.preferenceGroup}>
              <div className={styles.preferenceRow}>
                <div className={styles.preferenceInfo}>
                  <span className={styles.preferenceLabel}>Export Roadmap Data</span>
                  <span className={styles.preferenceDesc}>
                    {activeRoadmap
                      ? `Download a full JSON export of "${activeRoadmap.title}" including all days, tasks, and change history.`
                      : 'No active roadmap available to export.'}
                  </span>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleExportRoadmap}
                  disabled={!activeRoadmap || isExporting}
                  isLoading={isExporting}
                  leftIcon={<Download size={14} />}
                >
                  Export JSON
                </Button>
              </div>
            </div>
          </Card>

          {/* 7. Backend & Environment Connection */}
          <Card padding="lg" className={styles.card}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Server size={20} />
              </div>
              <div className={styles.serverTitleArea}>
                <div>
                  <h3 className={styles.cardTitle}>Backend Engine</h3>
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
                    <span className={styles.detailValue}>v{health.version}</span>
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
                  <span>{healthError || 'Cannot connect to backend server at /api/v1'}</span>
                </div>
              )}
            </div>

            <div className={styles.cardFooter}>
              <Button
                variant="secondary"
                size="sm"
                onClick={checkBackendHealth}
                isLoading={isCheckingHealth}
                leftIcon={<RefreshCw size={14} />}
              >
                Recheck Engine
              </Button>
            </div>
          </Card>

          {/* 8. Danger Zone */}
          <Card padding="lg" className={`${styles.card} ${styles.dangerCard} ${styles.fullWidthCard}`}>
            <div className={styles.cardHeader}>
              <div className={`${styles.iconCircle} ${styles.dangerIconCircle}`}>
                <AlertTriangle size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>Danger Zone</h3>
                <p className={styles.cardSubtitle}>Irreversible actions for your active roadmap</p>
              </div>
            </div>

            <div className={styles.dangerNotice}>
              <div className={styles.dangerNoticeText}>
                <span className={styles.dangerNoticeTitle}>
                  {activeRoadmap ? `Delete "${activeRoadmap.title}"` : 'Delete Roadmap'}
                </span>
                <span className={styles.dangerNoticeDesc}>
                  Permanently deletes this roadmap, including all days, tasks, and historical versions.
                </span>
              </div>
              <button
                type="button"
                className={styles.dangerBtn}
                onClick={() => setIsDeleteModalOpen(true)}
                disabled={!activeRoadmap}
              >
                Delete Roadmap
              </button>
            </div>
          </Card>

          {/* 9. About Mira */}
          <Card padding="lg" className={`${styles.card} ${styles.fullWidthCard}`}>
            <div className={styles.cardHeader}>
              <div className={styles.iconCircle}>
                <Compass size={20} />
              </div>
              <div>
                <h3 className={styles.cardTitle}>About Mira</h3>
                <p className={styles.cardSubtitle}>Turn your plans into progress</p>
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

      {/* Explicit Roadmap Deletion Modal */}
      {isDeleteModalOpen && activeRoadmap && (
        <div className={styles.modalOverlay} onClick={() => setIsDeleteModalOpen(false)}>
          <div
            className={styles.modalDialog}
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
            onClick={(e) => e.stopPropagation()}
          >
            <div className={styles.modalHeader}>
              <div className={styles.modalTitleArea}>
                <AlertTriangle size={20} className={styles.modalDangerIcon} />
                <h3 id="delete-dialog-title" className={styles.modalTitle}>
                  Delete &ldquo;{activeRoadmap.title}&rdquo;?
                </h3>
              </div>
              <button
                type="button"
                className={styles.modalCloseBtn}
                onClick={() => setIsDeleteModalOpen(false)}
                aria-label="Close dialog"
              >
                <X size={18} />
              </button>
            </div>

            <div className={styles.modalBody}>
              <p>
                This will permanently remove the roadmap and all associated records from your database:
              </p>
              <ul className={styles.modalConsequences}>
                <li>Roadmap container &ldquo;{activeRoadmap.title}&rdquo;</li>
                <li>All planned days and scheduled tasks</li>
                <li>Audit logs and version history</li>
              </ul>
              <p>
                <strong>This action cannot be undone.</strong>
              </p>
            </div>

            <div className={styles.modalFooter}>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsDeleteModalOpen(false)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <button
                type="button"
                className={styles.modalConfirmBtn}
                onClick={handleDeleteRoadmap}
                disabled={isDeleting}
              >
                {isDeleting ? 'Deleting...' : 'Delete Roadmap'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
