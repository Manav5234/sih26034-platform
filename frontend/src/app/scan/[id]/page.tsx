"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

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
  status: string;
  images: ImageInfo[];
  image_quality: { blur: string; glare: string; perspective: string; resolution: string; recommended_action: string } | null;
  compliance_results: Declaration[];
  overall_status: string | null;
  warnings: string[];
  created_at: string;
}

function formatDateValue(val: unknown): string {
  if (!val || typeof val !== "object") return val ? String(val) : "\u2014";
  const v = (val as Record<string, unknown>).value || val;
  if (typeof v !== "object" || !v) return String(v);
  const d = v as Record<string, unknown>;
  const monthNames = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const year = d.year;
  const month = d.month ? monthNames[d.month as number] : null;
  const day = d.day;
  if (!year || !month) return "\u2014";
  return day ? `${day} ${month} ${year}` : `${month} ${year}`;
}

function formatFieldValue(fieldName: string, value: unknown): string {
  if (value === null || value === undefined) return "\u2014";
  if (fieldName === "manufacture_date" || fieldName === "expiry_date") return formatDateValue(value);
  if (fieldName === "cautions") {
    if (typeof value === "object" && value !== null && (value as Record<string, unknown>).present) {
      return `"${(value as Record<string, unknown>).text || ""}"`;
    }
    return "Not present";
  }
  if (fieldName === "nutrition_facts" && Array.isArray(value)) {
    return value.map((n: Record<string, unknown>) => {
      const name = String(n.nutrient || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
      const val = n.value != null ? n.value : "\u2014";
      return `${name}: ${val} ${n.unit || ""}`;
    }).join("; ");
  }
  if (typeof value === "object") {
    if ((value as Record<string, unknown>).amount !== undefined) {
      const v = value as Record<string, unknown>;
      const sym = v.currency === "USD" ? "$" : v.currency === "EUR" ? "\u20ac" : "\u20b9";
      return `${sym}${v.amount}`;
    }
    if ((value as Record<string, unknown>).value !== undefined && (value as Record<string, unknown>).unit) {
      const v = value as Record<string, unknown>;
      return `${v.value} ${v.unit}`;
    }
    if ((value as Record<string, unknown>).name) return String((value as Record<string, unknown>).name);
    return JSON.stringify(value);
  }
  return String(value);
}

const VERDICT_COLORS: Record<string, string> = {
  SATISFIED: "bg-green-100 text-green-800",
  VIOLATION: "bg-red-100 text-red-800",
  NOT_VERIFIED: "bg-amber-100 text-amber-800",
  CONFLICT: "bg-purple-100 text-purple-800",
  NOT_APPLICABLE: "bg-slate-100 text-slate-600",
};

export default function ScanResultPage() {
  const params = useParams();
  const id = params.id as string;
  const [scan, setScan] = useState<ScanData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [activeImage, setActiveImage] = useState<string | null>(null);
  const [imgDimensions, setImgDimensions] = useState<{ naturalW: number; displayW: number } | null>(null);

  // Review mode state
  const [reviewMode, setReviewMode] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  const [correctForm, setCorrectForm] = useState<string | null>(null); // declaration_id being corrected
  const [correctValue, setCorrectValue] = useState("");
  const [correctReason, setCorrectReason] = useState("");

  // Geolocation state
  const [location, setLocation] = useState<{ latitude: number; longitude: number; accuracy_meters?: number; source: string; address_text?: string } | null>(null);
  const [locationStatus, setLocationStatus] = useState<"idle" | "capturing" | "manual">("idle");
  const [manualLat, setManualLat] = useState("");
  const [manualLng, setManualLng] = useState("");
  const [manualAddress, setManualAddress] = useState("");

  // Consumer flag state
  const [flagMode, setFlagMode] = useState(false);
  const [flagFields, setFlagFields] = useState<string[]>([]);
  const [flagNote, setFlagNote] = useState("");
  const [flagContact, setFlagContact] = useState("");
  const [flagSubmitting, setFlagSubmitting] = useState(false);
  const [flagSubmitted, setFlagSubmitted] = useState(false);
  const [flagError, setFlagError] = useState("");

  async function load() {
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const res = await fetch(`${API}/scan/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Scan not found");
      const data = await res.json();
      setScan(data);
      if (data.images.length > 0) setActiveImage(data.images[0].url);
    } catch {
      setError("Failed to load scan");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

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
      alert("Enter valid coordinates");
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

  async function submitReview(actions: Array<{ declaration_id: string; action: string; old_value: unknown; new_value?: unknown; reason: string }>) {
    setReviewing(true);
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const body: Record<string, unknown> = { scan_id: id, actions };
      if (location) body.location = location;
      await fetch(`${API}/inspection`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(body),
      });
      // Reload scan to show updated declarations
      await load();
      setReviewMode(false);
      setLocation(null);
    } catch {
      alert("Failed to submit review");
    } finally {
      setReviewing(false);
    }
  }

  function handleConfirm(decl: Declaration) {
    submitReview([{
      declaration_id: decl.id,
      action: "confirm",
      old_value: decl.extracted_value,
      reason: "Officer confirmed AI verdict",
    }]);
  }

  function handleCorrect(decl: Declaration) {
    let parsed: unknown;
    try {
      parsed = JSON.parse(correctValue);
    } catch {
      parsed = correctValue;
    }
    submitReview([{
      declaration_id: decl.id,
      action: "correct",
      old_value: decl.extracted_value,
      new_value: parsed,
      reason: correctReason,
    }]);
    setCorrectForm(null);
    setCorrectValue("");
    setCorrectReason("");
  }

  function handleMarkUnresolved(decl: Declaration) {
    const reason = prompt("Reason for marking unresolved:");
    if (!reason) return;
    submitReview([{
      declaration_id: decl.id,
      action: "mark_unresolved",
      old_value: decl.extracted_value,
      reason,
    }]);
  }

  async function submitFlag() {
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
      setFlagSubmitted(true);
      setFlagMode(false);
    } catch (e: unknown) {
      setFlagError(e instanceof Error ? e.message : "Failed to submit flag");
    } finally {
      setFlagSubmitting(false);
    }
  }

  function toggleFlagField(field: string) {
    setFlagFields((prev) =>
      prev.includes(field) ? prev.filter((f) => f !== field) : [...prev, field]
    );
  }

  if (loading) return <main className="flex min-h-screen items-center justify-center"><p className="text-slate-400">Loading...</p></main>;
  if (error || !scan) return <main className="flex min-h-screen items-center justify-center"><p className="text-red-500">{error || "Not found"}</p></main>;

  const verdictColor = (v: string) => VERDICT_COLORS[v] || "bg-slate-100 text-slate-600";

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-4 flex items-center gap-3">
          <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">&larr; Dashboard</Link>
          <Link href="/scans" className="text-sm text-blue-600 hover:underline">Scans</Link>
          <Link href="/scan" className="text-sm text-blue-600 hover:underline">New Scan</Link>
        </div>

        <div className="mb-4 flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-800">Scan Result</h1>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${verdictColor(scan.overall_status || "NOT_VERIFIED")}`}>
            {scan.overall_status || "NOT_VERIFIED"}
          </span>
          <div className="ml-auto flex gap-2">
            <button
              onClick={async () => {
                const tokenRes = await fetch("/api/auth/token");
                const { token } = await tokenRes.json();
                const r = await fetch(`${API}/reports/${id}/pdf`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
                if (r.ok) {
                  const blob = await r.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a"); a.href = url; a.download = `report-${id}.pdf`; a.click();
                  URL.revokeObjectURL(url);
                }
              }}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
            >
              PDF
            </button>
            <button
              onClick={async () => {
                const tokenRes = await fetch("/api/auth/token");
                const { token } = await tokenRes.json();
                const r = await fetch(`${API}/reports/${id}/docx`, { method: "POST", headers: { Authorization: `Bearer ${token}` } });
                if (r.ok) {
                  const blob = await r.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a"); a.href = url; a.download = `report-${id}.docx`; a.click();
                  URL.revokeObjectURL(url);
                }
              }}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
            >
              DOCX
            </button>
            <button
              onClick={() => setReviewMode(!reviewMode)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${reviewMode ? "bg-red-100 text-red-700 hover:bg-red-200" : "bg-blue-600 text-white hover:bg-blue-700"}`}
            >
              {reviewMode ? "Exit Review" : "Review"}
            </button>
          </div>
        </div>

        {scan.image_quality && (
          <div className="mb-4 rounded-xl bg-white p-4 shadow text-sm text-slate-600">
            <span className="font-medium">Image Quality:</span>{" "}
            Blur: {scan.image_quality.blur} | Glare: {scan.image_quality.glare} |{" "}
            Perspective: {scan.image_quality.perspective} | Resolution: {scan.image_quality.resolution} |{" "}
            Action: <span className="font-medium">{scan.image_quality.recommended_action}</span>
          </div>
        )}

        {/* Location capture — only shown in review mode */}
        {reviewMode && (
          <div className="mb-4 rounded-xl bg-white p-4 shadow">
            <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Inspection Location</h3>
            {location ? (
              <div className="flex items-center gap-3 text-sm">
                <span className="text-slate-700">
                  ({location.latitude.toFixed(6)}, {location.longitude.toFixed(6)})
                  {location.accuracy_meters != null && <span className="text-slate-400"> ±{Math.round(location.accuracy_meters)}m</span>}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${location.source === "GPS" ? "bg-green-100 text-green-700" : "bg-blue-100 text-blue-700"}`}>
                  {location.source}
                </span>
                <button onClick={() => setLocation(null)} className="text-xs text-red-500 hover:underline">Clear</button>
              </div>
            ) : locationStatus === "manual" ? (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <input type="text" placeholder="Latitude" value={manualLat} onChange={(e) => setManualLat(e.target.value)}
                    className="w-32 rounded border border-slate-300 px-2 py-1 text-xs" />
                  <input type="text" placeholder="Longitude" value={manualLng} onChange={(e) => setManualLng(e.target.value)}
                    className="w-32 rounded border border-slate-300 px-2 py-1 text-xs" />
                  <input type="text" placeholder="Address (optional)" value={manualAddress} onChange={(e) => setManualAddress(e.target.value)}
                    className="flex-1 rounded border border-slate-300 px-2 py-1 text-xs" />
                </div>
                <div className="flex gap-2">
                  <button onClick={submitManualLocation} className="rounded bg-blue-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-blue-700">Save Location</button>
                  <button onClick={() => setLocationStatus("idle")} className="text-xs text-slate-400 hover:underline">Cancel</button>
                </div>
              </div>
            ) : (
              <div className="flex gap-2">
                <button onClick={captureGPS} disabled={locationStatus === "capturing"}
                  className="rounded bg-green-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-green-700 disabled:opacity-50">
                  {locationStatus === "capturing" ? "Locating..." : "Use GPS"}
                </button>
                <button onClick={() => setLocationStatus("manual")}
                  className="rounded border border-slate-300 px-2 py-1 text-[10px] font-medium text-slate-600 hover:bg-slate-50">
                  Enter Manually
                </button>
                <span className="self-center text-[10px] text-slate-400">Optional — skip to submit without location</span>
              </div>
            )}
          </div>
        )}

        {/* Consumer Flag Section */}
        {scan.compliance_results.length > 0 && (
          <div className="mt-6 rounded-xl bg-white p-4 shadow">
            {flagSubmitted ? (
              <div className="text-center">
                <p className="text-sm font-medium text-green-700">Thank you — your flag has been submitted.</p>
                <p className="mt-1 text-xs text-slate-500">An officer will review it shortly.</p>
                <button
                  onClick={() => { setFlagSubmitted(false); setFlagFields([]); setFlagNote(""); setFlagContact(""); }}
                  className="mt-3 rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
                >
                  Flag another issue
                </button>
              </div>
            ) : flagMode ? (
              <div>
                <h3 className="mb-3 text-sm font-semibold text-slate-700">Report a problem with this label</h3>
                <p className="mb-3 text-xs text-slate-500">Select the fields that look incorrect:</p>
                <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
                  {scan.compliance_results.map((decl) => (
                    <label key={decl.id} className="flex items-center gap-2 text-xs text-slate-700">
                      <input
                        type="checkbox"
                        checked={flagFields.includes(decl.field_name)}
                        onChange={() => toggleFlagField(decl.field_name)}
                        className="h-3.5 w-3.5 rounded border-slate-300"
                      />
                      {decl.field_name}
                    </label>
                  ))}
                </div>
                <textarea
                  placeholder="Optional note (what looks wrong?)"
                  value={flagNote}
                  onChange={(e) => setFlagNote(e.target.value)}
                  className="mb-2 w-full rounded-lg border border-slate-300 px-3 py-2 text-xs"
                  rows={2}
                />
                <input
                  type="text"
                  placeholder="Optional contact (email or phone for follow-up)"
                  value={flagContact}
                  onChange={(e) => setFlagContact(e.target.value)}
                  className="mb-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-xs"
                />
                {flagError && <p className="mb-2 text-xs text-red-600">{flagError}</p>}
                <div className="flex gap-2">
                  <button
                    onClick={submitFlag}
                    disabled={flagSubmitting || flagFields.length === 0}
                    className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50"
                  >
                    {flagSubmitting ? "Submitting..." : "Submit Flag"}
                  </button>
                  <button
                    onClick={() => { setFlagMode(false); setFlagFields([]); setFlagNote(""); setFlagContact(""); setFlagError(""); }}
                    className="rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setFlagMode(true)}
                className="w-full rounded-lg border border-dashed border-slate-300 px-3 py-2 text-xs text-slate-500 hover:border-red-300 hover:text-red-600 transition"
              >
                Report a problem with this label
              </button>
            )}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          {/* Image viewer with bounding boxes */}
          <div className="rounded-xl bg-white p-4 shadow">
            <h2 className="mb-2 text-sm font-semibold text-slate-700">Image &amp; Evidence</h2>
            {scan.images.length === 0 ? (
              <p className="text-sm text-slate-400">No images</p>
            ) : (
              <>
                <div className="relative mb-2">
                  {activeImage && (
                    <img
                      src={`${API}${activeImage}`}
                      alt="Uploaded product"
                      className="w-full rounded-lg"
                      crossOrigin="anonymous"
                      onLoad={(e) => {
                        const el = e.currentTarget;
                        setImgDimensions({ naturalW: el.naturalWidth, displayW: el.clientWidth });
                      }}
                    />
                  )}
                  {activeImage && imgDimensions && scan.compliance_results.map((decl) =>
                    decl.evidence.map((ev) => {
                      if (!ev.bbox || ev.image_id !== scan.images.find((i) => i.url === activeImage)?.id) return null;
                      const scale = imgDimensions.displayW / imgDimensions.naturalW;
                      return (
                        <div
                          key={ev.id}
                          className="absolute border-2 border-red-500 bg-red-500/10"
                          style={{
                            left: `${ev.bbox.x * scale}px`,
                            top: `${ev.bbox.y * scale}px`,
                            width: `${ev.bbox.width * scale}px`,
                            height: `${ev.bbox.height * scale}px`,
                          }}
                        >
                          <span className="absolute -top-5 left-0 rounded bg-red-500 px-1 text-[10px] text-white whitespace-nowrap">
                            {decl.field_name}
                          </span>
                        </div>
                      );
                    })
                  )}
                </div>
                {scan.images.length > 1 && (
                  <div className="flex gap-2">
                    {scan.images.map((img, idx) => {
                      const label = img.label || (idx === 0 ? "front" : "back");
                      return (
                        <div key={img.id} className="flex flex-col items-center">
                          <button
                            onClick={() => { setActiveImage(img.url); setImgDimensions(null); }}
                            className={`rounded border p-1 ${activeImage === img.url ? "border-blue-500" : "border-slate-200"}`}
                          >
                            <img src={`${API}${img.url}`} alt="" className="h-12 w-12 rounded object-cover" crossOrigin="anonymous" />
                          </button>
                          <span className="mt-0.5 text-[10px] font-medium text-slate-500 capitalize">{label}</span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>

          {/* Declarations list */}
          <div className="space-y-3">
            <h2 className="text-sm font-semibold text-slate-700">Declarations</h2>
            {scan.compliance_results.length === 0 ? (
              <p className="text-sm text-slate-400">No declarations</p>
            ) : (
              scan.compliance_results.map((decl) => (
                <div key={decl.id} className="rounded-xl bg-white p-4 shadow">
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-800">{decl.field_name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${verdictColor(decl.verdict)}`}>
                      {decl.verdict}
                    </span>
                  </div>
                  <div className="mb-1 text-xs text-slate-500">
                    Value: <span className="font-mono text-slate-700">{formatFieldValue(decl.field_name, decl.extracted_value)}</span>
                  </div>
                  <div className="mb-1 text-xs text-slate-500">
                    Rule: <span className="font-mono text-slate-700">{decl.rule_id || "—"}</span>
                  </div>
                  <div className="mb-1 text-xs text-slate-500">Reason: {decl.reason}</div>

                  {/* Officer correction — additive, not overwriting */}
                  {decl.officer_correction && (
                    <div className="mt-2 rounded-lg border border-blue-200 bg-blue-50 p-2">
                      <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-blue-600">Officer Correction</p>
                      <div className="text-xs text-blue-800">
                        <span className="font-medium">{decl.officer_correction.officer_name || "Officer"}</span>
                        {" "}set value to{" "}
                        <span className="font-mono font-medium">{JSON.stringify(decl.officer_correction.corrected_value)}</span>
                      </div>
                      <div className="text-[10px] text-blue-500 mt-0.5">Reason: {decl.officer_correction.reason}</div>
                    </div>
                  )}

                  {decl.evidence.length > 0 && (
                    <div className="mt-2 border-t border-slate-100 pt-2">
                      <p className="mb-1 text-xs font-medium text-slate-500">Evidence:</p>
                      {decl.evidence.map((ev) => {
                        const sourceImg = scan.images.find(i => i.id === ev.image_id);
                        const imgLabel = sourceImg?.label || "—";
                        return (
                          <div key={ev.id} className="ml-2 text-xs text-slate-400">
                            [{ev.source_type}] &quot;{ev.raw_text}&quot; (conf: {(ev.confidence * 100).toFixed(0)}%)
                            <span className="ml-1 text-slate-300">[{imgLabel}]</span>
                            {ev.bbox && <span className="ml-1 text-slate-300">@ bbox({ev.bbox.x}, {ev.bbox.y}, {ev.bbox.width}, {ev.bbox.height})</span>}
                          </div>
                        );
                      })}
                    </div>
                  )}

                  {/* Review actions */}
                  {reviewMode && (
                    <div className="mt-3 border-t border-slate-100 pt-3 flex gap-2">
                      <button
                        onClick={() => handleConfirm(decl)}
                        disabled={reviewing}
                        className="rounded bg-green-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-green-700 disabled:opacity-50"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setCorrectForm(correctForm === decl.id ? null : decl.id)}
                        disabled={reviewing}
                        className="rounded bg-amber-500 px-2 py-1 text-[10px] font-medium text-white hover:bg-amber-600 disabled:opacity-50"
                      >
                        Correct
                      </button>
                      <button
                        onClick={() => handleMarkUnresolved(decl)}
                        disabled={reviewing}
                        className="rounded bg-slate-500 px-2 py-1 text-[10px] font-medium text-white hover:bg-slate-600 disabled:opacity-50"
                      >
                        Mark Unresolved
                      </button>
                    </div>
                  )}

                  {/* Correct form */}
                  {correctForm === decl.id && (
                    <div className="mt-2 rounded-lg border border-amber-200 bg-amber-50 p-2 space-y-2">
                      <input
                        type="text"
                        placeholder="New value (JSON or text)"
                        value={correctValue}
                        onChange={(e) => setCorrectValue(e.target.value)}
                        className="w-full rounded border border-amber-300 px-2 py-1 text-xs"
                      />
                      <input
                        type="text"
                        placeholder="Reason for correction"
                        value={correctReason}
                        onChange={(e) => setCorrectReason(e.target.value)}
                        className="w-full rounded border border-amber-300 px-2 py-1 text-xs"
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleCorrect(decl)}
                          disabled={reviewing || !correctReason}
                          className="rounded bg-amber-600 px-2 py-1 text-[10px] font-medium text-white hover:bg-amber-700 disabled:opacity-50"
                        >
                          Submit Correction
                        </button>
                        <button
                          onClick={() => { setCorrectForm(null); setCorrectValue(""); setCorrectReason(""); }}
                          className="rounded bg-slate-200 px-2 py-1 text-[10px] font-medium text-slate-600 hover:bg-slate-300"
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
