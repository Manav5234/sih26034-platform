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

  async function submitReview(actions: Array<{ declaration_id: string; action: string; old_value: unknown; new_value?: unknown; reason: string }>) {
    setReviewing(true);
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      await fetch(`${API}/inspection`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ scan_id: id, actions }),
      });
      // Reload scan to show updated declarations
      await load();
      setReviewMode(false);
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

  if (loading) return <main className="flex min-h-screen items-center justify-center"><p className="text-slate-400">Loading...</p></main>;
  if (error || !scan) return <main className="flex min-h-screen items-center justify-center"><p className="text-red-500">{error || "Not found"}</p></main>;

  const verdictColor = (v: string) => VERDICT_COLORS[v] || "bg-slate-100 text-slate-600";

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-4 flex items-center gap-3">
          <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">&larr; Dashboard</Link>
          <Link href="/scan" className="text-sm text-blue-600 hover:underline">New Scan</Link>
        </div>

        <div className="mb-4 flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-800">Scan Result</h1>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${verdictColor(scan.overall_status || "NOT_VERIFIED")}`}>
            {scan.overall_status || "NOT_VERIFIED"}
          </span>
          <button
            onClick={() => setReviewMode(!reviewMode)}
            className={`ml-auto rounded-lg px-3 py-1.5 text-xs font-medium transition ${reviewMode ? "bg-red-100 text-red-700 hover:bg-red-200" : "bg-blue-600 text-white hover:bg-blue-700"}`}
          >
            {reviewMode ? "Exit Review" : "Review"}
          </button>
        </div>

        {scan.image_quality && (
          <div className="mb-4 rounded-xl bg-white p-4 shadow text-sm text-slate-600">
            <span className="font-medium">Image Quality:</span>{" "}
            Blur: {scan.image_quality.blur} | Glare: {scan.image_quality.glare} |{" "}
            Perspective: {scan.image_quality.perspective} | Resolution: {scan.image_quality.resolution} |{" "}
            Action: <span className="font-medium">{scan.image_quality.recommended_action}</span>
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
                    {scan.images.map((img) => (
                      <button
                        key={img.id}
                        onClick={() => { setActiveImage(img.url); setImgDimensions(null); }}
                        className={`rounded border p-1 ${activeImage === img.url ? "border-blue-500" : "border-slate-200"}`}
                      >
                        <img src={`${API}${img.url}`} alt="" className="h-12 w-12 rounded object-cover" crossOrigin="anonymous" />
                      </button>
                    ))}
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
                    Value: <span className="font-mono text-slate-700">{JSON.stringify(decl.extracted_value)}</span>
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
                      {decl.evidence.map((ev) => (
                        <div key={ev.id} className="ml-2 text-xs text-slate-400">
                          [{ev.source_type}] &quot;{ev.raw_text}&quot; (conf: {(ev.confidence * 100).toFixed(0)}%)
                          {ev.bbox && <span className="ml-1 text-slate-300">@ bbox({ev.bbox.x}, {ev.bbox.y}, {ev.bbox.width}, {ev.bbox.height})</span>}
                        </div>
                      ))}
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
