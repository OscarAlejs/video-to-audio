// Barra de progreso animada

interface ProgressBarProps {
  progress: number;
  status?: string;
  className?: string;
}

export function ProgressBar({ progress, status, className = '' }: ProgressBarProps) {
  const getStatusColor = () => {
    if (status === 'failed') return 'bg-red-500';
    if (status === 'completed') return 'bg-green-500';
    return 'bg-gradient-to-r from-purple-500 to-pink-500';
  };

  return (
    <div className={`w-full ${className}`}>
      <div className="flex justify-between mb-1 text-sm">
        <span className="text-gray-400">{status || 'Procesando...'}</span>
        <span className="text-gray-400 font-mono">{progress}%</span>
      </div>
      <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
        <div
          className={`h-full transition-all duration-300 ease-out ${getStatusColor()}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
