// Tipos compartidos

export type AudioFormat = 'mp3' | 'm4a' | 'wav' | 'opus';
export type AudioQuality = '128' | '192' | '256' | '320';
export type JobStatus = 'pending' | 'processing' | 'downloading' | 'extracting' | 'uploading' | 'completed' | 'failed';

export interface VideoInfo {
  id: string;
  title: string;
  duration_seconds: number;
  duration_formatted: string;
  thumbnail?: string;
  source: string;
  channel?: string;
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

export interface JobResponse {
  job_id: string;
  status: JobStatus;
  progress: number;
  message: string;
  created_at: string;
  video_info?: VideoInfo;
  result?: ExtractResult;
}

export interface HealthStatus {
  status: string;
  version: string;
  supabase_configured: boolean;
  max_duration_minutes: number;
}

export interface JobLog {
  id: string;
  status: string;
  progress: number;
  stage: string;
  video_url: string;
  video_title?: string;
  video_duration?: number;
  format?: string;
  quality?: string;
  audio_url?: string;
  file_size?: string;
  processing_time?: number;
  error_code?: string;
  error_message?: string;
  source: string;
  created_at: string;
  updated_at?: string;
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

export interface UploadResponse {
  status: string;
  audio_url?: string;
  filename?: string;
  file_size?: number;
  file_size_formatted?: string;
  original_size?: number;
  original_size_formatted?: string;
  duration?: number;
  duration_formatted?: string;
  format?: string;
  quality?: string;
  processing_time?: number;
  job_id?: string;
  error_code?: string;
  message?: string;
}
