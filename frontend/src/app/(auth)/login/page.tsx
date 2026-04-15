"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useRouter } from "next/navigation";
import * as React from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAppConfig } from "@/lib/app-config-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchJson, HttpError } from "@/lib/http";

const LoginSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});
type LoginForm = z.infer<typeof LoginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const appConfig = useAppConfig();
  const supportEmail = process.env.NEXT_PUBLIC_SUPPORT_EMAIL || appConfig.product.support_email || "support@sentinel.local";
  const form = useForm<LoginForm>({
    resolver: zodResolver(LoginSchema),
    defaultValues: { email: "", password: "" },
  });

  React.useEffect(() => {
    document.title = `Sign in — ${appConfig.product.name}`;
  }, [appConfig.product.name]);

  const [error, setError] = React.useState<string | null>(null);
  const [loading, setLoading] = React.useState(false);

  async function onSubmit(values: LoginForm) {
    setLoading(true);
    setError(null);
    try {
      await fetchJson("/api/auth/login", { method: "POST", body: JSON.stringify(values) });
      router.replace("/dashboard");
    } catch (e) {
      if (e instanceof HttpError) {
        if (e.status === 401) setError("Invalid email or password.");
        else setError("Login failed.");
      } else setError("Login failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-48px)] items-center justify-center">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>{appConfig.copy.login_description}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
              {form.formState.errors.email ? (
                <div className="text-xs text-red-700">{form.formState.errors.email.message}</div>
              ) : null}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input id="password" type="password" autoComplete="current-password" {...form.register("password")} />
              {form.formState.errors.password ? (
                <div className="text-xs text-red-700">{form.formState.errors.password.message}</div>
              ) : null}
            </div>
            {error ? <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800">{error}</div> : null}
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in…" : "Sign in"}
            </Button>
            <div className="mt-2 text-center text-xs text-slate-600">
              Forgot your password? Contact your administrator or email{" "}
              <a className="underline underline-offset-2" href={`mailto:${supportEmail}`}>
                {supportEmail}
              </a>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
