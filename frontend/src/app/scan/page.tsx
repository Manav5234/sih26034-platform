"use client";

import { useState, useRef } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ScanUploadPage() {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");

  function handlePick(e: React.ChangeEvent<HTMLInputElement>) {
    const list = e.target.files;
    if (list) setFiles(Array.from(list));
  }

  async function handleUpload() {
    if (files.length === 0) return;
    setUploading(true);
    setProgress(0);
    setError("");

    const form = new FormData();
    files.forEach((f) => form.append("images", f));

    try {
      // Step 1: get token from cookie (for Authorization header)
      const me = await fetch(`${API}/dashboard`, { credentials: "include" });
      // We need the raw JWT — read it via the API route
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();

      setProgress(30);

      const res = await fetch(`${API}/scan`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: form,
      });

      setProgress(80);

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.detail || "Upload failed");
      }

      const data = await res.json();
      setProgress(100);
      router.push(`/scan/${data.scan_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setUploading(false);
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-lg">
        <h1 className="mb-1 text-xl font-bold text-slate-800">New Scan</h1>
        <p className="mb-6 text-sm text-slate-500">Upload product images for compliance analysis</p>

        <div className="rounded-2xl bg-white p-6 shadow">
          <div
            className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 p-8 hover:border-blue-400 transition-colors cursor-pointer"
            onClick={() => inputRef.current?.click()}
          >
            <svg className="mb-2 h-10 w-10 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 16V4m0 0l-4 4m4-4l4 4" />
            </svg>
            <p className="text-sm text-slate-500">
              {files.length > 0
                ? `${files.length} file(s) selected`
                : "Click to select images (JPEG, PNG, WebP — max 10 MB each)"}
            </p>
            <input
              ref={inputRef}
              type="file"
              accept="image/jpeg,image/png,image/webp"
              multiple
              className="hidden"
              onChange={handlePick}
            />
          </div>

          {files.length > 0 && (
            <ul className="mt-3 space-y-1">
              {files.map((f) => (
                <li key={f.name} className="flex items-center justify-between text-xs text-slate-600">
                  <span className="truncate">{f.name}</span>
                  <span className="ml-2 shrink-0 text-slate-400">{(f.size / 1024).toFixed(0)} KB</span>
                </li>
              ))}
            </ul>
          )}

          {uploading && (
            <div className="mt-4">
              <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
                <div
                  className="h-full rounded-full bg-blue-600 transition-all"
                  style={{ width: `${progress}%` }}
                />
              </div>
              <p className="mt-1 text-xs text-slate-400">{progress}% — Analyzing...</p>
            </div>
          )}

          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

          <button
            onClick={handleUpload}
            disabled={files.length === 0 || uploading}
            className="mt-4 w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Start Scan"}
          </button>
        </div>
      </div>
    </main>
  );
}
