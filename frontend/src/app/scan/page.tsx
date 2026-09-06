"use client";

import { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function ScanUploadPage() {
  const router = useRouter();
  const frontRef = useRef<HTMLInputElement>(null);
  const backRef = useRef<HTMLInputElement>(null);
  const [frontFile, setFrontFile] = useState<File | null>(null);
  const [backFile, setBackFile] = useState<File | null>(null);
  const [frontPreview, setFrontPreview] = useState<string | null>(null);
  const [backPreview, setBackPreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [qualityError, setQualityError] = useState("");

  // Check image quality before upload
  useEffect(() => {
    const checkQuality = async (file: File, label: string) => {
      if (!file) return;
      try {
        const form = new FormData();
        form.append("file", file);
        const res = await fetch(`${API}/quality`, {
          method: "POST",
          body: form,
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          // Extract human-readable message from FastAPI error formats
          let msg = "Quality check failed";
          if (err.detail) {
            if (typeof err.detail === "string") {
              msg = err.detail;
            } else if (Array.isArray(err.detail)) {
              msg = err.detail.length > 0 ? err.detail[0]?.msg || "Quality check failed" : "Quality check failed";
            } else if (typeof err.detail === "object") {
              msg = err.detail.msg || err.detail.message || "Quality check failed";
            }
          }
          setQualityError(msg);
          return;
        }
        const iq = await res.json();
        if (iq.recommended_action === "recapture") {
          setQualityError(
            `Image is too ${iq.blur}. Please retake the ${label} image.`
          );
        } else {
          setQualityError("");
        }
      } catch (e) {
        setQualityError("Quality check failed");
      }
    };
    const front = frontRef.current?.files?.[0] ?? frontFile;
    const back = backRef.current?.files?.[0] ?? backFile;
    if (front) {
      checkQuality(front, "front");
    }
    if (back) {
      checkQuality(back, "back");
    }
  }, [frontFile, backFile]);

  function handlePickFront(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setFrontFile(file);
      setFrontPreview(URL.createObjectURL(file));
      setQualityError(""); // clear quality error on new selection
    }
  }

  function handlePickBack(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setBackFile(file);
      setBackPreview(URL.createObjectURL(file));
      setQualityError(""); // clear quality error on new selection
    }
  }

  async function handleUpload() {
    if (!frontFile || !backFile) return;
    if (qualityError) {
      setError(qualityError);
      return;
    }
    setUploading(true);
    setProgress(0);
    setError("");

    const form = new FormData();
    form.append("front", frontFile);
    form.append("back", backFile);

    try {
      setProgress(30);

      const res = await fetch(`${API}/scan`, {
        method: "POST",
        body: form,
      });

      setProgress(80);

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        // Extract human-readable message from FastAPI/Pydantic error formats:
        // - {"detail": "string"} → string message
        // - {"detail": ["msg1", "msg2"]} → first message from array
        // - {"detail": {"field": "msg"}} → field-specific message
        // - {"detail": {"type": "...", "loc": [...], "msg": "..."}} → full validation error
        let msg = "Upload failed";
        if (body.detail) {
          if (typeof body.detail === "string") {
            msg = body.detail;
          } else if (Array.isArray(body.detail)) {
            msg = body.detail.length > 0 ? body.detail[0]?.msg || "Upload failed" : "Upload failed";
          } else if (typeof body.detail === "object") {
            // Pydantic validation error: {"type": "...", "loc": [...], "msg": "...", "input": ...}
            msg = body.detail.msg || body.detail.message || "Upload failed";
          }
        }
        throw new Error(msg);
      }

      const data = await res.json();
      setProgress(100);
      router.push(`/scan/${data.scan_id}`);
    } catch (err: unknown) {
      // Always ensure error is a string for safe JSX rendering
      const errorMessage = err instanceof Error ? err.message : "Upload failed";
      setError(String(errorMessage));
      setUploading(false);
    }
  }

  const canSubmit = frontFile && backFile && !uploading && !qualityError;

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-lg">
        <h1 className="mb-1 text-xl font-bold text-slate-800">New Scan</h1>
        <p className="mb-6 text-sm text-slate-500">
          Upload front and back product images for compliance analysis
        </p>

        {qualityError && (
          <div className="mb-4 p-3 rounded-xl bg-red-100 border border-red-200 text-red-800">
            <p className="font-medium">{qualityError}</p>
          </div>
        )}

        <div className="rounded-2xl bg-white p-6 shadow">
          {/* Front image picker */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Front image <span className="text-red-500">*</span>
            </label>
            <div
              className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 p-6 hover:border-blue-400 transition-colors cursor-pointer"
              onClick={() => frontRef.current?.click()}
            >
              {frontPreview ? (
                <img src={frontPreview} alt="Front preview" className="max-h-40 rounded object-contain" />
              ) : (
                <>
                  <svg className="mb-2 h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 16V4m0 0l-4 4m4-4l4 4" />
                  </svg>
                  <p className="text-xs text-slate-500">Click to select front image</p>
                </>
              )}
              <input
                ref={frontRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handlePickFront}
              />
            </div>
            {frontFile && (
              <p className="mt-1 text-xs text-slate-500">
                {frontFile.name} ({(frontFile.size / 1024).toFixed(0)} KB)
              </p>
            )}
          </div>

          {/* Back image picker */}
          <div className="mb-4">
            <label className="mb-1 block text-sm font-medium text-slate-700">
              Back image <span className="text-red-500">*</span>
            </label>
            <div
              className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 p-6 hover:border-blue-400 transition-colors cursor-pointer"
              onClick={() => backRef.current?.click()}
            >
              {backPreview ? (
                <img src={backPreview} alt="Back preview" className="max-h-40 rounded object-contain" />
              ) : (
                <>
                  <svg className="mb-2 h-8 w-8 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 16V4m0 0l-4 4m4-4l4 4" />
                  </svg>
                  <p className="text-xs text-slate-500">Click to select back image</p>
                </>
              )}
              <input
                ref={backRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handlePickBack}
              />
            </div>
            {backFile && (
              <p className="mt-1 text-xs text-slate-500">
                {backFile.name} ({(backFile.size / 1024).toFixed(0)} KB)
              </p>
            )}
          </div>

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
            disabled={!canSubmit}
            className="mt-4 w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {uploading ? "Uploading..." : "Start Scan"}
          </button>
        </div>
      </div>
    </main>
  );
}
