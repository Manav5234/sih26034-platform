"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { ComplianceBadge } from "@/components/ui/Badges";
import { Modal } from "@/components/ui/Modal";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  IconScan,
  IconCheckCircle,
  IconAlertTriangle,
  IconFileText,
  IconDownload,
  IconMapPin,
  IconFlag,
  IconArrowLeft,
  IconEye,
  IconShield,
} from "@/components/ui/Icons";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface BBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface Evidence {
  id: string;
  source_type: string;
  raw_text: string | null;
  confidence: number;
  image_id: string | null;
  bbox: BBox | null;
  preprocessing_variant: string | null;
  extracted_at: string;
}

interface OfficerCorrection {
  officer_id: string;
  officer_name?: string;
  corrected_value: unknown;
  reason: string;
  corrected_at: string;
}

interface Declaration {
  id: string;
  field_name: string;
  extracted_value: unknown;
  rule_id: string | null;
  verdict: string;
  reason: string;
  confidence: number;
  evidence: Evidence[];
  officer_correction?: OfficerCorrection | null;
}

interface ImageInfo {
  id: string;
  url: string;
  label?: string;
  uploaded_at: string;
}

interface ScanData {
  id: string;
  product_id?: string | null;
  status: string;
  images: ImageInfo[];
  image_quality: {
    blur: string;
    glare: string;
    perspective: string;
    resolution: string;
    recommended_action: string;
  } | null;
  compliance_results: Declaration[];
  overall_status: string | null;
  warnings: string[];
  created_at: string;
}

function formatDateValue(val: unknown): string {
  if (!val || typeof val !== "object") return val ? String(val) : "—";
  const v = (val as Record<string, unknown>).value || val;
  if (typeof v !== "object" || !v) return String(v);
  const d = v as Record<string, unknown>;
  const monthNames = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const year = d.year;
  const month = d.month ? monthNames[d.month as number] : null;
  const day = d.day;
  if (!year || !month) return "—";
  return day ? `${day} ${month} ${year}` : `${month} ${year}`;
}

