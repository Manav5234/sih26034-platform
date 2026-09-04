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

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-4xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-800">Dashboard</h1>
          <div className="flex gap-2">
            <Link
              href="/scan"
              className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
            >
              New Scan
            </Link>
            <form action="/api/auth/logout" method="post">
              <button className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
                Sign out
              </button>
            </form>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-xl bg-white p-5 shadow">
            <p className="text-sm text-slate-500">Total Scans</p>
            <p className="mt-1 text-2xl font-bold text-slate-800">{data.total_scans}</p>
          </div>
          <div className="rounded-xl bg-white p-5 shadow">
            <p className="text-sm text-slate-500">Violations</p>
            <p className="mt-1 text-2xl font-bold text-red-600">{data.violations}</p>
          </div>
          <div className="rounded-xl bg-white p-5 shadow">
            <p className="text-sm text-slate-500">Not Verified Rate</p>
            <p className="mt-1 text-2xl font-bold text-amber-600">
              {(data.not_verified_rate * 100).toFixed(1)}%
            </p>
          </div>
        </div>

        <div className="mt-6 rounded-xl bg-white p-5 shadow">
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Recent Inspections</h2>
          {data.recent_inspections.length === 0 ? (
            <p className="text-sm text-slate-400">No inspections yet.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {data.recent_inspections.map((insp: { id: string; notes: string | null; created_at: string }) => (
                <li key={insp.id} className="py-2 text-sm">
                  <span className="font-medium text-slate-700">{insp.id.slice(0, 8)}</span>
                  <span className="ml-2 text-slate-400">{insp.notes || "—"}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </main>
  );
}
