import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  CheckCheck,
  CheckCircle2,
  AlertCircle,
  Info,
  Clock,
  ExternalLink,
  Check,
} from 'lucide-react';
import { notificationApi } from '../../api/notifications';
import type { NotificationItem, NotificationSeverity } from '../../types';
import styles from './NotificationCenter.module.css';

function formatRelativeTime(dateString: string): string {
  try {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSec = Math.floor(diffMs / 1000);
    const diffMin = Math.floor(diffSec / 60);
    const diffHour = Math.floor(diffMin / 60);
    const diffDay = Math.floor(diffHour / 24);

    if (diffSec < 60) return 'Just now';
    if (diffMin < 60) return `${diffMin}m ago`;
    if (diffHour < 24) return `${diffHour}h ago`;
    if (diffDay === 1) return 'Yesterday';
    if (diffDay < 7) return `${diffDay}d ago`;
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return '';
  }
}

export const NotificationCenter: React.FC = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [loading, setLoading] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const buttonRef = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();

  const fetchNotifications = useCallback(async () => {
    try {
      setLoading(true);
      const data = await notificationApi.getNotifications(1);
      setNotifications(data.notifications);
      setUnreadCount(data.unread_count);
    } catch (err) {
      console.warn('Failed to load notifications:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load and periodic polling every 60s
  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 60000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  // Keyboard accessibility: Escape closes dropdown and returns focus to button
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && isOpen) {
        setIsOpen(false);
        buttonRef.current?.focus();
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen]);

  const toggleOpen = () => {
    const nextState = !isOpen;
    setIsOpen(nextState);
    if (nextState) {
      fetchNotifications();
    }
  };

  const handleMarkAsRead = async (id: number, e?: React.MouseEvent) => {
    e?.stopPropagation();
    try {
      await notificationApi.markAsRead(id, 1);
      setNotifications((prev) =>
        prev.map((item) => (item.id === id ? { ...item, read: true } : item))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err) {
      console.warn('Failed to mark notification as read:', err);
    }
  };

  const handleMarkAllAsRead = async () => {
    try {
      await notificationApi.markAllAsRead(1);
      setNotifications((prev) => prev.map((item) => ({ ...item, read: true })));
      setUnreadCount(0);
    } catch (err) {
      console.warn('Failed to mark all notifications as read:', err);
    }
  };

  const handleAction = async (item: NotificationItem) => {
    if (!item.read) {
      await handleMarkAsRead(item.id);
    }
    setIsOpen(false);

    if (item.action === 'VIEW_TODAY') {
      navigate('/');
    } else if (item.action === 'VIEW_ROADMAP') {
      navigate('/roadmap');
    }
  };

  const renderIcon = (severity: NotificationSeverity) => {
    switch (severity) {
      case 'ATTENTION':
        return <AlertCircle size={18} className={styles.attentionIcon} />;
      case 'SUCCESS':
        return <CheckCircle2 size={18} className={styles.successIcon} />;
      case 'INFO':
      default:
        return <Info size={18} className={styles.infoIcon} />;
    }
  };

  return (
    <div className={styles.container} ref={containerRef}>
      <button
        ref={buttonRef}
        className={`${styles.bellButton} ${isOpen ? styles.bellButtonActive : ''}`}
        onClick={toggleOpen}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className={styles.badge} aria-hidden="true">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <div className={styles.popover} role="dialog" aria-label="Notifications panel">
          <div className={styles.popoverHeader}>
            <div className={styles.headerLeft}>
              <h4 className={styles.headerTitle}>Notifications</h4>
              {unreadCount > 0 && (
                <span className={styles.unreadPill}>{unreadCount} new</span>
              )}
            </div>
            {unreadCount > 0 && (
              <button
                className={styles.markAllBtn}
                onClick={handleMarkAllAsRead}
                aria-label="Mark all notifications as read"
              >
                <CheckCheck size={14} />
                <span>Mark all read</span>
              </button>
            )}
          </div>

          <div className={styles.notificationList}>
            {loading && notifications.length === 0 ? (
              <div className={styles.emptyState}>
                <Clock size={28} className={styles.emptyIcon} />
                <p className={styles.emptyTitle}>Checking notifications...</p>
              </div>
            ) : notifications.length === 0 ? (
              <div className={styles.emptyState}>
                <CheckCircle2 size={32} className={styles.emptyIcon} />
                <p className={styles.emptyTitle}>All caught up</p>
                <p className={styles.emptySubtitle}>No notifications right now.</p>
              </div>
            ) : (
              notifications.map((item) => (
                <div
                  key={item.id}
                  className={`${styles.notificationItem} ${!item.read ? styles.unreadItem : ''}`}
                  onClick={() => !item.read && handleMarkAsRead(item.id)}
                >
                  <div className={styles.iconWrapper}>{renderIcon(item.severity)}</div>
                  <div className={styles.contentWrapper}>
                    <div className={styles.itemHeader}>
                      <h5 className={styles.itemTitle}>{item.title}</h5>
                      <span className={styles.itemTime}>
                        {formatRelativeTime(item.created_at)}
                      </span>
                    </div>
                    <p className={styles.itemMessage}>{item.message}</p>

                    <div className={styles.itemActions}>
                      {item.action === 'VIEW_TODAY' && (
                        <button
                          className={styles.actionBtn}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAction(item);
                          }}
                        >
                          View Today <ExternalLink size={11} />
                        </button>
                      )}
                      {item.action === 'VIEW_ROADMAP' && (
                        <button
                          className={styles.actionBtn}
                          onClick={(e) => {
                            e.stopPropagation();
                            handleAction(item);
                          }}
                        >
                          View Roadmap <ExternalLink size={11} />
                        </button>
                      )}
                      {!item.read && (
                        <button
                          className={styles.markReadBtn}
                          onClick={(e) => handleMarkAsRead(item.id, e)}
                          title="Mark as read"
                          aria-label="Mark as read"
                        >
                          <Check size={13} />
                          <span>Read</span>
                        </button>
                      )}
                    </div>
                  </div>
                  {!item.read && <span className={styles.unreadDot} aria-hidden="true" />}
                </div>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
};
