"use client";

import { Button } from "@/components/ui/button";

export default function AppError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="space-y-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-900">
      <div className="font-medium">Application error</div>
      <div className="text-xs text-red-800">Something went wrong while loading this page.</div>
      <div className="text-xs text-red-800">
        Try again. If the problem continues, contact your administrator and share the “Digest”.
      </div>
      {error.digest ? <div className="rounded border border-red-200 bg-white p-2 font-mono text-xs">Digest: {error.digest}</div> : null}
      <div className="flex items-center gap-2">
        <Button variant="outline" onClick={() => reset()}>
          Retry
        </Button>
        <Button
          variant="outline"
          onClick={() => {
            window.location.href = "/dashboard";
          }}
        >
          Go to dashboard
        </Button>
      </div>
    </div>
  );
}
