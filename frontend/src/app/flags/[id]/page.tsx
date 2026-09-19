"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { FlagStatusBadge } from "@/components/ui/Badges";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  IconFlag,
  IconArrowLeft,
  IconAlertTriangle,
  IconScan,
  IconShield,
  IconCheckCircle,
} from "@/components/ui/Icons";

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

export default function FlagDetailPage() {
  const params = useParams();
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
      if (!res.ok) throw new Error("Flag report not found");
      const data = await res.json();
      setFlag(data);
    } catch {
      setError("Failed to load flag investigation record.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [id]);

  async function submitReview() {
    setSubmitting(true);
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const res = await fetch(`${API}/flags/${id}/review`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          status: reviewStatus,
          officer_notes: officerNotes || null,
        }),
      });
      if (!res.ok) throw new Error("Failed to review flag");
      const updated = await res.json();
      setFlag(updated);
    } catch {
      alert("Failed to submit officer determination.");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <Skeleton className="h-8 w-64 rounded-xl" />
          <Skeleton className="h-48 w-full rounded-2xl" />
          <Skeleton className="h-48 w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  if (error || !flag) {
    return (
      <AppShell>
        <div className="py-20 text-center">
          <IconAlertTriangle className="h-12 w-12 text-rose-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-800">Concern Record Not Found</h2>
          <p className="mt-1 text-sm text-slate-500">{error || "The flag record does not exist."}</p>
          <Link
            href="/flags"
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-xs font-bold text-white shadow"
          >
            <IconArrowLeft className="h-4 w-4" />
            <span>Return to Flags</span>
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="max-w-3xl mx-auto space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
          <Link href="/dashboard" className="hover:text-slate-800 transition-colors">
            Dashboard
          </Link>
          <span>/</span>
          <Link href="/flags" className="hover:text-slate-800 transition-colors">
            Flags
          </Link>
          <span>/</span>
          <span className="font-mono text-slate-700">{flag.id.slice(0, 8)}...</span>
        </div>

        {/* Header */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">
                Consumer Packaging Report
              </h1>
              <FlagStatusBadge status={flag.status} />
            </div>
            <p className="mt-1 text-xs text-slate-500 font-mono">
              FLAG ID: {flag.id} • Submitted on {new Date(flag.created_at).toLocaleString()}
            </p>
          </div>

          <Link
            href={`/scan/${flag.scan_id}`}
            className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-3.5 py-2 text-xs font-bold text-white shadow hover:bg-brand-700"
          >
            <IconScan className="h-3.5 w-3.5" />
            <span>Open Packaging Scan</span>
          </Link>
        </div>

        {/* Report Evidence Details */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card space-y-4">
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 pb-3 border-b border-slate-100">
            Report Specifications
          </h2>

          <div className="space-y-3 text-xs">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                Linked Packaging Scan
              </span>
              <Link
                href={`/scan/${flag.scan_id}`}
                className="font-mono text-xs font-bold text-brand-600 hover:underline"
              >
                {flag.scan_id}
              </Link>
            </div>

            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1.5">
                Reported Incompliant Declarations
              </span>
              <div className="flex flex-wrap gap-2">
                {flag.reported_fields.map((f) => (
                  <span
                    key={f}
                    className="rounded-lg bg-rose-50 px-2.5 py-1 text-xs font-bold text-rose-800 border border-rose-200"
                  >
                    {f}
                  </span>
                ))}
              </div>
            </div>

            {flag.reporter_note && (
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-1">
                  Reporter Observations
                </span>
                <div className="rounded-xl bg-slate-50 p-3.5 border border-slate-200/60 text-slate-800 text-xs italic">
                  &ldquo;{flag.reporter_note}&rdquo;
                </div>
              </div>
            )}

            {flag.reporter_contact && (
              <div>
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block mb-0.5">
                  Reporter Contact Information
                </span>
                <span className="text-slate-700 font-mono">{flag.reporter_contact}</span>
              </div>
            )}
          </div>
        </div>

        {/* Previous Officer Review Findings (if any) */}
        {flag.officer_notes && (
          <div className="rounded-2xl border border-brand-200 bg-brand-50/50 p-6 shadow-card space-y-2">
            <div className="flex items-center justify-between text-xs font-bold text-brand-900">
              <span className="flex items-center gap-1.5">
                <IconShield className="h-4 w-4 text-brand-600" />
                <span>Recorded Officer Adjudication</span>
              </span>
              {flag.reviewed_at && (
                <span className="text-[11px] text-brand-700 font-mono">
                  {new Date(flag.reviewed_at).toLocaleString()}
                </span>
              )}
            </div>
            <p className="text-xs text-brand-800 leading-relaxed pt-1">
              {flag.officer_notes}
            </p>
          </div>
        )}

        {/* Review Action Card */}
        {flag.status === "NEW" && (
          <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card space-y-4">
            <div className="flex items-center gap-2 pb-3 border-b border-slate-100">
              <IconShield className="h-4 w-4 text-brand-600" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                Adjudicate Consumer Flag
              </h2>
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                  Determination Decision
                </label>
                <select
                  value={reviewStatus}
                  onChange={(e) => setReviewStatus(e.target.value)}
                  className="w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-xs font-semibold text-slate-800 focus:border-brand-600 focus:outline-none"
                >
                  <option value="ACKNOWLEDGED">Acknowledge (Investigation Commenced)</option>
                  <option value="RESOLVED">Resolve (Enforcement Notice Issued / Rectified)</option>
                  <option value="DISMISSED">Dismiss (Invalid / Frivolous Complaint)</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1.5">
                  Officer Inspection Findings &amp; Enforcement Action Notes
                </label>
                <textarea
                  value={officerNotes}
                  onChange={(e) => setOfficerNotes(e.target.value)}
                  rows={4}
                  placeholder="State investigation findings, physical inspection results, or reasons for resolution/dismissal..."
                  className="w-full rounded-xl border border-slate-300 p-3.5 text-xs focus:border-brand-600 focus:outline-none leading-relaxed"
                />
              </div>

              <div className="flex justify-end pt-2">
                <button
                  onClick={submitReview}
                  disabled={submitting}
                  className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-6 py-2.5 text-xs font-bold text-white shadow-md shadow-brand-600/25 hover:bg-brand-700 disabled:opacity-50 transition-all"
                >
                  <IconCheckCircle className="h-4 w-4" />
                  <span>{submitting ? "Recording Determination..." : "Submit Official Determination"}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
