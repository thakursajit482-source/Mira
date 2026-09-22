import { apiClient } from './client';
import { Task } from '../types';

export async function completeTask(taskId: number): Promise<Task> {
  return apiClient<Task>(`/tasks/${taskId}/complete`, {
    method: 'PATCH',
  });
}

export async function uncompleteTask(taskId: number): Promise<Task> {
  return apiClient<Task>(`/tasks/${taskId}/uncomplete`, {
    method: 'PATCH',
  });
}

export async function getTask(taskId: number): Promise<Task> {
  return apiClient<Task>(`/tasks/${taskId}`);
}
