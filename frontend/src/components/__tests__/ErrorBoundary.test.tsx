// ============================================
// TIME TRACKER - ERROR BOUNDARY TESTS
// Phase 1: Critical Safety Net
// ============================================
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ErrorBoundary } from '../ErrorBoundary';

// Component that renders normally
function GoodChild() {
  return <div>All is well</div>;
}

// Component that throws during render
function BadChild(): JSX.Element {
  throw new Error('Test rendering error');
}

describe('ErrorBoundary', () => {
  let consoleErrorSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    // Suppress console.error output during tests since we expect errors
    consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  afterEach(() => {
    consoleErrorSpy.mockRestore();
  });

  it('renders children normally when there is no error', () => {
    render(
      <ErrorBoundary name="test">
        <GoodChild />
      </ErrorBoundary>
    );

    expect(screen.getByText('All is well')).toBeInTheDocument();
  });

  it('catches a rendering error and shows fallback UI', () => {
    render(
      <ErrorBoundary name="test">
        <BadChild />
      </ErrorBoundary>
    );

    expect(screen.getByText('Something went wrong')).toBeInTheDocument();
    expect(
      screen.getByText('An unexpected error occurred. Please try reloading the page.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reload page/i })).toBeInTheDocument();
  });

  it('calls window.location.reload when the reload button is clicked', () => {
    const reloadMock = vi.fn();
    Object.defineProperty(window, 'location', {
      value: { ...window.location, reload: reloadMock },
      writable: true,
    });

    render(
      <ErrorBoundary name="test">
        <BadChild />
      </ErrorBoundary>
    );

    const reloadButton = screen.getByRole('button', { name: /reload page/i });
    fireEvent.click(reloadButton);

    expect(reloadMock).toHaveBeenCalledTimes(1);
  });

  it('logs the error via console.error with boundary name', () => {
    render(
      <ErrorBoundary name="MySection">
        <BadChild />
      </ErrorBoundary>
    );

    expect(consoleErrorSpy).toHaveBeenCalled();
    const calls = consoleErrorSpy.mock.calls.map((c) => String(c[0]));
    expect(calls.some((msg) => msg.includes('[ErrorBoundary:MySection]'))).toBe(true);
  });

  it('renders custom fallback when provided', () => {
    const customFallback = <div>Custom error fallback</div>;

    render(
      <ErrorBoundary name="test" fallback={customFallback}>
        <BadChild />
      </ErrorBoundary>
    );

    expect(screen.getByText('Custom error fallback')).toBeInTheDocument();
  });
});
