"use client";

import { useRouter } from "next/navigation";
import * as React from "react";

import { fetchJson } from "@/lib/http";

export default function LogoutPage() {
  const router = useRouter();

  React.useEffect(() => {
    (async () => {
      try {
        await fetchJson("/api/auth/logout", { method: "POST" });
      } finally {
        router.replace("/login");
      }
    })();
  }, [router]);

  return <div className="text-sm text-slate-700">Signing out…</div>;
}

