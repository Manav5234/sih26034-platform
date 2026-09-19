import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import Link from "next/link";
import { getServerApiUrl } from "@/lib/config";
import { AppShell } from "@/components/layout/AppShell";
import { StatCard } from "@/components/ui/StatCard";
import { ComplianceBadge } from "@/components/ui/Badges";
import {
  IconScan,
  IconHistory,
  IconAlertTriangle,
  IconCheckCircle,
  IconConflict,
  IconFlag,
  IconPlus,
  IconArrowRight,
  IconBarcode,
  IconProduct,
} from "@/components/ui/Icons";

async function getDashboard(token: string) {
  try {
    const res = await fetch(`${getServerApiUrl()}/dashboard`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

async function getRecentScans(token: string) {
  try {
    const res = await fetch(`${getServerApiUrl()}/scans?page=1&page_size=5`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = await res.json();
    return data.items || [];
  } catch {
    return [];
  }
}

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

export default async function DashboardPage() {
  const cookieStore = await cookies();
  const token = cookieStore.get("access_token")?.value;
  if (!token) redirect("/login");

  const [dashboardData, recentScans] = await Promise.all([
    getDashboard(token),
    getRecentScans(token),
  ]);

  if (!dashboardData) {
    redirect("/login");
  }

  const totalScans = dashboardData.total_scans || 0;
  const violationsAi = dashboardData.violations_ai || 0;
  const officerConfirmed = dashboardData.violations_officer_confirmed || 0;
  const notVerified = dashboardData.not_verified || 0;
  const conflicts = dashboardData.conflict || 0;
  const pendingReview = dashboardData.scans_pending_review || 0;
  const pendingFlags = dashboardData.pending_flags || 0;
  const scansToday = dashboardData.scans_today || 0;

  // Real compliance proportion calculation
  const totalAnalyzed = violationsAi + notVerified + conflicts;
  const compliantEstimated = Math.max(0, totalScans - totalAnalyzed);

  return (
    <AppShell>
      <div className="space-y-8">
        {/* Top Header Command Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-6 border-b border-slate-200/80">
          <div>
            <div className="inline-flex items-center gap-2 mb-1.5">
              <span className="text-[10px] font-bold uppercase tracking-widest text-brand-600">
                COMPLIANCE INTELLIGENCE
              </span>
              <span className="h-1 w-1 rounded-full bg-slate-300" />
              <div className="inline-flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>Systems operational</span>
              </div>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              {getGreeting()}, Officer
            </h1>
            <p className="mt-1 text-xs sm:text-sm text-slate-500">
              Monitor inspections, AI findings, and legal metrology compliance activity from one command center.
            </p>
          </div>

          {/* Quick Primary Actions */}
          <div className="flex items-center gap-3">
            <Link
              href="/scans"
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 hover:text-slate-900 transition-colors shadow-2xs"
            >
              <IconHistory className="h-4 w-4 text-slate-500" />
              <span>Inspection History</span>
            </Link>
            <Link
              href="/scan"
              className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-xs font-bold text-white shadow-md shadow-brand-600/25 hover:bg-brand-700 active:scale-95 transition-all"
            >
              <IconPlus className="h-4 w-4" />
              <span>New Inspection</span>
            </Link>

          </div>
        </div>

        {/* 8-Metric Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            label="Total Scans"
            value={totalScans}
            supportingText="All-time inspections"
            icon={<IconScan className="h-5 w-5" />}
            tone="brand"
          />
          <StatCard
            label="Pending Review"
            value={pendingReview}
            supportingText="Require officer attention"
            icon={<IconAlertTriangle className="h-5 w-5" />}
            tone="amber"
          />
          <StatCard
            label="AI Violations"
            value={violationsAi}
            supportingText="Detected by inspection engine"
            icon={<IconAlertTriangle className="h-5 w-5" />}
            tone="rose"
          />
          <StatCard
            label="Officer Confirmed"
            value={officerConfirmed}
            supportingText="Verified violation findings"
            icon={<IconCheckCircle className="h-5 w-5" />}
            tone="rose"
          />
          <StatCard
            label="Not Verified"
            value={notVerified}
            supportingText="Ambiguous or low confidence"
            icon={<IconAlertTriangle className="h-5 w-5" />}
            tone="amber"
          />
          <StatCard
            label="Conflicts"
            value={conflicts}
            supportingText="Require resolution"
            icon={<IconConflict className="h-5 w-5" />}
            tone="purple"
          />
          <StatCard
            label="Pending Flags"
            value={pendingFlags}
            supportingText="Consumer reports pending"
            icon={<IconFlag className="h-5 w-5" />}
            tone="rose"
          />
          <StatCard
            label="Inspected Today"
            value={scansToday}
            supportingText="Scans processed today"
            icon={<IconCheckCircle className="h-5 w-5" />}
            tone="emerald"
          />
        </div>

        {/* Operational Section: Recent Inspections & Compliance Overview */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Left Column (7 cols): Recent Inspections */}
          <div className="lg:col-span-7 rounded-2xl bg-white border border-slate-200/80 p-6 shadow-card">
            <div className="flex items-center justify-between pb-4 border-b border-slate-100 mb-4">
              <div>
                <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider">
                  Recent Inspections
                </h2>
                <p className="text-xs text-slate-500 mt-0.5">
                  Latest packaging scans processed by the compliance pipeline
                </p>
              </div>
              <Link
                href="/scans"
                className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600 hover:text-brand-700"
              >
                <span>View All</span>
                <IconArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>

            {recentScans.length === 0 ? (
              <div className="py-12 text-center">
                <IconScan className="h-10 w-10 text-slate-300 mx-auto mb-2" />
                <p className="text-sm font-semibold text-slate-700">No inspections recorded yet</p>
                <p className="text-xs text-slate-400 mt-1 max-w-xs mx-auto">
                  Start your first packaging inspection by capturing front and back product images.
                </p>
                <Link
                  href="/scan"
                  className="mt-4 inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-3.5 py-2 text-xs font-semibold text-white shadow-sm hover:bg-brand-700"
                >
                  <IconPlus className="h-3.5 w-3.5" />
                  <span>Start First Scan</span>
                </Link>
              </div>
            ) : (
              <div className="space-y-2.5">
                {recentScans.map((scan: {
                  id: string;
                  product_name: string | null;
                  barcode: string | null;
                  overall_status: string | null;
                  has_inspection: boolean;
                  declarations_count: number;
                  created_at: string;
                }) => (
                  <Link
                    key={scan.id}
                    href={`/scan/${scan.id}`}
                    className="group flex items-center justify-between rounded-xl border border-slate-100 bg-slate-50/60 p-3.5 hover:border-slate-200 hover:bg-white hover:shadow-sm transition-all"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white border border-slate-200 text-slate-500 group-hover:border-brand-300 group-hover:text-brand-600 transition-colors">
                        <IconProduct className="h-5 w-5" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-800 truncate">
                          {scan.product_name || `Product Scan ${scan.id.slice(0, 8)}`}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-500">
                          {scan.barcode && (
                            <span className="font-mono text-slate-400">
                              EAN: {scan.barcode}
                            </span>
                          )}
                          <span>•</span>
                          <span>
                            {new Date(scan.created_at).toLocaleDateString()}
                          </span>
                          {scan.has_inspection && (
                            <span className="text-emerald-600 font-semibold">• Reviewed</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <ComplianceBadge status={scan.overall_status} size="sm" />
                      <IconArrowRight className="h-4 w-4 text-slate-300 group-hover:text-slate-600 transition-colors" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </div>

          {/* Right Column (5 cols): Compliance Overview & Quick Actions */}
          <div className="lg:col-span-5 space-y-6">
            {/* Visual Compliance Breakdown Card */}
            <div className="rounded-2xl bg-white border border-slate-200/80 p-6 shadow-card">
              <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wider mb-1">
                Compliance Distribution
              </h2>
              <p className="text-xs text-slate-500 mb-6">
                Proportion of analyzed inspection outcomes across legal metrology rules
              </p>

              {totalScans === 0 ? (
                <p className="text-xs text-slate-400 py-6 text-center">
                  Awaiting scan data to generate compliance breakdown.
                </p>
              ) : (
                <div className="space-y-4">
                  {/* Multi-segment stacked distribution progress bar */}
                  <div className="h-3.5 w-full rounded-full bg-slate-100 overflow-hidden flex shadow-inner">
                    <div
                      style={{ width: `${(compliantEstimated / totalScans) * 100}%` }}
                      className="bg-emerald-500 transition-all duration-500"
                      title={`Compliant: ${compliantEstimated}`}
                    />
                    <div
                      style={{ width: `${(violationsAi / totalScans) * 100}%` }}
                      className="bg-rose-500 transition-all duration-500"
                      title={`Violations: ${violationsAi}`}
                    />
                    <div
                      style={{ width: `${(notVerified / totalScans) * 100}%` }}
                      className="bg-amber-400 transition-all duration-500"
                      title={`Not Verified: ${notVerified}`}
                    />
                    <div
                      style={{ width: `${(conflicts / totalScans) * 100}%` }}
                      className="bg-purple-500 transition-all duration-500"
                      title={`Conflicts: ${conflicts}`}
                    />
                  </div>

                  {/* Legend list */}
                  <div className="space-y-2 pt-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-slate-600 font-medium">
                        <span className="h-2 w-2 rounded-full bg-emerald-500" />
                        <span>Satisfied / Compliant</span>
                      </span>
                      <span className="font-bold text-slate-900">
                        {compliantEstimated} ({Math.round((compliantEstimated / totalScans) * 100)}%)
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-slate-600 font-medium">
                        <span className="h-2 w-2 rounded-full bg-rose-500" />
                        <span>Violations Detected</span>
                      </span>
                      <span className="font-bold text-rose-700">
                        {violationsAi} ({Math.round((violationsAi / totalScans) * 100)}%)
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-slate-600 font-medium">
                        <span className="h-2 w-2 rounded-full bg-amber-400" />
                        <span>Not Verified / Warning</span>
                      </span>
                      <span className="font-bold text-amber-700">
                        {notVerified} ({Math.round((notVerified / totalScans) * 100)}%)
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-slate-600 font-medium">
                        <span className="h-2 w-2 rounded-full bg-purple-500" />
                        <span>Cross-Source Conflicts</span>
                      </span>
                      <span className="font-bold text-purple-700">
                        {conflicts} ({Math.round((conflicts / totalScans) * 100)}%)
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Quick Repository Links */}
            <div className="rounded-2xl bg-gradient-to-br from-navy-950 to-slate-900 p-6 text-white shadow-card">
              <h3 className="text-sm font-bold tracking-wide">Inspection Repositories</h3>
              <p className="mt-1 text-xs text-slate-400">
                Direct access to compliance intelligence databases
              </p>

              <div className="mt-4 grid grid-cols-2 gap-3">
                <Link
                  href="/products"
                  className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 hover:bg-slate-800 hover:border-slate-700 transition-all text-left"
                >
                  <IconProduct className="h-4 w-4 text-brand-400 mb-1.5" />
                  <p className="text-xs font-bold text-slate-200">Products</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">Database search</p>
                </Link>

                <Link
                  href="/flags"
                  className="rounded-xl border border-slate-800 bg-slate-900/60 p-3 hover:bg-slate-800 hover:border-slate-700 transition-all text-left"
                >
                  <IconFlag className="h-4 w-4 text-rose-400 mb-1.5" />
                  <p className="text-xs font-bold text-slate-200">Consumer Flags</p>
                  <p className="text-[10px] text-slate-400 mt-0.5">Report queue</p>
                </Link>
              </div>
            </div>
          </div>
      </div>
    </AppShell>
  );
}

