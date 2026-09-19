"use client";

import React, { useState } from "react";
import Link from "next/link";
import { Sidebar } from "./Sidebar";
import { Logo } from "../brand/Logo";
import { IconMenu, IconPlus, IconX } from "../ui/Icons";

interface AppShellProps {
  children: React.ReactNode;
  officerRole?: string;
  officerName?: string;
}

export function AppShell({
  children,
  officerRole = "INSPECTOR",
  officerName = "Officer",
}: AppShellProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Desktop Persistent Sidebar */}
      <div className="hidden lg:block fixed inset-y-0 left-0 z-30 w-64 shadow-xl">
        <Sidebar officerRole={officerRole} officerName={officerName} />
      </div>

      {/* Mobile Drawer Backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-navy-950/70 backdrop-blur-xs lg:hidden transition-opacity"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Sliding Drawer */}
      <div
        className={`fixed inset-y-0 left-0 z-50 w-64 transform transition-transform duration-200 ease-in-out lg:hidden shadow-2xl ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="relative h-full">
          <Sidebar
            onCloseMobile={() => setMobileOpen(false)}
            officerRole={officerRole}
            officerName={officerName}
          />
          <button
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
            className="absolute top-4 right-[-44px] flex h-9 w-9 items-center justify-center rounded-xl bg-navy-900 text-white shadow-lg border border-slate-700"
          >
            <IconX className="h-5 w-5" />
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 lg:pl-64">
        {/* Top Navbar for Mobile & Quick Bar for Desktop */}
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-200/80 bg-white/90 px-4 sm:px-6 backdrop-blur-md">
          <div className="flex items-center gap-3">
            {/* Mobile Hamburger Toggle */}
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation menu"
              className="lg:hidden rounded-lg p-2 text-slate-600 hover:bg-slate-100 transition-colors"
            >
              <IconMenu className="h-6 w-6" />
            </button>

            {/* Mobile Logo */}
            <div className="lg:hidden">
              <Logo size="sm" variant="dark" href="/dashboard" />
            </div>

            {/* Desktop Status Badge */}
            <div className="hidden lg:flex items-center gap-2 text-xs font-semibold text-slate-500">
              <span className="h-2 w-2 rounded-full bg-emerald-500 ring-4 ring-emerald-100" />
              <span>LMPC Compliance Inspection Environment</span>
            </div>
          </div>

          {/* Quick Header Actions */}
          <div className="flex items-center gap-3">
            <Link
              href="/scan"
              className="inline-flex items-center gap-1.5 rounded-xl bg-brand-600 px-3.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-brand-700 active:scale-95 transition-all"
            >
              <IconPlus className="h-3.5 w-3.5" />
              <span>New Scan</span>
            </Link>
          </div>
        </header>

        {/* Page Body */}
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          {children}
        </main>
      </div>
    </div>
  );
}
