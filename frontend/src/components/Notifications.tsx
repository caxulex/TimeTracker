// ============================================
// TIME TRACKER - NOTIFICATIONS SYSTEM
// TASK-021: Create notification system
// Enhanced with backend API integration
// ============================================
import React, { useContext, useState, useCallback, useEffect } from 'react';
import { NotificationContext, NotificationContextType, Notification, NotificationType } from '../contexts/NotificationContext';
import { useWebSocketContext } from '../contexts/WebSocketContext';
import { useAuthStore } from '../stores/authStore';
import * as notificationsApi from '../api/notifications';
import type { BackendNotification } from '../api/notifications';
import { cn } from '../utils/helpers';

// Internal hook - not exported to avoid Fast Refresh warning
function useNotificationsInternal() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}

// Convert backend notification to frontend format
function toFrontendNotification(bn: BackendNotification): Notification {
  const typeMap: Record<string, NotificationType> = {
    info: 'info',
    success: 'success',
    warning: 'warning',
    error: 'error',
    timer_reminder: 'warning',
    approval_request: 'info',
    approval_response: 'info',
    team_update: 'info',
    payroll: 'info',
    system: 'info',
  };
  
  return {
    id: `backend-${bn.id}`,
    type: typeMap[bn.type] || 'info',
    title: bn.title,
    message: bn.message,
    duration: -1, // Persistent notification
    action: bn.link ? {
      label: 'View',
      onClick: () => {
        window.location.href = bn.link!;
      }
    } : undefined
  };
}

// Internal hook - not exported to avoid Fast Refresh warning
function useNotificationsInternal() {
  const context = useContext(NotificationContext);
  if (!context) {
    throw new Error('useNotifications must be used within a NotificationProvider');
  }
  return context;
}

// Notification Provider
export function NotificationProvider({ children }: { children: React.ReactNode }) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [toastNotifications, setToastNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [backendNotifications, setBackendNotifications] = useState<BackendNotification[]>([]);
  const { isAuthenticated } = useAuthStore();

  // Fetch notifications from backend on mount
  useEffect(() => {
    if (!isAuthenticated) return;
    
    const fetchNotifications = async () => {
      try {
        const response = await notificationsApi.getNotifications({ page_size: 50 });
        setBackendNotifications(response.items);
        setUnreadCount(response.unread_count);
        
        // Convert to frontend format and add to notifications
        const frontendNotifs = response.items.map(toFrontendNotification);
        setNotifications(frontendNotifs);
      } catch (error) {
        console.error('Failed to fetch notifications:', error);
      }
    };
    
    fetchNotifications();
    
    // Poll for new notifications every 60 seconds
    const interval = setInterval(fetchNotifications, 60000);
    return () => clearInterval(interval);
  }, [isAuthenticated]);

  // Handle incoming WebSocket notifications
  const handleWebSocketNotification = useCallback((data: BackendNotification) => {
    const frontendNotif = toFrontendNotification(data);
    
    // Add to persistent notifications
    setBackendNotifications(prev => [data, ...prev]);
    setNotifications(prev => [frontendNotif, ...prev]);
    setUnreadCount(prev => prev + 1);
    
    // Show toast
    const toastNotif = { ...frontendNotif, id: `toast-${Date.now()}`, duration: 5000 };
    setToastNotifications(prev => [toastNotif, ...prev]);
    
    setTimeout(() => {
      setToastNotifications(prev => prev.filter(n => n.id !== toastNotif.id));
    }, 5000);
  }, []);

  // Expose handler for WebSocket context
  useEffect(() => {
    // This will be called by the WebSocket context when a notification message arrives
    (window as any).__handleIncomingNotification = handleWebSocketNotification;
    return () => {
      delete (window as any).__handleIncomingNotification;
    };
  }, [handleWebSocketNotification]);

  const addNotification = useCallback((notification: Omit<Notification, 'id'>) => {
    const id = Math.random().toString(36).substr(2, 9);
    const newNotification = { ...notification, id };
    
    // Add to persistent notifications list (for bell dropdown)
    setNotifications(prev => [newNotification, ...prev]);
    setUnreadCount(prev => prev + 1);

    // Add to toast notifications (for bottom-right toasts)
    setToastNotifications(prev => [newNotification, ...prev]);

    // Auto remove toast after duration (default 5 seconds)
    const duration = notification.duration ?? 5000;
    if (duration > 0) {
      setTimeout(() => {
        setToastNotifications(prev => prev.filter(n => n.id !== id));
      }, duration);
    }
  }, []);

  const removeNotification = useCallback((id: string) => {
    setNotifications(prev => prev.filter(n => n.id !== id));
    setToastNotifications(prev => prev.filter(n => n.id !== id));
    
    // If it's a backend notification, delete it
    if (id.startsWith('backend-')) {
      const backendId = parseInt(id.replace('backend-', ''), 10);
      if (!isNaN(backendId)) {
        notificationsApi.deleteNotifications([backendId]).catch(console.error);
        setBackendNotifications(prev => prev.filter(n => n.id !== backendId));
      }
    }
  }, []);

  const clearAll = useCallback(async () => {
    setNotifications([]);
    setToastNotifications([]);
    setUnreadCount(0);
    
    // Delete all read backend notifications
    try {
      await notificationsApi.deleteNotifications();
      setBackendNotifications([]);
    } catch (error) {
      console.error('Failed to clear notifications:', error);
    }
  }, []);

  const markAllRead = useCallback(async () => {
    setUnreadCount(0);
    
    // Mark all backend notifications as read
    try {
      await notificationsApi.markNotificationsRead();
      setBackendNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    } catch (error) {
      console.error('Failed to mark notifications as read:', error);
    }
  }, []);

  return (
    <NotificationContext.Provider value={{
      notifications,
      unreadCount,
      addNotification,
      removeNotification,
      clearAll,
      markAllRead,
    }}>
      {children}
      <NotificationContainer toastNotifications={toastNotifications} />
    </NotificationContext.Provider>
  );
}

