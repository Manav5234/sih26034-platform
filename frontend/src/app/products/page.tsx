"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { getApiUrl } from "@/lib/config";
import { AppShell } from "@/components/layout/AppShell";
import { ComplianceBadge } from "@/components/ui/Badges";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonTable } from "@/components/ui/Skeleton";
import {
  IconProduct,
  IconSearch,
  IconBarcode,
  IconArrowRight,
  IconScan,
} from "@/components/ui/Icons";

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

export default function ProductsPage() {
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
      const params = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (search) params.set("search", search);
      if (brand) params.set("brand", brand);
      if (category) params.set("category", category);

      const res = await fetch(`${getApiUrl()}/products?${params}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setProducts(data.items || []);
        setTotal(data.total || 0);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [page, search, brand, category]);

  const totalPages = Math.ceil(total / pageSize);

  function handleResetFilters() {
    setSearch("");
    setBrand("");
    setCategory("");
    setPage(1);
  }

  const hasActiveFilters = Boolean(search || brand || category);

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200/80">
          <div>
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-brand-600 uppercase tracking-wider mb-1">
              <IconProduct className="h-3.5 w-3.5" />
              <span>Catalog Intelligence</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              Product Repository
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-500">
              Browse canonical records of packaged commodities inspected across Indian retail markets.
            </p>
          </div>

          <Link
            href="/scan"
            className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-brand-600/25 hover:bg-brand-700 active:scale-95 transition-all self-start sm:self-auto"
          >
            <IconScan className="h-4 w-4" />
            <span>Inspect New Product</span>
          </Link>
        </div>

        {/* Filters Toolbar */}
        <div className="rounded-2xl bg-white border border-slate-200/80 p-4 shadow-card">
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-4 gap-3">
            {/* Search Input */}
            <div className="lg:col-span-2">
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Search Product or Manufacturer
              </label>
              <div className="relative">
                <input
                  type="text"
                  placeholder="Search by identity, brand, or manufacturer..."
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setPage(1);
                  }}
                  className="w-full rounded-xl border border-slate-300 pl-9 pr-3 py-2 text-xs font-medium text-slate-900 placeholder:text-slate-400 focus:border-brand-600 focus:outline-none"
                />
                <IconSearch className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
              </div>
            </div>

            {/* Brand Filter */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Brand Filter
              </label>
              <input
                type="text"
                placeholder="Filter by brand name..."
                value={brand}
                onChange={(e) => {
                  setBrand(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-brand-600 focus:outline-none"
              />
            </div>

            {/* Category Filter */}
            <div>
              <label className="block text-[10px] font-bold uppercase tracking-wider text-slate-500 mb-1">
                Category
              </label>
              <input
                type="text"
                placeholder="Filter by category..."
                value={category}
                onChange={(e) => {
                  setCategory(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded-xl border border-slate-300 px-3 py-2 text-xs text-slate-900 focus:border-brand-600 focus:outline-none"
              />
            </div>
          </div>
        </div>

        {/* Product Cards Grid */}
        {loading ? (
          <SkeletonTable rows={6} />
        ) : products.length === 0 ? (
          <EmptyState
            title="No products found in repository"
            description={
              hasActiveFilters
                ? "Try adjusting your search criteria or resetting filters."
                : "Inspected commodities are automatically saved into the product catalog upon scan completion."
            }
            actionLabel={hasActiveFilters ? "Reset Filters" : "Scan a Product"}
            onAction={hasActiveFilters ? handleResetFilters : undefined}
            actionHref={hasActiveFilters ? undefined : "/scan"}
          />
        ) : (
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {products.map((p) => (
                <Link
                  key={p.id}
                  href={`/products/${p.id}`}
                  className="group rounded-2xl bg-white border border-slate-200/80 p-5 shadow-card hover:border-brand-300 hover:shadow-card-hover transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-start justify-between gap-3 mb-2">
                      <span className="rounded-md bg-slate-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">
                        {p.category || "Commodity"}
                      </span>
                      <ComplianceBadge status={p.latest_scan_status} size="sm" />
                    </div>

                    <h2 className="text-sm font-bold text-slate-900 group-hover:text-brand-600 transition-colors line-clamp-2">
                      {p.identity || "Unknown Packaging Identity"}
                    </h2>

                    <p className="text-xs text-slate-500 mt-1">
                      {p.brand && <strong className="text-slate-700">{p.brand}</strong>}
                      {p.brand && p.manufacturer && " • "}
                      {p.manufacturer && <span>{p.manufacturer}</span>}
                    </p>
                  </div>

                  <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1.5 text-slate-500 font-mono text-[11px]">
                      <IconBarcode className="h-3.5 w-3.5 text-slate-400" />
                      <span>{p.barcode_code || "No Barcode"}</span>
                    </div>

                    <span className="text-[11px] font-bold text-slate-600 bg-slate-50 px-2 py-0.5 rounded border border-slate-200/60">
                      {p.total_scans} Scan{p.total_scans !== 1 ? "s" : ""}
                    </span>
                  </div>
                </Link>
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-between px-2 py-4 text-xs">
                <span className="text-slate-500 font-medium">
                  Page <strong className="text-slate-900">{page}</strong> of <strong className="text-slate-900">{totalPages}</strong> ({total} commodities cataloged)
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
