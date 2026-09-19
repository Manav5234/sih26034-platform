import Link from "next/link";
import { getServerApiUrl } from "@/lib/config";
import { Logo } from "@/components/brand/Logo";
import {
  IconScan,
  IconShield,
  IconFileText,
  IconCheckCircle,
  IconAlertTriangle,
  IconArrowRight,
} from "@/components/ui/Icons";

async function getHealth() {
  try {
    const apiUrl = getServerApiUrl();
    const res = await fetch(`${apiUrl}/health`, {
      cache: "no-store",
    });
    if (!res.ok) return { status: "error", service: "unreachable" };
    return res.json();
  } catch {
    return { status: "error", service: "unreachable" };
  }
}

export default async function Home() {
  const health = await getHealth();
  const isHealthy = health.status === "ok";

  return (
    <div className="min-h-screen bg-slate-900 text-white selection:bg-brand-500/30 selection:text-white">
      {/* Top Glass Navigation */}
      <header className="sticky top-0 z-30 border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
        <div className="mx-auto flex h-18 max-w-7xl items-center justify-between px-6 sm:px-8">
          <Logo size="md" variant="light" withSubtitle href="/" />

          <div className="flex items-center gap-4">
            {/* Live Backend Indicator */}
            <div className="hidden sm:flex items-center gap-2 rounded-full border border-slate-800 bg-slate-900/80 px-3 py-1 text-xs">
              <span
                className={`h-2 w-2 rounded-full ${
                  isHealthy
                    ? "bg-emerald-400 ring-2 ring-emerald-400/20 animate-pulse"
                    : "bg-rose-500 ring-2 ring-rose-500/20"
                }`}
              />
              <span className="text-slate-300 text-[11px] font-mono">
                {isHealthy ? "API Online" : "API Offline"}
              </span>
            </div>

            <Link
              href="/login"
              className="inline-flex items-center justify-center rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-colors border border-slate-700"
            >
              Officer Login
            </Link>

            <Link
              href="/scan"
              className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-brand-600/30 hover:bg-brand-500 active:scale-95 transition-all"
            >
              <span>Start Inspection</span>
              <IconArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <main className="relative overflow-hidden pt-12 pb-24 lg:pt-20">
        {/* Subtle background glow */}
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[350px] bg-brand-600/15 blur-[120px] pointer-events-none rounded-full" />
        <div className="absolute top-1/3 right-10 w-[300px] h-[300px] bg-emerald-500/10 blur-[100px] pointer-events-none rounded-full" />

        <div className="relative mx-auto max-w-7xl px-6 sm:px-8">
          <div className="grid grid-cols-1 gap-12 lg:grid-cols-12 lg:items-center">
            {/* Left Hero Content */}
            <div className="lg:col-span-7 space-y-6">
              <div className="inline-flex items-center gap-2 rounded-full border border-brand-500/30 bg-brand-950/60 px-3.5 py-1 text-xs font-semibold text-brand-300">
                <span className="h-1.5 w-1.5 rounded-full bg-brand-400" />
                <span>Legal Metrology (Packaged Commodities) Rules</span>
              </div>

              <h1 className="text-4xl sm:text-5xl lg:text-6xl font-extrabold tracking-tight text-white leading-[1.15]">
                Inspect smarter. <br />
                <span className="text-transparent bg-clip-text bg-gradient-to-r from-brand-300 via-sky-200 to-emerald-300">
                  Verify faster.
                </span>
              </h1>

              <p className="max-w-xl text-base sm:text-lg text-slate-400 font-normal leading-relaxed">
                AI-assisted product label inspection built for accurate, transparent, and auditable compliance verification across Indian packaged commodities.
              </p>

              <div className="flex flex-wrap items-center gap-4 pt-2">
                <Link
                  href="/scan"
                  className="inline-flex items-center gap-2 rounded-xl bg-brand-600 px-6 py-3.5 text-sm font-bold text-white shadow-xl shadow-brand-600/25 hover:bg-brand-500 hover:shadow-brand-500/35 active:scale-98 transition-all"
                >
                  <IconScan className="w-4 h-4" />
                  <span>Start Inspection</span>
                </Link>

                <Link
                  href="/login"
                  className="inline-flex items-center gap-2 rounded-xl bg-slate-800/80 px-6 py-3.5 text-sm font-semibold text-slate-200 border border-slate-700 hover:bg-slate-700 hover:text-white transition-all"
                >
                  <span>Officer Portal</span>
                  <IconArrowRight className="w-4 h-4" />
                </Link>
              </div>

              {/* Compliance Trust Badges */}
              <div className="pt-6 border-t border-slate-800/80 grid grid-cols-2 sm:grid-cols-4 gap-4 text-slate-400 text-xs">
                <div>
                  <p className="font-bold text-slate-200">100% Auditable</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Additive officer overrides</p>
                </div>
                <div>
                  <p className="font-bold text-slate-200">Dual-Label OCR</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Front &amp; back packaging fusion</p>
                </div>
                <div>
                  <p className="font-bold text-slate-200">Location-Tagged</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">GPS verified enforcement</p>
                </div>
                <div>
                  <p className="font-bold text-slate-200">Report Ready</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">Instant PDF &amp; DOCX generation</p>
                </div>
              </div>
            </div>

            {/* Right Hero Visual Mockup: Computer Vision Inspection Simulation */}
            <div className="lg:col-span-5">
              <div className="relative rounded-2xl border border-slate-800 bg-slate-950/90 p-6 shadow-2xl shadow-brand-950/60 backdrop-blur-xl">
                {/* Header of the mock window */}
                <div className="flex items-center justify-between pb-4 border-b border-slate-800 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                    <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                    <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                    <span className="ml-2 font-mono text-[11px] text-slate-400">
                      SCAN_CV#890154
                    </span>
                  </div>
                  <span className="rounded-full bg-emerald-500/10 border border-emerald-500/30 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-400">
                    Rule Engine v2.4
                  </span>
                </div>

                {/* Simulated Product Package with Scanning Reticle */}
                <div className="relative mt-4 h-56 rounded-xl border border-dashed border-slate-700/80 bg-slate-900/60 p-4 overflow-hidden flex flex-col justify-between">
                  {/* Subtle Scan Line Animation Effect */}
                  <div className="absolute inset-x-0 h-0.5 bg-gradient-to-r from-transparent via-cyan-400 to-transparent animate-pulse top-1/2 -translate-y-1/2 shadow-lg shadow-cyan-400/50" />

                  {/* Simulated Bounding Boxes with Labels */}
                  <div className="relative flex justify-between items-start">
                    <div className="relative rounded border-2 border-emerald-400 bg-emerald-400/10 p-2 text-left">
                      <span className="absolute -top-3 left-1 rounded bg-emerald-500 px-1 py-0.2 text-[9px] font-bold text-slate-950">
                        MRP: ₹199.00
                      </span>
                      <p className="text-[11px] font-mono text-emerald-300 mt-1">
                        INCL. OF ALL TAXES
                      </p>
                    </div>

                    <div className="relative rounded border-2 border-brand-400 bg-brand-400/10 p-2 text-right">
                      <span className="absolute -top-3 right-1 rounded bg-brand-500 px-1 py-0.2 text-[9px] font-bold text-slate-950">
                        EAN-13
                      </span>
                      <p className="text-[11px] font-mono text-brand-300 mt-1">
                        8901542001406
                      </p>
                    </div>
                  </div>

                  {/* Bottom Bounding Box */}
                  <div className="relative rounded border-2 border-amber-400 bg-amber-400/10 p-2">
                    <span className="absolute -top-3 left-1 rounded bg-amber-500 px-1 py-0.2 text-[9px] font-bold text-slate-950">
                      Net Qty: 200 g
                    </span>
                    <p className="text-[10px] font-mono text-amber-200 mt-0.5">
                      LMPC Rule 6(1)(b) • High Confidence (98%)
                    </p>
                  </div>
                </div>

                {/* Real-time Extracted Findings Preview */}
                <div className="mt-4 space-y-2">
                  <div className="flex items-center justify-between rounded-xl bg-slate-900/80 p-2.5 text-xs border border-slate-800">
                    <div className="flex items-center gap-2">
                      <IconCheckCircle className="h-4 w-4 text-emerald-400" />
                      <span className="font-semibold text-slate-200">Maximum Retail Price</span>
                    </div>
                    <span className="font-mono text-emerald-400 font-bold">Compliant</span>
                  </div>

                  <div className="flex items-center justify-between rounded-xl bg-slate-900/80 p-2.5 text-xs border border-slate-800">
                    <div className="flex items-center gap-2">
                      <IconCheckCircle className="h-4 w-4 text-emerald-400" />
                      <span className="font-semibold text-slate-200">Consumer Care Address</span>
                    </div>
                    <span className="font-mono text-emerald-400 font-bold">Compliant</span>
                  </div>

                  <div className="flex items-center justify-between rounded-xl bg-slate-900/80 p-2.5 text-xs border border-slate-800">
                    <div className="flex items-center gap-2">
                      <IconAlertTriangle className="h-4 w-4 text-amber-400" />
                      <span className="font-semibold text-slate-200">Unit Sale Price (USP)</span>
                    </div>
                    <span className="font-mono text-amber-400 font-bold">Review Flag</span>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-[11px] text-slate-400 font-mono">
                  <span>OVERALL COMPLIANCE</span>
                  <span className="text-emerald-400 font-bold">92.4% SATISFIED</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Feature Strip */}
        <div className="mt-20 border-y border-slate-800/80 bg-slate-950/60 py-10">
          <div className="mx-auto max-w-7xl px-6 sm:px-8">
            <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-500/10 text-brand-400 border border-brand-500/20">
                  <IconScan className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">AI-Assisted Inspection</h3>
                  <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                    Automated multi-variant OCR and barcode fusion extracts packaging text with precision.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  <IconShield className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Evidence-Based Verification</h3>
                  <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                    Interactive bounding box visual coordinates guarantee every declaration traces to real packaging.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
                  <IconCheckCircle className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Officer-Controlled Review</h3>
                  <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                    Full officer authority to confirm, correct, or unresolve findings with an immutable audit log.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-4">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  <IconFileText className="h-5 w-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white">Audit-Ready Reports</h3>
                  <p className="mt-1 text-xs text-slate-400 leading-relaxed">
                    Generate court and enforcement-grade PDF &amp; DOCX inspection documentation in seconds.
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Clean Footer */}
      <footer className="border-t border-slate-800 bg-slate-950 py-8 text-center text-xs text-slate-500">
        <div className="mx-auto max-w-7xl px-6 sm:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Logo size="sm" variant="light" href="/" />
          <p>SIH 26034 • Legal Metrology Packaged Commodities Compliance Intelligence</p>
          <div className="flex items-center gap-4 text-slate-400">
            <Link href="/login" className="hover:text-white transition-colors">
              Officer Portal
            </Link>
            <Link href="/scan" className="hover:text-white transition-colors">
              New Inspection
            </Link>
          </div>
        </div>
      </footer>
    </div>
  );
}
