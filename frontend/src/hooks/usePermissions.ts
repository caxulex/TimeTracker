// ============================================
// TIME TRACKER - PERMISSION HOOK
// Phase 9: Security Enhancements
// ============================================
import { useAuthStore } from '../stores/authStore';
import { hasPermission, securityLogger } from '../utils/security';
import type { User } from '../types';

/**
 * Hook for checking user permissions
 */
export function usePermissions() {
  const { user } = useAuthStore();

  /**
   * Check if current user has required role
   */
  const checkPermission = (
    requiredRole: 'super_admin' | 'admin' | 'regular_user',
    action?: string
  ): boolean => {
    const allowed = hasPermission(user?.role, requiredRole);

    if (!allowed && action) {
      securityLogger.log({
        type: 'access_denied',
        action,
        details: `User role: ${user?.role}, Required: ${requiredRole}`,
        userId: user?.id,
      });
    }

    return allowed;
  };

  /**
   * Check if user can manage staff (admin or super_admin)
   */
  const canManageStaff = (): boolean => {
    return checkPermission('admin', 'manage_staff');
  };

  /**
   * Check if user can view payroll (admin or super_admin)
   */
  const canViewPayroll = (): boolean => {
    return checkPermission('admin', 'view_payroll');
  };

  /**
   * Check if user can manage teams (admin or super_admin)
   */
  const canManageTeams = (): boolean => {
    return checkPermission('admin', 'manage_teams');
  };

  /**
   * Check if user can export data (admin or super_admin)
   */
  const canExportData = (): boolean => {
    return checkPermission('admin', 'export_data');
  };

  /**
   * Check if user can modify specific staff member
   */
  const canModifyStaff = (targetStaff: User): boolean => {
    // Super admins can modify anyone except themselves for deactivation
    if (!canManageStaff()) {
      securityLogger.log({
        type: 'access_denied',
        action: 'modify_staff',
        details: `Attempted to modify staff ID: ${targetStaff.id}`,
        userId: user?.id,
      });
      return false;
    }

    // Prevent self-modification of role
    if (targetStaff.id === user?.id) {
      securityLogger.log({
        type: 'permission_check',
        action: 'self_modification',
        details: 'Attempted self-modification',
        userId: user?.id,
      });
      return false;
    }

    return true;
  };

  /**
   * Check if user can deactivate specific staff member
   */
  const canDeactivateStaff = (targetStaff: User): boolean => {
    // Cannot deactivate yourself
    if (targetStaff.id === user?.id) {
      securityLogger.log({
        type: 'permission_check',
        action: 'self_deactivation_attempt',
        details: 'User attempted to deactivate themselves',
        userId: user?.id,
      });
      return false;
    }

    return canManageStaff();
  };

  /**
   * Check if user can set pay rates (admin or super_admin)
   */
  const canSetPayRates = (): boolean => {
    return checkPermission('admin', 'set_pay_rates');
  };

  /**
   * Check if user can view analytics (admin or super_admin)
   */
  const canViewAnalytics = (): boolean => {
    return checkPermission('admin', 'view_analytics');
  };

  /**
   * Check if user can perform bulk operations (admin or super_admin)
   */
  const canPerformBulkOperations = (): boolean => {
    return checkPermission('admin', 'bulk_operations');
  };

  /**
   * Check if user can access staff detail page
   */
  const canViewStaffDetails = (targetStaff?: User): boolean => {
    // Users can view their own details
    if (targetStaff && targetStaff.id === user?.id) {
      return true;
    }

    // Only admins can view other staff details
    return canManageStaff();
  };

  /**
   * Get permission summary for current user
   */
  const getPermissionSummary = () => {
    return {
      role: user?.role,
      canManageStaff: canManageStaff(),
      canViewPayroll: canViewPayroll(),
      canManageTeams: canManageTeams(),
      canExportData: canExportData(),
      canSetPayRates: canSetPayRates(),
      canViewAnalytics: canViewAnalytics(),
      canPerformBulkOperations: canPerformBulkOperations(),
    };
  };

  return {
    user,
    checkPermission,
    canManageStaff,
    canViewPayroll,
    canManageTeams,
    canExportData,
    canModifyStaff,
    canDeactivateStaff,
    canSetPayRates,
    canViewAnalytics,
    canPerformBulkOperations,
    canViewStaffDetails,
    getPermissionSummary,
  };
}
