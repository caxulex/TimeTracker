// ============================================
// TIME TRACKER - APP COMPONENT WITH ROUTING
// ============================================
// Lazy loading enabled for optimal bundle splitting
// ============================================
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Suspense, lazy } from 'react';
import { Layout } from './components/layout/Layout';
import { NotificationProvider } from './components/Notifications';
import { WebSocketProvider } from './contexts/WebSocketContext';
import { ThemeProvider } from './contexts/ThemeContext';
import { BrandingProvider } from './contexts/BrandingContext';
import { useAuthStore } from './stores/authStore';
import './App.css';

// ============================================
// LAZY LOADED PAGES - Code Splitting
// ============================================
// Public pages (load immediately for fast initial load)
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { AccountRequestPage } from './pages/AccountRequestPage';
import { NotFoundPage } from './pages/NotFoundPage';

// Core pages - lazy loaded
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(m => ({ default: m.DashboardPage })));
const ProjectsPage = lazy(() => import('./pages/ProjectsPage').then(m => ({ default: m.ProjectsPage })));
const TasksPage = lazy(() => import('./pages/TasksPage').then(m => ({ default: m.TasksPage })));
const TimePage = lazy(() => import('./pages/TimePage').then(m => ({ default: m.TimePage })));
const TeamsPage = lazy(() => import('./pages/TeamsPage').then(m => ({ default: m.TeamsPage })));
const ReportsPage = lazy(() => import('./pages/ReportsPage').then(m => ({ default: m.ReportsPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(m => ({ default: m.SettingsPage })));

// Admin pages - lazy loaded (separate chunk)
const AdminPage = lazy(() => import('./pages/AdminPage').then(m => ({ default: m.AdminPage })));
const AdminSettingsPage = lazy(() => import('./pages/AdminSettingsPage').then(m => ({ default: m.AdminSettingsPage })));
const UsersPage = lazy(() => import('./pages/UsersPage').then(m => ({ default: m.UsersPage })));
const StaffPage = lazy(() => import('./pages/StaffPage').then(m => ({ default: m.StaffPage })));
const StaffDetailPage = lazy(() => import('./pages/StaffDetailPage').then(m => ({ default: m.StaffDetailPage })));
const AccountRequestsPage = lazy(() => import('./pages/AccountRequestsPage').then(m => ({ default: m.AccountRequestsPage })));
const AdminReportsPage = lazy(() => import('./pages/AdminReportsPage'));
const UserDetailPage = lazy(() => import('./pages/UserDetailPage'));

// Payroll pages - lazy loaded (separate chunk)
const PayRatesPage = lazy(() => import('./pages/PayRatesPage').then(m => ({ default: m.PayRatesPage })));
const PayrollPeriodsPage = lazy(() => import('./pages/PayrollPeriodsPage').then(m => ({ default: m.PayrollPeriodsPage })));
const PayrollReportsPage = lazy(() => import('./pages/PayrollReportsPage').then(m => ({ default: m.PayrollReportsPage })));

// ============================================
// LOADING FALLBACK COMPONENT
// ============================================
function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[400px]">
      <div className="flex flex-col items-center gap-3">
        <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <span className="text-gray-500 dark:text-gray-400">Loading...</span>
      </div>
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Don't retry on auth errors - prevents hammering server during logout flow
      retry: (failureCount, error: unknown) => {
        const axiosError = error as { response?: { status?: number } };
        const status = axiosError?.response?.status;
        // Never retry on auth errors (401, 403) or rate limit (429)
        if (status === 401 || status === 403 || status === 429) {
          return false;
        }
        return failureCount < 1;
      },
      staleTime: 5 * 60 * 1000, // 5 minutes - data stays fresh for 5 min
      gcTime: 10 * 60 * 1000, // 10 minutes - cache persists for 10 min
      refetchOnWindowFocus: false,
      refetchOnMount: false, // Don't refetch if data is fresh
      refetchOnReconnect: true, // Refetch on network reconnect
      // Performance: prefetch on hover for common queries
      structuralSharing: true, // Prevent unnecessary re-renders
    },
    mutations: {
      retry: 0, // Don't retry mutations by default
    },
  },
});

// Protected route wrapper
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  // Also check for actual token to prevent redirect loops when persisted state is stale
  const hasToken = !!localStorage.getItem('access_token');

  // Require BOTH conditions - prevents loop when isAuthenticated is stale but token is gone
  if (!isAuthenticated || !hasToken) {
    return <Navigate to="/login" replace />;
  }

  return <Layout>{children}</Layout>;
}

