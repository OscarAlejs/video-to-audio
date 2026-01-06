// Panel de Logs de Ejecuciones

import { useState, useEffect } from 'react';
import type { ExecutionLog, LogsStats } from '../types';
import { api } from '../services/api';

type TabType = 'all' | 'api' | 'web' | 'errors';

export function LogsPanel() {
  const [activeTab, setActiveTab] = useState<TabType>('all');
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  const [stats, setStats] = useState<LogsStats | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  const fetchLogs = async () => {
    setIsLoading(true);
    try {
      let data;
      switch (activeTab) {
        case 'api':
          data = await api.getApiLogs();
          break;
        case 'web':
          data = await api.getWebLogs();
          break;
        case 'errors':
          data = await api.getErrorLogs();
          break;
        default:
          data = await api.getAllLogs();
      }
      setLogs(data.logs);
    } catch (err) {
      console.error('Error fetching logs:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const data = await api.getLogsStats();
      setStats(data);
    } catch (err) {
      console.error('Error fetching stats:', err);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchLogs();
      fetchStats();
    }
  }, [activeTab, isOpen]);

  const handleClearLogs = async () => {
    if (window.confirm('¿Estás seguro de eliminar todos los logs?')) {
      await api.clearLogs();
      fetchLogs();
      fetchStats();
    }
  };

  const formatDate = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('es-ES', {
      day: '2-digit',
      month: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const truncateUrl = (url: string, maxLength: number = 40) => {
    if (url.length <= maxLength) return url;
    return url.substring(0, maxLength) + '...';
  };

  const tabs: { id: TabType; label: string; count?: number }[] = [
    { id: 'all', label: 'Todos', count: stats?.total },
    { id: 'api', label: 'API', count: stats?.api_total },
    { id: 'web', label: 'Web', count: stats?.web_total },
    { id: 'errors', label: 'Errores', count: (stats?.api_errors || 0) + (stats?.web_errors || 0) },
  ];

  return (
    <div className="mt-8 w-full max-w-4xl mx-auto">
      {/* Toggle Button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800/50 hover:bg-gray-800/70 border border-gray-700/50 rounded-xl transition"
      >
        <div className="flex items-center gap-2">
          <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01" />
          </svg>
          <span className="text-white font-medium">Historial de Ejecuciones</span>
          {stats && (
            <span className="px-2 py-0.5 bg-gray-700 rounded-full text-xs text-gray-300">
              {stats.total} total
            </span>
          )}
        </div>
        <svg
          className={`w-5 h-5 text-gray-400 transition-transform ${isOpen ? 'rotate-180' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {/* Panel Content */}
      {isOpen && (
        <div className="mt-2 bg-gray-800/50 backdrop-blur-xl border border-gray-700/50 rounded-xl overflow-hidden">
          {/* Stats Summary */}
          {stats && (
            <div className="grid grid-cols-4 gap-2 p-4 border-b border-gray-700/50">
              <div className="text-center">
                <div className="text-2xl font-bold text-white">{stats.total}</div>
                <div className="text-xs text-gray-400">Total</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-400">{stats.api_total}</div>
                <div className="text-xs text-gray-400">API</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-purple-400">{stats.web_total}</div>
                <div className="text-xs text-gray-400">Web</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-red-400">
                  {(stats.api_errors || 0) + (stats.web_errors || 0)}
                </div>
                <div className="text-xs text-gray-400">Errores</div>
              </div>
            </div>
          )}

          {/* Tabs */}
          <div className="flex items-center justify-between border-b border-gray-700/50 px-4">
            <div className="flex">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`px-4 py-3 text-sm font-medium transition border-b-2 -mb-px ${
                    activeTab === tab.id
                      ? 'border-purple-500 text-purple-400'
                      : 'border-transparent text-gray-400 hover:text-white'
                  }`}
                >
                  {tab.label}
                  {tab.count !== undefined && (
                    <span className="ml-1.5 text-xs text-gray-500">({tab.count})</span>
                  )}
                </button>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                onClick={fetchLogs}
                className="p-2 text-gray-400 hover:text-white transition"
                title="Refrescar"
              >
                <svg className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              </button>
              <button
                onClick={handleClearLogs}
                className="p-2 text-gray-400 hover:text-red-400 transition"
                title="Limpiar logs"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </button>
            </div>
          </div>

          {/* Logs List */}
          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-12">
                <svg className="animate-spin h-8 w-8 text-purple-500" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              </div>
            ) : logs.length === 0 ? (
              <div className="text-center py-12 text-gray-500">
                <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                </svg>
                <p>No hay ejecuciones registradas</p>
              </div>
            ) : (
              <div className="divide-y divide-gray-700/50">
                {logs.map((log) => (
                  <div key={log.id} className="p-4 hover:bg-gray-700/20 transition">
                    <div className="flex items-start justify-between gap-4">
                      {/* Left side */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          {/* Source Badge */}
                          <span
                            className={`px-2 py-0.5 text-xs font-medium rounded ${
                              log.source === 'api'
                                ? 'bg-blue-500/20 text-blue-400'
                                : 'bg-purple-500/20 text-purple-400'
                            }`}
                          >
                            {log.source.toUpperCase()}
                          </span>
                          {/* Status Badge */}
                          <span
                            className={`px-2 py-0.5 text-xs font-medium rounded ${
                              log.status === 'success'
                                ? 'bg-green-500/20 text-green-400'
                                : 'bg-red-500/20 text-red-400'
                            }`}
                          >
                            {log.status === 'success' ? '✓ Éxito' : '✗ Error'}
                          </span>
                          {/* Time */}
                          <span className="text-xs text-gray-500">{formatDate(log.timestamp)}</span>
                        </div>

                        {/* Video Title or URL */}
                        <h4 className="text-sm font-medium text-white truncate">
                          {log.video_title || truncateUrl(log.video_url)}
                        </h4>

                        {/* Details */}
                        {log.status === 'success' ? (
                          <div className="flex items-center gap-3 mt-1 text-xs text-gray-400">
                            {log.format && <span>📁 {log.format.toUpperCase()}</span>}
                            {log.quality && <span>🎵 {log.quality}kbps</span>}
                            {log.file_size_formatted && <span>💾 {log.file_size_formatted}</span>}
                            {log.duration_formatted && <span>⏱️ {log.duration_formatted}</span>}
                            {log.processing_time && <span>⚡ {log.processing_time}s</span>}
                          </div>
                        ) : (
                          <div className="mt-1">
                            {log.error_code && (
                              <span className="text-xs text-red-400 font-mono">{log.error_code}</span>
                            )}
                            {log.error_message && (
                              <p className="text-xs text-red-300 mt-0.5 line-clamp-2">{log.error_message}</p>
                            )}
                          </div>
                        )}
                      </div>

                      {/* Right side - Audio URL button */}
                      {log.status === 'success' && log.audio_url && (
                        <a
                          href={log.audio_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex-shrink-0 p-2 text-gray-400 hover:text-white bg-gray-700/50 hover:bg-gray-700 rounded-lg transition"
                          title="Abrir audio"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
