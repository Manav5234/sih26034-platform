"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Declaration {
  id: string;
  field_name: string;
  extracted_value: unknown;
  verdict: string;
  reason: string;
  confidence: number;
  evidence: Array<{ id: string; source_type: string; raw_text: string | null; confidence: number }>;
  officer_correction?: { officer_name?: string; corrected_value: unknown; reason: string; corrected_at: string } | null;
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
  dates: { manufacture: string | null; best_before: string | null; use_by: string | null };
  consumer_care: string | null;
  barcode: { code: string; format: string } | null;
  declarations: Declaration[];
  created_at: string;
}

const VERDICT_COLORS: Record<string, string> = {
  SATISFIED: "bg-green-100 text-green-800",
  VIOLATION: "bg-red-100 text-red-800",
  NOT_VERIFIED: "bg-amber-100 text-amber-800",
  CONFLICT: "bg-purple-100 text-purple-800",
};

const MONTH_NAMES = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

function formatFieldValue(fieldName: string, value: unknown): string {
  if (value === null || value === undefined) return "\u2014";
  if (typeof value === "object" && !Array.isArray(value)) {
    const v = value as Record<string, unknown>;
    if (fieldName === "mrp" && v.amount !== undefined) {
      const sym = v.currency === "USD" ? "$" : v.currency === "EUR" ? "\u20ac" : "\u20b9";
      return `${sym}${v.amount}`;
    }
    if (fieldName === "net_quantity" && v.value !== undefined && v.unit) return `${v.value} ${v.unit}`;
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
      return value.map((n: Record<string, unknown>) => {
        const name = String(n.nutrient || "").replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
        return `${name}: ${n.value != null ? n.value : "\u2014"} ${n.unit || ""}`;
      }).join("; ");
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

  if (loading) return <main className="flex min-h-screen items-center justify-center"><p className="text-slate-400">Loading...</p></main>;
  if (!product) return <main className="flex min-h-screen items-center justify-center"><p className="text-red-500">Not found</p></main>;

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-4 flex items-center gap-3">
          <Link href="/products" className="text-sm text-blue-600 hover:underline">&larr; Products</Link>
          <h1 className="text-xl font-bold text-slate-800">{product.identity || "Unknown Product"}</h1>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div className="rounded-xl bg-white p-5 shadow">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Product Info</h2>
            <dl className="space-y-1 text-sm">
              {product.brand && <div><dt className="text-slate-400">Brand</dt><dd className="text-slate-700">{product.brand}</dd></div>}
              {product.category && <div><dt className="text-slate-400">Category</dt><dd className="text-slate-700">{product.category}</dd></div>}
              {product.manufacturer && <div><dt className="text-slate-400">Manufacturer</dt><dd className="text-slate-700">{product.manufacturer}</dd></div>}
              {product.quantity && <div><dt className="text-slate-400">Net Quantity</dt><dd className="text-slate-700">{product.quantity.value} {product.quantity.unit}</dd></div>}
              {product.mrp && <div><dt className="text-slate-400">MRP</dt><dd className="text-slate-700">{product.mrp.currency} {product.mrp.amount}</dd></div>}
              {product.barcode && <div><dt className="text-slate-400">Barcode</dt><dd className="text-slate-700">{product.barcode.code} ({product.barcode.format})</dd></div>}
              {product.country_of_origin && <div><dt className="text-slate-400">Origin</dt><dd className="text-slate-700">{product.country_of_origin}</dd></div>}
              {product.consumer_care && <div><dt className="text-slate-400">Consumer Care</dt><dd className="text-slate-700">{product.consumer_care}</dd></div>}
            </dl>
          </div>

          <div className="rounded-xl bg-white p-5 shadow">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Dates</h2>
            <dl className="space-y-1 text-sm">
              {product.dates.manufacture && <div><dt className="text-slate-400">Manufactured</dt><dd className="text-slate-700">{product.dates.manufacture}</dd></div>}
              {product.dates.best_before && <div><dt className="text-slate-400">Best Before</dt><dd className="text-slate-700">{product.dates.best_before}</dd></div>}
              {product.dates.use_by && <div><dt className="text-slate-400">Use By</dt><dd className="text-slate-700">{product.dates.use_by}</dd></div>}
              {!product.dates.manufacture && !product.dates.best_before && !product.dates.use_by && (
                <p className="text-xs text-slate-400">No date information</p>
              )}
            </dl>
          </div>
        </div>

        {product.declarations.length > 0 && (
          <div className="mt-6 rounded-xl bg-white p-5 shadow">
            <h2 className="mb-3 text-sm font-semibold text-slate-700">Latest Scan Declarations</h2>
            <div className="space-y-3">
              {product.declarations.map((d) => (
                <div key={d.id} className="rounded-lg border border-slate-100 p-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-slate-700">{d.field_name}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${VERDICT_COLORS[d.verdict] || "bg-slate-100 text-slate-600"}`}>
                      {d.verdict}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">
                    Value: <span className="font-mono text-slate-700">{formatFieldValue(d.field_name, d.extracted_value)}</span>
                  </p>
                  {d.officer_correction && (
                    <div className="mt-2 rounded border border-blue-200 bg-blue-50 p-2">
                      <p className="text-[10px] font-semibold uppercase text-blue-600">Officer Correction</p>
                      <p className="text-xs text-blue-800">
                        {d.officer_correction.officer_name || "Officer"} set to{" "}
                        <span className="font-mono">{JSON.stringify(d.officer_correction.corrected_value)}</span>
                      </p>
                      <p className="text-[10px] text-blue-500">{d.officer_correction.reason}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
