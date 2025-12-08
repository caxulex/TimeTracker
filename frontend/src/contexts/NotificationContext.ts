// ============================================
// TIME TRACKER - Notification Context
// Extracted for Fast Refresh compliance
// ============================================
import { createContext } from 'react';

// Notification Types
export type NotificationType = 'success' | 'error' | 'warning' | 'info';

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message?: string;
  duration?: number;
  action?: {
    label: string;
    onClick: () => void;
  };
}

export interface NotificationContextType {
  notifications: Notification[];
  unreadCount: number;
  addNotification: (notification: Omit<Notification, 'id'>) => void;
  removeNotification: (id: string) => void;
  clearAll: () => void;
  markAllRead: () => void;
}

export const NotificationContext = createContext<NotificationContextType | undefined>(undefined);