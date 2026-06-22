import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import TaskEstimationCard from './TaskEstimationCard';

const estimateTaskDurationMock = vi.fn();

vi.mock('../../api/aiServices', () => ({
  aiApi: {
    estimateTaskDuration: (...args: unknown[]) => estimateTaskDurationMock(...args),
  },
}));

function renderWithQueryClient(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  });

  return render(
    <QueryClientProvider client={queryClient}>
      {ui}
    </QueryClientProvider>
  );
}

describe('TaskEstimationCard', () => {
  beforeEach(() => {
    estimateTaskDurationMock.mockReset();
  });

  it('renders estimation input and button in normal state', () => {
    renderWithQueryClient(<TaskEstimationCard />);

    expect(screen.getByPlaceholderText(/Describe the task/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Estimate Duration/ })).toBeInTheDocument();
  });

  it('shows estimated result when success:true with valid estimate', async () => {
    estimateTaskDurationMock.mockResolvedValue({
      success: true,
      estimated_minutes: 120,
      estimated_hours: 2,
      confidence: 0.85,
      range_min_minutes: 90,
      range_max_minutes: 150,
      method: 'historical',
      recommendation: 'Based on similar completed tasks',
    });

    renderWithQueryClient(<TaskEstimationCard />);

    const input = screen.getByPlaceholderText(/Describe the task/);
    fireEvent.change(input, { target: { value: 'Implement user auth' } });

    const button = screen.getByRole('button', { name: /Estimate Duration/ });
    fireEvent.click(button);

    expect(await screen.findByText('2h')).toBeInTheDocument();
    expect(screen.getByText('85% confidence')).toBeInTheDocument();
    expect(screen.getByText('Based on similar completed tasks')).toBeInTheDocument();
  });

  it('shows error state when backend returns HTTP 200 with success:false (body-flag error)', async () => {
    estimateTaskDurationMock.mockResolvedValue({
      success: false,
      error: 'Estimation model not available',
    });

    renderWithQueryClient(<TaskEstimationCard />);

    const input = screen.getByPlaceholderText(/Describe the task/);
    fireEvent.change(input, { target: { value: 'Some task' } });

    const button = screen.getByRole('button', { name: /Estimate Duration/ });
    fireEvent.click(button);

    expect(await screen.findByText('Estimation model not available')).toBeInTheDocument();
  });

  it('shows error state when HTTP request fails with 503 (network error)', async () => {
    const errorMessage = 'HTTP Error: Service Unavailable';
    const error = new Error(errorMessage);
    estimateTaskDurationMock.mockRejectedValue(error);

    renderWithQueryClient(<TaskEstimationCard />);

    const input = screen.getByPlaceholderText(/Describe the task/);
    fireEvent.change(input, { target: { value: 'Some task' } });

    const button = screen.getByRole('button', { name: /Estimate Duration/ });
    fireEvent.click(button);

    // Error message from the mock should be rendered
    expect(await screen.findByText(errorMessage)).toBeInTheDocument();
  });

  it('calls onEstimate callback when estimation succeeds', async () => {
    const onEstimate = vi.fn();
    estimateTaskDurationMock.mockResolvedValue({
      success: true,
      estimated_minutes: 45,
      confidence: 0.90,
      method: 'ml',
    });

    renderWithQueryClient(<TaskEstimationCard onEstimate={onEstimate} />);

    const input = screen.getByPlaceholderText(/Describe the task/);
    fireEvent.change(input, { target: { value: 'Test task' } });

    const button = screen.getByRole('button', { name: /Estimate Duration/ });
    fireEvent.click(button);

    await waitFor(() => {
      expect(onEstimate).toHaveBeenCalled();
    });
  });

  it('shows error when estimation fails without calling onEstimate', async () => {
    const onEstimate = vi.fn();
    estimateTaskDurationMock.mockResolvedValue({
      success: false,
      error: 'Invalid description',
    });

    renderWithQueryClient(<TaskEstimationCard onEstimate={onEstimate} />);

    const input = screen.getByPlaceholderText(/Describe the task/);
    fireEvent.change(input, { target: { value: 'Test' } });

    const button = screen.getByRole('button', { name: /Estimate Duration/ });
    fireEvent.click(button);

    expect(await screen.findByText('Invalid description')).toBeInTheDocument();
    expect(onEstimate).not.toHaveBeenCalled();
  });

  it('disables estimate button while request is in progress', async () => {
    let resolveEstimate: any;
    const estimatePromise = new Promise((resolve) => {
      resolveEstimate = resolve;
    });
    estimateTaskDurationMock.mockReturnValue(estimatePromise);

    renderWithQueryClient(<TaskEstimationCard />);

    const input = screen.getByPlaceholderText(/Describe the task/);
    fireEvent.change(input, { target: { value: 'Test task' } });

    const button = screen.getByRole('button', { name: /Estimate Duration/ });
    fireEvent.click(button);

    // Button should be disabled during request
    await waitFor(() => {
      expect(button).toBeDisabled();
    });

    // Resolve the request
    resolveEstimate({ success: true, estimated_minutes: 60 });

    await waitFor(() => {
      expect(button).not.toBeDisabled();
    });
  });

  it('renders compact mode correctly', () => {
    renderWithQueryClient(<TaskEstimationCard compact={true} />);

    const input = screen.getByPlaceholderText('Enter task description...');
    expect(input).toBeInTheDocument();
    expect(input).toHaveClass('text-sm');
  });
});
