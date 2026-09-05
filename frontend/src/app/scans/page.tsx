"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

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

const STATUS_COLORS: Record<string, string> = {
  SATISFIED: "bg-green-100 text-green-800",
  VIOLATION: "bg-red-100 text-red-800",
  NOT_VERIFIED: "bg-amber-100 text-amber-800",
  CONFLICT: "bg-purple-100 text-purple-800",
};

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
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (statusFilter) params.set("status", statusFilter);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (barcodeFilter) params.set("barcode", barcodeFilter);
      const res = await fetch(`${API}/scans?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setScans(data.items);
        setTotal(data.total);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [page, statusFilter, dateFrom, dateTo, barcodeFilter]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-4 flex items-center gap-3">
          <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">&larr; Dashboard</Link>
          <h1 className="text-xl font-bold text-slate-800">Scans</h1>
          <Link href="/scan" className="ml-auto rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-blue-700">
            New Scan
          </Link>
        </div>

        {/* Filters */}
        <div className="mb-4 flex flex-wrap gap-2">
          <select
            value={statusFilter}
            onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          >
            <option value="">All statuses</option>
            <option value="SATISFIED">Satisfied</option>
            <option value="VIOLATION">Violation</option>
            <option value="NOT_VERIFIED">Not Verified</option>
            <option value="CONFLICT">Conflict</option>
          </select>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            placeholder="From"
          />
          <input
            type="date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            placeholder="To"
          />
          <input
            type="text"
            value={barcodeFilter}
            onChange={(e) => { setBarcodeFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
            placeholder="Barcode"
          />
        </div>

        {loading ? (
          <p className="text-sm text-slate-400">Loading...</p>
        ) : scans.length === 0 ? (
          <p className="text-sm text-slate-400">No scans found.</p>
        ) : (
          <div className="space-y-3">
            {scans.map((s) => (
              <Link
                key={s.id}
                href={`/scan/${s.id}`}
                className="block rounded-xl bg-white p-4 shadow hover:shadow-md transition"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      {s.product_name || `Scan ${s.id.slice(0, 8)}`}
                    </p>
                    <p className="text-xs text-slate-400">
                      {new Date(s.created_at).toLocaleDateString()} · {s.declarations_count} declaration{s.declarations_count !== 1 ? "s" : ""}
                      {s.has_inspection && <span className="ml-1 text-green-600">· reviewed</span>}
                    </p>
                  </div>
                  <div className="text-right">
                    {s.overall_status && (
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[s.overall_status] || "bg-slate-100 text-slate-600"}`}>
                        {s.overall_status}
                      </span>
                    )}
                    {s.barcode && (
                      <p className="mt-1 text-[10px] text-slate-300">EAN: {s.barcode}</p>
                    )}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}

        {totalPages > 1 && (
          <div className="mt-4 flex items-center justify-center gap-2">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="rounded border border-slate-300 px-3 py-1 text-sm disabled:opacity-50"
            >
              Prev
            </button>
            <span className="text-sm text-slate-500">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="rounded border border-slate-300 px-3 py-1 text-sm disabled:opacity-50"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </main>
  );
}
