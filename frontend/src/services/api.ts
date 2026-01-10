// API Client

import type { VideoInfo, JobResponse, HealthStatus, AudioFormat, AudioQuality, JobLog, LogsStats, UploadResponse } from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

async function request<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

export const api = {
  // Health
  health: () => request<HealthStatus>('/health'),

  // Video Info
  getVideoInfo: (url: string) => 
    request<VideoInfo>(`/info?url=${encodeURIComponent(url)}`),

  // Extract (async)
  startExtraction: (url: string, format: AudioFormat, quality: AudioQuality) =>
    request<JobResponse>('/extract', {
      method: 'POST',
      body: JSON.stringify({ url, format, quality }),
    }),

  // Jobs
  getJob: (jobId: string) => request<JobResponse>(`/jobs/${jobId}`),
  getJobs: () => request<JobResponse[]>('/jobs'),
  deleteJob: (jobId: string) => request<void>(`/jobs/${jobId}`, { method: 'DELETE' }),

  // Logs
  getAllLogs: (limit = 50) => request<{ total: number; logs: JobLog[] }>(`/logs?limit=${limit}`),
  getApiLogs: (limit = 50) => request<{ total: number; logs: JobLog[] }>(`/logs/api?limit=${limit}`),
  getWebLogs: (limit = 50) => request<{ total: number; logs: JobLog[] }>(`/logs/web?limit=${limit}`),
  getErrorLogs: (limit = 50) => request<{ total: number; logs: JobLog[] }>(`/logs/errors?limit=${limit}`),
  getLogsStats: () => request<LogsStats>('/logs/stats'),

  // Upload - envía archivo de video
  uploadVideo: async (file: File, format: AudioFormat, quality: AudioQuality): Promise<UploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('format', format);
    formData.append('quality', quality);

    const response = await fetch(`${API_BASE}/upload`, {
      method: 'POST',
      body: formData,
      // No Content-Type header - browser sets it with boundary for FormData
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
      throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
  },
};
