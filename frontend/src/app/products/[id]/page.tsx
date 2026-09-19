"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { AppShell } from "@/components/layout/AppShell";
import { ComplianceBadge } from "@/components/ui/Badges";
import { Skeleton } from "@/components/ui/Skeleton";
import {
  IconArrowLeft,
  IconBarcode,
  IconAlertTriangle,
  IconScan,
} from "@/components/ui/Icons";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Declaration {
  id: string;
  field_name: string;
  extracted_value: unknown;
  verdict: string;
  reason: string;
  confidence: number;
  evidence: Array<{ id: string; source_type: string; raw_text: string | null; confidence: number }>;
  officer_correction?: {
    officer_name?: string;
    corrected_value: unknown;
    reason: string;
    corrected_at: string;
  } | null;
}

interface ProductDetail {
  id: string;
  identity: string | null;
  brand: string | null;
  category: string | null;
  manufacturer: string | null;
  packer: string | null;
  importer: string | null;
  country_of_origin: string | null;
  quantity: { value: number; unit: string } | null;
  mrp: { amount: number; currency: string } | null;
  dates: {
    manufacture: string | null;
    best_before: string | null;
    use_by: string | null;
  };
  consumer_care: string | null;
  barcode: { code: string; format: string } | null;
  declarations: Declaration[];
  created_at: string;
}

const MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatFieldValue(fieldName: string, value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object" && !Array.isArray(value)) {
    const v = value as Record<string, unknown>;
    if (fieldName === "mrp" && v.amount !== undefined) {
      const sym = v.currency === "USD" ? "$" : v.currency === "EUR" ? "€" : "₹";
      return `${sym}${v.amount}`;
    }
    if (fieldName === "net_quantity" && v.value !== undefined && v.unit) {
      return `${v.value} ${v.unit}`;
    }
    if (fieldName === "manufacturer" && v.name) return String(v.name);
    if (fieldName === "manufacture_date" || fieldName === "expiry_date") {
      const val = (v.value || v) as Record<string, unknown>;
      if (val && typeof val === "object" && val.year && val.month) {
        const month = MONTH_NAMES[val.month as number] || "";
        return val.day ? `${val.day} ${month} ${val.year}` : `${month} ${val.year}`;
      }
    }
    if (fieldName === "cautions") return v.present ? `Present: ${v.text || ""}` : "Not present";
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    if (fieldName === "nutrition_facts") {
      return value
        .map((n: Record<string, unknown>) => {
          const name = String(n.nutrient || "").replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
          return `${name}: ${n.value != null ? n.value : "—"} ${n.unit || ""}`;
        })
        .join("; ");
    }
    return JSON.stringify(value);
  }
  return String(value);
}

