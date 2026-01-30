// ============================================
// TIME TRACKER - MEETING CONTROLS COMPONENT
// Controls for starting/ending meetings
// ============================================
import { useState } from 'react';
import { useSessionStore, formatDuration } from '../../stores/sessionStore';
import { useTimerStore } from '../../stores/timerStore';
import { useNotifications } from '../../hooks/useNotifications';
import { cn } from '../../utils/helpers';
import type { MeetingType } from '../../types';

export function MeetingControls() {
  const {
    activeMeeting,
    meetingElapsedSeconds,
    isLoading,
    startMeeting,
    endMeeting,
  } = useSessionStore();

  const { fetchTimer } = useTimerStore();

  const { addNotification } = useNotifications();
  const [showMenu, setShowMenu] = useState(false);
  const [showTitleInput, setShowTitleInput] = useState(false);
  const [meetingTitle, setMeetingTitle] = useState('');
  const [selectedType, setSelectedType] = useState<MeetingType>('internal');

  const handleStartMeeting = async () => {
    setShowMenu(false);
    setShowTitleInput(false);
    try {
      await startMeeting({ 
        title: meetingTitle || undefined, 
        meeting_type: selectedType 
      });
      // Refresh timer state to get isPaused=true
      await fetchTimer();
      const labels: Record<MeetingType, string> = {
        internal: 'Internal meeting',
        external: 'External meeting',
        client: 'Client meeting',
      };
      addNotification({
        type: 'info',
        title: `${labels[selectedType]} Started`,
        message: meetingTitle || 'Your task timer is paused.',
        duration: 3000,
      });
      setMeetingTitle('');
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to Start Meeting',
        message: 'Please try again',
      });
    }
  };

  const handleEndMeeting = async () => {
    try {
      await endMeeting();
      // Refresh timer state to get isPaused=false and resume counting
      await fetchTimer();
      addNotification({
        type: 'success',
        title: 'Meeting Ended',
        message: `Meeting lasted ${formatDuration(meetingElapsedSeconds)}. Back to your task!`,
        duration: 3000,
      });
    } catch {
      addNotification({
        type: 'error',
        title: 'Failed to End Meeting',
        message: 'Please try again',
      });
    }
  };

  const selectMeetingType = (type: MeetingType) => {
    setSelectedType(type);
    setShowTitleInput(true);
  };

  // If in meeting, show end meeting button
  if (activeMeeting) {
    return (
      <button
        onClick={handleEndMeeting}
        disabled={isLoading}
        className={cn(
          'px-4 py-2 rounded-lg font-semibold text-sm transition-all',
          'bg-blue-700 hover:bg-blue-800 text-white',
          isLoading && 'opacity-50 cursor-not-allowed'
        )}
      >
        {isLoading ? 'Loading...' : '📅 End Meeting'}
      </button>
    );
  }

  // Show meeting menu
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
        📅 Meeting
      </button>

      {showMenu && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-10" 
            onClick={() => {
              setShowMenu(false);
              setShowTitleInput(false);
              setMeetingTitle('');
            }}
          />
          
          {/* Dropdown menu */}
          <div className="absolute right-0 mt-2 w-64 bg-white rounded-lg shadow-lg z-20 py-1 border">
            {!showTitleInput ? (
              // Meeting type selection
              <>
                <button
                  onClick={() => selectMeetingType('internal')}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                >
                  <span>👥</span>
                  <span>Internal Meeting</span>
                  <span className="text-xs text-gray-400 ml-auto">Team</span>
                </button>
                <button
                  onClick={() => selectMeetingType('external')}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                >
                  <span>🌐</span>
                  <span>External Meeting</span>
                  <span className="text-xs text-gray-400 ml-auto">Partner</span>
                </button>
                <button
                  onClick={() => selectMeetingType('client')}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-100 flex items-center gap-2"
                >
                  <span>💼</span>
                  <span>Client Meeting</span>
                  <span className="text-xs text-gray-400 ml-auto">Customer</span>
                </button>
              </>
            ) : (
              // Title input
              <div className="p-3">
                <label className="block text-xs font-medium text-gray-500 mb-1">
                  Meeting Title (optional)
                </label>
                <input
                  type="text"
                  value={meetingTitle}
                  onChange={(e) => setMeetingTitle(e.target.value)}
                  placeholder="e.g., Sprint Planning"
                  className="w-full px-3 py-2 text-sm border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-2"
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      handleStartMeeting();
                    }
                  }}
                  autoFocus
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => setShowTitleInput(false)}
                    className="flex-1 px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded-lg"
                  >
                    Back
                  </button>
                  <button
                    onClick={handleStartMeeting}
                    className="flex-1 px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg"
                  >
                    Start
                  </button>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
