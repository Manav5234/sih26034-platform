import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";

const API_URL = process.env.API_URL || "http://localhost:8000";

async function getDashboard(token: string) {
  const res = await fetch(`${API_URL}/dashboard`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  if (!token) redirect("/login");

  const data = await getDashboard(token);
  if (!data) redirect("/login");

  const stats = [
    { label: "Total Scans", value: data.total_scans, color: "text-slate-800" },
    { label: "Pending Review", value: data.scans_pending_review, color: "text-amber-600" },
    { label: "AI Violations", value: data.violations_ai, color: "text-red-600" },
    { label: "Officer Confirmed", value: data.violations_officer_confirmed, color: "text-red-800" },
    { label: "Not Verified", value: data.not_verified, color: "text-amber-600" },
    { label: "Conflicts", value: data.conflict, color: "text-purple-600" },
    { label: "Today", value: data.scans_today, color: "text-blue-600" },
    { label: "This Week", value: data.scans_this_week, color: "text-blue-600" },
  ];

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-800">Dashboard</h1>
          <div className="flex gap-2">
            <Link href="/scans" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
              All Scans
            </Link>
            <Link href="/products" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
              Products
            </Link>
            <Link href="/scan" className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700">
              New Scan
            </Link>
            <form action="/api/auth/logout" method="post">
              <button className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
                Sign out
              </button>
            </form>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label} className="rounded-xl bg-white p-5 shadow">
              <p className="text-xs text-slate-500">{s.label}</p>
              <p className={`mt-1 text-2xl font-bold ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Link href="/scans" className="rounded-xl bg-white p-5 shadow hover:shadow-md transition">
            <h2 className="text-sm font-semibold text-slate-700">View All Scans</h2>
            <p className="mt-1 text-xs text-slate-400">Filter by status, date, officer, or barcode</p>
          </Link>
          <Link href="/products" className="rounded-xl bg-white p-5 shadow hover:shadow-md transition">
            <h2 className="text-sm font-semibold text-slate-700">Product Repository</h2>
            <p className="mt-1 text-xs text-slate-400">Search products by name, brand, or category</p>
          </Link>
        </div>
      </div>
    </main>
  );
}
