// Hook para manejar extracción de audio con polling

import { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../services/api';
import type { AudioFormat, AudioQuality, Job, VideoInfo } from '../types';

interface UseExtractOptions {
  pollingInterval?: number;
  onComplete?: (job: Job) => void;
  onError?: (error: Error) => void;
}

export function useExtract(options: UseExtractOptions = {}) {
  const { pollingInterval = 1000, onComplete, onError } = options;

  const [isLoading, setIsLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);

  // Limpiar polling al desmontar
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current);
      }
    };
  }, []);

  // Fetch video info
  const fetchInfo = useCallback(async (url: string) => {
    setIsLoading(true);
    setError(null);
    setVideoInfo(null);

    try {
      const info = await api.getVideoInfo(url);
      setVideoInfo(info);
      return info;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al obtener información';
      setError(message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Poll job status
  const pollJob = useCallback(async (jobId: string) => {
    try {
      const updatedJob = await api.getJob(jobId);
      setJob(updatedJob);

      if (updatedJob.status === 'completed') {
        setIsPolling(false);
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        onComplete?.(updatedJob);
      } else if (updatedJob.status === 'failed') {
        setIsPolling(false);
        setError(updatedJob.result?.error || 'Error en la extracción');
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        onError?.(new Error(updatedJob.result?.error || 'Error'));
      }
    } catch (err) {
      console.error('Error polling job:', err);
    }
  }, [onComplete, onError]);

  // Start extraction
  const extract = useCallback(async (
    url: string,
    format: AudioFormat = 'mp3',
    quality: AudioQuality = '192'
  ) => {
    // Limpiar estado previo
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }

    setIsLoading(true);
    setIsPolling(false);
    setError(null);
    setJob(null);

    try {
      const newJob = await api.startExtraction({ url, format, quality });
      setJob(newJob);
      jobIdRef.current = newJob.job_id;

      // Iniciar polling
      setIsPolling(true);
      setIsLoading(false);

      pollingRef.current = setInterval(() => {
        if (jobIdRef.current) {
          pollJob(jobIdRef.current);
        }
      }, pollingInterval);

      return newJob;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al iniciar extracción';
      setError(message);
      setIsLoading(false);
      onError?.(err instanceof Error ? err : new Error(message));
      return null;
    }
  }, [pollingInterval, pollJob, onError]);

  // Reset state
  const reset = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    setIsLoading(false);
    setIsPolling(false);
    setJob(null);
    setVideoInfo(null);
    setError(null);
    jobIdRef.current = null;
  }, []);

  return {
    // State
    isLoading,
    isPolling,
    isProcessing: isLoading || isPolling,
    job,
    videoInfo,
    error,
    progress: job?.progress ?? 0,
    status: job?.status ?? null,

    // Actions
    fetchInfo,
    extract,
    reset,
  };
}
