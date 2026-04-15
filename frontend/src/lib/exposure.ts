export type ExposureLevel = "LOW" | "MEDIUM" | "HIGH";

export function exposureLevelFromScore(score: number | null | undefined): ExposureLevel | null {
  if (score == null) return null;
  if (score < 34) return "LOW";
  if (score <= 66) return "MEDIUM";
  return "HIGH";
}

