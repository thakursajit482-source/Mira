import React, { useState, useEffect } from 'react';
import { User, Server, Shield, CheckCircle2, AlertCircle, RefreshCw } from 'lucide-react';
import { DEV_USER } from '../utils/devUser';
import { apiClient } from '../api/client';
import { Card } from '../components/common/Card';
import { Badge } from '../components/common/Badge';
import { Button } from '../components/common/Button';
import { formatMinutes } from '../utils/formatters';
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

  useEffect(() => {
    checkBackendHealth();
  }, []);

  return (
    <div className="container">
      <div className={styles.wrapper}>
        <div className={styles.header}>
          <span className={styles.category}>Configuration</span>
          <h1 className={styles.title}>Settings & Environment</h1>
          <p className={styles.subtitle}>
            Manage development profile, review backend connectivity, and check application status.
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