function formatFieldValue(fieldName: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (fieldName === "manufacture_date" || fieldName === "expiry_date") return formatDateValue(value);
  if (fieldName === "cautions") {
    if (typeof value === "object" && value !== null && (value as Record<string, unknown>).present) {
      return `"${(value as Record<string, unknown>).text || ""}"`;
    }
    return "Not present";
  }
  if (fieldName === "nutrition_facts" && Array.isArray(value)) {
    return value
      .map((n: Record<string, unknown>) => {
        const name = String(n.nutrient || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
        const val = n.value != null ? n.value : "—";
        return `${name}: ${val} ${n.unit || ""}`;
      })
      .join("; ");
  }
  if (typeof value === "object") {
    const v = value as Record<string, unknown>;
    if (v.amount !== undefined) {
      const sym = v.currency === "USD" ? "$" : v.currency === "EUR" ? "€" : "₹";
      return `${sym}${v.amount}`;
    }
    if (v.value !== undefined && v.unit) {
      return `${v.value} ${v.unit}`;
    }
    if (v.name) return String(v.name);
    return JSON.stringify(value);
  }
  return String(value);
}

export default function ScanResultPage() {
  const params = useParams();
  const id = params.id as string;

  const [scan, setScan] = useState<ScanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeImage, setActiveImage] = useState<string | null>(null);
  const [imgDimensions, setImgDimensions] = useState<{ naturalW: number; displayW: number } | null>(null);

  // Synchronized hover between bounding boxes and declarations
  const [highlightedField, setHighlightedField] = useState<string | null>(null);

  // Review mode & modal state
  const [reviewMode, setReviewMode] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [correctionTarget, setCorrectionTarget] = useState<Declaration | null>(null);
  const [correctValue, setCorrectValue] = useState("");
  const [correctReason, setCorrectReason] = useState("");

  // Report export loading states
  const [exportingPdf, setExportingPdf] = useState(false);
  const [exportingDocx, setExportingDocx] = useState(false);

  // Geolocation state
  const [location, setLocation] = useState<{
    latitude: number;
    longitude: number;
    accuracy_meters?: number;
    source: string;
    address_text?: string;
  } | null>(null);
  const [locationStatus, setLocationStatus] = useState<"idle" | "capturing" | "manual">("idle");
  const [manualLat, setManualLat] = useState("");
  const [manualLng, setManualLng] = useState("");
  const [manualAddress, setManualAddress] = useState("");

  // Consumer flag modal state
  const [flagModalOpen, setFlagModalOpen] = useState(false);
  const [flagFields, setFlagFields] = useState<string[]>([]);
  const [flagNote, setFlagNote] = useState("");
  const [flagContact, setFlagContact] = useState("");
  const [flagSubmitting, setFlagSubmitting] = useState(false);
  const [flagSuccess, setFlagSuccess] = useState(false);
  const [flagError, setFlagError] = useState("");

  async function load() {
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const res = await fetch(`${API}/scan/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Inspection record not found");
      const data = await res.json();
      setScan(data);
      if (data.images && data.images.length > 0) {
        setActiveImage(data.images[0].url);
      }
    } catch {
      setError("Failed to load inspection record.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  function captureGPS() {
    if (!navigator.geolocation) {
      setLocationStatus("manual");
      return;
    }
    setLocationStatus("capturing");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          accuracy_meters: pos.coords.accuracy,
          source: "GPS",
        });
        setLocationStatus("idle");
      },
      () => {
        setLocationStatus("manual");
      },
      { enableHighAccuracy: true, timeout: 10000 }
    );
  }

  function submitManualLocation() {
    const lat = parseFloat(manualLat);
    const lng = parseFloat(manualLng);
    if (isNaN(lat) || isNaN(lng)) {
      alert("Please enter valid decimal coordinates.");
      return;
    }
    setLocation({
      latitude: lat,
      longitude: lng,
      source: "MANUAL",
      address_text: manualAddress || undefined,
    });
    setLocationStatus("idle");
  }

  async function submitReview(
    actions: Array<{
      declaration_id: string;
      action: string;
      old_value: unknown;
      new_value?: unknown;
      reason: string;
    }>
  ) {
    setReviewing(true);
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const body: Record<string, unknown> = { scan_id: id, actions };
      if (location) body.location = location;

      const res = await fetch(`${API}/inspection`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) throw new Error("Failed to record officer review");

      await load();
      setCorrectionTarget(null);
      setCorrectValue("");
      setCorrectReason("");
    } catch {
      alert("Failed to submit officer review action.");
    } finally {
      setReviewing(false);
    }
  }

  function handleConfirm(decl: Declaration) {
    submitReview([
      {
        declaration_id: decl.id,
        action: "confirm",
        old_value: decl.extracted_value,
        reason: "Officer verified and confirmed compliance finding",
      },
    ]);
  }

  function handleOpenCorrection(decl: Declaration) {
    setCorrectionTarget(decl);
    setCorrectValue(
      typeof decl.extracted_value === "object"
        ? JSON.stringify(decl.extracted_value)
        : String(decl.extracted_value ?? "")
    );
    setCorrectReason("");
  }

  function handleConfirmCorrection() {
    if (!correctionTarget || !correctReason.trim()) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(correctValue);
    } catch {
      parsed = correctValue;
    }

    submitReview([
      {
        declaration_id: correctionTarget.id,
        action: "correct",
        old_value: correctionTarget.extracted_value,
        new_value: parsed,
        reason: correctReason,
      },
    ]);
  }

  function handleMarkUnresolved(decl: Declaration) {
    const reason = prompt("Enter specific reason for marking this declaration unresolved:");
    if (!reason) return;
    submitReview([
      {
        declaration_id: decl.id,
        action: "mark_unresolved",
        old_value: decl.extracted_value,
        reason,
      },
    ]);
  }

  async function handleExportReport(format: "pdf" | "docx") {
    if (format === "pdf") setExportingPdf(true);
    else setExportingDocx(true);

    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const res = await fetch(`${API}/reports/${id}/${format}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) throw new Error("Report generation failed");
      const blob = await res.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `ScanCheck-Inspection-${id}.${format}`;
      a.click();
      URL.revokeObjectURL(downloadUrl);
    } catch {
      alert(`Unable to export ${format.toUpperCase()} report.`);
    } finally {
      if (format === "pdf") setExportingPdf(false);
      else setExportingDocx(false);
    }
  }

  async function submitConsumerFlag() {
    if (flagFields.length === 0) return;
    setFlagSubmitting(true);
    setFlagError("");
    try {
      const res = await fetch(`${API}/scan/${id}/flag`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          reported_fields: flagFields,
          reporter_note: flagNote || null,
          reporter_contact: flagContact || null,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to submit flag");
      }

      setFlagSuccess(true);
      setTimeout(() => {
        setFlagModalOpen(false);
        setFlagSuccess(false);
        setFlagFields([]);
        setFlagNote("");
        setFlagContact("");
      }, 1500);
    } catch (e: unknown) {
      setFlagError(e instanceof Error ? e.message : "Failed to submit flag");
    } finally {
      setFlagSubmitting(false);
    }
  }

  if (loading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <div className="h-10 w-72 animate-pulse bg-slate-200 rounded-xl" />
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <div className="lg:col-span-6 h-[500px] animate-pulse bg-slate-200 rounded-2xl" />
            <div className="lg:col-span-6 space-y-4">
              <Skeleton className="h-24 w-full rounded-2xl" />
              <Skeleton className="h-24 w-full rounded-2xl" />
              <Skeleton className="h-24 w-full rounded-2xl" />
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  if (error || !scan) {
    return (
      <AppShell>
        <div className="py-20 text-center">
          <IconAlertTriangle className="h-12 w-12 text-rose-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-800">Inspection Record Not Found</h2>
          <p className="mt-1 text-sm text-slate-500">{error || "The requested scan ID does not exist."}</p>
          <Link
            href="/scans"
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-xs font-bold text-white shadow"
          >
            <IconArrowLeft className="h-4 w-4" />
            <span>Return to Scans</span>
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Top Breadcrumb Bar */}
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
            <Link href="/dashboard" className="hover:text-slate-800 transition-colors">
              Dashboard
            </Link>
            <span>/</span>
            <Link href="/scans" className="hover:text-slate-800 transition-colors">
              Scans
            </Link>
            <span>/</span>
            <span className="font-mono text-slate-700">{scan.id.slice(0, 8)}...</span>
          </div>

          {/* Action Buttons: Export & Review Toggle */}
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => handleExportReport("pdf")}
              disabled={exportingPdf}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-2xs transition-all disabled:opacity-50"
            >
              <IconFileText className="h-3.5 w-3.5 text-rose-600" />
              <span>{exportingPdf ? "Exporting..." : "Export PDF"}</span>
            </button>

            <button
              onClick={() => handleExportReport("docx")}
              disabled={exportingDocx}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-slate-900 shadow-2xs transition-all disabled:opacity-50"
            >
              <IconDownload className="h-3.5 w-3.5 text-brand-600" />
              <span>{exportingDocx ? "Exporting..." : "Export DOCX"}</span>
            </button>

            <button
              onClick={() => setReviewMode(!reviewMode)}
              className={`inline-flex items-center gap-1.5 rounded-xl px-4 py-1.5 text-xs font-bold transition-all shadow-sm ${
                reviewMode
                  ? "bg-amber-600 text-white hover:bg-amber-700"
                  : "bg-brand-600 text-white hover:bg-brand-700"
              }`}
            >
              <IconShield className="h-3.5 w-3.5" />
              <span>{reviewMode ? "Exit Review Mode" : "Enter Review Mode"}</span>
            </button>
          </div>
        </div>

        {/* Hero Inspection Header Banner */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
                Product Packaging Inspection
              </h1>
              <ComplianceBadge status={scan.overall_status} size="md" />
            </div>

            <div className="flex flex-wrap items-center gap-4 mt-2 text-xs text-slate-500 font-mono">
              <span>SCAN ID: {scan.id}</span>
              <span>•</span>
              <span>{new Date(scan.created_at).toLocaleString()}</span>
              <span>•</span>
              <span>{scan.compliance_results.length} Declarations Verified</span>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setFlagModalOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-rose-200 bg-rose-50/60 px-3.5 py-2 text-xs font-semibold text-rose-700 hover:bg-rose-100 transition-colors"
            >
              <IconFlag className="h-3.5 w-3.5 text-rose-600" />
              <span>Report Label Concern</span>
            </button>
          </div>
        </div>

        {/* OpenCV Quality Diagnostic Ribbon */}
        {scan.image_quality && (
          <div className="rounded-xl border border-slate-200/80 bg-slate-50/80 px-4 py-3 flex flex-wrap items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-2 font-bold text-slate-700">
              <IconEye className="h-4 w-4 text-brand-600" />
              <span>Computer Vision Diagnostic:</span>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-slate-600">
              <span>Blur: <strong className="text-slate-800 capitalize">{scan.image_quality.blur}</strong></span>
              <span>•</span>
              <span>Glare: <strong className="text-slate-800 capitalize">{scan.image_quality.glare}</strong></span>
              <span>•</span>
              <span>Perspective: <strong className="text-slate-800 capitalize">{scan.image_quality.perspective}</strong></span>
              <span>•</span>
              <span>Resolution: <strong className="text-slate-800 capitalize">{scan.image_quality.resolution}</strong></span>
              <span>•</span>
              <span>
                Recommended:{" "}
                <span className={`font-semibold px-2 py-0.5 rounded text-[11px] ${
                  scan.image_quality.recommended_action === "proceed"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-amber-100 text-amber-800"
                }`}>
                  {scan.image_quality.recommended_action}
                </span>
              </span>
            </div>
          </div>
        )}

        {/* Location Capture Bar (Only shown in Review Mode) */}
        {reviewMode && (
          <div className="rounded-2xl border border-brand-200 bg-brand-50/40 p-5 shadow-2xs">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <IconMapPin className="h-4 w-4 text-brand-600" />
                <h3 className="text-xs font-bold uppercase tracking-wider text-brand-900">
                  Officer Inspection Location Tag
                </h3>
              </div>
              <span className="text-[11px] text-slate-500">Attach GPS coordinates to this inspection</span>
            </div>

            {location ? (
              <div className="flex items-center justify-between rounded-xl bg-white p-3 border border-brand-200 text-xs">
                <div className="flex items-center gap-3">
                  <span className="font-mono font-bold text-slate-800">
                    ({location.latitude.toFixed(6)}, {location.longitude.toFixed(6)})
                  </span>
                  {location.accuracy_meters != null && (
                    <span className="text-slate-500">±{Math.round(location.accuracy_meters)}m accuracy</span>
                  )}
                  <span className="rounded-full bg-emerald-100 text-emerald-800 px-2 py-0.5 font-bold text-[10px]">
                    {location.source}
                  </span>
                  {location.address_text && (
                    <span className="text-slate-600 truncate max-w-xs">{location.address_text}</span>
                  )}
                </div>
                <button
                  onClick={() => setLocation(null)}
                  className="text-xs font-semibold text-rose-600 hover:underline"
                >
                  Clear
                </button>
              </div>
            ) : locationStatus === "manual" ? (
              <div className="space-y-2">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <input
                    type="text"
                    placeholder="Latitude (e.g. 28.6139)"
                    value={manualLat}
                    onChange={(e) => setManualLat(e.target.value)}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs"
                  />
                  <input
                    type="text"
                    placeholder="Longitude (e.g. 77.2090)"
                    value={manualLng}
                    onChange={(e) => setManualLng(e.target.value)}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs"
                  />
                  <input
                    type="text"
                    placeholder="Premises / Store Address (optional)"
                    value={manualAddress}
                    onChange={(e) => setManualAddress(e.target.value)}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs"
                  />
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={submitManualLocation}
                    className="rounded-xl bg-brand-600 px-3 py-1.5 text-xs font-bold text-white hover:bg-brand-700"
                  >
                    Save Coordinates
                  </button>
                  <button
                    onClick={() => setLocationStatus("idle")}
                    className="text-xs font-medium text-slate-500 hover:text-slate-800"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <button
                  onClick={captureGPS}
                  disabled={locationStatus === "capturing"}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-emerald-700 disabled:opacity-50"
                >
                  <IconMapPin className="h-3.5 w-3.5" />
                  <span>{locationStatus === "capturing" ? "Acquiring GPS Fix..." : "Use Current GPS Location"}</span>
                </button>
                <button
                  onClick={() => setLocationStatus("manual")}
                  className="rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                >
                  Enter Manually
                </button>
                <span className="text-xs text-slate-400">Optional: you may submit reviews without location.</span>
              </div>
            )}
          </div>
        )}

        {/* HERO WORKSPACE: DUAL-COLUMN COMPUTER VISION & COMPLIANCE FINDINGS */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          {/* LEFT (6 cols): Computer Vision Canvas */}
          <div className="lg:col-span-6 rounded-2xl bg-white border border-slate-200/80 p-5 shadow-card sticky top-20">
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <IconScan className="h-4 w-4 text-brand-600" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                  Evidence &amp; Reticle Viewer
                </h2>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                AI Precision Canvas
              </span>
            </div>

            {/* Packaging Image Canvas with Proportional Overlays */}
            {scan.images.length === 0 ? (
              <div className="h-72 rounded-xl bg-slate-100 flex items-center justify-center text-slate-400 text-xs">
                No images available for this scan
              </div>
            ) : (
              <div>
                <div className="relative rounded-xl border border-slate-200 overflow-hidden bg-slate-950 flex items-center justify-center">
                  {activeImage && (
                    <img
                      src={`${API}${activeImage}`}
                      alt="Packaging Evidence"
                      className="w-full max-h-[520px] object-contain select-none"
                      crossOrigin="anonymous"
                      onLoad={(e) => {
                        const el = e.currentTarget;
                        setImgDimensions({
                          naturalW: el.naturalWidth,
                          displayW: el.clientWidth,
                        });
                      }}
                    />
                  )}

                  {/* Bounding Box Overlays */}
                  {activeImage && imgDimensions && scan.compliance_results.map((decl) =>
                    decl.evidence.map((ev) => {
                      if (!ev.bbox || ev.image_id !== scan.images.find((i) => i.url === activeImage)?.id) {
                        return null;
                      }
                      const scale = imgDimensions.displayW / imgDimensions.naturalW;
                      const isHighlighted = highlightedField === decl.field_name;

                      return (
                        <div
                          key={ev.id}
                          className={`absolute border-2 transition-all duration-150 ${
                            isHighlighted
                              ? "border-cyan-400 bg-cyan-400/25 ring-2 ring-cyan-400/50 z-20"
                              : decl.verdict === "SATISFIED"
                              ? "border-emerald-500 bg-emerald-500/10 hover:border-emerald-400 hover:bg-emerald-500/20 z-10"
                              : "border-rose-500 bg-rose-500/15 hover:border-rose-400 hover:bg-rose-500/25 z-10"
                          }`}
                          style={{
                            left: `${ev.bbox.x * scale}px`,
                            top: `${ev.bbox.y * scale}px`,
                            width: `${ev.bbox.width * scale}px`,
                            height: `${ev.bbox.height * scale}px`,
                          }}
                          onMouseEnter={() => setHighlightedField(decl.field_name)}
                          onMouseLeave={() => setHighlightedField(null)}
                        >
                          <span
                            className={`absolute -top-5 left-0 rounded px-1.5 py-0.2 text-[9px] font-bold text-white whitespace-nowrap shadow-xs ${
                              isHighlighted
                                ? "bg-cyan-600 ring-1 ring-cyan-300"
                                : decl.verdict === "SATISFIED"
                                ? "bg-emerald-600"
                                : "bg-rose-600"
                            }`}
                          >
                            {decl.field_name}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>

                {/* Packaging Angle Switcher (Front / Back) */}
                {scan.images.length > 1 && (
                  <div className="mt-4 flex items-center gap-3 pt-3 border-t border-slate-100">
                    <span className="text-[11px] font-semibold text-slate-500">Angle:</span>
                    {scan.images.map((img, idx) => {
                      const label = img.label || (idx === 0 ? "Front Label" : "Back Label");
                      const isActive = activeImage === img.url;
                      return (
                        <button
                          key={img.id}
                          onClick={() => {
                            setActiveImage(img.url);
                            setImgDimensions(null);
                          }}
                          className={`flex items-center gap-2 rounded-xl border p-1.5 transition-all text-xs font-bold ${
                            isActive
                              ? "border-brand-600 bg-brand-50/50 text-brand-900 ring-2 ring-brand-500/20"
                              : "border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
                          }`}
                        >
                          <img
                            src={`${API}${img.url}`}
                            alt=""
                            className="h-9 w-9 rounded-lg object-cover"
                            crossOrigin="anonymous"
                          />
                          <span className="capitalize pr-2">{label}</span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* RIGHT (6 cols): Compliance Findings Cards */}
          <div className="lg:col-span-6 space-y-4">
            <div className="flex items-center justify-between pb-2">
              <div>
                <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Compliance Declarations ({scan.compliance_results.length})
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Extracted packaging fields checked against Legal Metrology Rules
                </p>
              </div>
            </div>

            {scan.compliance_results.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center bg-white">
                <p className="text-sm font-semibold text-slate-700">No declarations extracted</p>
                <p className="text-xs text-slate-400 mt-1">
                  The inspection engine could not locate text fields on this packaging.
                </p>
              </div>
            ) : (
              scan.compliance_results.map((decl) => {
                const isHovered = highlightedField === decl.field_name;

                return (
                  <div
                    key={decl.id}
                    onMouseEnter={() => setHighlightedField(decl.field_name)}
                    onMouseLeave={() => setHighlightedField(null)}
                    className={`rounded-2xl bg-white border p-5 shadow-card transition-all duration-150 ${
                      isHovered
                        ? "border-brand-500 ring-2 ring-brand-500/20 shadow-card-hover"
                        : "border-slate-200/80 hover:border-slate-300"
                    }`}
                  >
                    {/* Declaration Header */}
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-sm font-bold text-slate-900 capitalize">
                            {decl.field_name.replace(/_/g, " ")}
                          </h3>
                          {decl.rule_id && (
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-mono font-semibold text-slate-600 border border-slate-200">
                              {decl.rule_id}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {decl.reason}
                        </p>
                      </div>

                      <ComplianceBadge status={decl.verdict} size="sm" />
                    </div>

                    {/* Extracted Value Callout */}
                    <div className="mt-3 rounded-xl bg-slate-50 border border-slate-200/60 p-3 flex items-center justify-between">
                      <div className="min-w-0">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400 block">
                          AI Extracted Value
                        </span>
                        <span className="text-xs font-mono font-bold text-slate-800 break-all">
                          {formatFieldValue(decl.field_name, decl.extracted_value)}
                        </span>
                      </div>
                      <div className="text-right shrink-0">
                        <span className="text-[10px] uppercase tracking-wider font-bold text-slate-400 block">
                          Confidence
                        </span>
                        <span className="text-xs font-mono font-bold text-emerald-700">
                          {(decl.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>

                    {/* Officer Correction Callout (Additive, does not overwrite AI findings) */}
                    {decl.officer_correction && (
                      <div className="mt-3 rounded-xl border border-brand-200 bg-brand-50/50 p-3.5 space-y-1">
                        <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-brand-700">
                          <span>Officer Correction Override</span>
                          <span>{new Date(decl.officer_correction.corrected_at).toLocaleDateString()}</span>
                        </div>
                        <div className="text-xs text-brand-900 font-semibold">
                          <span>{decl.officer_correction.officer_name || "Officer"} set value to: </span>
                          <span className="font-mono bg-white px-1.5 py-0.5 rounded border border-brand-200">
                            {JSON.stringify(decl.officer_correction.corrected_value)}
                          </span>
                        </div>
                        <p className="text-[11px] text-brand-700">
                          Justification: &quot;{decl.officer_correction.reason}&quot;
                        </p>
                      </div>
                    )}

                    {/* Evidence Source Badges */}
                    {decl.evidence.length > 0 && (
                      <div className="mt-3 pt-3 border-t border-slate-100 flex flex-wrap items-center gap-2">
                        <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          Evidence:
                        </span>
                        {decl.evidence.map((ev) => (
                          <span
                            key={ev.id}
                            className="inline-flex items-center gap-1 rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-mono text-slate-600 border border-slate-200"
                          >
                            <span>[{ev.source_type}]</span>
                            {ev.raw_text && <span className="font-semibold text-slate-800">&quot;{ev.raw_text}&quot;</span>}
                            <span>({(ev.confidence * 100).toFixed(0)}%)</span>
                          </span>
                        ))}
                      </div>
                    )}

                    {/* Review Mode Action Bar */}
                    {reviewMode && (
                      <div className="mt-4 pt-3 border-t border-slate-100 flex items-center gap-2">
                        <button
                          onClick={() => handleConfirm(decl)}
                          disabled={reviewing}
                          className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-emerald-700 disabled:opacity-50 transition-colors"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => handleOpenCorrection(decl)}
                          disabled={reviewing}
                          className="rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-bold text-white shadow-2xs hover:bg-amber-600 disabled:opacity-50 transition-colors"
                        >
                          Correct Finding
                        </button>
                        <button
                          onClick={() => handleMarkUnresolved(decl)}
                          disabled={reviewing}
                          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 transition-colors"
                        >
                          Mark Unresolved
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* OFFICER CORRECTION MODAL */}
        <Modal
          isOpen={Boolean(correctionTarget)}
          onClose={() => setCorrectionTarget(null)}
          title={`Correct Finding: ${correctionTarget?.field_name.replace(/_/g, " ")}`}
          subtitle="All changes are recorded as additive overrides in the immutable audit trail."
        >
          {correctionTarget && (
            <div className="space-y-4">
              <div className="rounded-xl bg-slate-50 p-3 border border-slate-200 text-xs">
                <span className="text-slate-400 font-bold block">Current AI Extracted Value:</span>
                <span className="font-mono text-slate-800 font-bold">
                  {formatFieldValue(correctionTarget.field_name, correctionTarget.extracted_value)}
                </span>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Corrected Value (JSON or plain text)
                </label>
                <input
                  type="text"
                  value={correctValue}
                  onChange={(e) => setCorrectValue(e.target.value)}
                  placeholder="Enter corrected value..."
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs font-mono focus:border-brand-600 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Regulatory Reason / Justification
                </label>
                <textarea
                  value={correctReason}
                  onChange={(e) => setCorrectReason(e.target.value)}
                  placeholder="State evidence observed on packaging justifying this correction..."
                  rows={3}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs focus:border-brand-600 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  onClick={() => setCorrectionTarget(null)}
                  className="rounded-xl border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  onClick={handleConfirmCorrection}
                  disabled={reviewing || !correctReason.trim()}
                  className="rounded-xl bg-amber-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-amber-700 disabled:opacity-50"
                >
                  {reviewing ? "Saving Correction..." : "Submit Audit Correction"}
                </button>
              </div>
            </div>
          )}
        </Modal>

        {/* CONSUMER FLAG REPORTING MODAL */}
        <Modal
          isOpen={flagModalOpen}
          onClose={() => setFlagModalOpen(false)}
          title="Report a Problem with this Product Label"
          subtitle="Submit an enforcement flag if packaging declarations appear false, missing, or misleading."
        >
          {flagSuccess ? (
            <div className="py-6 text-center space-y-2">
              <IconCheckCircle className="h-10 w-10 text-emerald-600 mx-auto" />
              <h4 className="text-sm font-bold text-slate-900">Flag Successfully Submitted</h4>
              <p className="text-xs text-slate-500">
                An authorized legal metrology officer will inspect this packaging report.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {flagError && (
                <div className="rounded-xl bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800">
                  {flagError}
                </div>
              )}

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-2">
                  Select Problematic Declarations
                </label>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 max-h-48 overflow-y-auto p-1">
                  {scan.compliance_results.map((decl) => {
                    const isChecked = flagFields.includes(decl.field_name);
                    return (
                      <label
                        key={decl.id}
                        className={`flex items-center gap-2 rounded-lg border p-2 text-xs cursor-pointer transition-all ${
                          isChecked
                            ? "border-rose-300 bg-rose-50/70 text-rose-900 font-bold"
                            : "border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={isChecked}
                          onChange={() => {
                            setFlagFields((prev) =>
                              prev.includes(decl.field_name)
                                ? prev.filter((f) => f !== decl.field_name)
                                : [...prev, decl.field_name]
                            );
                          }}
                          className="rounded border-slate-300 text-rose-600 focus:ring-rose-500"
                        />
                        <span className="truncate">{decl.field_name}</span>
                      </label>
                    );
                  })}
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Observation Notes (Optional)
                </label>
                <textarea
                  value={flagNote}
                  onChange={(e) => setFlagNote(e.target.value)}
                  placeholder="Describe what looks incorrect (e.g., MRP missing currency symbol, expiry date smudged)..."
                  rows={2}
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs focus:border-rose-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1">
                  Reporter Contact (Optional)
                </label>
                <input
                  type="text"
                  value={flagContact}
                  onChange={(e) => setFlagContact(e.target.value)}
                  placeholder="Email or phone for investigation follow-up"
                  className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs focus:border-rose-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  onClick={() => setFlagModalOpen(false)}
                  className="rounded-xl border border-slate-300 px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
                >
                  Cancel
                </button>
                <button
                  onClick={submitConsumerFlag}
                  disabled={flagSubmitting || flagFields.length === 0}
                  className="rounded-xl bg-rose-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-rose-700 disabled:opacity-50"
                >
                  {flagSubmitting ? "Submitting Flag..." : "Submit Regulatory Flag"}
                </button>
              </div>
            </div>
          )}
        </Modal>
      </div>
    </AppShell>
  );
}
