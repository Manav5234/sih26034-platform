import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { getServerApiUrl } from "@/lib/config";
import { AppShell } from "@/components/layout/AppShell";
import { FlagStatusBadge } from "@/components/ui/Badges";
import { EmptyState } from "@/components/ui/EmptyState";
import {
  IconFlag,
  IconArrowRight,
} from "@/components/ui/Icons";

async function getFlags(token: string, status?: string) {
  try {
    const params = new URLSearchParams();
    if (status) params.set("status", status);
    const res = await fetch(`${getServerApiUrl()}/flags?${params}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export default async function FlagsPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string }>;
}) {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  if (!token) redirect("/login");

  const params = await searchParams;
  const currentStatus = params.status || "";
  const data = await getFlags(token, currentStatus);

  const flagsList = data?.items || [];
  const totalCount = data?.total || 0;

  const tabs = [
    { label: "All Concerns", value: "" },
    { label: "New", value: "NEW" },
    { label: "Acknowledged", value: "ACKNOWLEDGED" },
    { label: "Resolved", value: "RESOLVED" },
    { label: "Dismissed", value: "DISMISSED" },
  ];

  return (
    <AppShell>
      <div className="space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200/80">
          <div>
            <div className="inline-flex items-center gap-1.5 text-xs font-bold text-rose-600 uppercase tracking-wider mb-1">
              <IconFlag className="h-3.5 w-3.5" />
              <span>Public Moderation Queue</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              Consumer Packaging Concerns
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-500">
              Review, investigate, and adjudicate label violation reports submitted by consumers and retailers.
            </p>
          </div>

          <div className="text-xs font-bold text-slate-600 bg-white border border-slate-200 px-3.5 py-2 rounded-xl shadow-2xs self-start sm:self-auto">
            <span>Total Flags: </span>
            <span className="text-slate-900 font-mono">{totalCount}</span>
          </div>
        </div>

        {/* Status Filter Tabs */}
        <div className="flex flex-wrap gap-2">
          {tabs.map((tab) => {
            const isActive = currentStatus === tab.value;
            return (
              <Link
                key={tab.value}
                href={tab.value ? `/flags?status=${tab.value}` : "/flags"}
                className={`rounded-xl px-4 py-2 text-xs font-bold transition-all shadow-2xs ${
                  isActive
                    ? "bg-slate-900 text-white shadow-sm"
                    : "bg-white text-slate-600 border border-slate-200/80 hover:bg-slate-50 hover:text-slate-900"
                }`}
              >
                {tab.label}
              </Link>
            );
          })}
        </div>

        {/* Flag Moderation List */}
        {flagsList.length === 0 ? (
          <EmptyState
            title="No consumer flags in this queue"
            description={
              currentStatus
                ? `There are no flags currently marked with the "${currentStatus}" status.`
                : "No consumer packaging reports have been logged yet."
            }
            icon={<IconFlag className="h-7 w-7 text-slate-400" />}
          />
        ) : (
          <div className="rounded-2xl border border-slate-200/80 bg-white shadow-card overflow-hidden">
            <div className="divide-y divide-slate-100">
              {flagsList.map((flag: {
                id: string;
                scan_id: string;
                reported_fields: string[];
                reporter_note: string | null;
                status: string;
                created_at: string;
              }) => (
                <Link
                  key={flag.id}
                  href={`/flags/${flag.id}`}
                  className="flex flex-col sm:flex-row sm:items-center justify-between p-5 hover:bg-slate-50/80 transition-all gap-4 group"
                >
                  <div className="space-y-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-xs font-bold text-slate-900 group-hover:text-brand-600 transition-colors">
                        Flag #{flag.id.slice(0, 8)}
                      </span>
                      <span className="text-slate-300">•</span>
                      <span className="font-mono text-[11px] text-slate-500">
                        Scan: {flag.scan_id.slice(0, 8)}...
                      </span>
                    </div>

                    <div className="flex flex-wrap items-center gap-1.5 pt-1">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mr-1">
                        Reported Fields:
                      </span>
                      {flag.reported_fields.map((field) => (
                        <span
                          key={field}
                          className="rounded-md bg-rose-50 px-2 py-0.5 text-[10px] font-bold text-rose-700 border border-rose-200/60"
                        >
                          {field}
                        </span>
                      ))}
                    </div>

                    {flag.reporter_note && (
                      <p className="text-xs text-slate-600 italic pt-1 line-clamp-1 max-w-xl">
                        &ldquo;{flag.reporter_note}&rdquo;
                      </p>
                    )}
                  </div>

                  <div className="flex items-center gap-4 shrink-0 sm:self-center">
                    <div className="text-right">
                      <FlagStatusBadge status={flag.status} />
                      <p className="mt-1 text-[10px] text-slate-400 font-mono">
                        {new Date(flag.created_at).toLocaleDateString()}
                      </p>
                    </div>

                    <IconArrowRight className="h-4 w-4 text-slate-300 group-hover:text-slate-600 transition-colors" />
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}
      </div>
    </AppShell>
  );
}
