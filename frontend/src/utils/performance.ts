// ============================================
// PERFORMANCE UTILITIES
// ============================================

/**
 * Throttle function execution to at most once per specified time
 * Useful for scroll handlers, resize handlers, etc.
 * 
 * @param func - Function to throttle
 * @param delay - Minimum time between executions in milliseconds
 * @returns Throttled function
 */
export function throttle<T extends (...args: any[]) => any>(
  func: T,
  delay: number
): (...args: Parameters<T>) => void {
  let lastCall = 0;
  let timeoutId: ReturnType<typeof setTimeout> | null = null;

  return function throttled(...args: Parameters<T>) {
    const now = Date.now();
    const timeSinceLastCall = now - lastCall;

    if (timeSinceLastCall >= delay) {
      lastCall = now;
      func(...args);
    } else {
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
      timeoutId = setTimeout(() => {
        lastCall = Date.now();
        func(...args);
      }, delay - timeSinceLastCall);
    }
  };
}

/**
 * Memoize expensive function results
 * Caches results based on function arguments
 * 
 * @param fn - Function to memoize
 * @returns Memoized function
 */
export function memoize<T extends (...args: any[]) => any>(
  fn: T
): T {
  const cache = new Map<string, ReturnType<T>>();

  return ((...args: Parameters<T>): ReturnType<T> => {
    const key = JSON.stringify(args);
    
    if (cache.has(key)) {
      return cache.get(key)!;
    }

    const result = fn(...args);
    cache.set(key, result);
    return result;
  }) as T;
}

/**
 * Batch multiple state updates to prevent excessive re-renders
 * Uses requestAnimationFrame for optimal batching
 * 
 * @param callback - Function containing state updates
 */
export function batchUpdates(callback: () => void): void {
  requestAnimationFrame(() => {
    callback();
  });
}

/**
 * Lazy load component with retry logic
 * Handles network failures gracefully
 * 
 * @param importFunc - Dynamic import function
 * @param retries - Number of retries on failure (default: 3)
 * @returns Promise resolving to component module
 */
export function lazyWithRetry<T>(
  importFunc: () => Promise<T>,
  retries = 3
): Promise<T> {
  return new Promise((resolve, reject) => {
    importFunc()
      .then(resolve)
      .catch((error) => {
        if (retries === 0) {
          reject(error);
          return;
        }

        // Retry after a delay
        setTimeout(() => {
          lazyWithRetry(importFunc, retries - 1)
            .then(resolve)
            .catch(reject);
        }, 1000);
      });
  });
}

/**
 * Format large numbers with K, M, B suffixes
 * Reduces DOM text node size for large values
 * 
 * @param num - Number to format
 * @returns Formatted string
 */
export function formatLargeNumber(num: number): string {
  if (num >= 1000000000) {
    return (num / 1000000000).toFixed(1) + 'B';
  }
  if (num >= 1000000) {
    return (num / 1000000).toFixed(1) + 'M';
  }
  if (num >= 1000) {
    return (num / 1000).toFixed(1) + 'K';
  }
  return num.toString();
}

/**
 * Check if device has reduced motion preference
 * Used to disable animations for accessibility
 * 
 * @returns true if user prefers reduced motion
 */
export function prefersReducedMotion(): boolean {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

/**
 * Get optimal image size based on device pixel ratio
 * Helps serve appropriate image sizes for performance
 * 
 * @param baseSize - Base image size in pixels
 * @returns Optimal size considering DPR
 */
export function getOptimalImageSize(baseSize: number): number {
  const dpr = window.devicePixelRatio || 1;
  
  // Cap at 2x for performance
  const multiplier = Math.min(dpr, 2);
  
  return Math.round(baseSize * multiplier);
}

/**
 * Measure component render time (development only)
 * Useful for identifying performance bottlenecks
 * 
 * @param componentName - Name of component being measured
 * @param callback - Render callback to measure
 * @returns Result of callback
 */
export function measureRender<T>(
  componentName: string,
  callback: () => T
): T {
  if (process.env.NODE_ENV === 'production') {
    return callback();
  }

  const start = performance.now();
  const result = callback();
  const end = performance.now();
  
  const duration = end - start;
  if (duration > 16) { // Slower than 60fps
    console.warn(
      `[Performance] ${componentName} render took ${duration.toFixed(2)}ms (> 16ms)`
    );
  }

  return result;
}
