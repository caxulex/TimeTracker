// ============================================
// TIME TRACKER - STAFF NOTIFICATIONS HOOK
// Phase 8: Real-time Notifications System
// ============================================
import { useContext } from 'react';
import { NotificationContext } from '../contexts/NotificationContext';
import type { User } from '../types';

/**
 * Custom hook for staff management notifications
 * Provides pre-configured notification methods for common staff operations
 */
export function useStaffNotifications() {
  const context = useContext(NotificationContext);
  
  if (!context) {
    throw new Error('useStaffNotifications must be used within a NotificationProvider');
  }

  const { addNotification } = context;

  return {
    // Staff Creation Notifications
    notifyStaffCreated: (staff: User) => {
      addNotification({
        type: 'success',
        title: 'Staff Member Created',
        message: `${staff.name} has been successfully added to the system.`,
        duration: 5000,
      });
    },

    notifyStaffCreationFailed: (error: string) => {
      addNotification({
        type: 'error',
        title: 'Failed to Create Staff Member',
        message: error || 'An unexpected error occurred. Please try again.',
        duration: 7000,
      });
    },

    // Staff Update Notifications
    notifyStaffUpdated: (staff: User) => {
      addNotification({
        type: 'success',
        title: 'Staff Information Updated',
        message: `Changes to ${staff.name}'s profile have been saved.`,
        duration: 4000,
      });
    },

    notifyStaffUpdateFailed: (error: string) => {
      addNotification({
        type: 'error',
        title: 'Update Failed',
        message: error || 'Could not save changes. Please try again.',
        duration: 6000,
      });
    },

    // Staff Status Notifications
    notifyStaffActivated: (staff: User) => {
      addNotification({
        type: 'success',
        title: 'Staff Member Activated',
        message: `${staff.name} is now active and can access the system.`,
        duration: 4000,
      });
    },

    notifyStaffDeactivated: (staff: User) => {
      addNotification({
        type: 'warning',
        title: 'Staff Member Deactivated',
        message: `${staff.name} has been deactivated and cannot access the system.`,
        duration: 5000,
      });
    },

    // Pay Rate Notifications
    notifyPayRateSet: (staff: User, amount: number, type: string) => {
      addNotification({
        type: 'success',
        title: 'Pay Rate Updated',
        message: `New ${type} rate of $${amount.toFixed(2)} set for ${staff.name}.`,
        duration: 5000,
      });
    },

    notifyPayRateFailed: (error: string) => {
      addNotification({
        type: 'error',
        title: 'Pay Rate Update Failed',
        message: error || 'Could not update pay rate. Please try again.',
        duration: 6000,
      });
    },

    // Team Assignment Notifications
    notifyAddedToTeam: (staffName: string, teamName: string) => {
      addNotification({
        type: 'success',
        title: 'Team Assignment Successful',
        message: `${staffName} has been added to ${teamName}.`,
        duration: 4000,
      });
    },

    notifyRemovedFromTeam: (staffName: string, teamName: string) => {
      addNotification({
        type: 'info',
        title: 'Removed from Team',
        message: `${staffName} has been removed from ${teamName}.`,
        duration: 4000,
      });
    },

    notifyTeamOperationFailed: (error: string) => {
      addNotification({
        type: 'error',
        title: 'Team Operation Failed',
        message: error || 'Could not complete team operation. Please try again.',
        duration: 6000,
      });
    },

    // Bulk Operation Notifications
    notifyBulkOperationStart: (count: number, operation: string) => {
      addNotification({
        type: 'info',
        title: 'Processing Bulk Operation',
        message: `${operation} ${count} staff members...`,
        duration: 0, // Stay until manually removed
      });
    },

    notifyBulkOperationComplete: (successCount: number, failCount: number, operation: string) => {
      if (failCount === 0) {
        addNotification({
          type: 'success',
          title: 'Bulk Operation Complete',
          message: `Successfully ${operation} ${successCount} staff members.`,
          duration: 5000,
        });
      } else {
        addNotification({
          type: 'warning',
          title: 'Bulk Operation Completed with Errors',
          message: `${successCount} succeeded, ${failCount} failed.`,
          duration: 7000,
        });
      }
    },

    // Data Export Notifications
    notifyExportStarted: (format: string) => {
      addNotification({
        type: 'info',
        title: 'Preparing Export',
        message: `Generating ${format.toUpperCase()} file...`,
        duration: 3000,
      });
    },

    notifyExportComplete: (format: string, filename: string) => {
      addNotification({
        type: 'success',
        title: 'Export Complete',
        message: `${filename} has been downloaded.`,
        duration: 4000,
      });
    },

    notifyExportFailed: (error: string) => {
      addNotification({
        type: 'error',
        title: 'Export Failed',
        message: error || 'Could not generate export file. Please try again.',
        duration: 6000,
      });
    },

    // Validation Notifications
    notifyValidationError: (field: string, message: string) => {
      addNotification({
        type: 'warning',
        title: `Validation Error: ${field}`,
        message: message,
        duration: 5000,
      });
    },

    notifyMissingRequiredFields: (fields: string[]) => {
      addNotification({
        type: 'warning',
        title: 'Required Fields Missing',
        message: `Please fill in: ${fields.join(', ')}`,
        duration: 6000,
      });
    },

    // Permission Notifications
    notifyInsufficientPermissions: () => {
      addNotification({
        type: 'error',
        title: 'Access Denied',
        message: 'You do not have permission to perform this action.',
        duration: 5000,
      });
    },

    // Time Tracking Notifications
    notifyTimeEntryConflict: (conflictDate: string) => {
      addNotification({
        type: 'warning',
        title: 'Time Entry Conflict',
        message: `Overlapping time entries detected on ${conflictDate}.`,
        duration: 6000,
      });
    },

    // Analytics Notifications
    notifyAnalyticsGenerated: (staffName: string) => {
      addNotification({
        type: 'success',
        title: 'Analytics Generated',
        message: `Performance report for ${staffName} is ready.`,
        duration: 4000,
      });
    },

    // General Success/Error
    notifySuccess: (title: string, message?: string) => {
      addNotification({
        type: 'success',
        title,
        message,
        duration: 4000,
      });
    },

    notifyError: (title: string, message?: string) => {
      addNotification({
        type: 'error',
        title,
        message,
        duration: 6000,
      });
    },

    notifyWarning: (title: string, message?: string) => {
      addNotification({
        type: 'warning',
        title,
        message,
        duration: 5000,
      });
    },

    notifyInfo: (title: string, message?: string) => {
      addNotification({
        type: 'info',
        title,
        message,
        duration: 4000,
      });
    },

    // Loading state notifications (for long operations)
    notifyLoading: (message: string) => {
      const id = Math.random().toString(36).substr(2, 9);
      addNotification({
        type: 'info',
        title: 'Processing...',
        message,
        duration: 0, // Persist until removed
      });
      return id;
    },
  };
}