// Toast notification container
function NotificationContainer({ toastNotifications }: { toastNotifications: Notification[] }) {
  const { removeNotification } = useNotificationsInternal();

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {toastNotifications.slice(0, 5).map((notification) => (
        <Toast
          key={notification.id}
          notification={notification}
          onClose={() => removeNotification(notification.id)}
        />
      ))}
    </div>
  );
}

// Individual Toast component
interface ToastProps {
  notification: Notification;
  onClose: () => void;
}

function Toast({ notification, onClose }: ToastProps) {
  const [isLeaving, setIsLeaving] = useState(false);

  const handleClose = () => {
    setIsLeaving(true);
    setTimeout(onClose, 200);
  };

  const icons: Record<NotificationType, React.ReactNode> = {
    success: (
      <svg className="w-5 h-5 text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    error: (
      <svg className="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    warning: (
      <svg className="w-5 h-5 text-yellow-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    ),
    info: (
      <svg className="w-5 h-5 text-blue-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  };

  const bgColors: Record<NotificationType, string> = {
    success: 'bg-green-50 border-green-200',
    error: 'bg-red-50 border-red-200',
    warning: 'bg-yellow-50 border-yellow-200',
    info: 'bg-blue-50 border-blue-200',
  };

  return (
    <div
      className={cn(
        'flex items-start gap-3 p-4 rounded-lg shadow-lg border transition-all duration-200',
        bgColors[notification.type],
        isLeaving ? 'opacity-0 translate-x-4' : 'opacity-100 translate-x-0'
      )}
    >
      <div className="flex-shrink-0">{icons[notification.type]}</div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-gray-900">{notification.title}</p>
        {notification.message && (
          <p className="mt-1 text-sm text-gray-500">{notification.message}</p>
        )}
        {notification.action && (
          <button
            onClick={notification.action.onClick}
            className="mt-2 text-sm font-medium text-blue-600 hover:text-blue-500"
          >
            {notification.action.label}
          </button>
        )}
      </div>
      <button
        onClick={handleClose}
        className="flex-shrink-0 text-gray-400 hover:text-gray-600"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

// Notification Bell component for navbar
export function NotificationBell() {
  const { unreadCount, notifications, markAllRead, clearAll } = useNotificationsInternal();
  const [isOpen, setIsOpen] = useState(false);

  const handleToggle = () => {
    setIsOpen(!isOpen);
    if (!isOpen) {
      markAllRead();
    }
  };

  return (
    <div className="relative">
      <button
        onClick={handleToggle}
        className="relative p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-full"
      >
        <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
        {unreadCount > 0 && (
          <span className="absolute top-0 right-0 w-5 h-5 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 mt-2 w-80 bg-white rounded-lg shadow-lg border z-50">
            <div className="flex items-center justify-between p-4 border-b">
              <h3 className="font-semibold text-gray-900">Notifications</h3>
              {notifications.length > 0 && (
                <button
                  onClick={clearAll}
                  className="text-sm text-blue-600 hover:text-blue-500"
                >
                  Clear all
                </button>
              )}
            </div>
            <div className="max-h-96 overflow-y-auto">
              {notifications.length === 0 ? (
                <div className="p-8 text-center text-gray-500">
                  <svg className="w-12 h-12 mx-auto mb-4 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                  </svg>
                  <p>No notifications</p>
                </div>
              ) : (
                notifications.map((notification) => (
                  <div
                    key={notification.id}
                    className="p-4 border-b last:border-b-0 hover:bg-gray-50"
                  >
                    <p className="font-medium text-gray-900">{notification.title}</p>
                    {notification.message && (
                      <p className="text-sm text-gray-500 mt-1">{notification.message}</p>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// Re-export types and hook for external use
export type { Notification, NotificationType, NotificationContextType } from '../contexts/NotificationContext';

export default NotificationProvider;