export default function ProductDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [product, setProduct] = useState<ProductDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const tokenRes = await fetch("/api/auth/token");
        const { token } = await tokenRes.json();
        const res = await fetch(`${API}/products/${id}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setProduct(await res.json());
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  if (loading) {
    return (
      <AppShell>
        <div className="space-y-6">
          <Skeleton className="h-8 w-60 rounded-xl" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Skeleton className="h-64 rounded-2xl" />
            <Skeleton className="h-64 rounded-2xl" />
          </div>
        </div>
      </AppShell>
    );
  }

  if (!product) {
    return (
      <AppShell>
        <div className="py-20 text-center">
          <IconAlertTriangle className="h-12 w-12 text-rose-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-slate-800">Product Not Found</h2>
          <p className="mt-1 text-sm text-slate-500">The product record could not be loaded.</p>
          <Link
            href="/products"
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-xs font-bold text-white shadow"
          >
            <IconArrowLeft className="h-4 w-4" />
            <span>Return to Repository</span>
          </Link>
        </div>
      </AppShell>
    );
  }

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 font-medium">
          <Link href="/dashboard" className="hover:text-slate-800 transition-colors">
            Dashboard
          </Link>
          <span>/</span>
          <Link href="/products" className="hover:text-slate-800 transition-colors">
            Products
          </Link>
          <span>/</span>
          <span className="font-mono text-slate-700">{product.id.slice(0, 8)}...</span>
        </div>

        {/* Product Identity Header */}
        <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="rounded-md bg-slate-100 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-slate-600">
                {product.category || "Packaged Commodity"}
              </span>
              {product.brand && (
                <span className="rounded-md bg-brand-50 px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-brand-700 border border-brand-200">
                  {product.brand}
                </span>
              )}
            </div>

            <h1 className="text-xl sm:text-2xl font-extrabold text-slate-900 tracking-tight">
              {product.identity || "Unknown Commodity Identity"}
            </h1>

            {product.barcode && (
              <div className="flex items-center gap-2 mt-2 font-mono text-xs text-slate-500">
                <IconBarcode className="h-4 w-4 text-slate-400" />
                <span>{product.barcode.code} ({product.barcode.format})</span>
              </div>
            )}
          </div>

          <Link
            href="/scan"
            className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-xs font-bold text-white shadow-sm hover:bg-brand-700 transition-all self-start md:self-auto"
          >
            <IconScan className="h-4 w-4" />
            <span>Scan This Packaging</span>
          </Link>
        </div>

        {/* 2-Column Product Specs */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Packaging & Pricing Specifications */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card space-y-4">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 pb-3 border-b border-slate-100">
              Mandatory Packaging Declarations
            </h2>

            <dl className="grid grid-cols-2 gap-4 text-xs">
              <div>
                <dt className="text-slate-400 font-bold uppercase text-[10px]">Maximum Retail Price</dt>
                <dd className="text-slate-900 font-bold text-sm mt-0.5">
                  {product.mrp ? `${product.mrp.currency} ${product.mrp.amount}` : "—"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-400 font-bold uppercase text-[10px]">Net Quantity</dt>
                <dd className="text-slate-900 font-bold text-sm mt-0.5">
                  {product.quantity ? `${product.quantity.value} ${product.quantity.unit}` : "—"}
                </dd>
              </div>

              <div>
                <dt className="text-slate-400 font-bold uppercase text-[10px]">Manufacturer</dt>
                <dd className="text-slate-700 font-medium mt-0.5">{product.manufacturer || "—"}</dd>
              </div>

              <div>
                <dt className="text-slate-400 font-bold uppercase text-[10px]">Country of Origin</dt>
                <dd className="text-slate-700 font-medium mt-0.5">{product.country_of_origin || "—"}</dd>
              </div>

              {product.packer && (
                <div>
                  <dt className="text-slate-400 font-bold uppercase text-[10px]">Packer</dt>
                  <dd className="text-slate-700 font-medium mt-0.5">{product.packer}</dd>
                </div>
              )}

              {product.importer && (
                <div>
                  <dt className="text-slate-400 font-bold uppercase text-[10px]">Importer</dt>
                  <dd className="text-slate-700 font-medium mt-0.5">{product.importer}</dd>
                </div>
              )}

              <div className="col-span-2">
                <dt className="text-slate-400 font-bold uppercase text-[10px]">Consumer Care Details</dt>
                <dd className="text-slate-700 font-medium mt-0.5">{product.consumer_care || "—"}</dd>
              </div>
            </dl>
          </div>

          {/* Dates & Validity Information */}
          <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card space-y-4">
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-500 pb-3 border-b border-slate-100">
              Manufacturing &amp; Expiry Dates
            </h2>

            <dl className="space-y-4 text-xs">
              <div className="flex items-center justify-between py-2 border-b border-slate-50">
                <dt className="text-slate-500 font-medium">Date of Manufacture</dt>
                <dd className="text-slate-900 font-mono font-bold">
                  {product.dates.manufacture || "Not specified"}
                </dd>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-50">
                <dt className="text-slate-500 font-medium">Best Before Date</dt>
                <dd className="text-slate-900 font-mono font-bold">
                  {product.dates.best_before || "Not specified"}
                </dd>
              </div>

              <div className="flex items-center justify-between py-2 border-b border-slate-50">
                <dt className="text-slate-500 font-medium">Use By Date</dt>
                <dd className="text-slate-900 font-mono font-bold">
                  {product.dates.use_by || "Not specified"}
                </dd>
              </div>

              <div className="pt-2 text-[11px] text-slate-400">
                Extracted according to Legal Metrology Packaged Commodities Rule 6(1)(d).
              </div>
            </dl>
          </div>
        </div>

        {/* Latest Scan Compliance Declarations */}
        {product.declarations.length > 0 && (
          <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-card space-y-4">
            <div className="flex items-center justify-between pb-3 border-b border-slate-100">
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-900">
                Latest Inspection Findings ({product.declarations.length})
              </h2>
              <span className="text-[11px] text-slate-400">Recorded from latest packaging audit</span>
            </div>

            <div className="space-y-3">
              {product.declarations.map((d) => (
                <div
                  key={d.id}
                  className="rounded-xl border border-slate-100 bg-slate-50/50 p-4 hover:bg-white hover:border-slate-200 transition-all flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3"
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold text-slate-800 capitalize">
                        {d.field_name.replace(/_/g, " ")}
                      </span>
                    </div>
                    <p className="mt-1 text-xs font-mono font-bold text-slate-900">
                      {formatFieldValue(d.field_name, d.extracted_value)}
                    </p>
                    {d.reason && (
                      <p className="text-[11px] text-slate-500 mt-0.5">{d.reason}</p>
                    )}

                    {d.officer_correction && (
                      <div className="mt-2 rounded-lg bg-brand-50 border border-brand-200 p-2 text-[11px] text-brand-900">
                        <span className="font-bold">Officer Correction: </span>
                        <span>{JSON.stringify(d.officer_correction.corrected_value)} ({d.officer_correction.reason})</span>
                      </div>
                    )}
                  </div>

                  <ComplianceBadge status={d.verdict} size="sm" />
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
