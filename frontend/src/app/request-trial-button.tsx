"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { useAppConfig } from "@/lib/app-config-context";
import { useToast } from "@/components/toaster";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { fetchJson, HttpError } from "@/lib/http";

const TrialSchema = z.object({
  organization_name: z.string().min(1).max(200),
  contact_name: z.string().min(1).max(200),
  email: z.string().email(),
});
type TrialForm = z.infer<typeof TrialSchema>;

export default function RequestTrialButton() {
  const appConfig = useAppConfig();
  const toast = useToast();
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const form = useForm<TrialForm>({
    resolver: zodResolver(TrialSchema),
    defaultValues: { organization_name: "", contact_name: "", email: "" },
  });

  async function onSubmit(values: TrialForm) {
    setLoading(true);
    setError(null);
    try {
      await fetchJson("/api/public/trial-requests", { method: "POST", body: JSON.stringify(values) });
      toast.push({ title: "Request received", description: "We’ll contact you to set up a free trial." });
      form.reset();
      setOpen(false);
    } catch (e) {
      if (e instanceof HttpError) {
        if (e.status === 400) setError("Please check the form fields and try again.");
        else setError("Request failed.");
      } else {
        setError("Request failed.");
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>{appConfig.copy.trial_title}</Button>
      </DialogTrigger>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{appConfig.copy.trial_title}</DialogTitle>
          <DialogDescription>{appConfig.copy.trial_description}</DialogDescription>
        </DialogHeader>

        <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
          <div className="space-y-2">
            <Label htmlFor="organization_name">{appConfig.terminology.organization_singular} name</Label>
            <Input id="organization_name" autoComplete="organization" {...form.register("organization_name")} />
            {form.formState.errors.organization_name ? (
              <div className="text-xs text-red-700">{form.formState.errors.organization_name.message}</div>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="contact_name">Contact name</Label>
            <Input id="contact_name" autoComplete="name" {...form.register("contact_name")} />
            {form.formState.errors.contact_name ? (
              <div className="text-xs text-red-700">{form.formState.errors.contact_name.message}</div>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
            {form.formState.errors.email ? (
              <div className="text-xs text-red-700">{form.formState.errors.email.message}</div>
            ) : null}
          </div>

          {error ? <div className="rounded border border-red-200 bg-red-50 p-2 text-xs text-red-800">{error}</div> : null}

          <DialogFooter>
            <Button type="submit" disabled={loading}>
              {loading ? "Sending…" : "Submit"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
