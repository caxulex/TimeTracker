// ============================================
// KEYBOARD SHORTCUTS HOOK
// Global keyboard shortcuts for common actions
// ============================================
import { useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTimerStore } from '../stores/timerStore';
import { useAuthStore } from '../stores/authStore';

interface ShortcutHandlers {
  onStartTimer?: () => void;
  onStopTimer?: () => void;
  onNewEntry?: () => void;
}

export function useKeyboardShortcuts(handlers: ShortcutHandlers = {}) {
  const navigate = useNavigate();
  const location = useLocation();
  const { isAuthenticated } = useAuthStore();
  const { isRunning, stopTimer } = useTimerStore();

  const handleKeyDown = useCallback(
    (event: KeyboardEvent) => {
      // Don't trigger shortcuts when typing in inputs
      const target = event.target as HTMLElement;
      if (
        target.tagName === 'INPUT' ||
        target.tagName === 'TEXTAREA' ||
        target.isContentEditable
      ) {
        return;
      }

      // Only handle shortcuts when authenticated
      if (!isAuthenticated) return;

      const isCtrlOrCmd = event.ctrlKey || event.metaKey;

      // Ctrl/Cmd + S: Start timer (if not running)
      if (isCtrlOrCmd && event.key === 's') {
        event.preventDefault();
        if (!isRunning) {
          if (handlers.onStartTimer) {
            handlers.onStartTimer();
          } else {
            // Navigate to time page to start a timer
            navigate('/time');
          }
        }
      }

      // Ctrl/Cmd + E: Stop timer (if running)
      if (isCtrlOrCmd && event.key === 'e') {
        event.preventDefault();
        if (isRunning) {
          if (handlers.onStopTimer) {
            handlers.onStopTimer();
          } else {
            stopTimer();
          }
        }
      }

      // Ctrl/Cmd + N: New entry
      if (isCtrlOrCmd && event.key === 'n') {
        event.preventDefault();
        if (handlers.onNewEntry) {
          handlers.onNewEntry();
        } else {
          navigate('/time');
        }
      }

      // Navigation shortcuts (without Ctrl/Cmd)
      if (!isCtrlOrCmd && event.altKey) {
        switch (event.key) {
          case 'd':
            event.preventDefault();
            navigate('/dashboard');
            break;
          case 't':
            event.preventDefault();
            navigate('/time');
            break;
          case 'p':
            event.preventDefault();
            navigate('/projects');
            break;
          case 'r':
            event.preventDefault();
            navigate('/reports');
            break;
        }
      }

      // Escape: Close modals (handled by individual components)
      // ? : Show keyboard shortcuts help
      if (event.key === '?' && event.shiftKey) {
        event.preventDefault();
        // Dispatch custom event for shortcuts modal
        window.dispatchEvent(new CustomEvent('show-shortcuts-help'));
      }
    },
    [isAuthenticated, activeTimer, navigate, handlers, stopTimer]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);
}

// Shortcuts data for help modal
export const KEYBOARD_SHORTCUTS = [
  { keys: ['Ctrl', 'S'], description: 'Start timer', category: 'Timer' },
  { keys: ['Ctrl', 'E'], description: 'Stop timer', category: 'Timer' },
  { keys: ['Ctrl', 'N'], description: 'New time entry', category: 'Timer' },
  { keys: ['Alt', 'D'], description: 'Go to Dashboard', category: 'Navigation' },
  { keys: ['Alt', 'T'], description: 'Go to Time Entries', category: 'Navigation' },
  { keys: ['Alt', 'P'], description: 'Go to Projects', category: 'Navigation' },
  { keys: ['Alt', 'R'], description: 'Go to Reports', category: 'Navigation' },
  { keys: ['Shift', '?'], description: 'Show shortcuts help', category: 'Help' },
  { keys: ['Esc'], description: 'Close modal/dialog', category: 'General' },
];
