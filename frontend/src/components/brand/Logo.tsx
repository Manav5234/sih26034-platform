import React from "react";
import Link from "next/link";

interface LogoProps {
  size?: "sm" | "md" | "lg";
  variant?: "dark" | "light"; // "dark" = dark text for light bg, "light" = light text for dark bg
  withSubtitle?: boolean;
  href?: string;
  className?: string;
}

export function Logo({
  size = "md",
  variant = "dark",
  withSubtitle = false,
  href = "/dashboard",
  className = "",
}: LogoProps) {
  const isLight = variant === "light";

  const sizeClasses = {
    sm: {
      mark: "h-7 w-7",
      title: "text-base tracking-tight font-bold",
      sub: "text-[9px]",
    },
    md: {
      mark: "h-9 w-9",
      title: "text-lg tracking-tight font-bold",
      sub: "text-[10px]",
    },
    lg: {
      mark: "h-11 w-11",
      title: "text-2xl tracking-tight font-extrabold",
      sub: "text-xs",
    },
  }[size];

  const content = (
    <div className={`flex items-center gap-3 select-none ${className}`}>
      {/* Precision Logo Icon Mark: Frame + Check + Document Lines */}
      <div
        className={`relative flex items-center justify-center rounded-xl transition-transform hover:scale-105 ${
          sizeClasses.mark
        } ${
          isLight
            ? "bg-gradient-to-br from-brand-600 to-navy-900 border border-brand-400/30 text-white shadow-lg shadow-brand-950/40"
            : "bg-gradient-to-br from-navy-900 to-brand-900 border border-slate-700/20 text-white shadow-md shadow-slate-900/10"
        }`}
      >
        <svg
          viewBox="0 0 32 32"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="h-5/6 w-5/6"
        >
          {/* Outer Scanner Reticle Corners */}
          <path
            d="M6 10V6H10"
            stroke={isLight ? "#60a5fa" : "#38bdf8"}
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M22 6H26V10"
            stroke={isLight ? "#60a5fa" : "#38bdf8"}
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M6 22V26H10"
            stroke={isLight ? "#60a5fa" : "#38bdf8"}
            strokeWidth="2"
            strokeLinecap="round"
          />
          <path
            d="M22 26H26V22"
            stroke={isLight ? "#60a5fa" : "#38bdf8"}
            strokeWidth="2"
            strokeLinecap="round"
          />

          {/* Compliance Shield / Document Grid Outline */}
          <rect
            x="9"
            y="9"
            width="14"
            height="14"
            rx="3"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeOpacity="0.4"
          />

          {/* Verified Checkmark */}
          <path
            d="M11.5 16.5L14.5 19.5L20.5 12.5"
            stroke="#10b981"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Wordmark */}
      <div className="flex flex-col">
        <div className="flex items-center gap-1.5">
          <span
            className={`${sizeClasses.title} ${
              isLight ? "text-white" : "text-slate-900"
            }`}
          >
            Scan<span className={isLight ? "text-brand-300" : "text-brand-600"}>Check</span>
          </span>
          <span
            className={`rounded px-1.5 py-0.2 text-[9px] font-semibold uppercase tracking-wider ${
              isLight
                ? "bg-brand-500/20 text-brand-300 border border-brand-400/20"
                : "bg-brand-50 text-brand-700 border border-brand-200"
            }`}
          >
            LMPC
          </span>
        </div>
        {withSubtitle && (
          <span
            className={`font-medium tracking-wide uppercase ${sizeClasses.sub} ${
              isLight ? "text-slate-400" : "text-slate-500"
            }`}
          >
            Compliance Intelligence
          </span>
        )}
      </div>
    </div>
  );

  if (href) {
    return (
      <Link href={href} className="inline-block focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded-lg">
        {content}
      </Link>
    );
  }

  return content;
}
