"use client";

import * as React from "react";
import { Toast, ToastDescription, ToastProvider, ToastTitle, ToastViewport } from "@/components/ui/toast";

type ToastItem = { id: string; title: string; description?: string };

const ToastContext = React.createContext<{ push: (t: Omit<ToastItem, "id">) => void } | null>(null);

export function useToast() {
  const ctx = React.useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within Toaster");
  return ctx;
}

export function Toaster({ children }: { children: React.ReactNode }) {
  const [items, setItems] = React.useState<ToastItem[]>([]);

  const push = React.useCallback((t: Omit<ToastItem, "id">) => {
    const id = crypto.randomUUID();
    setItems((prev) => [...prev, { id, ...t }]);
    setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), 4000);
  }, []);

  return (
    <ToastProvider swipeDirection="right">
      <ToastContext.Provider value={{ push }}>
        {children}
        <ToastViewport className="fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2 outline-none" />
        {items.map((t) => (
          <Toast key={t.id} open>
            <ToastTitle>{t.title}</ToastTitle>
            {t.description ? <ToastDescription>{t.description}</ToastDescription> : null}
          </Toast>
        ))}
      </ToastContext.Provider>
    </ToastProvider>
  );
}

