"use client";

import { useRef, useState } from "react";

type Props = {
  front: React.ReactNode;
  back: React.ReactNode;
  className?: string;
  onMouseMove?: (e: React.MouseEvent<HTMLDivElement>) => void;
};

export function PlayerCardContainer({ front, back, className = "", onMouseMove }: Props) {
  const [flipped, setFlipped] = useState(false);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const rootRef = useRef<HTMLDivElement | null>(null);

  function handleMouseMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    e.currentTarget.style.setProperty("--holo-x", String(x));
    e.currentTarget.style.setProperty("--holo-y", String(y));
    e.currentTarget.style.setProperty("--holo-angle", String((x + y) * 180));

    const rotateX = (y - 0.5) * -10;
    const rotateY = (x - 0.5) * 10;
    setTilt({ x: rotateX, y: rotateY });

    onMouseMove?.(e);
  }

  function handleMouseLeave() {
    if (rootRef.current) {
      rootRef.current.style.setProperty("--holo-x", "0.5");
      rootRef.current.style.setProperty("--holo-y", "0.5");
      rootRef.current.style.setProperty("--holo-angle", "0");
    }
    setTilt({ x: 0, y: 0 });
  }

  return (
    <div
      ref={rootRef}
      className={`relative h-[490px] w-[350px] select-none [perspective:1000px] ${className}`}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      onClick={() => setFlipped((prev) => !prev)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setFlipped((prev) => !prev);
        }
      }}
      aria-label="Flip player card"
    >
      <div
        className="relative h-full w-full transition-transform duration-150"
        style={{ transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)` }}
      >
        <div
          className="relative h-full w-full transition-transform duration-500 [transform-style:preserve-3d]"
          style={{ transform: flipped ? "rotateY(180deg)" : "rotateY(0deg)" }}
        >
          <div className="absolute inset-0 overflow-hidden rounded-2xl [backface-visibility:hidden]">{front}</div>
          <div className="absolute inset-0 overflow-hidden rounded-2xl [transform:rotateY(180deg)] [backface-visibility:hidden]">
            {back}
          </div>
        </div>
      </div>
    </div>
  );
}
