// Codeforces colour bands (rating -> colour), used for difficulty chips.
export function ratingColor(r: number | null) {
  if (r == null) return "#9a95b5";
  if (r < 1200) return "#9ca3af"; if (r < 1400) return "#4ade80"; if (r < 1600) return "#22d3ee";
  if (r < 1900) return "#60a5fa"; if (r < 2100) return "#c084fc"; if (r < 2400) return "#fbbf24"; return "#fb7185";
}
export const BANDS: [number, number, string][] = [[800, 1000, "Warm-up"], [1000, 1300, "Foundation"], [1300, 1600, "Growth"], [1600, 1900, "Specialist"], [1900, 2200, "Expert push"]];
