// ============================================
// TIME TRACKER - USE AUTH HOOK
// Re-exports auth store for convenience
// ============================================
import { useAuthStore } from '../stores/authStore';

export function useAuth() {
  const { user, isAuthenticated, isLoading, error, login, logout, register, fetchUser, clearError } = useAuthStore();
  
  return {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    logout,
    register,
    fetchUser,
    clearError,
  };
}

export default useAuth;
