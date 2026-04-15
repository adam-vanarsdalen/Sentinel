import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function NotFoundPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-3 p-6">
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-900 shadow-sm">
        <div className="text-lg font-semibold">404 Not Found</div>
        <div className="mt-2 text-slate-600">The page you requested does not exist or is no longer available.</div>
        <div className="mt-4 flex gap-2">
          <Link href="/dashboard" className={buttonVariants({ variant: "outline" })}>
            Go to dashboard
          </Link>
        </div>
      </div>
    </main>
  );
}
