const moduleClasses: Record<string, string> = {
  spec: "bg-sky-50 text-sky-700 ring-sky-200",
  price: "bg-amber-50 text-amber-800 ring-amber-200",
  logistics: "bg-violet-50 text-violet-700 ring-violet-200",
  quality: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  general: "bg-slate-100 text-slate-700 ring-slate-200",
};

export function moduleClass(moduleName: string | undefined): string {
  if (!moduleName) {
    return "bg-slate-100 text-slate-600 ring-slate-200";
  }

  return moduleClasses[moduleName] ?? "bg-slate-100 text-slate-700 ring-slate-200";
}

export function strategyClass(strategy: string | undefined): string {
  if (!strategy) {
    return "bg-slate-100 text-slate-700 ring-slate-200";
  }

  if (strategy.includes("handoff") || strategy.includes("blocked")) {
    return "bg-red-50 text-red-700 ring-red-200";
  }

  if (strategy.includes("boundary") || strategy.includes("split")) {
    return "bg-orange-50 text-orange-700 ring-orange-200";
  }

  return "bg-emerald-50 text-emerald-700 ring-emerald-200";
}
