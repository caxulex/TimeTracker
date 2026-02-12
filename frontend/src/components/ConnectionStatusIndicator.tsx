// ============================================
// TIME TRACKER - CONNECTION STATUS INDICATOR
// TASK 7.2: Visual WebSocket connection status + reconnect notification
// ============================================
import { useWebSocketContext } from '../contexts/WebSocketContext';
import type { ConnectionState } from '../contexts/WebSocketContext';

const STATE_CONFIG: Record<ConnectionState, {
  color: string;
  pulseClass: string;
  label: string;
}> = {
  connected: {
    color: 'bg-green-500',
    pulseClass: '',
    label: 'Connected',
  },
  connecting: {
    color: 'bg-yellow-400',
    pulseClass: 'animate-pulse',
    label: 'Connecting...',
  },
  reconnecting: {
    color: 'bg-yellow-400',
    pulseClass: 'animate-pulse',
    label: 'Reconnecting...',
  },
  disconnected: {
    color: 'bg-gray-400',
    pulseClass: '',
    label: 'Disconnected',
  },
  failed: {
    color: 'bg-red-500',
    pulseClass: '',
    label: 'Connection failed',
  },
};

export function ConnectionStatusDot() {
  const { connectionState } = useWebSocketContext();
  const config = STATE_CONFIG[connectionState];

  return (
    <div className="relative group" title={`Real-time: ${config.label}`}>
      <span
        className={`inline-block w-2 h-2 rounded-full ${config.color} ${config.pulseClass}`}
        data-testid="connection-status-dot"
        aria-label={`WebSocket status: ${config.label}`}
      />
      {/* Tooltip on hover */}
      <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 px-2 py-0.5 text-xs text-white bg-gray-800 dark:bg-gray-700 rounded whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50">
        {config.label}
      </span>
    </div>
  );
}

export function ReconnectBanner() {
  const { showReconnectNotification, reconnectNow, connectionState } = useWebSocketContext();

  if (!showReconnectNotification) return null;

  return (
    <div className="fixed top-0 left-0 right-0 z-[9999] bg-yellow-50 dark:bg-yellow-900/50 border-b border-yellow-200 dark:border-yellow-800 px-4 py-2 flex items-center justify-center gap-3 text-sm shadow-sm">
      <span className="text-yellow-800 dark:text-yellow-200">
        {connectionState === 'failed'
          ? '\u26A0 Real-time connection lost. Updates may be delayed.'
          : '\u26A0 Real-time connection lost. Retrying...'}
      </span>
      <button
        onClick={reconnectNow}
        className="px-3 py-1 text-xs font-medium rounded bg-yellow-600 hover:bg-yellow-700 text-white transition-colors"
      >
        Reconnect Now
      </button>
    </div>
  );
}
