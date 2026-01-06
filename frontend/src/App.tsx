// App Principal - Video to Audio

import { useCallback, useState, useEffect } from 'react';
import { ExtractForm, ProgressBar, ResultCard, VideoPreview, LogsPanel } from './components';
import { useExtract } from './hooks/useExtract';
import { api } from './services/api';
import type { AudioFormat, AudioQuality, HealthStatus } from './types';

function App() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [showToast, setShowToast] = useState<string | null>(null);

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
            <p className="text-gray-400">Extrae audio de YouTube y Vimeo en segundos</p>
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
            {job?.status === 'completed' && job.result ? (
              <ResultCard
                result={job.result}
                videoInfo={job.video_info}
                onNewExtraction={reset}
              />
            ) : job?.status === 'failed' && job.result ? (
              <ResultCard
                result={job.result}
                onNewExtraction={reset}
              />
            ) : (
              <>
                {/* Form */}
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
          </div>

          {/* Footer */}
          <div className="text-center mt-6 text-gray-500 text-sm">
            <p>Soporta YouTube y Vimeo • Max {health?.max_duration_minutes || 60} min</p>
          </div>
        </div>

        {/* Logs Panel */}
        <LogsPanel />
      </div>
    </div>
  );
}

export default App;
