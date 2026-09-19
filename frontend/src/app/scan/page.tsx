"use client";

import React, { useState, useRef, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import {
  IconCamera,
  IconUpload,
  IconCheckCircle,
  IconAlertTriangle,
  IconScan,
  IconArrowRight,
} from "@/components/ui/Icons";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ImageQualityResult {
  blur: string;
  glare: string;
  perspective: string;
  resolution: string;
  recommended_action: string;
}

export default function ScanUploadPage() {
  const router = useRouter();
  const frontRef = useRef<HTMLInputElement>(null);
  const backRef = useRef<HTMLInputElement>(null);

  const [frontFile, setFrontFile] = useState<File | null>(null);
  const [backFile, setBackFile] = useState<File | null>(null);
  const [frontPreview, setFrontPreview] = useState<string | null>(null);
  const [backPreview, setBackPreview] = useState<string | null>(null);

  const [frontQuality, setFrontQuality] = useState<ImageQualityResult | null>(null);
  const [backQuality, setBackQuality] = useState<ImageQualityResult | null>(null);
  const [checkingQuality, setCheckingQuality] = useState<"front" | "back" | null>(null);

  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [analysisStage, setAnalysisStage] = useState("");
  const [error, setError] = useState("");
  const [qualityError, setQualityError] = useState("");

  // Check image quality via backend /quality endpoint
  async function runQualityCheck(file: File, label: "front" | "back") {
    if (!file) return;
    setCheckingQuality(label);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${API}/quality`, {
        method: "POST",
        body: form,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        let msg = "Image quality check failed";
        if (err.detail) {
          if (typeof err.detail === "string") msg = err.detail;
          else if (Array.isArray(err.detail)) msg = err.detail[0]?.msg || msg;
          else if (typeof err.detail === "object") msg = err.detail.msg || err.detail.message || msg;
        }
        setQualityError(msg);
        return;
      }

      const iq: ImageQualityResult = await res.json();
      if (label === "front") setFrontQuality(iq);
      else setBackQuality(iq);

      if (iq.recommended_action === "recapture") {
        setQualityError(`The ${label} image is too ${iq.blur}. For reliable regulatory inspection, please retake with clear focus.`);
      } else {
        setQualityError("");
      }
    } catch {
      setQualityError("Quality pre-check could not reach the server.");
    } finally {
      setCheckingQuality(null);
    }
  }

  function handlePickFront(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setFrontFile(file);
      setFrontPreview(URL.createObjectURL(file));
      setQualityError("");
      runQualityCheck(file, "front");
    }
  }

  function handlePickBack(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) {
      setBackFile(file);
      setBackPreview(URL.createObjectURL(file));
      setQualityError("");
      runQualityCheck(file, "back");
    }
  }

  function clearFront() {
    setFrontFile(null);
    setFrontPreview(null);
    setFrontQuality(null);
    setQualityError("");
    if (frontRef.current) frontRef.current.value = "";
  }

  function clearBack() {
    setBackFile(null);
    setBackPreview(null);
    setBackQuality(null);
    setQualityError("");
    if (backRef.current) backRef.current.value = "";
  }

  async function handleUpload() {
    if (!frontFile || !backFile) return;
    if (qualityError) {
      setError(qualityError);
      return;
    }

    setUploading(true);
    setProgress(15);
    setAnalysisStage("Uploading high-resolution product labels...");
    setError("");

    const form = new FormData();
    form.append("front", frontFile);
    form.append("back", backFile);

    try {
      // Smooth stage simulation tied to existing upload state
      const stageTimer1 = setTimeout(() => {
        setProgress(40);
        setAnalysisStage("Running multi-pass OCR & barcode computer vision extraction...");
      }, 700);

      const stageTimer2 = setTimeout(() => {
        setProgress(75);
        setAnalysisStage("Evaluating extracted declarations against Legal Metrology Rules...");
      }, 1500);

      const res = await fetch(`${API}/scan`, {
        method: "POST",
        body: form,
      });

      clearTimeout(stageTimer1);
      clearTimeout(stageTimer2);

      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        let msg = "Compliance check upload failed";
        if (body.detail) {
          if (typeof body.detail === "string") msg = body.detail;
          else if (Array.isArray(body.detail)) msg = body.detail[0]?.msg || msg;
          else if (typeof body.detail === "object") msg = body.detail.msg || body.detail.message || msg;
        }
        throw new Error(msg);
      }

      const data = await res.json();
      setProgress(100);
      setAnalysisStage("Compliance analysis complete. Loading findings...");
      setTimeout(() => {
        router.push(`/scan/${data.scan_id}`);
      }, 400);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "Upload failed";
      setError(String(errorMessage));
      setUploading(false);
      setProgress(0);
      setAnalysisStage("");
    }
  }

  const canSubmit = Boolean(frontFile && backFile && !uploading && !qualityError);

  const steps = [
    { num: "01", title: "Front Label", done: Boolean(frontFile) },
    { num: "02", title: "Back Label", done: Boolean(backFile) },
    { num: "03", title: "AI Analysis", done: uploading && progress > 50 },
    { num: "04", title: "Officer Review", done: false },
  ];

  return (
    <AppShell>
      <div className="max-w-4xl mx-auto space-y-8">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200/80">
          <div>
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-600 uppercase tracking-wider mb-1">
              <IconScan className="h-3.5 w-3.5" />
              <span>Inspection Intake</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              New Inspection
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-500">
              Capture both sides of the packaged commodity label for automated compliance extraction.
            </p>
          </div>

          <Link
            href="/scans"
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-600 hover:text-slate-900"
          >
            <span>View Previous Scans</span>
            <IconArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {/* 4-Step Progress Indicator */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {steps.map((step, idx) => (
            <div
              key={step.num}
              className={`flex items-center gap-3 rounded-xl border p-3 transition-all ${
                step.done
                  ? "border-emerald-200 bg-emerald-50/70 text-emerald-900"
                  : idx === (frontFile ? (backFile ? 2 : 1) : 0)
                  ? "border-brand-300 bg-brand-50/50 text-brand-900 ring-2 ring-brand-500/20"
                  : "border-slate-200/80 bg-white text-slate-400"
              }`}
            >
              <div
                className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs font-bold ${
                  step.done
                    ? "bg-emerald-600 text-white"
                    : idx === (frontFile ? (backFile ? 2 : 1) : 0)
                    ? "bg-brand-600 text-white"
                    : "bg-slate-100 text-slate-500"
                }`}
              >
                {step.done ? <IconCheckCircle className="h-4 w-4" /> : step.num}
              </div>
              <div className="min-w-0">
                <p className="text-[10px] uppercase font-bold tracking-wider opacity-70">
                  Step {step.num}
                </p>
                <p className="text-xs font-semibold truncate">{step.title}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Quality or Validation Alert */}
        {(qualityError || error) && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-4 flex items-start gap-3 text-xs text-rose-800 shadow-2xs">
            <IconAlertTriangle className="h-5 w-5 shrink-0 text-rose-600 mt-0.5" />
            <div className="flex-1">
              <p className="font-bold">Image Validation Issue</p>
              <p className="mt-0.5 text-rose-700">{qualityError || error}</p>
            </div>
          </div>
        )}

        {/* Dual Upload Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* FRONT LABEL CARD */}
          <div className="rounded-2xl bg-white border border-slate-200/80 p-6 shadow-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-900 text-white text-[10px] font-bold">
                    1
                  </span>
                  <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                    Front Label
                  </h2>
                </div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-rose-600 bg-rose-50 px-2 py-0.5 rounded">
                  Mandatory
                </span>
              </div>
              <p className="text-xs text-slate-500 mb-4">
                Primary package face displaying brand identity, product name, and net quantity.
              </p>

              {frontPreview ? (
                <div className="relative rounded-xl border border-slate-200 overflow-hidden bg-slate-950/5 group">
                  <img
                    src={frontPreview}
                    alt="Front label preview"
                    className="w-full h-56 object-contain"
                  />
                  <div className="absolute inset-0 bg-navy-950/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    <button
                      onClick={() => frontRef.current?.click()}
                      className="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 shadow hover:bg-slate-100"
                    >
                      Replace Image
                    </button>
                    <button
                      onClick={clearFront}
                      className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white shadow hover:bg-rose-700"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => frontRef.current?.click()}
                  className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 hover:border-brand-500 bg-slate-50/50 hover:bg-brand-50/20 p-8 cursor-pointer transition-all h-56"
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-slate-500 shadow-2xs border border-slate-200 mb-3">
                    <IconCamera className="h-6 w-6 text-slate-600" />
                  </div>
                  <p className="text-xs font-bold text-slate-700">
                    Click to select front packaging
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Supports JPEG, PNG, WEBP up to 10MB
                  </p>
                </div>
              )}

              <input
                ref={frontRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handlePickFront}
              />
            </div>

            {/* Front Quality Diagnostic Card */}
            <div className="mt-4 pt-4 border-t border-slate-100">
              {checkingQuality === "front" ? (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="h-3 w-3 rounded-full border-2 border-brand-600/30 border-t-brand-600 animate-spin" />
                  <span>Checking OpenCV image clarity...</span>
                </div>
              ) : frontQuality ? (
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="rounded-lg bg-slate-50 p-2 border border-slate-200/60">
                    <span className="text-slate-400 block">Blur:</span>
                    <span className="font-semibold text-slate-700 capitalize">{frontQuality.blur}</span>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-2 border border-slate-200/60">
                    <span className="text-slate-400 block">Glare:</span>
                    <span className="font-semibold text-slate-700 capitalize">{frontQuality.glare}</span>
                  </div>
                </div>
              ) : (
                <p className="text-[11px] text-slate-400">Quality check runs automatically upon image selection</p>
              )}
            </div>
          </div>

          {/* BACK LABEL CARD */}
          <div className="rounded-2xl bg-white border border-slate-200/80 p-6 shadow-card flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-900 text-white text-[10px] font-bold">
                    2
                  </span>
                  <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                    Back / Declaration Panel
                  </h2>
                </div>
                <span className="text-[11px] font-bold uppercase tracking-wider text-rose-600 bg-rose-50 px-2 py-0.5 rounded">
                  Mandatory
                </span>
              </div>
              <p className="text-xs text-slate-500 mb-4">
                Secondary panel with MRP, dates, manufacturer address, and barcode.
              </p>

              {backPreview ? (
                <div className="relative rounded-xl border border-slate-200 overflow-hidden bg-slate-950/5 group">
                  <img
                    src={backPreview}
                    alt="Back label preview"
                    className="w-full h-56 object-contain"
                  />
                  <div className="absolute inset-0 bg-navy-950/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                    <button
                      onClick={() => backRef.current?.click()}
                      className="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-slate-900 shadow hover:bg-slate-100"
                    >
                      Replace Image
                    </button>
                    <button
                      onClick={clearBack}
                      className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs font-semibold text-white shadow hover:bg-rose-700"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  onClick={() => backRef.current?.click()}
                  className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 hover:border-brand-500 bg-slate-50/50 hover:bg-brand-50/20 p-8 cursor-pointer transition-all h-56"
                >
                  <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-slate-500 shadow-2xs border border-slate-200 mb-3">
                    <IconUpload className="h-6 w-6 text-slate-600" />
                  </div>
                  <p className="text-xs font-bold text-slate-700">
                    Click to select back packaging
                  </p>
                  <p className="text-[11px] text-slate-400 mt-1">
                    Supports JPEG, PNG, WEBP up to 10MB
                  </p>
                </div>
              )}

              <input
                ref={backRef}
                type="file"
                accept="image/jpeg,image/png,image/webp"
                className="hidden"
                onChange={handlePickBack}
              />
            </div>

            {/* Back Quality Diagnostic Card */}
            <div className="mt-4 pt-4 border-t border-slate-100">
              {checkingQuality === "back" ? (
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <span className="h-3 w-3 rounded-full border-2 border-brand-600/30 border-t-brand-600 animate-spin" />
                  <span>Checking OpenCV image clarity...</span>
                </div>
              ) : backQuality ? (
                <div className="grid grid-cols-2 gap-2 text-[11px]">
                  <div className="rounded-lg bg-slate-50 p-2 border border-slate-200/60">
                    <span className="text-slate-400 block">Blur:</span>
                    <span className="font-semibold text-slate-700 capitalize">{backQuality.blur}</span>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-2 border border-slate-200/60">
                    <span className="text-slate-400 block">Glare:</span>
                    <span className="font-semibold text-slate-700 capitalize">{backQuality.glare}</span>
                  </div>
                </div>
              ) : (
                <p className="text-[11px] text-slate-400">Quality check runs automatically upon image selection</p>
              )}
            </div>
          </div>
        </div>

        {/* Processing Progress Display */}
        {uploading && (
          <div className="rounded-2xl border border-brand-200 bg-brand-50/50 p-6 shadow-sm space-y-3">
            <div className="flex items-center justify-between text-xs font-bold text-brand-900">
              <span className="flex items-center gap-2">
                <span className="h-3.5 w-3.5 rounded-full border-2 border-brand-600 border-t-transparent animate-spin" />
                <span>{analysisStage}</span>
              </span>
              <span className="font-mono">{progress}%</span>
            </div>

            <div className="h-2 w-full overflow-hidden rounded-full bg-brand-200/60">
              <div
                className="h-full rounded-full bg-brand-600 transition-all duration-300 ease-out shadow-sm"
                style={{ width: `${progress}%` }}
              />
            </div>
          </div>
        )}

        {/* Primary Action Button */}
        <div className="flex justify-end pt-4">
          <button
            onClick={handleUpload}
            disabled={!canSubmit}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-8 py-3.5 text-sm font-bold text-white shadow-lg shadow-brand-600/25 hover:bg-brand-700 active:scale-98 transition-all disabled:opacity-50 disabled:pointer-events-none"
          >
            <IconScan className="h-4 w-4" />
            <span>{uploading ? "Analyzing Declarations..." : "Run Compliance Check"}</span>
          </button>
        </div>
      </div>
    </AppShell>
  );
}
