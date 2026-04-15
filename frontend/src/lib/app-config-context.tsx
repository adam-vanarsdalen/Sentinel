"use client";

import * as React from "react";

import { DEFAULT_APP_CONFIG, type AppConfig } from "./app-config";

const AppConfigContext = React.createContext<AppConfig>(DEFAULT_APP_CONFIG);

export function AppConfigProvider({ value, children }: { value: AppConfig; children: React.ReactNode }) {
  return <AppConfigContext.Provider value={value}>{children}</AppConfigContext.Provider>;
}

export function useAppConfig() {
  return React.useContext(AppConfigContext);
}
