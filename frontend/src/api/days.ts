import { apiClient } from './client';
import { Day } from '../types';

export async function getDay(dayId: number): Promise<Day> {
  return apiClient<Day>(`/days/${dayId}`);
}
