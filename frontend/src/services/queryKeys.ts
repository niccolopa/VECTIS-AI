// Centralized TanStack Query keys — one place to keep cache keys consistent and
// avoid typos across hooks.
export const qk = {
  health: ["health"] as const,
  regions: ["regions"] as const,
  analyses: ["analyses"] as const,
  analysis: (id: string) => ["analyses", id] as const,
  modelCard: (region: string) => ["models", region] as const,
  datasets: ["datasets"] as const,
};
