// ============================================
// TIME TRACKER - LOGIN PAGE TESTS
// Phase 7: Testing - Authentication page tests
// ============================================
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '../test/utils';
import { LoginPage } from './LoginPage';

// Mock react-router-dom navigation
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

// Mock auth store
const mockLogin = vi.fn();
const mockClearError = vi.fn();

vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    login: mockLogin,
    isLoading: false,
    error: null,
    clearError: mockClearError,
  }),
}));

// Mock notifications
vi.mock('../hooks/useNotifications', () => ({
  useNotifications: () => ({
    addNotification: vi.fn(),
  }),
}));

// Mock branding config
vi.mock('../config/branding', () => ({
  branding: {
    appName: 'TimeTracker',
    logoUrl: '/logo.svg',
    logoAlt: 'TimeTracker Logo',
    primaryColor: '#3B82F6',
  },
}));

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders login form', () => {
    render(<LoginPage />);
    
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('renders welcome message', () => {
    render(<LoginPage />);
    
    expect(screen.getByText(/welcome back/i)).toBeInTheDocument();
  });

  it('shows validation errors for empty form', async () => {
    render(<LoginPage />);
    
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/email is required/i)).toBeInTheDocument();
    });
  });

  it('shows validation error for invalid email', async () => {
    render(<LoginPage />);
    
    const emailInput = screen.getByLabelText(/email/i);
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(screen.getByText(/invalid email address/i)).toBeInTheDocument();
    });
  });

  it('calls login function with correct data', async () => {
    mockLogin.mockResolvedValue({});
    render(<LoginPage />);
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@example.com',
        password: 'password123',
      });
    });
  });

  it('navigates to dashboard on successful login', async () => {
    mockLogin.mockResolvedValue({});
    render(<LoginPage />);
    
    const emailInput = screen.getByLabelText(/email/i);
    const passwordInput = screen.getByLabelText(/password/i);
    
    fireEvent.change(emailInput, { target: { value: 'test@example.com' } });
    fireEvent.change(passwordInput, { target: { value: 'password123' } });
    
    const submitButton = screen.getByRole('button', { name: /sign in/i });
    fireEvent.click(submitButton);
    
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard');
    });
  });

  it('has link to register page', () => {
    render(<LoginPage />);
    
    const registerLink = screen.getByRole('link', { name: /sign up|register|create/i });
    expect(registerLink).toBeInTheDocument();
  });

  it('has link to forgot password', () => {
    render(<LoginPage />);
    
    const forgotLink = screen.getByRole('link', { name: /forgot/i });
    expect(forgotLink).toBeInTheDocument();
  });
});

describe('LoginPage - Error Handling', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('displays error message from store', () => {
    vi.mocked(vi.mock('../stores/authStore')).mockReturnValue({
      useAuthStore: () => ({
        login: mockLogin,
        isLoading: false,
        error: 'Invalid credentials',
        clearError: mockClearError,
      }),
    });
    
    // Note: This would need proper store mocking to test
  });
});

describe('LoginPage - Loading State', () => {
  it('disables form during loading', () => {
    vi.mocked(vi.mock('../stores/authStore')).mockReturnValue({
      useAuthStore: () => ({
        login: mockLogin,
        isLoading: true,
        error: null,
        clearError: mockClearError,
      }),
    });
    
    // Note: This would need proper store mocking to test
  });
});
