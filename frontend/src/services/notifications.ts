/**
 * Browser Notification Helper for Mira.
 *
 * Guarantees:
 * - Permission is ONLY requested on explicit user action (e.g., clicking in Settings).
 * - Safe no-ops if browser notifications are unsupported or denied.
 * - Non-intrusive, calm notifications.
 */

export type BrowserNotificationPermission = 'default' | 'granted' | 'denied' | 'unsupported';

export function isNotificationSupported(): boolean {
  return typeof window !== 'undefined' && 'Notification' in window;
}

export function getBrowserNotificationPermission(): BrowserNotificationPermission {
  if (!isNotificationSupported()) {
    return 'unsupported';
  }
  return window.Notification.permission;
}

export async function requestBrowserNotificationPermission(): Promise<BrowserNotificationPermission> {
  if (!isNotificationSupported()) {
    return 'unsupported';
  }

  try {
    const permission = await window.Notification.requestPermission();
    return permission;
  } catch (error) {
    console.warn('Failed to request browser notification permission:', error);
    return 'denied';
  }
}

export function showBrowserNotification(
  title: string,
  options?: NotificationOptions
): Notification | null {
  if (!isNotificationSupported()) {
    return null;
  }

  if (window.Notification.permission !== 'granted') {
    return null;
  }

  try {
    return new window.Notification(title, {
      icon: '/favicon.ico',
      badge: '/favicon.ico',
      ...options,
    });
  } catch (error) {
    console.warn('Failed to display browser notification:', error);
    return null;
  }
}
