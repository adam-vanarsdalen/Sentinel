"use client";

import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { useAppConfig } from "@/lib/app-config-context";

export function ForbiddenState() {
  const appConfig = useAppConfig();
  return (
    <div className="space-y-3 rounded-lg border border-amber-200 bg-amber-50 p-6 text-sm text-amber-950">
      <div className="text-lg font-semibold">403 Forbidden</div>
      <div>You do not have access to this page for the selected {appConfig.terminology.organization_context}.</div>
      <div className="text-xs text-amber-900">
        If you believe this is incorrect, confirm your {appConfig.terminology.organization_context} selection or contact your administrator.
      </div>
      <div className="flex gap-2">
        <Link href="/dashboard" className={buttonVariants({ variant: "outline" })}>
          Go to dashboard
        </Link>
      </div>
    </div>
  );
}
