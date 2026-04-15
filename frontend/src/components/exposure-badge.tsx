"use client";

import { Badge } from "@/components/ui/badge";

export function ExposureBadge({
  level,
  score,
}: {
  level: "LOW" | "MEDIUM" | "HIGH" | null | undefined;
  score?: number | null | undefined;
}) {
  if (!level) return <span className="text-slate-600">—</span>;

  const label = level === "LOW" ? "Low" : level === "MEDIUM" ? "Medium" : "High";
  const cls =
    level === "LOW"
      ? "border-emerald-200 bg-emerald-50 text-emerald-900"
      : level === "MEDIUM"
        ? "border-amber-200 bg-amber-50 text-amber-900"
        : "border-red-200 bg-red-50 text-red-900";
  const title = `Confidentiality Exposure Level: ${label}${score != null ? ` (Score: ${score}/100)` : ""}. Indicates likelihood that sensitive data or confidential identifiers were included.`;

  return (
    <Badge className={cls} title={title}>
      {label}
    </Badge>
  );
}
