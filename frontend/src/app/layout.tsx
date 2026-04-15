import "../styles/globals.css";
import { loadAppConfig } from "@/lib/app-config-server";
import { Providers } from "./providers";
import { Toaster } from "@/components/toaster";

export default async function RootLayout({ children }: { children: React.ReactNode }) {
  const appConfig = await loadAppConfig();
  return (
    <html lang="en" data-preset={appConfig.preset_id}>
      <head>
        <link rel="icon" href="/favicon.svg" type="image/svg+xml" />
      </head>
      <body className="min-h-screen bg-slate-50 text-slate-900">
        <Providers appConfig={appConfig}>
          <Toaster>
            <div className="mx-auto max-w-7xl p-6">{children}</div>
          </Toaster>
        </Providers>
      </body>
    </html>
  );
}
