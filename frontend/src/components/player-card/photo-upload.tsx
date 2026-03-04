"use client";

import { useRef, useState } from "react";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const MAX_FILE_BYTES = 5 * 1024 * 1024;
const ALLOWED_TYPES = new Set(["image/jpeg", "image/png", "image/webp"]);

type PhotoUploadProps = {
  accessToken: string;
  currentPhotoUrl?: string | null;
  onUploaded?: (photoUrl: string) => void;
};

export function PhotoUpload({ accessToken, currentPhotoUrl, onUploaded }: PhotoUploadProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(currentPhotoUrl || null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  function validateFile(nextFile: File): string | null {
    if (!ALLOWED_TYPES.has(nextFile.type)) return "Use JPEG, PNG, or WEBP.";
    if (nextFile.size > MAX_FILE_BYTES) return "File must be 5MB or smaller.";
    return null;
  }

  function setSelectedFile(nextFile: File) {
    const fileError = validateFile(nextFile);
    if (fileError) {
      setError(fileError);
      return;
    }

    setError("");
    setFile(nextFile);
    setPreviewUrl(URL.createObjectURL(nextFile));
  }

  async function handleUpload() {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API_BASE_URL}/cards/me/photo`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body: formData,
      });
      const data = (await response.json()) as { photo_url?: string; detail?: string };
      if (!response.ok) {
        throw new Error(data.detail || "Photo upload failed.");
      }
      if (data.photo_url) {
        setPreviewUrl(data.photo_url);
        onUploaded?.(data.photo_url);
      }
      setFile(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Photo upload failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          const dropped = e.dataTransfer.files?.[0];
          if (dropped) setSelectedFile(dropped);
        }}
        className="rounded-2xl border border-dashed border-[var(--stroke)] bg-white/75 p-4"
      >
        {previewUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={previewUrl} alt="Card photo preview" className="h-44 w-full rounded-xl object-cover" />
        ) : (
          <div className="grid h-44 place-items-center rounded-xl bg-[var(--sand)]/30">
            <p className="text-sm text-[var(--muted)]">Drop an image here or choose a file.</p>
          </div>
        )}

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="rounded-full border border-[var(--stroke)] bg-white px-4 py-2 text-xs font-semibold text-[var(--navy)]"
          >
            Choose File
          </button>
          <button
            type="button"
            onClick={() => void handleUpload()}
            disabled={!file || loading}
            className="rounded-full bg-[var(--primary)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-70"
          >
            {loading ? "Uploading..." : "Upload"}
          </button>
        </div>

        <input
          ref={inputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden"
          onChange={(e) => {
            const next = e.target.files?.[0];
            if (next) setSelectedFile(next);
          }}
        />
      </div>

      {error ? <p className="text-xs text-red-600">{error}</p> : null}
    </div>
  );
}
