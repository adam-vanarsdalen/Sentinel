"use client";

export function InfoTip({ text }: { text: string }) {
  return (
    <span
      className="ml-1 inline-flex h-4 w-4 cursor-help items-center justify-center rounded-full border border-slate-200 bg-white text-[10px] font-semibold text-slate-600"
      title={text}
      aria-label={text}
    >
      i
    </span>
  );
}

