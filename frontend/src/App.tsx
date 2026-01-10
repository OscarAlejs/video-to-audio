// App Principal - Video to Audio

import { useCallback, useState, useEffect } from 'react';
import { ExtractForm, ProgressBar, ResultCard, VideoPreview, LogsPanel, FileUpload } from './components';
import { useExtract } from './hooks/useExtract';
import { api } from './services/api';
import type { AudioFormat, AudioQuality, HealthStatus, UploadResponse } from './types';

type InputMode = 'url' | 'upload';

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [showToast, setShowToast] = useState<string | null>(null);
  const [inputMode, setInputMode] = useState<InputMode>('url');
  
  // Upload state
  const [isUploading, setIsUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<UploadResponse | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);

  const {
    isProcessing,
    job,
    videoInfo,
    error,
    progress,
    status,
    extract,
    reset,
  } = useExtract({
    onComplete: () => {
      setShowToast('¡Audio extraído exitosamente!');
      setTimeout(() => setShowToast(null), 3000);
    },
  });

  // Check API health on mount
  useEffect(() => {
    api.health()
      .then(setHealth)
      .catch(() => setHealth(null));
  }, []);

  const handleExtract = useCallback((url: string, format: AudioFormat, quality: AudioQuality) => {
    extract(url, format, quality);
  }, [extract]);

  const handleUpload = useCallback(async (file: File, format: AudioFormat, quality: AudioQuality) => {
    setIsUploading(true);
    setUploadError(null);
    setUploadResult(null);
    setUploadProgress(10);

    try {
      // Simulate progress while uploading
      const progressInterval = setInterval(() => {
        setUploadProgress(prev => Math.min(prev + 10, 90));
      }, 500);

      const result = await api.uploadVideo(file, format, quality);
      
      clearInterval(progressInterval);
      setUploadProgress(100);

      if (result.status === 'success') {
        setUploadResult(result);
        setShowToast('¡Audio extraído exitosamente!');
        setTimeout(() => setShowToast(null), 3000);
      } else {
        setUploadError(result.message || 'Error al procesar el archivo');
      }
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : 'Error desconocido');
    } finally {
      setIsUploading(false);
    }
  }, []);

  const handleReset = useCallback(() => {
    reset();
    setUploadResult(null);
    setUploadError(null);
    setUploadProgress(0);
  }, [reset]);

  const getStatusMessage = () => {
    switch (status) {
      case 'pending': return 'Iniciando...';
      case 'processing': return 'Obteniendo información...';
      case 'downloading': return 'Descargando video...';
      case 'extracting': return 'Extrayendo audio...';
      case 'uploading': return 'Subiendo a la nube...';
      case 'completed': return '¡Completado!';
      case 'failed': return 'Error';
      default: return 'Procesando...';
    }
  };

  const isLoading = isProcessing || isUploading;
  const hasResult = (job?.status === 'completed' && job.result) || (uploadResult?.status === 'success');
  const hasError = (job?.status === 'failed' && job.result) || uploadError;

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900/20 to-gray-900">
      {/* Background Pattern */}
      <div className="absolute inset-0 bg-[url('data:image/svg+xml,%3Csvg%20width%3D%2260%22%20height%3D%2260%22%20viewBox%3D%220%200%2060%2060%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%3E%3Cg%20fill%3D%22none%22%20fill-rule%3D%22evenodd%22%3E%3Cg%20fill%3D%22%239C92AC%22%20fill-opacity%3D%220.03%22%3E%3Cpath%20d%3D%22M36%2034v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6%2034v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6%204V0H4v4H0v2h4v4h2V6h4V4H6z%22%2F%3E%3C%2Fg%3E%3C%2Fg%3E%3C%2Fsvg%3E')] opacity-40" />

      {/* Toast Notification */}
      {showToast && (
        <div className="fixed top-4 right-4 z-50 animate-fade-in">
          <div className="bg-green-500 text-white px-6 py-3 rounded-lg shadow-lg flex items-center gap-2">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {showToast}
          </div>
        </div>
      )}

      <div className="relative min-h-screen flex flex-col items-center justify-center p-4">
        {/* Main Card */}
        <div className="w-full max-w-lg">
          {/* Header */}
          <div className="text-center mb-8">
            <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500 to-pink-500 mb-4 shadow-lg shadow-purple-500/25">
              <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
              </svg>
            </div>
            <h1 className="text-3xl font-bold text-white mb-2">Video to Audio</h1>
            <p className="text-gray-400">Extrae audio de videos en segundos</p>
          </div>

          {/* Card */}
          <div className="bg-gray-800/50 backdrop-blur-xl rounded-2xl p-6 border border-gray-700/50 shadow-2xl">
            {/* Status Badge */}
            {health && (
              <div className="flex justify-center mb-4">
                <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs ${health.supabase_configured ? 'bg-green-500/10 text-green-400' : 'bg-amber-500/10 text-amber-400'}`}>
                  <span className={`w-2 h-2 rounded-full ${health.supabase_configured ? 'bg-green-500' : 'bg-amber-500'}`} />
                  {health.supabase_configured ? 'Conectado' : 'Supabase no configurado'}
                </div>
              </div>
            )}

            {/* Show Result if completed */}
            {hasResult ? (
              uploadResult?.status === 'success' ? (
                // Upload Result
                <div className="bg-green-500/10 border border-green-500/30 rounded-xl p-6">
                  <div className="flex items-center gap-3 mb-4">
                    <div className="w-12 h-12 rounded-full bg-green-500/20 flex items-center justify-center">
                      <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-white">¡Extracción completada!</h3>
                      <p className="text-green-400 text-sm">Tu audio está listo</p>
                    </div>
                  </div>

                  <div className="bg-gray-800/50 rounded-lg p-4 mb-4">
                    <h4 className="font-medium text-white mb-2 truncate">
                      {uploadResult.filename}
                    </h4>
                    <div className="grid grid-cols-2 gap-2 text-sm text-gray-400">
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                        </svg>
                        <span>{uploadResult.format?.toUpperCase()}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                        </svg>
                        <span>{uploadResult.file_size_formatted}</span>
                      </div>
                      {uploadResult.duration_formatted && (
                        <div className="flex items-center gap-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <span>{uploadResult.duration_formatted}</span>
                        </div>
                      )}
                      {uploadResult.processing_time && (
                        <div className="flex items-center gap-2">
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          <span>{uploadResult.processing_time}s</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex gap-3">
                    <a
                      href={uploadResult.audio_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-lg font-medium transition"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                      Descargar
                    </a>
                    <button
                      onClick={handleReset}
                      className="flex items-center justify-center gap-2 px-4 py-3 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition"
                    >
                      <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                  </div>
                </div>
              ) : (
                <ResultCard
                  result={job!.result!}
                  videoInfo={job!.video_info}
                  onNewExtraction={handleReset}
                />
              )
            ) : hasError ? (
              uploadError ? (
                // Upload Error
                <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-6 text-center">
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/20 flex items-center justify-center">
                    <svg className="w-8 h-8 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </div>
                  <h3 className="text-xl font-semibold text-white mb-2">Error</h3>
                  <p className="text-red-400 mb-4">{uploadError}</p>
                  <button
                    onClick={handleReset}
                    className="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition"
                  >
                    Intentar de nuevo
                  </button>
                </div>
              ) : (
                <ResultCard
                  result={job!.result!}
                  onNewExtraction={handleReset}
                />
              )
            ) : (
              <>
                {/* Input Mode Tabs */}
                <div className="flex mb-6 bg-gray-900/50 rounded-xl p-1">
                  <button
                    onClick={() => setInputMode('url')}
                    disabled={isLoading}
                    className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition ${
                      inputMode === 'url'
                        ? 'bg-purple-600 text-white'
                        : 'text-gray-400 hover:text-white'
                    } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                    </svg>
                    URL
                  </button>
                  <button
                    onClick={() => setInputMode('upload')}
                    disabled={isLoading}
                    className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-medium transition ${
                      inputMode === 'upload'
                        ? 'bg-purple-600 text-white'
                        : 'text-gray-400 hover:text-white'
                    } ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                  >
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                    </svg>
                    Subir archivo
                  </button>
                </div>

                {/* URL Form */}
                {inputMode === 'url' && (
                  <>
                    <ExtractForm
                      onSubmit={handleExtract}
                      isLoading={isProcessing}
                      disabled={!health?.supabase_configured}
                    />

                    {/* Error Message */}
                    {error && !job?.result && (
                      <div className="mt-4 p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
                        <p className="text-red-400 text-sm">{error}</p>
                      </div>
                    )}

                    {/* Video Preview */}
                    {(videoInfo || job?.video_info) && (
                      <div className="mt-4">
                        <VideoPreview info={videoInfo || job!.video_info!} />
                      </div>
                    )}

                    {/* Progress Bar */}
                    {isProcessing && (
                      <div className="mt-6">
                        <ProgressBar
                          progress={progress}
                          status={getStatusMessage()}
                        />
                        <p className="text-center text-gray-500 text-sm mt-2">
                          {job?.message || 'Procesando...'}
                        </p>
                      </div>
                    )}
                  </>
                )}

                {/* File Upload */}
                {inputMode === 'upload' && (
                  <>
                    <FileUpload
                      onUpload={handleUpload}
                      isLoading={isUploading}
                      disabled={!health?.supabase_configured}
                    />

                    {/* Upload Progress */}
                    {isUploading && (
                      <div className="mt-6">
                        <ProgressBar
                          progress={uploadProgress}
                          status={uploadProgress < 30 ? 'Subiendo archivo...' : uploadProgress < 70 ? 'Extrayendo audio...' : 'Finalizando...'}
                        />
                      </div>
                    )}
                  </>
                )}
              </>
            )}
          </div>

          {/* Footer */}
          <div className="text-center mt-6 text-gray-500 text-sm">
            <p>
              {inputMode === 'url' 
                ? `Soporta YouTube y Vimeo • Max ${health?.max_duration_minutes || 60} min`
                : 'Soporta MP4, MKV, WebM, AVI, MOV • Max 500MB'
              }
            </p>
          </div>
        </div>

        {/* Logs Panel */}
        <LogsPanel />
      </div>
    </div>
  );
}

export default App;
