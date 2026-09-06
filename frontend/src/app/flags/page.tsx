import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";

import { getServerApiUrl } from "@/lib/config";

async function getFlags(token: string, status?: string) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  const res = await fetch(`${getServerApiUrl()}/flags?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

const STATUS_COLORS: Record<string, string> = {
  NEW: "bg-red-100 text-red-800",
  ACKNOWLEDGED: "bg-amber-100 text-amber-800",
  RESOLVED: "bg-green-100 text-green-800",
  DISMISSED: "bg-slate-100 text-slate-600",
};

export default async function FlagsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  if (!token) redirect("/login");

  const params = await searchParams;
  const data = await getFlags(token, params.status);

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="mx-auto max-w-5xl">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-xl font-bold text-slate-800">Consumer Flags</h1>
          <div className="flex gap-2">
            <Link href="/dashboard" className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
              Dashboard
            </Link>
          </div>
        </div>

        <div className="mb-4 flex gap-2">
          {["", "NEW", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"].map((s) => (
            <Link
              key={s}
              href={s ? `/flags?status=${s}` : "/flags"}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition ${
                (params.status || "") === s
                  ? "bg-blue-600 text-white"
                  : "bg-white text-slate-600 border border-slate-300 hover:bg-slate-100"
              }`}
            >
              {s || "All"}
            </Link>
          ))}
        </div>

        {!data || data.items.length === 0 ? (
          <div className="rounded-xl bg-white p-8 shadow text-center">
            <p className="text-sm text-slate-400">No flags found.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {data.items.map((flag: { id: string; scan_id: string; reported_fields: string[]; reporter_note: string | null; status: string; created_at: string }) => (
              <Link
                key={flag.id}
                href={`/flags/${flag.id}`}
                className="block rounded-xl bg-white p-4 shadow hover:shadow-md transition"
              >
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium text-slate-800">
                      Flag for scan {flag.scan_id.slice(0, 8)}...
                    </p>
                    <p className="mt-1 text-xs text-slate-500">
                      Fields: {flag.reported_fields.join(", ")}
                    </p>
                    {flag.reporter_note && (
                      <p className="mt-1 text-xs text-slate-400 truncate max-w-md">
                        &ldquo;{flag.reporter_note}&rdquo;
                      </p>
                    )}
                  </div>
                  <div className="text-right">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[flag.status] || "bg-slate-100 text-slate-600"}`}>
                      {flag.status}
                    </span>
                    <p className="mt-1 text-[10px] text-slate-400">
                      {new Date(flag.created_at).toLocaleDateString()}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}

        {data && (
          <p className="mt-4 text-xs text-slate-400 text-center">
            {data.total} total flags
          </p>
        )}
      </div>
    </main>
  );
}
