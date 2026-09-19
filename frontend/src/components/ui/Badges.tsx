import React from "react";
import {
  IconCheckCircle,
  IconXCircle,
  IconAlertTriangle,
  IconConflict,
  IconShield,
} from "./Icons";

export type VerificationState =
  | "SATISFIED"
  | "VIOLATION"
  | "NOT_VERIFIED"
  | "CONFLICT"
  | "NOT_APPLICABLE";

interface ComplianceBadgeProps {
  status: string | null | undefined;
  size?: "sm" | "md" | "lg";
  withIcon?: boolean;
  className?: string;
}

export function ComplianceBadge({
  status,
  size = "md",
  withIcon = true,
  className = "",
}: ComplianceBadgeProps) {
  const norm = (status || "NOT_VERIFIED").toUpperCase();

  const configs: Record<
    string,
    {
      label: string;
      bg: string;
      border: string;
      text: string;
      icon: React.ReactNode;
    }
  > = {
    SATISFIED: {
      label: "Compliant",
      bg: "bg-emerald-50",
      border: "border-emerald-200/80",
      text: "text-emerald-800",
      icon: <IconCheckCircle className="w-3.5 h-3.5 text-emerald-600" />,
    },
    VIOLATION: {
      label: "Violation",
      bg: "bg-rose-50",
      border: "border-rose-200/80",
      text: "text-rose-800",
      icon: <IconXCircle className="w-3.5 h-3.5 text-rose-600" />,
    },
    NOT_VERIFIED: {
      label: "Not Verified",
      bg: "bg-amber-50",
      border: "border-amber-200/80",
      text: "text-amber-800",
      icon: <IconAlertTriangle className="w-3.5 h-3.5 text-amber-600" />,
    },
    CONFLICT: {
      label: "Conflict",
      bg: "bg-purple-50",
      border: "border-purple-200/80",
      text: "text-purple-800",
      icon: <IconConflict className="w-3.5 h-3.5 text-purple-600" />,
    },
    NOT_APPLICABLE: {
      label: "N/A",
      bg: "bg-slate-100",
      border: "border-slate-200",
      text: "text-slate-600",
      icon: <IconShield className="w-3.5 h-3.5 text-slate-400" />,
    },
  };

  const config = configs[norm] || configs.NOT_VERIFIED;

  const sizeClasses = {
    sm: "px-2 py-0.5 text-[11px] gap-1",
    md: "px-2.5 py-1 text-xs gap-1.5",
    lg: "px-3 py-1.5 text-sm gap-2",
  }[size];

  return (
    <span
      className={`inline-flex items-center font-medium rounded-full border shadow-2xs select-none transition-colors ${config.bg} ${config.border} ${config.text} ${sizeClasses} ${className}`}
    >
      {withIcon && config.icon}
      <span>{config.label}</span>
    </span>
  );
}

export function FlagStatusBadge({
  status,
  className = "",
}: {
  status: string;
  className?: string;
}) {
  const norm = (status || "NEW").toUpperCase();

  const configs: Record<
    string,
    { label: string; bg: string; border: string; text: string }
  > = {
    NEW: {
      label: "New",
      bg: "bg-rose-50",
      border: "border-rose-200",
      text: "text-rose-700",
    },
    ACKNOWLEDGED: {
      label: "Acknowledged",
      bg: "bg-amber-50",
      border: "border-amber-200",
      text: "text-amber-700",
    },
    RESOLVED: {
      label: "Resolved",
      bg: "bg-emerald-50",
      border: "border-emerald-200",
      text: "text-emerald-700",
    },
    DISMISSED: {
      label: "Dismissed",
      bg: "bg-slate-100",
      border: "border-slate-200",
      text: "text-slate-600",
    },
  };

  const config = configs[norm] || configs.NEW;

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold border ${config.bg} ${config.border} ${config.text} ${className}`}
    >
      {config.label}
    </span>
  );
}

export function RoleBadge({
  role,
  className = "",
}: {
  role: string;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-md text-[10px] font-bold tracking-wider uppercase bg-brand-500/10 text-brand-700 border border-brand-500/20 ${className}`}
    >
      {role}
    </span>
  );
}
