import { apiClient } from './client';
import { Roadmap, RoadmapDetail, RoadmapProgress, RoadmapGenerationRequest } from '../types';

export async function listRoadmaps(userId?: number): Promise<Roadmap[]> {
  const query = userId !== undefined ? `?user_id=${userId}` : '';
  return apiClient<Roadmap[]>(`/roadmaps${query}`);
}

export async function getRoadmap(id: number): Promise<Roadmap> {
  return apiClient<Roadmap>(`/roadmaps/${id}`);
}

export async function getRoadmapDetails(id: number): Promise<RoadmapDetail> {
  return apiClient<RoadmapDetail>(`/roadmaps/${id}/details`);
}

export async function getRoadmapProgress(id: number): Promise<RoadmapProgress> {
  return apiClient<RoadmapProgress>(`/roadmaps/${id}/progress`);
}

export async function generateRoadmap(request: RoadmapGenerationRequest): Promise<RoadmapDetail> {
  return apiClient<RoadmapDetail>('/roadmaps/generate', {
    method: 'POST',
    body: JSON.stringify(request),
    timeoutMs: 30000, // AI generation can take longer
  });
}