// Admin route wrapper (requires admin role)
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore();
  // Also check for actual token to prevent redirect loops when persisted state is stale
  const hasToken = !!localStorage.getItem('access_token');

  // Require BOTH conditions - prevents loop when isAuthenticated is stale but token is gone
  if (!isAuthenticated || !hasToken) {
    return <Navigate to="/login" replace />;
  }

  if (user?.role !== 'admin' && user?.role !== 'super_admin') {
    return <Navigate to="/dashboard" replace />;
  }

  return <Layout>{children}</Layout>;
}

// Super Admin route wrapper - Now allows both admin and super_admin
// (All admins have full capabilities)
function SuperAdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore();
  const hasToken = !!localStorage.getItem('access_token');

  if (!isAuthenticated || !hasToken) {
    return <Navigate to="/login" replace />;
  }

  // Allow both admin and super_admin (they have the same capabilities now)
  if (user?.role !== 'admin' && user?.role !== 'super_admin') {
    return <Navigate to="/dashboard" replace />;
  }

  return <Layout>{children}</Layout>;
}

// Public route wrapper (redirect to dashboard if already logged in)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();
  // Also check for actual token - prevents redirect loop when isAuthenticated is stale
  const hasToken = !!localStorage.getItem('access_token');

  // Only redirect if BOTH persisted state AND token exist - prevents redirect loops
  if (isAuthenticated && hasToken) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <ThemeProvider>
      <BrandingProvider>
      <QueryClientProvider client={queryClient}>
        <NotificationProvider>
          <WebSocketProvider>
          <BrowserRouter>
          <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public routes */}
            <Route
              path="/login"
              element={
                <PublicRoute>
                  <LoginPage />
                </PublicRoute>
              }
            />
            <Route
              path="/register"
              element={
                <PublicRoute>
                  <RegisterPage />
                </PublicRoute>
              }
            />
            <Route
              path="/forgot-password"
              element={
                <PublicRoute>
                  <ForgotPasswordPage />
                </PublicRoute>
              }
            />
            <Route
              path="/reset-password"
              element={
                <PublicRoute>
                  <ResetPasswordPage />
                </PublicRoute>
              }
            />

            {/* Protected routes */}
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <DashboardPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/projects"
              element={
                <ProtectedRoute>
                  <ProjectsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tasks"
              element={
                <ProtectedRoute>
                  <TasksPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/time"
              element={
                <ProtectedRoute>
                  <TimePage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/teams"
              element={
                <ProtectedRoute>
                  <TeamsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/reports"
              element={
                <ProtectedRoute>
                  <ReportsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <SettingsPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/admin"
              element={
                <AdminRoute>
                  <AdminPage />
                </AdminRoute>
              }
            />

            {/* Payroll routes (Admin only) */}
            <Route
              path="/payroll/rates"
              element={
                <AdminRoute>
                  <PayRatesPage />
                </AdminRoute>
              }
            />
            <Route
              path="/payroll/periods"
              element={
                <AdminRoute>
                  <PayrollPeriodsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/payroll/reports"
              element={
                <AdminRoute>
                  <PayrollReportsPage />
                </AdminRoute>
              }
            />

            {/* User Management (Super Admin only) */}
            <Route
              path="/users"
              element={
                <AdminRoute>
                  <UsersPage />
                </AdminRoute>
              }
            />
            
            {/* Staff Management (Admin only) */}
            <Route
              path="/staff"
              element={
                <AdminRoute>
                  <StaffPage />
                </AdminRoute>
              }
            />
            
            {/* Account Requests (Admin only) */}
            <Route
              path="/account-requests"
              element={
                <AdminRoute>
                  <AccountRequestsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/staff/:id"
              element={
                <AdminRoute>
                  <StaffDetailPage />
                </AdminRoute>
              }
            />

            {/* Admin Reports (Admin only) */}
            <Route
              path="/admin/reports"
              element={
                <AdminRoute>
                  <AdminReportsPage />
                </AdminRoute>
              }
            />
            <Route
              path="/admin/user/:userId"
              element={
                <AdminRoute>
                  <UserDetailPage />
                </AdminRoute>
              }
            />

            {/* Admin Settings - Super Admin Only (API Key Management) */}
            <Route
              path="/admin/settings"
              element={
                <SuperAdminRoute>
                  <AdminSettingsPage />
                </SuperAdminRoute>
              }
            />

            {/* Public Account Request */}
            <Route path="/request-account" element={<AccountRequestPage />} />

            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            
            {/* 404 Not Found */}
            <Route path="*" element={<NotFoundPage />} />
          </Routes>
          </Suspense>
        </BrowserRouter>
        </WebSocketProvider>
      </NotificationProvider>
    </QueryClientProvider>
    </BrandingProvider>
    </ThemeProvider>
  );
}

export default App;
