import { apiClient } from './client';
import {
  Roadmap,
  RoadmapDetail,
  RoadmapProgress,
  RoadmapGenerationRequest,
  GeneratedRoadmap,
  RoadmapInsertionRequest,
  InsertionPreviewResponse,
  InsertionResultResponse,
  RoadmapHistoryResponse,
} from '../types';

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

export async function previewGeneratedRoadmap(request: RoadmapGenerationRequest): Promise<GeneratedRoadmap> {
  return apiClient<GeneratedRoadmap>('/roadmaps/generate/preview', {
    method: 'POST',
    body: JSON.stringify(request),
    timeoutMs: 30000,
  });
}

export async function previewInsertion(
  roadmapId: number,
  request: RoadmapInsertionRequest
): Promise<InsertionPreviewResponse> {
  return apiClient<InsertionPreviewResponse>(`/roadmaps/${roadmapId}/insert/preview`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function applyInsertion(
  roadmapId: number,
  request: RoadmapInsertionRequest
): Promise<InsertionResultResponse> {
  return apiClient<InsertionResultResponse>(`/roadmaps/${roadmapId}/insert`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function getRoadmapHistory(roadmapId: number): Promise<RoadmapHistoryResponse> {
  return apiClient<RoadmapHistoryResponse>(`/roadmaps/${roadmapId}/history`);
}
