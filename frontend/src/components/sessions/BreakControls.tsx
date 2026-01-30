// ============================================
// TIME TRACKER - BREAK CONTROLS COMPONENT
// Controls for starting/ending breaks
// ============================================
import { useState } from 'react';
import { useSessionStore, formatDuration } from '../../stores/sessionStore';
import { useNotifications } from '../../hooks/useNotifications';
import { cn } from '../../utils/helpers';
import type { BreakType } from '../../types';

export function BreakControls() {
  const {
    activeBreak,
    breakElapsedSeconds,
    isLoading,
    startBreak,
    endBreak,
  } = useSessionStore();

  const { addNotification } = useNotifications();
  const [showMenu, setShowMenu] = useState(false);

  const handleStartBreak = async (breakType: BreakType) => {
    setShowMenu(false);
    try {
      await startBreak({ break_type: breakType });
      const labels: Record<BreakType, string> = {
        short: 'Short break',
        lunch: 'Lunch break',
        other: 'Break',
      };
      addNotification({
        type: 'info',
        title: `${labels[breakType]} Started`,
        message: 'Your timer is paused. Enjoy your break!',
        duration: 3000,
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to Start Break',
        message: 'Please try again',
      });
    }
  };

  const handleEndBreak = async () => {
    try {
      await endBreak();
      addNotification({
        type: 'success',
        title: 'Break Ended',
        message: `You were on break for ${formatDuration(breakElapsedSeconds)}. Back to work!`,
        duration: 3000,
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to End Break',
        message: 'Please try again',
      });
    }
  };

  // If on break, show end break button
  if (activeBreak) {
    return (
      <button
        onClick={handleEndBreak}
        disabled={isLoading}
        className={cn(
          'px-4 py-2 rounded-lg font-semibold text-sm transition-all',
          'bg-amber-700 hover:bg-amber-800 text-white',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
      >
        {isLoading ? 'Loading...' : '☕ End Break'}
      </button>
    );
  }

  // Show break menu
  return (
    <div className="relative">
      <button
        onClick={() => setShowMenu(!showMenu)}
        disabled={isLoading}
        className={cn(
          'px-4 py-2 rounded-lg font-semibold text-sm transition-all',
          'bg-white/20 hover:bg-white/30 text-white border border-white/30',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
      >
        ☕ Break
      </button>

      {showMenu && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => setShowMenu(false)}
          />
          
          {/* Dropdown menu */}
          <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg z-20 py-1 border">
            <button
              onClick={() => handleStartBreak('short')}
              className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
            >
              <span>⚡</span>
              <span>Short Break</span>
              <span className="text-xs text-gray-400 ml-auto">5-15 min</span>
            </button>
            <button
              onClick={() => handleStartBreak('lunch')}
              className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
            >
              <span>🍽️</span>
              <span>Lunch Break</span>
              <span className="text-xs text-gray-400 ml-auto">30-60 min</span>
            </button>
            <button
              onClick={() => handleStartBreak('other')}
              className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
            >
              <span>🚶</span>
              <span>Other Break</span>
            </button>
          </div>
        </>
      )}
    </div>
  );
}
