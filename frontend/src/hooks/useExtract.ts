// Hook para manejar extracción de audio con polling y persistencia

import { useState, useCallback, useRef, useEffect } from 'react';
import { api } from '../services/api';
import type { AudioFormat, AudioQuality, JobResponse, VideoInfo } from '../types';

const STORAGE_KEY = 'video-to-audio-current-job';

interface UseExtractOptions {
  pollingInterval?: number;
  onComplete?: (job: JobResponse) => void;
  onError?: (error: Error) => void;
}

export function useExtract(options: UseExtractOptions = {}) {
  const { pollingInterval = 1000, onComplete, onError } = options;

  const [isLoading, setIsLoading] = useState(false);
  const [isPolling, setIsPolling] = useState(false);
  const [job, setJob] = useState<JobResponse | null>(null);
  const [videoInfo, setVideoInfo] = useState<VideoInfo | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const jobIdRef = useRef<string | null>(null);

  // Guardar job_id en localStorage
  const saveJobId = (jobId: string) => {
    localStorage.setItem(STORAGE_KEY, jobId);
  };

  // Limpiar job_id de localStorage
  const clearJobId = () => {
    localStorage.removeItem(STORAGE_KEY);
  };

  // Obtener job_id guardado
  const getSavedJobId = (): string | null => {
    return localStorage.getItem(STORAGE_KEY);
  };

  // Poll job status
  const pollJob = useCallback(async (jobId: string) => {
    try {
      const updatedJob = await api.getJob(jobId);
      setJob(updatedJob);

      // Actualizar video info si existe
      if (updatedJob.video_info) {
        setVideoInfo(updatedJob.video_info);
      }

      if (updatedJob.status === 'completed') {
        setIsPolling(false);
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        clearJobId();
        onComplete?.(updatedJob);
      } else if (updatedJob.status === 'failed') {
        setIsPolling(false);
        setError(updatedJob.result?.error || 'Error en la extracción');
        if (pollingRef.current) {
          clearInterval(pollingRef.current);
          pollingRef.current = null;
        }
        clearJobId();
        onError?.(new Error(updatedJob.result?.error || 'Error'));
      }
    } catch (err) {
      console.error('Error polling job:', err);
    }
  }, [onComplete, onError]);

  // Iniciar polling para un job
  const startPolling = useCallback((jobId: string) => {
    jobIdRef.current = jobId;
    setIsPolling(true);
    setIsLoading(false);

    // Poll inmediatamente
    pollJob(jobId);

    // Luego cada intervalo
    pollingRef.current = setInterval(() => {
      if (jobIdRef.current) {
        pollJob(jobIdRef.current);
      }
    }, pollingInterval);
  }, [pollingInterval, pollJob]);

  // Recuperar job al montar (si existe uno pendiente)
  useEffect(() => {
    const savedJobId = getSavedJobId();
    
    if (savedJobId) {
      // Verificar si el job existe y su estado
      api.getJob(savedJobId)
        .then((existingJob) => {
          if (existingJob) {
            setJob(existingJob);
            if (existingJob.video_info) {
              setVideoInfo(existingJob.video_info);
            }

            // Si está en proceso, reanudar polling
            if (['pending', 'processing', 'downloading', 'extracting', 'uploading'].includes(existingJob.status)) {
              startPolling(savedJobId);
            } else {
              // Ya terminó (completed o failed)
              clearJobId();
              if (existingJob.status === 'completed') {
                onComplete?.(existingJob);
              }
            }
          } else {
            clearJobId();
          }
        })
        .catch(() => {
          clearJobId();
        });
    }

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
      const newJob = await api.startExtraction(url, format, quality);
      setJob(newJob);
      
      // Guardar en localStorage
      saveJobId(newJob.job_id);
      
      // Iniciar polling
      startPolling(newJob.job_id);

      return newJob;
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Error al iniciar extracción';
      setError(message);
      setIsLoading(false);
      onError?.(err instanceof Error ? err : new Error(message));
      return null;
    }
  }, [startPolling, onError]);

  // Reset state
  const reset = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
    clearJobId();
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
