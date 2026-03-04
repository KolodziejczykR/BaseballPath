"use client";

import { useState } from "react";
import { toPng } from "html-to-image";

type CardExportButtonProps = {
  cardRef: React.RefObject<HTMLElement | null>;
};

async function exportCard(cardElement: HTMLElement, size: "instagram" | "twitter") {
  const dimensions =
    size === "instagram"
      ? { width: 1080, height: 1512, fileName: "baseballpath-card-instagram.png" }
      : { width: 1200, height: 675, fileName: "baseballpath-card-twitter.png" };

  const pixelRatio = dimensions.width / cardElement.offsetWidth;

  const dataUrl = await toPng(cardElement, {
    width: cardElement.offsetWidth,
    height: cardElement.offsetHeight,
    pixelRatio,
    cacheBust: true,
    canvasWidth: dimensions.width,
    canvasHeight: dimensions.height,
  });

  const link = document.createElement("a");
  link.download = dimensions.fileName;
  link.href = dataUrl;
  link.click();
}

export function CardExportButton({ cardRef }: CardExportButtonProps) {
  const [loading, setLoading] = useState<"instagram" | "twitter" | null>(null);
  const [error, setError] = useState("");

  async function handleExport(size: "instagram" | "twitter") {
    if (!cardRef.current) {
      setError("Card preview is not ready yet.");
      return;
    }

    setLoading(size);
    setError("");
    try {
      await exportCard(cardRef.current, size);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to export card.");
    } finally {
      setLoading(null);
    }
  }

  return (
    <div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void handleExport("instagram")}
          disabled={loading !== null}
          className="rounded-full border border-[var(--stroke)] bg-white/80 px-4 py-2 text-xs font-semibold text-[var(--navy)] disabled:opacity-70"
        >
          {loading === "instagram" ? "Exporting..." : "Download (Instagram)"}
        </button>
        <button
          type="button"
          onClick={() => void handleExport("twitter")}
          disabled={loading !== null}
          className="rounded-full border border-[var(--stroke)] bg-white/80 px-4 py-2 text-xs font-semibold text-[var(--navy)] disabled:opacity-70"
        >
          {loading === "twitter" ? "Exporting..." : "Download (Twitter)"}
        </button>
      </div>
      {error ? <p className="mt-2 text-xs text-red-600">{error}</p> : null}
    </div>
  );
}
