// ============================================
// TIME TRACKER - NOTIFICATIONS API
// ============================================
// API client for in-app notifications
// ============================================

import api from './client';

// Types
export interface BackendNotification {
  id: number;
  user_id: number;
  company_id: number | null;
  type: string;
  title: string;
  message: string;
  link: string | null;
  entity_type: string | null;
  entity_id: number | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
  metadata: Record<string, unknown> | null;
}

export interface NotificationListResponse {
  items: BackendNotification[];
  total: number;
  page: number;
  page_size: number;
  unread_count: number;
}

export interface UnreadCountResponse {
  unread_count: number;
}

export interface MarkReadResponse {
  updated_count: number;
  message: string;
}

export interface DeleteResponse {
  deleted_count: number;
  message: string;
}

// API Functions

/**
 * Get paginated list of notifications for current user
 */
export async function getNotifications(params?: {
  page?: number;
  page_size?: number;
  unread_only?: boolean;
  type?: string;
}): Promise<NotificationListResponse> {
  const response = await api.get('/api/notifications', { params });
  return response.data;
}

/**
 * Get unread notification count for badge display
 */
export async function getUnreadCount(): Promise<UnreadCountResponse> {
  const response = await api.get('/api/notifications/unread-count');
  return response.data;
}

/**
 * Get a specific notification by ID
 */
export async function getNotification(id: number): Promise<BackendNotification> {
  const response = await api.get(`/api/notifications/${id}`);
  return response.data;
}

/**
 * Mark notifications as read
 * @param notificationIds - Array of IDs to mark as read, or undefined to mark all as read
 */
export async function markNotificationsRead(notificationIds?: number[]): Promise<MarkReadResponse> {
  const response = await api.post('/api/notifications/mark-read', {
    notification_ids: notificationIds
  });
  return response.data;
}

/**
 * Delete notifications
 * @param notificationIds - Array of IDs to delete, or undefined to delete all read notifications
 */
export async function deleteNotifications(notificationIds?: number[]): Promise<DeleteResponse> {
  const response = await api.delete('/api/notifications', {
    data: { notification_ids: notificationIds }
  });
  return response.data;
}

// Admin functions

/**
 * Send a notification to a specific user (admin only)
 */
export async function sendNotification(data: {
  user_id: number;
  type?: string;
  title: string;
  message: string;
  link?: string;
  entity_type?: string;
  entity_id?: number;
  metadata?: Record<string, unknown>;
}): Promise<BackendNotification> {
  const response = await api.post('/api/notifications/send', {
    ...data,
    type: data.type || 'info'
  });
  return response.data;
}

/**
 * Send a notification to multiple users (admin only)
 */
export async function sendBulkNotifications(data: {
  user_ids: number[];
  type?: string;
  title: string;
  message: string;
  link?: string;
  entity_type?: string;
  entity_id?: number;
  metadata?: Record<string, unknown>;
}): Promise<{
  message: string;
  created_count: number;
  websocket_delivered: number;
  user_ids: number[];
}> {
  const response = await api.post('/api/notifications/send-bulk', {
    ...data,
    type: data.type || 'info'
  });
  return response.data;
}

export default {
  getNotifications,
  getUnreadCount,
  getNotification,
  markNotificationsRead,
  deleteNotifications,
  sendNotification,
  sendBulkNotifications
};
