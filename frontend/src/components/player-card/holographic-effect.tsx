"use client";

export function HolographicEffect() {
  return (
    <div
      className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-400 group-hover:opacity-[0.35]"
      style={{
        background: `conic-gradient(
          from calc(var(--holo-angle, 0) * 1deg) at var(--holo-x, 50%) var(--holo-y, 50%),
          hsl(35, 80%, 65%) 0deg,
          hsl(45, 75%, 60%) 60deg,
          hsl(25, 70%, 55%) 120deg,
          hsl(100, 30%, 55%) 180deg,
          hsl(30, 85%, 60%) 240deg,
          hsl(40, 80%, 65%) 300deg,
          hsl(35, 80%, 65%) 360deg
        )`,
        mixBlendMode: 'color-dodge',
      }}
    />
  );
}
