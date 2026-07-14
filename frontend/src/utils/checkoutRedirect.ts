import axios from 'axios';

type CheckoutErrorPayload = {
  reason?: string;
  checkout_url?: string;
};

export function maybeRedirectToCheckout(error: unknown): boolean {
  if (!axios.isAxiosError<CheckoutErrorPayload>(error)) return false;

  const res = error.response;
  if (res?.status !== 402) return false;

  const data = res.data;
  if (!data || data.reason !== 'checkout_required') return false;

  const url = data.checkout_url;
  if (typeof url !== 'string' || url.length === 0) return false;
  if (!/^https:\/\//i.test(url)) return false;

  window.location.assign(url);
  return true;
}
