"use client";

import * as React from "react";
import { useRouter } from "next/navigation";

import { useAppConfig } from "@/lib/app-config-context";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const PRESET_COOKIE_NAME = "sentinel_preset";

function formatPresetLabel(name: string, industry: string) {
  const suffix = industry && industry !== "general" ? industry : "shared";
  return `${name} · ${suffix}`;
}

export function PresetSelector({
  label = "Demo Preset",
  compact = false,
}: {
  label?: string;
  compact?: boolean;
}) {
  const router = useRouter();
  const appConfig = useAppConfig();
  const [presetId, setPresetId] = React.useState(appConfig.preset_id);

  React.useEffect(() => {
    setPresetId(appConfig.preset_id);
  }, [appConfig.preset_id]);

  function onChange(nextPresetId: string) {
    setPresetId(nextPresetId);
    document.cookie = `${PRESET_COOKIE_NAME}=${encodeURIComponent(nextPresetId)}; path=/; max-age=31536000; samesite=lax`;
    router.refresh();
  }

  if (appConfig.available_presets.length <= 1) return null;

  return (
    <div className={compact ? "min-w-[210px]" : "space-y-2"}>
      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-slate-500">{label}</div>
      <Select value={presetId} onValueChange={onChange}>
        <SelectTrigger className={compact ? "h-9 bg-white" : "h-10 bg-white"}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {appConfig.available_presets.map((preset) => (
            <SelectItem key={preset.id} value={preset.id}>
              {formatPresetLabel(preset.product_name, preset.industry)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {!compact ? (
        <div className="text-xs leading-5 text-slate-600">
          Switch the visible product framing and terminology without changing the underlying platform.
        </div>
      ) : null}
    </div>
  );
}
