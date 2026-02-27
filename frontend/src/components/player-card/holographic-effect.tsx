"use client";

export function HolographicEffect() {
  return (
    <div
      className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-50 mix-blend-color-dodge transition-transform duration-100 ease-out motion-reduce:opacity-0"
      style={{
        background:
          "conic-gradient(from calc(var(--holo-angle, 0) * 1deg), hsl(0, 80%, 70%), hsl(60, 80%, 70%), hsl(120, 80%, 70%), hsl(180, 80%, 70%), hsl(240, 80%, 70%), hsl(300, 80%, 70%), hsl(360, 80%, 70%))",
        transform:
          "translate(calc((var(--holo-x, 0.5) - 0.5) * 20px), calc((var(--holo-y, 0.5) - 0.5) * 20px))",
      }}
    />
  );
}
