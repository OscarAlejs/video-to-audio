// Componente para subir archivos de video

import { useState, useRef, type ChangeEvent, type DragEvent } from 'react';
import type { AudioFormat, AudioQuality } from '../types';

interface FileUploadProps {
  onUpload: (file: File, format: AudioFormat, quality: AudioQuality) => void;
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

const SUPPORTED_FORMATS = [
  'video/mp4',
  'video/webm',
  'video/x-matroska',
  'video/avi',
  'video/quicktime',
  'video/x-flv',
  'video/x-ms-wmv',
  'video/mpeg',
  'video/3gpp',
];

const SUPPORTED_EXTENSIONS = ['.mp4', '.mkv', '.webm', '.avi', '.mov', '.flv', '.wmv', '.mpeg', '.mpg', '.3gp'];

export function FileUpload({ onUpload, isLoading = false, disabled = false }: FileUploadProps) {
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState<AudioFormat>('mp3');
  const [quality, setQuality] = useState<AudioQuality>('192');
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (f: File): boolean => {
    setError(null);
    
    // Validar tipo MIME o extensión
    const extension = '.' + f.name.split('.').pop()?.toLowerCase();
    const isValidType = SUPPORTED_FORMATS.includes(f.type) || SUPPORTED_EXTENSIONS.includes(extension);
    
    if (!isValidType) {
      setError('Formato no soportado. Usa: MP4, MKV, WebM, AVI, MOV, FLV, WMV');
      return false;
    }
    
    // Validar tamaño (max 500MB)
    const maxSize = 500 * 1024 * 1024;
    if (f.size > maxSize) {
      setError('Archivo muy grande. Máximo: 500MB');
      return false;
    }
    
    return true;
  };

  const handleFileSelect = (f: File) => {
    if (validateFile(f)) {
      setFile(f);
    }
  };

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) {
      handleFileSelect(f);
    }
  };

  const handleDragOver = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    
    const f = e.dataTransfer.files?.[0];
    if (f) {
      handleFileSelect(f);
    }
  };

  const handleSubmit = () => {
    if (file && !disabled && !isLoading) {
      onUpload(file, format, quality);
    }
  };

  const handleClear = () => {
    setFile(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-4">
      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        className={`
          relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-all
          ${isDragging 
            ? 'border-purple-500 bg-purple-500/10' 
            : file 
              ? 'border-green-500/50 bg-green-500/5' 
              : 'border-gray-600 hover:border-gray-500 hover:bg-gray-800/30'
          }
          ${(disabled || isLoading) ? 'opacity-50 cursor-not-allowed' : ''}
        `}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept={SUPPORTED_EXTENSIONS.join(',')}
          onChange={handleInputChange}
          disabled={disabled || isLoading}
          className="hidden"
        />
        
        {file ? (
          <div className="space-y-2">
            <div className="w-12 h-12 mx-auto rounded-full bg-green-500/20 flex items-center justify-center">
              <svg className="w-6 h-6 text-green-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <p className="text-white font-medium truncate max-w-xs mx-auto" title={file.name}>
              {file.name}
            </p>
            <p className="text-gray-400 text-sm">{formatFileSize(file.size)}</p>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleClear();
              }}
              className="text-gray-400 hover:text-white text-sm underline"
            >
              Cambiar archivo
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <div className="w-12 h-12 mx-auto rounded-full bg-gray-700 flex items-center justify-center">
              <svg className="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <div>
              <p className="text-white font-medium">
                {isDragging ? 'Suelta el archivo aquí' : 'Arrastra un video o haz clic'}
              </p>
              <p className="text-gray-400 text-sm mt-1">
                MP4, MKV, WebM, AVI, MOV • Max 500MB
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
          <p className="text-red-400 text-sm">{error}</p>
        </div>
      )}

      {/* Options - only show when file is selected */}
      {file && (
        <>
          {/* Format & Quality */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label htmlFor="upload-format" className="block text-sm font-medium text-gray-300 mb-2">
                Formato
              </label>
              <select
                id="upload-format"
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
              <label htmlFor="upload-quality" className="block text-sm font-medium text-gray-300 mb-2">
                Calidad
              </label>
              <select
                id="upload-quality"
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

          {/* Submit Button */}
          <button
            type="button"
            onClick={handleSubmit}
            disabled={!file || disabled || isLoading}
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
        </>
      )}
    </div>
  );
}
