"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as React from "react";

import { AppConfigProvider } from "@/lib/app-config-context";
import type { AppConfig } from "@/lib/app-config";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export function Providers({ children, appConfig }: { children: React.ReactNode; appConfig: AppConfig }) {
  return (
    <QueryClientProvider client={queryClient}>
      <AppConfigProvider value={appConfig}>{children}</AppConfigProvider>
    </QueryClientProvider>
  );
}
