import "server-only";

import { promises as fs } from "node:fs";
import path from "node:path";
import { cookies } from "next/headers";

import { DEFAULT_APP_CONFIG, type AppConfig } from "./app-config";

const PRESET_FILES = ["manifest", "terminology", "copy", "roles", "risk_taxonomy"] as const;
const DEFAULT_PRESET_ID = "general";
const PRESET_COOKIE_NAME = "sentinel_preset";

function presetsRoot() {
  return path.resolve(process.cwd(), "..", "config", "presets");
}

async function readJson(filePath: string): Promise<Record<string, unknown>> {
  const raw = await fs.readFile(filePath, "utf8");
  const parsed = JSON.parse(raw);
  return parsed && typeof parsed === "object" ? (parsed as Record<string, unknown>) : {};
}

async function listAvailablePresets(root: string): Promise<AppConfig["available_presets"]> {
  try {
    const entries = await fs.readdir(root, { withFileTypes: true });
    const presets: AppConfig["available_presets"] = [];
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const manifest = await readJson(path.join(root, entry.name, "manifest.json"));
      presets.push({
        id: String(manifest.id ?? entry.name),
        name: String(manifest.name ?? entry.name),
        industry: String(manifest.industry ?? entry.name),
        product_name: String(manifest.product_name ?? manifest.name ?? entry.name),
      });
    }
    return presets.sort((a, b) => a.name.localeCompare(b.name));
  } catch {
    return DEFAULT_APP_CONFIG.available_presets;
  }
}

async function readCookiePreset(): Promise<string | null> {
  try {
    return (await cookies()).get(PRESET_COOKIE_NAME)?.value?.trim().toLowerCase() || null;
  } catch {
    return null;
  }
}

export async function loadAppConfig(options?: { presetId?: string | null }): Promise<AppConfig> {
  const root = presetsRoot();
  const requestedPreset = (
    options?.presetId ||
    (await readCookiePreset()) ||
    process.env.NEXT_PUBLIC_SENTINEL_PRESET ||
    process.env.SENTINEL_PRESET ||
    DEFAULT_PRESET_ID
  )
    .trim()
    .toLowerCase();
  const presetDir = path.join(root, requestedPreset);
  const fallbackDir = path.join(root, DEFAULT_PRESET_ID);
  const targetDir = await fs
    .stat(presetDir)
    .then((stat) => (stat.isDirectory() ? presetDir : fallbackDir))
    .catch(() => fallbackDir);

  try {
    const sections = await Promise.all(PRESET_FILES.map(async (section) => [section, await readJson(path.join(targetDir, `${section}.json`))] as const));
    const loaded = Object.fromEntries(sections) as Record<(typeof PRESET_FILES)[number], Record<string, unknown>>;
    const manifest = loaded.manifest;
    return {
      preset_id: String(manifest.id ?? requestedPreset ?? DEFAULT_PRESET_ID),
      available_presets: await listAvailablePresets(root),
      manifest: {
        id: String(manifest.id ?? DEFAULT_PRESET_ID),
        name: String(manifest.name ?? DEFAULT_PRESET_ID),
        industry: String(manifest.industry ?? DEFAULT_PRESET_ID),
        product_name: String(manifest.product_name ?? DEFAULT_APP_CONFIG.product.name),
        console_name: String(manifest.console_name ?? DEFAULT_APP_CONFIG.product.console_name),
        default_policy_template_id: String(manifest.default_policy_template_id ?? DEFAULT_APP_CONFIG.manifest.default_policy_template_id),
        support_email: typeof manifest.support_email === "string" ? manifest.support_email : null,
        demo: typeof manifest.demo === "object" && manifest.demo ? (manifest.demo as Record<string, unknown>) : {},
      },
      product: {
        name: String(manifest.product_name ?? DEFAULT_APP_CONFIG.product.name),
        console_name: String(manifest.console_name ?? DEFAULT_APP_CONFIG.product.console_name),
        support_email: typeof manifest.support_email === "string" ? manifest.support_email : null,
      },
      terminology: {
        ...DEFAULT_APP_CONFIG.terminology,
        ...(loaded.terminology as AppConfig["terminology"]),
        workflow: {
          ...DEFAULT_APP_CONFIG.terminology.workflow,
          ...((loaded.terminology.workflow as AppConfig["terminology"]["workflow"]) ?? {}),
        },
        messages: {
          ...DEFAULT_APP_CONFIG.terminology.messages,
          ...((loaded.terminology.messages as AppConfig["terminology"]["messages"]) ?? {}),
        },
      },
      copy: {
        ...DEFAULT_APP_CONFIG.copy,
        ...(loaded.copy as AppConfig["copy"]),
      },
      roles: {
        ...DEFAULT_APP_CONFIG.roles,
        ...(loaded.roles as AppConfig["roles"]),
      },
      risk_taxonomy: {
        shared_categories: Array.isArray(loaded.risk_taxonomy.shared_categories)
          ? (loaded.risk_taxonomy.shared_categories as AppConfig["risk_taxonomy"]["shared_categories"])
          : DEFAULT_APP_CONFIG.risk_taxonomy.shared_categories,
        preset_categories: Array.isArray(loaded.risk_taxonomy.preset_categories)
          ? (loaded.risk_taxonomy.preset_categories as AppConfig["risk_taxonomy"]["preset_categories"])
          : DEFAULT_APP_CONFIG.risk_taxonomy.preset_categories,
      },
    };
  } catch {
    return DEFAULT_APP_CONFIG;
  }
}
