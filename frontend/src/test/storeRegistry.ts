const storeResetters = new Set<() => void>();

export function registerStoreReset(reset: () => void) {
  storeResetters.add(reset);
}

export function resetRegisteredStores() {
  for (const reset of storeResetters) {
    try {
      reset();
    } catch (error) {
      console.error('[test/storeRegistry] Failed to reset store state:', error);
    }
  }
}