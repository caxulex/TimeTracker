import { afterEach, describe, expect, it, vi } from 'vitest';

import { maybeRedirectToCheckout } from './checkoutRedirect';

describe('maybeRedirectToCheckout', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('redirects to checkout URL for 402 checkout_required', () => {
    const assignSpy = vi.fn();
    vi.stubGlobal('location', {
      ...window.location,
      assign: assignSpy,
    });

    const error = {
      isAxiosError: true,
      response: {
        status: 402,
        data: {
          reason: 'checkout_required',
          checkout_url: 'https://checkout.stripe.com/x',
        },
      },
    };

    const redirected = maybeRedirectToCheckout(error);

    expect(redirected).toBe(true);
    expect(assignSpy).toHaveBeenCalledTimes(1);
    expect(assignSpy).toHaveBeenCalledWith('https://checkout.stripe.com/x');
  });

  it('does not redirect for 402 with a different reason', () => {
    const assignSpy = vi.fn();
    vi.stubGlobal('location', {
      ...window.location,
      assign: assignSpy,
    });

    const error = {
      isAxiosError: true,
      response: {
        status: 402,
        data: {
          reason: 'something_else',
          checkout_url: 'https://checkout.stripe.com/x',
        },
      },
    };

    const redirected = maybeRedirectToCheckout(error);

    expect(redirected).toBe(false);
    expect(assignSpy).not.toHaveBeenCalled();
  });
});
