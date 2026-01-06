// Formulario principal de extracción

import { useState, type FormEvent } from 'react';
import type { AudioFormat, AudioQuality } from '../types';

interface ExtractFormProps {
  onSubmit: (url: string, format: AudioFormat, quality: AudioQuality) => void;
  isLoading?: boolean;
  disabled?: boolean;
}

const formatOptions: { value: AudioFormat; label: string }[] = [
  { value: 'mp3', label: 'MP3' },
  { value: 'm4a', label: 'M4A' },
  { value: 'wav', label: 'WAV' },
  { value: 'opus', label: 'OPUS' },
];

const qualityOptions: { value: AudioQuality; label: string }[] = [
  { value: '128', label: '128 kbps' },
  { value: '192', label: '192 kbps' },
  { value: '256', label: '256 kbps' },
  { value: '320', label: '320 kbps' },
];

export function ExtractForm({ onSubmit, isLoading = false, disabled = false }: ExtractFormProps) {
  const [url, setUrl] = useState('');
  const [format, setFormat] = useState<AudioFormat>('mp3');
  const [quality, setQuality] = useState<AudioQuality>('192');

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (url.trim() && !disabled && !isLoading) {
      onSubmit(url.trim(), format, quality);
    }
  };

  const isValidUrl = url.includes('youtube.com') || url.includes('youtu.be') || url.includes('vimeo.com');

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {/* URL Input */}
      <div>
        <label htmlFor="url" className="block text-sm font-medium text-gray-300 mb-2">
          URL del Video
        </label>
        <div className="relative">
          <input
            type="url"
            id="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://youtube.com/watch?v=..."
            disabled={disabled || isLoading}
            className="w-full px-4 py-3 pl-12 bg-gray-800 border border-gray-700 rounded-xl text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:opacity-50 transition"
          />
          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-500">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
            </svg>
          </div>
        </div>
        {url && !isValidUrl && (
          <p className="mt-1 text-sm text-amber-400">Solo se admiten URLs de YouTube o Vimeo</p>
        )}
      </div>

      {/* Format & Quality */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="format" className="block text-sm font-medium text-gray-300 mb-2">
            Formato
          </label>
          <select
            id="format"
            value={format}
            onChange={(e) => setFormat(e.target.value as AudioFormat)}
            disabled={disabled || isLoading}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:opacity-50 transition cursor-pointer"
          >
            {formatOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="quality" className="block text-sm font-medium text-gray-300 mb-2">
            Calidad
          </label>
          <select
            id="quality"
            value={quality}
            onChange={(e) => setQuality(e.target.value as AudioQuality)}
            disabled={disabled || isLoading}
            className="w-full px-4 py-3 bg-gray-800 border border-gray-700 rounded-xl text-white focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent disabled:opacity-50 transition cursor-pointer"
          >
            {qualityOptions.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Submit */}
      <button
        type="submit"
        disabled={!url.trim() || !isValidUrl || disabled || isLoading}
        className="w-full py-4 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-xl transition transform hover:scale-[1.02] active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none flex items-center justify-center gap-2"
      >
        {isLoading ? (
          <>
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            <span>Procesando...</span>
          </>
        ) : (
          <>
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
            </svg>
            <span>Extraer Audio</span>
          </>
        )}
      </button>
    </form>
  );
}
