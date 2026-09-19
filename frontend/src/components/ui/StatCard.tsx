import React from "react";

interface StatCardProps {
  label: string;
  value: number | string;
  supportingText?: string;
  icon?: React.ReactNode;
  tone?: "neutral" | "brand" | "emerald" | "amber" | "rose" | "purple";
  className?: string;
}

export function StatCard({
  label,
  value,
  supportingText,
  icon,
  tone = "neutral",
  className = "",
}: StatCardProps) {
  const toneClasses = {
    neutral: {
      border: "border-slate-200/80 hover:border-slate-300",
      value: "text-slate-900",
      iconBg: "bg-slate-100 text-slate-600",
      sub: "text-slate-500",
    },
    brand: {
      border: "border-brand-200/80 hover:border-brand-300",
      value: "text-brand-900",
      iconBg: "bg-brand-50 text-brand-700",
      sub: "text-brand-700/80",
    },
    emerald: {
      border: "border-emerald-200/80 hover:border-emerald-300",
      value: "text-emerald-900",
      iconBg: "bg-emerald-50 text-emerald-700",
      sub: "text-emerald-700/80",
    },
    amber: {
      border: "border-amber-200/80 hover:border-amber-300",
      value: "text-amber-900",
      iconBg: "bg-amber-50 text-amber-700",
      sub: "text-amber-700/80",
    },
    rose: {
      border: "border-rose-200/80 hover:border-rose-300",
      value: "text-rose-900",
      iconBg: "bg-rose-50 text-rose-700",
      sub: "text-rose-700/80",
    },
    purple: {
      border: "border-purple-200/80 hover:border-purple-300",
      value: "text-purple-900",
      iconBg: "bg-purple-50 text-purple-700",
      sub: "text-purple-700/80",
    },
  }[tone];

  return (
    <div
      className={`group relative overflow-hidden rounded-2xl bg-white p-5 border shadow-card transition-all duration-200 hover:shadow-card-hover ${toneClasses.border} ${className}`}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            {label}
          </p>
          <p className={`mt-2 text-3xl font-extrabold tracking-tight ${toneClasses.value}`}>
            {value}
          </p>
        </div>
        {icon && (
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-xl p-2 transition-transform duration-200 group-hover:scale-110 ${toneClasses.iconBg}`}
          >
            {icon}
          </div>
        )}
      </div>
      {supportingText && (
        <p className={`mt-3 text-xs font-medium ${toneClasses.sub}`}>
          {supportingText}
        </p>
      )}
    </div>
  );
}
