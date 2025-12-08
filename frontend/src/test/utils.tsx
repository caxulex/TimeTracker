// ============================================
// TIME TRACKER - TEST UTILITIES
// TASK-049/050: Test helpers and render utilities
// ============================================
import { ReactNode } from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { BrowserRouter } from 'react-router-dom';

// Create a test query client with disabled retries
function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: Infinity,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

interface AllProvidersProps {
  children: ReactNode;
}

function AllProviders({ children }: AllProvidersProps) {
  const queryClient = createTestQueryClient();
  
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        {children}
      </BrowserRouter>
    </QueryClientProvider>
  );
}

function customRender(
  ui: React.ReactElement,
  options?: Omit<RenderOptions, 'wrapper'>
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

// Re-export everything
export * from '@testing-library/react';
export { customRender as render };
export { createTestQueryClient };

// Mock user data for tests
export const mockUser = {
  id: 1,
  name: 'Test User',
  email: 'test@example.com',
  role: 'worker' as const,
  is_active: true,
  created_at: new Date().toISOString(),
};

export const mockAdminUser = {
  id: 2,
  name: 'Admin User',
  email: 'admin@example.com',
  role: 'super_admin' as const,
  is_active: true,
  created_at: new Date().toISOString(),
};

export const mockProject = {
  id: 1,
  name: 'Test Project',
  description: 'A test project',
  team_id: 1,
  team_name: 'Test Team',
  color: '#3B82F6',
  is_archived: false,
  created_at: new Date().toISOString(),
  updated_at: null,
  task_count: 5,
};

export const mockTask = {
  id: 1,
  name: 'Test Task',
  description: 'A test task',
  project_id: 1,
  project_name: 'Test Project',
  status: 'TODO' as const,
  created_at: new Date().toISOString(),
  updated_at: null,
};

export const mockTimeEntry = {
  id: 1,
  user_id: 1,
  project_id: 1,
  project_name: 'Test Project',
  task_id: null,
  task_name: null,
  description: 'Working on feature',
  start_time: new Date().toISOString(),
  end_time: null,
  duration_seconds: 3600,
};
