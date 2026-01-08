// Tipos compartidos del frontend

export type AudioFormat = 'mp3' | 'm4a' | 'wav' | 'opus';
export type AudioQuality = '128' | '192' | '256' | '320';
export type JobStatus = 'pending' | 'processing' | 'downloading' | 'extracting' | 'uploading' | 'completed' | 'failed';
export type ExecutionSource = 'api' | 'web';

export interface VideoInfo {
  id: string;
  title: string;
  duration_seconds: number;
  duration_formatted: string;
  thumbnail: string | null;
  source: string;
  channel: string | null;
}

export interface ExtractResult {
  success: boolean;
  audio_url?: string;
  filename?: string;
  file_size?: string;
  format?: string;
  quality?: string;
  error?: string;
}

export interface Job {
  job_id: string;
  status: JobStatus;
  progress: number;
  message: string;
  created_at: string;
  video_info?: VideoInfo;
  result?: ExtractResult;
}

export interface ExtractRequest {
  url: string;
  format: AudioFormat;
  quality: AudioQuality;
}

export interface HealthStatus {
  status: string;
  version: string;
  supabase_configured: boolean;
  max_duration_minutes: number;
}

export interface Stats {
  total_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  active_jobs: number;
}

// Job desde Supabase (tabla jobs)
export interface JobLog {
  id: string;
  status: string;
  progress: number;
  stage: string;
  video_url: string;
  video_title?: string;
  video_id?: string;
  video_duration?: number;
  video_thumbnail?: string;
  video_source?: string;
  video_channel?: string;
  format: string;
  quality: string;
  audio_url?: string;
  file_size?: string;
  error_code?: string;
  error_message?: string;
  processing_time?: number;
  source: ExecutionSource;
  created_at: string;
  updated_at: string;
}

export interface LogsResponse {
  total: number;
  logs: JobLog[];
}

export interface LogsStats {
  total: number;
  pending: number;
  processing: number;
  completed: number;
  failed: number;
  api_total: number;
  web_total: number;
}
