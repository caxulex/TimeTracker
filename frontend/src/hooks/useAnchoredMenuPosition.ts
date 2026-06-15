import { useLayoutEffect, useRef, useState } from 'react';
import type { CSSProperties, RefObject } from 'react';

type Placement = 'bottom-end' | 'top-end';

interface UseAnchoredMenuPositionOptions {
  isOpen: boolean;
  offset?: number;
  viewportPadding?: number;
  mobileBreakpoint?: number;
  desktopPlacement?: Placement;
  mobilePlacement?: Placement;
}

function clamp(value: number, min: number, max: number): number {
  if (value < min) return min;
  if (value > max) return max;
  return value;
}

export function useAnchoredMenuPosition<
  TTrigger extends HTMLElement = HTMLElement,
  TMenu extends HTMLElement = HTMLElement,
>(
  options: UseAnchoredMenuPositionOptions
): {
  triggerRef: RefObject<TTrigger>;
  menuRef: RefObject<TMenu>;
  menuStyle: CSSProperties;
} {
  const {
    isOpen,
    offset = 8,
    viewportPadding = 8,
    mobileBreakpoint = 768,
    desktopPlacement = 'bottom-end',
    mobilePlacement = 'top-end',
  } = options;

  const triggerRef = useRef<TTrigger>(null);
  const menuRef = useRef<TMenu>(null);

  const [menuStyle, setMenuStyle] = useState<CSSProperties>({
    position: 'fixed',
    visibility: 'hidden',
  });

  useLayoutEffect(() => {
    if (!isOpen) {
      setMenuStyle({
        position: 'fixed',
        visibility: 'hidden',
      });
      return;
    }

    const updatePosition = () => {
      const trigger = triggerRef.current;
      const menu = menuRef.current;
      if (!trigger || !menu) return;

      const triggerRect = trigger.getBoundingClientRect();
      const menuRect = menu.getBoundingClientRect();

      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      const menuWidth = Math.min(
        menuRect.width || menu.offsetWidth || 0,
        viewportWidth - viewportPadding * 2
      );
      const menuHeight = menuRect.height || menu.offsetHeight || 0;

      const preferredPlacement: Placement =
        viewportWidth < mobileBreakpoint ? mobilePlacement : desktopPlacement;

      const topY = triggerRect.top - offset - menuHeight;
      const bottomY = triggerRect.bottom + offset;

      const canPlaceTop = topY >= viewportPadding;
      const canPlaceBottom =
        bottomY + menuHeight <= viewportHeight - viewportPadding;

      let placement = preferredPlacement;
      if (placement === 'top-end' && !canPlaceTop && canPlaceBottom) {
        placement = 'bottom-end';
      }
      if (placement === 'bottom-end' && !canPlaceBottom && canPlaceTop) {
        placement = 'top-end';
      }

      const rawLeft = triggerRect.right - menuWidth;
      const maxLeft = Math.max(viewportPadding, viewportWidth - viewportPadding - menuWidth);
      const left = clamp(rawLeft, viewportPadding, maxLeft);

      const rawTop = placement === 'top-end' ? topY : bottomY;
      const maxTop = Math.max(viewportPadding, viewportHeight - viewportPadding - menuHeight);
      const top = clamp(rawTop, viewportPadding, maxTop);

      setMenuStyle({
        position: 'fixed',
        left,
        top,
        maxWidth: `calc(100vw - ${viewportPadding * 2}px)`,
        visibility: 'visible',
      });
    };

    updatePosition();

    window.addEventListener('resize', updatePosition);
    window.addEventListener('scroll', updatePosition, true);

    return () => {
      window.removeEventListener('resize', updatePosition);
      window.removeEventListener('scroll', updatePosition, true);
    };
  }, [
    isOpen,
    offset,
    viewportPadding,
    mobileBreakpoint,
    desktopPlacement,
    mobilePlacement,
  ]);

  return {
    triggerRef,
    menuRef,
    menuStyle,
  };
}
