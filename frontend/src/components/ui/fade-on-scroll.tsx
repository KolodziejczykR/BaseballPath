"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { clsx } from "clsx";

type FadeOnScrollProps = {
  children: React.ReactNode;
  className?: string;
  delayMs?: number;
  threshold?: number;
};

export function FadeOnScroll({
  children,
  className,
  delayMs = 0,
  threshold = 0.25,
}: FadeOnScrollProps) {
  const ref = useRef<HTMLDivElement | null>(null);
  const [visible, setVisible] = useState(false);

  const observerOptions = useMemo(
    () => ({
      threshold,
      rootMargin: "0px 0px -8% 0px",
    }),
    [threshold],
  );

  useEffect(() => {
    if (!ref.current) return;
    const element = ref.current;

    const observer = new IntersectionObserver(([entry]) => {
      setVisible(entry.isIntersecting);
    }, observerOptions);

    observer.observe(element);
    return () => observer.unobserve(element);
  }, [observerOptions]);

  return (
    <div
      ref={ref}
      className={clsx(
        "scroll-fade",
        visible ? "scroll-fade-visible" : "scroll-fade-hidden",
        className,
      )}
      style={{ transitionDelay: `${delayMs}ms` }}
    >
      {children}
    </div>
  );
}
