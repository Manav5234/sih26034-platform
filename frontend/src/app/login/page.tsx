"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getApiUrl } from "@/lib/config";
import { Logo } from "@/components/brand/Logo";
import {
  IconScan,
  IconShield,
  IconCheckCircle,
  IconBarcode,
  IconAlertTriangle,
  IconEye,
  IconEyeOff,
  IconArrowLeft,
} from "@/components/ui/Icons";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const res = await fetch(`${getApiUrl()}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        if (res.status === 429) {
          setError("Too many login attempts. Please wait a few minutes before trying again.");
        } else {
          setError("Invalid officer credentials. Please verify email and password.");
        }
        setLoading(false);
        return;
      }

      const data = await res.json();

      // Store JWT in httpOnly cookie via Next.js internal auth route
      const cookieRes = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: data.token }),
      });

      if (!cookieRes.ok) {
        throw new Error("Failed to set session cookie");
      }

      router.push("/dashboard");
    } catch {
      setError("Unable to connect to the compliance backend service. Please check network connection.");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen grid grid-cols-1 lg:grid-cols-12 bg-slate-900">
      {/* Left Branded Canvas (Hidden on mobile, 5 cols on lg, 6 cols on xl) */}
      <div className="hidden lg:flex lg:col-span-5 xl:col-span-6 flex-col justify-between p-12 bg-gradient-to-br from-navy-950 via-slate-900 to-navy-900 border-r border-slate-800 text-white relative overflow-hidden">
        {/* Decorative Grid and Soft Glows */}
        <div className="absolute inset-0 bg-grid-dark opacity-30 pointer-events-none" />
        <div className="absolute top-1/4 left-10 w-72 h-72 bg-brand-600/15 rounded-full blur-3xl pointer-events-none" />

        {/* Top Header */}
        <div className="relative z-10">
          <Logo size="lg" variant="light" withSubtitle href="/" />
        </div>

        {/* Central Graphic Presentation */}
        <div className="relative z-10 space-y-6 my-auto max-w-lg">
          <div className="inline-flex items-center gap-2 rounded-full border border-brand-400/30 bg-brand-500/10 px-3 py-1 text-xs font-semibold text-brand-300">
            <IconShield className="h-3.5 w-3.5 text-brand-400" />
            <span>Authorized Legal Metrology Access</span>
          </div>

          <h2 className="text-3xl font-extrabold tracking-tight text-white leading-tight">
            Enforcing standards with AI-powered precision.
          </h2>

          <p className="text-sm text-slate-400 leading-relaxed">
            ScanCheck provides verification officers with automated packaging inspection, computerized evidence extraction, and legal metrology rule auditing.
          </p>

          {/* Minimalist Graphic Features Card */}
          <div className="rounded-2xl border border-slate-800 bg-slate-950/70 p-5 space-y-3.5 backdrop-blur-md">
            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <IconCheckCircle className="h-4 w-4" />
              </div>
              <div>
                <p className="font-semibold text-white">Rule 6 Mandatory Declarations</p>
                <p className="text-[11px] text-slate-400">MRP, USP, Net Qty, Dates &amp; Consumer Care</p>
              </div>
            </div>

            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-500/10 text-brand-400 border border-brand-500/20">
                <IconBarcode className="h-4 w-4" />
              </div>
              <div>
                <p className="font-semibold text-white">GS1 Barcode &amp; Database Cross-Referencing</p>
                <p className="text-[11px] text-slate-400">Automated EAN-13 verification and fraud detection</p>
              </div>
            </div>

            <div className="flex items-center gap-3 text-xs text-slate-300">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <IconScan className="h-4 w-4" />
              </div>
              <div>
                <p className="font-semibold text-white">Cryptographic Officer Audit Trail</p>
                <p className="text-[11px] text-slate-400">Additive verification records for enforcement</p>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Legal / Security Notice */}
        <div className="relative z-10 pt-6 border-t border-slate-800/80 text-[11px] text-slate-500 flex items-center justify-between">
          <span>Protected Government Regulatory System</span>
          <span className="font-mono">Security Tier 1</span>
        </div>
      </div>

      {/* Right Authentication Panel */}
      <div className="lg:col-span-7 xl:col-span-6 flex flex-col justify-between p-6 sm:p-12 lg:p-16 bg-white">
        {/* Mobile Logo & Back to Home */}
        <div className="flex items-center justify-between">
          <div className="lg:hidden">
            <Logo size="sm" variant="dark" href="/" />
          </div>
          <Link
            href="/"
            className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 hover:text-slate-800 transition-colors ml-auto"
          >
            <IconArrowLeft className="h-3.5 w-3.5" />
            <span>Return to Overview</span>
          </Link>
        </div>

        {/* Center Form Container */}
        <div className="mx-auto w-full max-w-md my-auto py-8">
          <div className="mb-8">
            <div className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-700 mb-3">
              <span>Official Access</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">
              Officer Sign In
            </h1>
            <p className="mt-1.5 text-sm text-slate-500">
              Access your regulatory compliance inspection workspace.
            </p>
          </div>

          {error && (
            <div className="mb-6 flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-xs text-rose-800 animate-in fade-in duration-200">
              <IconAlertTriangle className="h-4 w-4 shrink-0 text-rose-600 mt-0.5" />
              <div className="flex-1">
                <p className="font-bold">Authentication failed</p>
                <p className="mt-0.5 text-rose-700">{error}</p>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label
                htmlFor="officer-email"
                className="block text-xs font-bold uppercase tracking-wider text-slate-700 mb-1.5"
              >
                Official Email
              </label>
              <input
                id="officer-email"
                type="email"
                required
                autoComplete="email"
                placeholder="officer@nic.in"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
                className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-3 focus:ring-brand-500/20 transition-all disabled:opacity-60"
              />
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label
                  htmlFor="officer-password"
                  className="block text-xs font-bold uppercase tracking-wider text-slate-700"
                >
                  Password
                </label>
              </div>
              <div className="relative">
                <input
                  id="officer-password"
                  type={showPassword ? "text" : "password"}
                  required
                  autoComplete="current-password"
                  placeholder="••••••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={loading}
                  className="w-full rounded-xl border border-slate-300 px-3.5 py-2.5 pr-10 text-sm text-slate-900 placeholder:text-slate-400 focus:border-brand-600 focus:outline-none focus:ring-3 focus:ring-brand-500/20 transition-all disabled:opacity-60"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute inset-y-0 right-0 flex items-center pr-3 text-slate-400 hover:text-slate-600 transition-colors"
                >
                  {showPassword ? (
                    <IconEyeOff className="h-4 w-4" />
                  ) : (
                    <IconEye className="h-4 w-4" />
                  )}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading || !email || !password}
              className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 py-3 text-sm font-bold text-white shadow-md shadow-brand-600/25 hover:bg-brand-700 active:scale-98 transition-all disabled:opacity-50 disabled:pointer-events-none"
            >
              {loading ? (
                <>
                  <span className="h-4 w-4 rounded-full border-2 border-white/30 border-t-white animate-spin" />
                  <span>Verifying Credentials...</span>
                </>
              ) : (
                <span>Sign In to Command Center</span>
              )}
            </button>
          </form>

          {/* Security Hint */}
          <div className="mt-8 pt-6 border-t border-slate-100 text-center">
            <p className="text-xs text-slate-400">
              Only authorized enforcement officers with verified credentials may sign in.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center text-xs text-slate-400">
          ScanCheck Compliance Intelligence • Legal Metrology Platform
        </div>
      </div>
    </div>
  );
}
