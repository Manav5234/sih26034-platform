"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface FlagDetail {
  id: string;
  scan_id: string;
  reported_fields: string[];
  reporter_note: string | null;
  reporter_contact: string | null;
  status: string;
  created_at: string;
  reviewed_by_officer_id: string | null;
  reviewed_at: string | null;
  officer_notes: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  NEW: "bg-red-100 text-red-800",
  ACKNOWLEDGED: "bg-amber-100 text-amber-800",
  RESOLVED: "bg-green-100 text-green-800",
  DISMISSED: "bg-slate-100 text-slate-600",
};

export default function FlagDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const [flag, setFlag] = useState<FlagDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [reviewStatus, setReviewStatus] = useState<string>("ACKNOWLEDGED");
  const [officerNotes, setOfficerNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function load() {
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const res = await fetch(`${API}/flags/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Flag not found");
      setFlag(await res.json());
    } catch {
      setError("Failed to load flag");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [id]);

  async function submitReview() {
    setSubmitting(true);
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const res = await fetch(`${API}/flags/${id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ status: reviewStatus, officer_notes: officerNotes || null }),
      });
      if (!res.ok) throw new Error("Failed to review");
      setFlag(await res.json());
    } catch {
      alert("Failed to submit review");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <main className="flex min-h-screen items-center justify-center"><p className="text-slate-400">Loading...</p></main>;
  if (error || !flag) return <main className="flex min-h-screen items-center justify-center"><p className="text-red-500">{error || "Not found"}</p></main>;

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-3xl">
        <div className="mb-4 flex items-center gap-3">
          <Link href="/flags" className="text-sm text-blue-600 hover:underline">&larr; Flags</Link>
          <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">Dashboard</Link>
        </div>

        <div className="mb-6 flex items-center gap-3">
          <h1 className="text-xl font-bold text-slate-800">Consumer Flag</h1>
          <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[flag.status] || "bg-slate-100 text-slate-600"}`}>
            {flag.status}
          </span>
        </div>

        <div className="space-y-4">
          <div className="rounded-xl bg-white p-4 shadow">
            <h2 className="mb-2 text-sm font-semibold text-slate-700">Report Details</h2>
            <div className="space-y-2 text-sm">
              <p><span className="text-slate-500">Scan:</span>{" "}
                <Link href={`/scan/${flag.scan_id}`} className="text-blue-600 hover:underline font-mono text-xs">
                  {flag.scan_id}
                </Link>
              </p>
              <p><span className="text-slate-500">Flagged fields:</span>{" "}
                <span className="font-medium">{flag.reported_fields.join(", ")}</span>
              </p>
              {flag.reporter_note && (
                <p><span className="text-slate-500">Note:</span> {flag.reporter_note}</p>
              )}
              {flag.reporter_contact && (
                <p><span className="text-slate-500">Contact:</span> {flag.reporter_contact}</p>
              )}
              <p><span className="text-slate-500">Submitted:</span> {new Date(flag.created_at).toLocaleString()}</p>
            </div>
          </div>

          {flag.officer_notes && (
            <div className="rounded-xl bg-white p-4 shadow">
              <h2 className="mb-2 text-sm font-semibold text-slate-700">Officer Notes</h2>
              <p className="text-sm text-slate-600">{flag.officer_notes}</p>
              {flag.reviewed_at && (
                <p className="mt-2 text-xs text-slate-400">
                  Reviewed at {new Date(flag.reviewed_at).toLocaleString()}
                </p>
              )}
            </div>
          )}

          {flag.status === "NEW" && (
            <div className="rounded-xl bg-white p-4 shadow">
              <h2 className="mb-3 text-sm font-semibold text-slate-700">Review Flag</h2>
              <div className="space-y-3">
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Action</label>
                  <select
                    value={reviewStatus}
                    onChange={(e) => setReviewStatus(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                  >
                    <option value="ACKNOWLEDGED">Acknowledge</option>
                    <option value="RESOLVED">Resolve</option>
                    <option value="DISMISSED">Dismiss</option>
                  </select>
                </div>
                <div>
                  <label className="mb-1 block text-xs text-slate-500">Notes (optional)</label>
                  <textarea
                    value={officerNotes}
                    onChange={(e) => setOfficerNotes(e.target.value)}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                    rows={3}
                    placeholder="Add review notes..."
                  />
                </div>
                <button
                  onClick={submitReview}
                  disabled={submitting}
                  className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                >
                  {submitting ? "Submitting..." : "Submit Review"}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
