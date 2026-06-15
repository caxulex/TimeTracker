import { screen, waitFor, within } from '@testing-library/react';

const RELIABILITY_TIMEOUT = 5000;

type Container = HTMLElement | Document;

function queriesFor(container?: Container) {
  if (!container) {
    return screen;
  }

  return 'body' in container ? within(container.body) : within(container);
}

export function waitForReliable<T>(callback: () => T | Promise<T>, options?: Parameters<typeof waitFor>[1]) {
  return waitFor(callback, { timeout: RELIABILITY_TIMEOUT, ...options });
}

export function findByTextReliable(
  text: Parameters<typeof screen.findByText>[0],
  options?: Parameters<typeof screen.findByText>[1],
  container?: Container
) {
  return queriesFor(container).findByText(text, options, { timeout: RELIABILITY_TIMEOUT });
}

export function findByRoleReliable(
  role: Parameters<typeof screen.findByRole>[0],
  options?: Parameters<typeof screen.findByRole>[1],
  container?: Container
) {
  return queriesFor(container).findByRole(role, options, { timeout: RELIABILITY_TIMEOUT });
}

export function findByTestIdReliable(
  testId: Parameters<typeof screen.findByTestId>[0],
  options?: Parameters<typeof screen.findByTestId>[1],
  container?: Container
) {
  return queriesFor(container).findByTestId(testId, options, { timeout: RELIABILITY_TIMEOUT });
}

export function findByLabelTextReliable(
  text: Parameters<typeof screen.findByLabelText>[0],
  options?: Parameters<typeof screen.findByLabelText>[1],
  container?: Container
) {
  return queriesFor(container).findByLabelText(text, options, { timeout: RELIABILITY_TIMEOUT });
}