"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { Logo } from "../brand/Logo";
import {
  IconDashboard,
  IconHistory,
  IconProduct,
  IconFlag,
  IconLogOut,
  IconPlus,
} from "../ui/Icons";

interface SidebarProps {
  onCloseMobile?: () => void;
  officerRole?: string;
  officerName?: string;
}

export function Sidebar({
  onCloseMobile,
  officerRole = "INSPECTOR",
  officerName = "Officer",
}: SidebarProps) {
  const pathname = usePathname();

  const navSections = [
    {
      title: "SCAN",
      items: [
        {
          label: "New Scan",
          href: "/scan",
          icon: <IconPlus className="w-4 h-4" />,
          highlight: true,
        },
        {
          label: "Scan History",
          href: "/scans",
          icon: <IconHistory className="w-4 h-4" />,
        },
      ],
    },
    {
      title: "INTELLIGENCE",
      items: [
        {
          label: "Dashboard",
          href: "/dashboard",
          icon: <IconDashboard className="w-4 h-4" />,
        },
        {
          label: "Product Repository",
          href: "/products",
          icon: <IconProduct className="w-4 h-4" />,
        },
      ],
    },
    {
      title: "REVIEW",
      items: [
        {
          label: "Consumer Flags",
          href: "/flags",
          icon: <IconFlag className="w-4 h-4" />,
        },
      ],
    },
  ];

  const isActive = (href: string) => {
    if (href === "/dashboard") return pathname === "/dashboard";
    return pathname.startsWith(href);
  };

  return (
    <aside className="flex h-full w-64 flex-col justify-between bg-navy-950 text-slate-300 border-r border-slate-800/80 select-none">
      {/* Top Brand Header */}
      <div>
        <div className="flex h-16 items-center px-6 border-b border-slate-800/80">
          <Logo size="md" variant="light" withSubtitle href="/dashboard" />
        </div>

        {/* Navigation Sections */}
        <nav className="space-y-6 px-3 py-6">
          {navSections.map((section) => (
            <div key={section.title}>
              <p className="px-3 text-[10px] font-bold uppercase tracking-widest text-slate-500">
                {section.title}
              </p>
              <ul className="mt-2 space-y-1">
                {section.items.map((item) => {
                  const active = isActive(item.href);
                  return (
                    <li key={item.href}>
                      <Link
                        href={item.href}
                        onClick={onCloseMobile}
                        className={`group flex items-center gap-3 rounded-xl px-3 py-2 text-xs font-semibold transition-all duration-150 ${
                          active
                            ? "bg-brand-600 text-white shadow-md shadow-brand-950/40"
                            : item.highlight
                            ? "bg-brand-500/10 text-brand-300 hover:bg-brand-500/20 hover:text-white"
                            : "text-slate-400 hover:bg-slate-900 hover:text-slate-200"
                        }`}
                      >
                        <span
                          className={`transition-colors ${
                            active
                              ? "text-white"
                              : item.highlight
                              ? "text-brand-400"
                              : "text-slate-500 group-hover:text-slate-300"
                          }`}
                        >
                          {item.icon}
                        </span>
                        <span className="flex-1">{item.label}</span>
                        {active && (
                          <span className="h-1.5 w-1.5 rounded-full bg-white shadow-xs" />
                        )}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>
      </div>

      {/* Bottom Officer Profile & Sign Out */}
      <div className="border-t border-slate-800/80 p-4 space-y-3">
        {/* Live System Status indicator */}
        <div className="flex items-center gap-2 px-2 py-1 text-[11px] font-medium text-slate-400 bg-slate-900/60 rounded-lg border border-slate-800">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="text-slate-300">Systems Operational</span>
        </div>

        {/* Officer info & logout button */}
        <div className="flex items-center justify-between px-2 pt-1">
          <div className="flex flex-col min-w-0">
            <span className="text-xs font-semibold text-slate-200 truncate">
              {officerName}
            </span>
            <span className="text-[10px] uppercase tracking-wider font-bold text-brand-400">
              {officerRole}
            </span>
          </div>

          <form action="/api/auth/logout" method="post">
            <button
              type="submit"
              title="Sign out"
              aria-label="Sign out"
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-800 bg-slate-900 text-slate-400 hover:border-slate-700 hover:bg-slate-800 hover:text-white transition-colors"
            >
              <IconLogOut className="h-4 w-4" />
            </button>
          </form>
        </div>
      </div>
    </aside>
  );
}
