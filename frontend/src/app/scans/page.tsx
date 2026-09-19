"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { ComplianceBadge } from "@/components/ui/Badges";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";
import {
  IconPlus,
  IconHistory,
  IconBarcode,
  IconArrowRight,
} from "@/components/ui/Icons";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ScanItem {
  id: string;
  status: string;
  overall_status: string | null;
  product_name: string | null;
  barcode: string | null;
  has_inspection: boolean;
  declarations_count: number;
  created_at: string;
}

export default function ScansPage() {
  const [scans, setScans] = useState<ScanItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [barcodeFilter, setBarcodeFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  async function load() {
    setLoading(true);
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (statusFilter) params.set("status", statusFilter);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (barcodeFilter) params.set("barcode", barcodeFilter);

      const res = await fetch(`${API}/scans?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setScans(data.items || []);
        setTotal(data.total || 0);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, statusFilter, dateFrom, dateTo, barcodeFilter]);

  const totalPages = Math.ceil(total / pageSize);

  function handleResetFilters() {
    setStatusFilter("");
    setDateFrom("");
    setDateTo("");
    setBarcodeFilter("");
    setPage(1);
  }

  const hasActiveFilters = Boolean(statusFilter || dateFrom || dateTo || barcodeFilter);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200/80">
          <div>
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-600 uppercase tracking-wider mb-1">
              <IconHistory className="h-3.5 w-3.5" />
              <span>Inspection Registry</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              Inspection History
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-500">
              Search and review previously inspected packaged commodities and officer audit trails.
            </p>
          </div>

          <Link
            href="/scan"
            className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-brand-600/25 hover:bg-brand-700 active:scale-95 transition-all self-start sm:self-auto"
          >
            <IconPlus className="h-4 w-4" />
            <span>New Inspection</span>
          </Link>
        </div>

        {/* Filter Bar */}
        <div className="rounded-2xl bg-white border border-slate-200/80 p-4 shadow-card">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
            {/* Status Dropdown */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Compliance Status
              </label>
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 focus:border-brand-600 focus:outline-none"
              >
                <option value="">All Statuses</option>
                <option value="SATISFIED">Compliant / Satisfied</option>
                <option value="VIOLATION">Violation Detected</option>
                <option value="NOT_VERIFIED">Not Verified</option>
                <option value="CONFLICT">Cross-Source Conflict</option>
              </select>
            </div>

            {/* Barcode Search */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Barcode / EAN
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="e.g. 890154..."
                  value={barcodeFilter}
                  onChange={(e) => {
                    setBarcodeFilter(e.target.value);
                    setPage(1);
                  }}
                  className="w-full rounded-xl border border-slate-300 bg-white pl-8 pr-3 py-2 text-xs font-mono focus:border-brand-600 focus:outline-none"
                />
                <IconBarcode className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-400" />
              </div>
            </div>

            {/* Date From */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Date From
              </label>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 focus:border-brand-600 focus:outline-none"
              />
            </div>

            {/* Date To */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Date To
              </label>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-700 focus:border-brand-600 focus:outline-none"
              />
            </div>

            {/* Filter Reset Button */}
            <div className="flex items-end">
              {hasActiveFilters ? (
                <button
                  onClick={handleResetFilters}
                  className="w-full rounded-xl border border-slate-300 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-100 transition-colors"
                >
                  Reset Filters
                </button>
              ) : (
                <div className="w-full py-2 text-center text-[11px] text-slate-400">
                  {total} Record{total !== 1 ? "s" : ""}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Results List */}
        {loading ? (
          <SkeletonTable rows={6} />
        ) : scans.length === 0 ? (
          <EmptyState
            title="No inspection scans match your query"
            description={
              hasActiveFilters
                ? "Try clearing your filters or searching for another barcode."
                : "No packaging inspections have been recorded yet. Click below to begin."
            }
            actionLabel={hasActiveFilters ? "Clear Filters" : "Start First Scan"}
            onAction={hasActiveFilters ? handleResetFilters : undefined}
            actionHref={hasActiveFilters ? undefined : "/scan"}
          />
        ) : (
          <div className="rounded-2xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-50/80 border-b border-slate-200 text-[10px] uppercase font-bold tracking-wider text-slate-500">
                  <tr>
                    <th className="px-6 py-3.5">Product Identity</th>
                    <th className="px-6 py-3.5">Barcode / EAN</th>
                    <th className="px-6 py-3.5">Inspection Date</th>
                    <th className="px-6 py-3.5">Declarations</th>
                    <th className="px-6 py-3.5">Compliance Status</th>
                    <th className="px-6 py-3.5 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {scans.map((s) => (
                    <tr
                      key={s.id}
                      className="hover:bg-slate-50/80 transition-colors group cursor-pointer"
                    >
                      <td className="px-6 py-4">
                        <Link href={`/scan/${s.id}`} className="block">
                          <p className="font-bold text-slate-900 group-hover:text-brand-600 transition-colors">
                            {s.product_name || `Scan #${s.id.slice(0, 8)}`}
                          </p>
                          <span className="font-mono text-[10px] text-slate-400 block mt-0.5">
                            ID: {s.id.slice(0, 16)}...
                          </span>
                        </Link>
                      </td>

                      <td className="px-6 py-4">
                        {s.barcode ? (
                          <span className="font-mono text-slate-700 bg-slate-100 px-2 py-0.5 rounded border border-slate-200/60 text-[11px]">
                            {s.barcode}
                          </span>
                        ) : (
                          <span className="text-slate-400">—</span>
                        )}
                      </td>

                      <td className="px-6 py-4 text-slate-600 font-medium">
                        {new Date(s.created_at).toLocaleDateString()}
                        <span className="block text-[10px] text-slate-400">
                          {new Date(s.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </td>

                      <td className="px-6 py-4">
                        <span className="font-semibold text-slate-700">
                          {s.declarations_count} field{s.declarations_count !== 1 ? "s" : ""}
                        </span>
                        {s.has_inspection && (
                          <span className="block text-[10px] font-bold text-emerald-600">
                            ✓ Officer Reviewed
                          </span>
                        )}
                      </td>

                      <td className="px-6 py-4">
                        <ComplianceBadge status={s.overall_status} size="sm" />
                      </td>

                      <td className="px-6 py-4 text-right">
                        <Link
                          href={`/scan/${s.id}`}
                          className="inline-flex items-center gap-1 font-bold text-brand-600 hover:text-brand-800"
                        >
                          <span>Inspect</span>
                          <IconArrowRight className="h-3.5 w-3.5" />
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination Controls */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 text-xs">
                <span className="text-slate-500 font-medium">
                  Showing page <strong className="text-slate-900">{page}</strong> of <strong className="text-slate-900">{totalPages}</strong> ({total} total inspections)
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(Math.max(1, page - 1))}
                    disabled={page <= 1}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 shadow-2xs"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(Math.min(totalPages, page + 1))}
                    disabled={page >= totalPages}
                    className="rounded-xl border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-40 shadow-2xs"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  );
}
