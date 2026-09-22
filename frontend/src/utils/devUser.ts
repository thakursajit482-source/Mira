/**
 * Isolated development user configuration.
 *
 * In Phase 8, authentication is out of scope.
 * This mock user corresponds to the development user initialized
 * in the backend database (id=1, email="dev@mira.local").
 */

export interface DevUser {
  id: number;
  username: string;
  email: string;
  dailyAvailableMinutes: number;
}

export const DEV_USER: DevUser = {
  id: 1,
  username: 'dev_user',
  email: 'dev@mira.local',
  dailyAvailableMinutes: 120,
};
