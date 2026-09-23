import { apiClient } from './client';
import type { UserPreferences, UserPreferencesUpdate } from '../types';

export const userApi = {
  /**
   * Retrieve unified preferences and profile information for a user.
   */
  async getUserPreferences(userId: number = 1): Promise<UserPreferences> {
    const params = new URLSearchParams({ user_id: String(userId) });
    return apiClient<UserPreferences>(`/users/preferences?${params.toString()}`);
  },

  /**
   * Update personal preferences, available capacity, appearance, and roadmap behavior.
   */
  async updateUserPreferences(
    patch: UserPreferencesUpdate,
    userId: number = 1
  ): Promise<UserPreferences> {
    const params = new URLSearchParams({ user_id: String(userId) });
    return apiClient<UserPreferences>(`/users/preferences?${params.toString()}`, {
      method: 'PATCH',
      body: JSON.stringify(patch),
    });
  },
};
