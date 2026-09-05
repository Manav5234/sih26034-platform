"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface ProductItem {
  id: string;
  identity: string | null;
  brand: string | null;
  category: string | null;
  manufacturer: string | null;
  barcode_code: string | null;
  mrp_amount: number | null;
  latest_scan_status: string | null;
  total_scans: number;
  created_at: string;
}

const STATUS_COLORS: Record<string, string> = {
  SATISFIED: "bg-green-100 text-green-800",
  VIOLATION: "bg-red-100 text-red-800",
  NOT_VERIFIED: "bg-amber-100 text-amber-800",
  CONFLICT: "bg-purple-100 text-purple-800",
};

export default function ProductsPage() {
  const router = useRouter();
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [loading, setLoading] = useState(true);
  const pageSize = 20;

  async function load() {
    setLoading(true);
    try {
      const tokenRes = await fetch("/api/auth/token");
      const { token } = await tokenRes.json();
      const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
      if (search) params.set("search", search);
      if (brand) params.set("brand", brand);
      if (category) params.set("category", category);
      const res = await fetch(`${API}/products?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setProducts(data.items);
        setTotal(data.total);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, [page, search, brand, category]);

  const totalPages = Math.ceil(total / pageSize);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-4 flex items-center gap-3">
          <Link href="/dashboard" className="text-sm text-blue-600 hover:underline">&larr; Dashboard</Link>
          <h1 className="text-xl font-bold text-slate-800">Products</h1>
        </div>

        {/* Filters */}
        <div className="mb-4 flex flex-wrap gap-2">
          <input
            type="text"
            placeholder="Search name, brand, manufacturer..."
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          />
          <input
            type="text"
            placeholder="Brand"
            value={brand}
            onChange={(e) => { setBrand(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          />
          <input
            type="text"
            placeholder="Category"
            value={category}
            onChange={(e) => { setCategory(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm"
          />
        </div>

        {loading ? (
          <p className="text-sm text-slate-400">Loading...</p>
        ) : products.length === 0 ? (
          <p className="text-sm text-slate-400">No products found.</p>
        ) : (
          <div className="space-y-3">
            {products.map((p) => (
              <Link
                key={p.id}
                href={`/products/${p.id}`}
                className="block rounded-xl bg-white p-4 shadow hover:shadow-md transition"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-800">{p.identity || "Unknown product"}</p>
                    <p className="text-xs text-slate-400">
                      {p.brand && `${p.brand} · `}{p.category || "—"} {p.manufacturer && `· ${p.manufacturer}`}
                    </p>
                  </div>
                  <div className="text-right">
                    {p.latest_scan_status && (
                      <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[p.latest_scan_status] || "bg-slate-100 text-slate-600"}`}>
                        {p.latest_scan_status}
                      </span>
                    )}
                    <p className="mt-1 text-xs text-slate-400">{p.total_scans} scan{p.total_scans !== 1 ? "s" : ""}</p>
                  </div>
                </div>
                {p.barcode_code && (
                  <p className="mt-1 text-xs text-slate-300">Barcode: {p.barcode_code}</p>
                )}
              </Link>
            ))}
          </div>
        )}

        {/* Pagination */}
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
