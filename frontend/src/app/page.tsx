import Link from "next/link";
import { redirect } from "next/navigation";
import { cookies } from "next/headers";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PresetSelector } from "@/components/preset-selector";
import { loadAppConfig } from "@/lib/app-config-server";
import RequestTrialButton from "./request-trial-button";

export async function generateMetadata() {
  const appConfig = await loadAppConfig();
  return {
    title: appConfig.product.name,
  };
}

export default async function Home() {
  const token = (await cookies()).get("sentinel_access_token")?.value;
  if (token) redirect("/dashboard");
  return <Landing />;
}

async function Landing() {
  const appConfig = await loadAppConfig();
  return (
    <main className="mx-auto max-w-5xl py-12">
      <div className="grid gap-6 lg:grid-cols-[1.15fr_320px]">
        <section className="space-y-6 rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <div className="space-y-3">
            <div className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-600">{appConfig.copy.landing_eyebrow}</div>
            <h1 className="text-4xl font-semibold tracking-tight text-slate-950">{appConfig.copy.landing_title}</h1>
            <p className="max-w-2xl text-base leading-7 text-slate-700">{appConfig.copy.landing_description}</p>
          </div>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
            <div className="text-sm font-medium text-slate-900">How {appConfig.product.name} works</div>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              {appConfig.product.name} is an AI governance layer that sits between users and model providers, enforces
              organizational rules, flags risky usage, and creates an audit trail.
            </p>
          </div>

          <ul className="list-disc space-y-2 pl-5 text-sm leading-6 text-slate-700">
            {appConfig.copy.landing_highlights.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>

          <div className="flex flex-wrap items-center gap-4 pt-2">
            <RequestTrialButton />
            <Link href="/login" className="text-sm text-slate-700 underline underline-offset-2 hover:text-slate-900">
              Login
            </Link>
          </div>
        </section>

        <div className="space-y-4">
          <Card className="border-slate-200 shadow-sm">
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Demo Framing</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <PresetSelector />
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                <div className="font-medium text-slate-900">{appConfig.product.name}</div>
                <div className="mt-1 leading-6">
                  {appConfig.product.console_name} uses the same governance platform with preset-specific terminology,
                  workflow labels, and demo positioning.
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </main>
  );
}
