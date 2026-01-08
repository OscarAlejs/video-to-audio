// API Service para comunicación con el backend

import type { ExtractRequest, HealthStatus, Job, JobLog, LogsResponse, LogsStats, Stats, VideoInfo } from '../types';

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
  // Health Check
  async health(): Promise<HealthStatus> {
    const response = await fetch(`${API_URL}/health`);
    return handleResponse<HealthStatus>(response);
  },

  // Video Info
  async getVideoInfo(url: string): Promise<VideoInfo> {
    const response = await fetch(`${API_URL}/info?url=${encodeURIComponent(url)}`);
    return handleResponse<VideoInfo>(response);
  },

  // Start Extraction
  async startExtraction(request: ExtractRequest): Promise<Job> {
    const response = await fetch(`${API_URL}/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });
    return handleResponse<Job>(response);
  },

  // Get Job Status
  async getJob(jobId: string): Promise<Job> {
    const response = await fetch(`${API_URL}/jobs/${jobId}`);
    return handleResponse<Job>(response);
  },

  // List Jobs
  async listJobs(): Promise<Job[]> {
    const response = await fetch(`${API_URL}/jobs`);
    return handleResponse<Job[]>(response);
  },

  // Get Stats
  async getStats(): Promise<Stats> {
    const response = await fetch(`${API_URL}/jobs/stats`);
    return handleResponse<Stats>(response);
  },

  // Delete Job
  async deleteJob(jobId: string): Promise<void> {
    const response = await fetch(`${API_URL}/jobs/${jobId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new ApiError(response.status, 'Error al eliminar job');
    }
  },

  // ============== Logs (desde tabla jobs) ==============

  // Get All Logs
  async getAllLogs(limit: number = 50): Promise<LogsResponse> {
    const response = await fetch(`${API_URL}/logs?limit=${limit}`);
    return handleResponse<LogsResponse>(response);
  },

  // Get API Logs
  async getApiLogs(limit: number = 50): Promise<LogsResponse> {
    const response = await fetch(`${API_URL}/logs/api?limit=${limit}`);
    return handleResponse<LogsResponse>(response);
  },

  // Get Web Logs
  async getWebLogs(limit: number = 50): Promise<LogsResponse> {
    const response = await fetch(`${API_URL}/logs/web?limit=${limit}`);
    return handleResponse<LogsResponse>(response);
  },

  // Get Error Logs
  async getErrorLogs(limit: int = 50): Promise<LogsResponse> {
    const response = await fetch(`${API_URL}/logs/errors?limit=${limit}`);
    return handleResponse<LogsResponse>(response);
  },

  // Get Logs Stats
  async getLogsStats(): Promise<LogsStats> {
    const response = await fetch(`${API_URL}/logs/stats`);
    return handleResponse<LogsStats>(response);
  },
};

export { ApiError };
