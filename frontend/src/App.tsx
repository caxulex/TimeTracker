// ============================================
// TIME TRACKER - APP COMPONENT WITH ROUTING
// ============================================
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout/Layout';
import { NotificationProvider } from './components/Notifications';
import { WebSocketProvider } from './contexts/WebSocketContext';
import {
  LoginPage,
  RegisterPage,
  AccountRequestPage,
  DashboardPage,
  ProjectsPage,
  TasksPage,
  TimePage,
  TeamsPage,
  ReportsPage,
  SettingsPage,
  AdminPage,
  PayRatesPage,
  PayrollPeriodsPage,
  PayrollReportsPage,
  UsersPage,
  StaffPage,
  AccountRequestsPage,
} from './pages';
import { StaffDetailPage } from './pages/StaffDetailPage';
import { useAuthStore } from './stores/authStore';
import './App.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
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

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Layout>{children}</Layout>;
}

// Admin route wrapper (requires admin role)
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (user?.role !== 'admin' && user?.role !== 'super_admin') {
    return <Navigate to="/dashboard" replace />;
  }

  return <Layout>{children}</Layout>;
}

// Public route wrapper (redirect to dashboard if already logged in)
function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated } = useAuthStore();

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <NotificationProvider>
        <WebSocketProvider>
          <BrowserRouter>
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

            {/* Public Account Request */}
            <Route path="/request-account" element={<AccountRequestPage />} />

            {/* Default redirect */}
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </BrowserRouter>
        </WebSocketProvider>
      </NotificationProvider>
    </QueryClientProvider>
  );
}

export default App;
