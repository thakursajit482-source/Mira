import { apiClient } from './client';
import type {
  NotificationItem,
  NotificationListResponse,
  NotificationPreferences,
  NotificationPreferencesUpdate,
} from '../types';

export const notificationApi = {
  /**
   * Sync and list notifications for a user.
   */
  async getNotifications(
    userId: number = 1,
    unreadOnly: boolean = false,
    limit: number = 50
  ): Promise<NotificationListResponse> {
    const params = new URLSearchParams({
      user_id: String(userId),
      unread_only: String(unreadOnly),
      limit: String(limit),
    });
    return apiClient<NotificationListResponse>(`/notifications?${params.toString()}`);
  },

  /**
   * Mark a single notification as read.
   */
  async markAsRead(notificationId: number, userId: number = 1): Promise<NotificationItem> {
    const params = new URLSearchParams({ user_id: String(userId) });
    return apiClient<NotificationItem>(`/notifications/${notificationId}/read?${params.toString()}`, {
      method: 'PATCH',
    });
  },

  /**
   * Mark all notifications as read for a user.
   */
  async markAllAsRead(userId: number = 1): Promise<{ updated_count: number }> {
    const params = new URLSearchParams({ user_id: String(userId) });
    return apiClient<{ updated_count: number }>(`/notifications/read-all?${params.toString()}`, {
      method: 'PATCH',
    });
  },

  /**
   * Get user notification preferences.
   */
  async getPreferences(userId: number = 1): Promise<NotificationPreferences> {
    const params = new URLSearchParams({ user_id: String(userId) });
    return apiClient<NotificationPreferences>(`/notifications/preferences?${params.toString()}`);
  },

  /**
   * Update user notification preferences.
   */
  async updatePreferences(
    preferences: NotificationPreferencesUpdate,
    userId: number = 1
  ): Promise<NotificationPreferences> {
    const params = new URLSearchParams({ user_id: String(userId) });
    return apiClient<NotificationPreferences>(`/notifications/preferences?${params.toString()}`, {
      method: 'PATCH',
      body: JSON.stringify(preferences),
    });
  },
};
