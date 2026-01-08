// API Service para comunicación con el backend

import type { ExtractRequest, HealthStatus, Job, LogsResponse, LogsStats, Stats, VideoInfo } from '../types';

const API_URL = import.meta.env.VITE_API_URL || 'https://videoconverter-api.8r3zyw.easypanel.host/api';

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Error desconocido' }));
    throw new ApiError(response.status, error.detail || 'Error en la solicitud');
  }
  return response.json();
}

export const api = {
  async health(): Promise<HealthStatus> {
    const response = await fetch(`${API_URL}/health`);
    return handleResponse<HealthStatus>(response);
  },

  async getVideoInfo(url: string): Promise<VideoInfo> {
    const response = await fetch(`${API_URL}/info?url=${encodeURIComponent(url)}`);
    return handleResponse<VideoInfo>(response);
  },

  async startExtraction(request: ExtractRequest): Promise<Job> {
    const response = await fetch(`${API_URL}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<Job>(response);
  },

  async getJob(jobId: string): Promise<Job> {
    const response = await fetch(`${API_URL}/jobs/${jobId}`);
    return handleResponse<Job>(response);
  },

  async listJobs(): Promise<Job[]> {
    const response = await fetch(`${API_URL}/jobs`);
    return handleResponse<Job[]>(response);
  },

  async getStats(): Promise<Stats> {
    const response = await fetch(`${API_URL}/jobs/stats`);
    return handleResponse<Stats>(response);
  },

  async deleteJob(jobId: string): Promise<void> {
    const response = await fetch(`${API_URL}/jobs/${jobId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new ApiError(response.status, 'Error al eliminar job');
    }
  },

  async getAllLogs(limit: number = 50): Promise<LogsResponse> {
    const response = await fetch(`${API_URL}/logs?limit=${limit}`);
    return handleResponse<LogsResponse>(response);
  },

  async getApiLogs(limit: number = 50): Promise<LogsResponse> {
    const response = await fetch(`${API_URL}/logs/api?limit=${limit}`);
    return handleResponse<LogsResponse>(response);
  },

  async getWebLogs(limit: number = 50): Promise<LogsResponse> {
    const response = await fetch(`${API_URL}/logs/web?limit=${limit}`);
    return handleResponse<LogsResponse>(response);
  },

  async getErrorLogs(limit: number = 50): Promise<LogsResponse> {
    const response = await fetch(`${API_URL}/logs/errors?limit=${limit}`);
    return handleResponse<LogsResponse>(response);
  },

  async getLogsStats(): Promise<LogsStats> {
    const response = await fetch(`${API_URL}/logs/stats`);
    return handleResponse<LogsStats>(response);
  },
};

export { ApiError };
