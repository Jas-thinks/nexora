import { EXTRA_ALGOS } from "./viz2";

// Algorithm visualisation engine. Every algorithm is a pure function returning the real
// sequence of states it passes through, so the animation is the algorithm — not a canned GIF.

export type Cell = { v: number | string; tone?: "idle" | "active" | "compare" | "done" | "found" | "wall" | "path" };

export type Aux = { name: string; value: string };
export type GNode = { id: string; x: number; y: number; tone: NonNullable<Cell["tone"]>; label?: string };
export type GEdge = { a: string; b: string; w: number; tone: NonNullable<Cell["tone"]> };

export type Frame =
  | { kind: "graph"; nodes: GNode[]; edges: GEdge[]; aux: Aux[]; line: number; note: string; directed?: boolean; hideW?: boolean }
  | { kind: "array"; cells: Cell[]; pointers: Record<string, number>; line: number; note: string; aux?: Aux[] }
  | { kind: "grid"; cells: Cell[][]; line: number; note: string; queue?: string }
  | { kind: "table"; rows: string[]; cols: string[]; cells: Cell[][]; line: number; note: string };

export interface Algo {
  id: string;
  title: string;
  blurb: string;
  complexity: string;
  code: string[];
  invariant: string;
  run: () => Frame[];
  // optional custom input: parse+validate user text, return frames or throw Error(message)
  input?: { hint: string; default: string; run: (text: string) => Frame[] };
}

const nums = (t: string, max = 16): number[] => {
  const a = t.split(/[\s,]+/).filter(Boolean).map(Number);
  if (!a.length || a.some((x) => !Number.isFinite(x) || !Number.isInteger(x) || Math.abs(x) > 999)) throw new Error("Enter integers between -999 and 999, separated by commas.");
  if (a.length > max) throw new Error(`At most ${max} values.`);
  return a;
};

const arr = (a: number[], tone: Record<number, Cell["tone"]> = {}): Cell[] =>
  a.map((v, i) => ({ v, tone: tone[i] ?? "idle" }));

export function binarySearch(a: number[], target: number): Frame[] {
  const f: Frame[] = [];
  let lo = 0, hi = a.length - 1;
  f.push({ kind: "array", cells: arr(a), pointers: { lo, hi }, line: 0, note: `Search ${target} in a sorted array. Maintain the interval [lo, hi] that could still contain it.` });
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    const tones: Record<number, Cell["tone"]> = {};
    for (let i = 0; i < a.length; i++) if (i < lo || i > hi) tones[i] = "done";
    tones[mid] = "compare";
    f.push({ kind: "array", cells: arr(a, tones), pointers: { lo, mid, hi }, line: 2, note: `mid = ${mid}; a[mid] = ${a[mid]}. Compare with ${target}.` });
    if (a[mid] === target) {
      f.push({ kind: "array", cells: arr(a, { [mid]: "found" }), pointers: { mid }, line: 3, note: `Found ${target} at index ${mid}. Each step halved the interval: O(log n).` });
      return f;
    }
    if (a[mid] < target) { lo = mid + 1; f.push({ kind: "array", cells: arr(a, tones), pointers: { lo, mid, hi }, line: 4, note: `${a[mid]} < ${target}: everything left of mid is too small. lo = mid + 1 = ${lo}.` }); }
    else { hi = mid - 1; f.push({ kind: "array", cells: arr(a, tones), pointers: { lo, mid, hi }, line: 5, note: `${a[mid]} > ${target}: everything right of mid is too large. hi = mid - 1 = ${hi}.` }); }
  }
  f.push({ kind: "array", cells: arr(a), pointers: {}, line: 6, note: `Interval is empty: ${target} is not present.` });
  return f;
}

export function quickSort(input: number[]): Frame[] {
  const a = [...input], f: Frame[] = [];
  const snap = (tones: Record<number, Cell["tone"]>, ptr: Record<string, number>, line: number, note: string) =>
    f.push({ kind: "array", cells: arr(a, tones), pointers: ptr, line, note });
  const sorted = new Set<number>();
  const base = () => Object.fromEntries([...sorted].map((i) => [i, "found" as const]));
  const qs = (l: number, r: number) => {
    if (l > r) return;
    if (l === r) { sorted.add(l); return; }
    const p = a[r];
    snap({ ...base(), [r]: "compare" }, { l, r }, 1, `Partition [${l}..${r}] around pivot ${p} (last element).`);
    let i = l;
    for (let j = l; j < r; j++) {
      snap({ ...base(), [r]: "compare", [j]: "active", [i]: "active" }, { i, j, pivot: r }, 3, `a[${j}] = ${a[j]} ${a[j] < p ? "<" : ">="} pivot ${p}${a[j] < p ? ": move into the 'smaller' zone." : ": leave it on the right."}`);
      if (a[j] < p) { [a[i], a[j]] = [a[j], a[i]]; i++; }
    }
    [a[i], a[r]] = [a[r], a[i]];
    sorted.add(i);
    snap({ ...base() }, { pivot: i }, 5, `Pivot ${p} lands at its final index ${i}: smaller values are left, larger are right.`);
    qs(l, i - 1); qs(i + 1, r);
  };
  snap({}, {}, 0, "Quick sort: pick a pivot, partition, recurse on both sides. Average O(n log n).");
  qs(0, a.length - 1);
  snap(Object.fromEntries(a.map((_, i) => [i, "found" as const])), {}, 6, "Sorted.");
  return f;
}

export function bfsGrid(maze: string[]): Frame[] {
  const R = maze.length, C = maze[0].length, f: Frame[] = [];
  let s: [number, number] = [0, 0], t: [number, number] = [0, 0];
  maze.forEach((row, r) => [...row].forEach((ch, c) => { if (ch === "S") s = [r, c]; if (ch === "T") t = [r, c]; }));
  const tone: Cell["tone"][][] = maze.map((row) => [...row].map((ch) => (ch === "#" ? "wall" : "idle")));
  const dist = maze.map((row) => [...row].map(() => -1));
  const prev: Record<string, [number, number]> = {};
  const draw = (line: number, note: string, q: [number, number][]) =>
    f.push({ kind: "grid", cells: tone.map((row, r) => row.map((tn, c) => ({ v: dist[r][c] >= 0 ? dist[r][c] : maze[r][c] === "S" ? "S" : maze[r][c] === "T" ? "T" : "", tone: tn }))), line, note, queue: q.map(([r, c]) => `(${r},${c})`).join(" ") });
  const q: [number, number][] = [s]; dist[s[0]][s[1]] = 0; tone[s[0]][s[1]] = "active";
  draw(0, "BFS explores cells in rings of increasing distance, so the first time it reaches T is a shortest path.", q);
  let head = 0;
  while (head < q.length) {
    const [r, c] = q[head++];
    tone[r][c] = "compare";
    draw(3, `Pop (${r},${c}) at distance ${dist[r][c]}. Try its 4 neighbours.`, q.slice(head));
    if (r === t[0] && c === t[1]) break;
    for (const [dr, dc] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
      const nr = r + dr, nc = c + dc;
      if (nr < 0 || nc < 0 || nr >= R || nc >= C || maze[nr][nc] === "#" || dist[nr][nc] >= 0) continue;
      dist[nr][nc] = dist[r][c] + 1; prev[`${nr},${nc}`] = [r, c]; tone[nr][nc] = "active"; q.push([nr, nc]);
    }
    tone[r][c] = "done";
    draw(6, `Unvisited neighbours get distance ${dist[r][c] + 1} and join the queue.`, q.slice(head));
  }
  if (dist[t[0]][t[1]] < 0) { draw(7, "Queue emptied without reaching T: no path.", []); return f; }
  let cur: [number, number] | undefined = t;
  while (cur) { tone[cur[0]][cur[1]] = "path"; cur = prev[`${cur[0]},${cur[1]}`]; }
  draw(8, `Shortest path length = ${dist[t[0]][t[1]]}. Walk the parent links back from T.`, []);
  return f;
}

export function lcs(a: string, b: string): Frame[] {
  const n = a.length, m = b.length, f: Frame[] = [];
  const dp = Array.from({ length: n + 1 }, () => Array<number | null>(m + 1).fill(null));
  for (let i = 0; i <= n; i++) dp[i][0] = 0;
  for (let j = 0; j <= m; j++) dp[0][j] = 0;
  const rows = ["∅", ...a], cols = ["∅", ...b];
  const draw = (tones: Record<string, Cell["tone"]>, line: number, note: string) =>
    f.push({ kind: "table", rows, cols, line, note, cells: dp.map((row, i) => row.map((v, j) => ({ v: v ?? "", tone: tones[`${i},${j}`] ?? (v === null ? "idle" : "done") }))) });
  draw({}, 0, `dp[i][j] = length of the LCS of the first i letters of "${a}" and first j letters of "${b}". Row/column 0 are empty prefixes = 0.`);
  for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
    if (a[i - 1] === b[j - 1]) {
      dp[i][j] = (dp[i - 1][j - 1] as number) + 1;
      draw({ [`${i},${j}`]: "found", [`${i - 1},${j - 1}`]: "compare" }, 3, `'${a[i - 1]}' = '${b[j - 1]}': extend the best answer from the diagonal: ${dp[i - 1][j - 1]} + 1 = ${dp[i][j]}.`);
    } else {
      dp[i][j] = Math.max(dp[i - 1][j] as number, dp[i][j - 1] as number);
      draw({ [`${i},${j}`]: "active", [`${i - 1},${j}`]: "compare", [`${i},${j - 1}`]: "compare" }, 5, `'${a[i - 1]}' ≠ '${b[j - 1]}': take the better of skipping a letter from either string: max(${dp[i - 1][j]}, ${dp[i][j - 1]}) = ${dp[i][j]}.`);
    }
  }
  draw({ [`${n},${m}`]: "found" }, 6, `LCS length = ${dp[n][m]}. Time and space O(n·m).`);
  return f;
}

export type WGraph = { n: number; pos: [number, number][]; edges: [number, number, number][] };
export const DEMO_GRAPH: WGraph = { n: 6, pos: [[60, 140], [170, 50], [170, 230], [310, 50], [310, 230], [430, 140]],
  edges: [[0, 1, 7], [0, 2, 9], [0, 5, 14], [1, 2, 10], [1, 3, 15], [2, 3, 11], [2, 5, 2], [3, 4, 6], [4, 5, 9]] };
const NAME = (i: number) => String.fromCharCode(65 + i);

/** Dijkstra with an explicit binary-heap-free PQ (sorted array) so every pop/relax is visible and deterministic. */
export function dijkstra(g: WGraph, src = 0): Frame[] {
  const f: Frame[] = [], INF = Infinity;
  const dist = Array(g.n).fill(INF), parent = Array(g.n).fill(-1), done = Array(g.n).fill(false);
  const adj: [number, number][][] = Array.from({ length: g.n }, () => []);
  g.edges.forEach(([a, b, w]) => { adj[a].push([b, w]); adj[b].push([a, w]); });
  const eTone: Record<string, GEdge["tone"]> = {};
  const key = (a: number, b: number) => (a < b ? `${a}-${b}` : `${b}-${a}`);
  dist[src] = 0;
  let pq: [number, number][] = [[0, src]];
  let cur = -1, relaxTo = -1;
  const show = (line: number, note: string) => f.push({ kind: "graph", line, note,
    nodes: g.pos.map(([x, y], i) => ({ id: NAME(i), x, y, label: dist[i] === INF ? "∞" : String(dist[i]), tone: i === cur ? "compare" : i === relaxTo ? "active" : done[i] ? "found" : dist[i] < INF ? "active" : "idle" })),
    edges: g.edges.map(([a, b, w]) => ({ a: NAME(a), b: NAME(b), w, tone: eTone[key(a, b)] ?? "idle" })),
    aux: [{ name: "dist", value: dist.map((d, i) => `${NAME(i)}=${d === INF ? "∞" : d}`).join("  ") }, { name: "parent", value: parent.map((p, i) => `${NAME(i)}←${p < 0 ? "–" : NAME(p)}`).join("  ") },
      { name: "priority queue (dist,node)", value: pq.length ? pq.map(([d, v]) => `(${d},${NAME(v)})`).join(" ") : "∅" }] });
  show(0, `Distances start at ∞ except the source ${NAME(src)} = 0. The priority queue always yields the closest unfinished node.`);
  while (pq.length) {
    pq.sort((x, y) => x[0] - y[0] || x[1] - y[1]);
    const [d, u] = pq.shift()!;
    if (done[u] || d > dist[u]) { cur = -1; show(3, `Pop (${d},${NAME(u)}): stale entry (a shorter path to ${NAME(u)} was already finalised). Skip.`); continue; }
    cur = u; relaxTo = -1; done[u] = true;
    show(4, `Pop ${NAME(u)} with distance ${d}. Its distance is now final, because every edge weight is non-negative.`);
    for (const [v, w] of adj[u]) {
      if (done[v]) continue;
      relaxTo = v;
      if (dist[u] + w < dist[v]) {
        const old = dist[v]; dist[v] = dist[u] + w; parent[v] = u; pq.push([dist[v], v]);
        Object.keys(eTone).forEach((k) => { if (eTone[k] === "path") delete eTone[k]; });
        eTone[key(u, v)] = "path";
        show(7, `Relax ${NAME(u)}→${NAME(v)} (w=${w}): ${dist[u]} + ${w} = ${dist[v]} < ${old === INF ? "∞" : old}. Update dist[${NAME(v)}], set parent = ${NAME(u)}, push to the queue.`);
      } else {
        show(7, `Relax ${NAME(u)}→${NAME(v)} (w=${w}): ${dist[u]} + ${w} = ${dist[u] + w} ≥ ${dist[v]}. No improvement.`);
      }
    }
    relaxTo = -1; cur = -1;
  }
  g.edges.forEach(([a, b]) => { eTone[key(a, b)] = "idle"; });
  for (let v = 0; v < g.n; v++) if (parent[v] >= 0) eTone[key(parent[v], v)] = "path";
  show(9, "Queue empty. The highlighted edges form the shortest-path tree; follow parents back from any node to recover its path.");
  return f;
}
export const dijkstraDistances = (g: WGraph, src = 0): number[] => {
  const last = dijkstra(g, src).at(-1)!;
  return last.kind === "graph" ? last.aux[0].value.split(/\s+/).filter(Boolean).map((t) => (t.split("=")[1] === "∞" ? Infinity : Number(t.split("=")[1]))) : [];
};

export function knapsack(weights: number[], values: number[], cap: number): Frame[] {
  const n = weights.length, f: Frame[] = [];
  const dp = Array.from({ length: n + 1 }, () => Array<number | null>(cap + 1).fill(null));
  for (let j = 0; j <= cap; j++) dp[0][j] = 0;
  const rows = ["∅", ...weights.map((w, i) => `#${i + 1} (w${w},v${values[i]})`)], cols = Array.from({ length: cap + 1 }, (_, j) => String(j));
  const draw = (t: Record<string, Cell["tone"]>, line: number, note: string) => f.push({ kind: "table", rows, cols, line, note, cells: dp.map((r, i) => r.map((v, j) => ({ v: v ?? "", tone: t[`${i},${j}`] ?? (v === null ? "idle" : "done") }))) });
  draw({}, 0, "dp[i][c] = best value using the first i items with capacity c. Row 0: no items, value 0.");
  for (let i = 1; i <= n; i++) for (let c = 0; c <= cap; c++) {
    const skip = dp[i - 1][c] as number;
    if (weights[i - 1] <= c) {
      const take = (dp[i - 1][c - weights[i - 1]] as number) + values[i - 1];
      dp[i][c] = Math.max(skip, take);
      draw({ [`${i},${c}`]: take > skip ? "found" : "active", [`${i - 1},${c}`]: "compare", [`${i - 1},${c - weights[i - 1]}`]: "compare" }, 4,
        `Item ${i} fits (w=${weights[i - 1]} ≤ ${c}). Skip = ${skip}; take = dp[${i - 1}][${c - weights[i - 1]}] + ${values[i - 1]} = ${take}. Keep the larger: ${dp[i][c]}.`);
    } else {
      dp[i][c] = skip;
      draw({ [`${i},${c}`]: "active", [`${i - 1},${c}`]: "compare" }, 2, `Item ${i} (w=${weights[i - 1]}) does not fit capacity ${c}: copy dp[${i - 1}][${c}] = ${skip}.`);
    }
  }
  draw({ [`${n},${cap}`]: "found" }, 6, `Best total value = ${dp[n][cap]}. Time and space O(n·W); space can drop to O(W) by iterating capacity downward.`);
  return f;
}

export function slidingWindowMax(a: number[], k: number): Frame[] {
  const f: Frame[] = [];
  let sum = a.slice(0, k).reduce((x, y) => x + y, 0), best = sum, bestAt = 0;
  const snap = (i: number, line: number, note: string) => f.push({ kind: "array", line, note, pointers: { l: i, r: i + k - 1 },
    cells: a.map((v, j) => ({ v, tone: j >= i && j < i + k ? (i === bestAt ? "found" : "active") : "idle" })) });
  snap(0, 1, `Window of size ${k}: sum of the first ${k} elements = ${sum}. Slide it by adding the new element and removing the old one: O(1) per step.`);
  for (let i = 1; i + k <= a.length; i++) {
    sum += a[i + k - 1] - a[i - 1];
    if (sum > best) { best = sum; bestAt = i; }
    snap(i, 3, `Slide to [${i}..${i + k - 1}]: + a[${i + k - 1}] (${a[i + k - 1]}) − a[${i - 1}] (${a[i - 1]}) = ${sum}. Best so far ${best} at index ${bestAt}.`);
  }
  f.push({ kind: "array", line: 5, note: `Maximum window sum = ${best}, window starting at index ${bestAt}. One pass: O(n).`, pointers: { l: bestAt, r: bestAt + k - 1 },
    cells: a.map((v, j) => ({ v, tone: j >= bestAt && j < bestAt + k ? "found" : "idle" })) });
  return f;
}

export const ALGOS: Algo[] = [...([
  { id: "binary-search", title: "Binary Search", blurb: "Halve the search space using monotonicity.", complexity: "O(log n)",
    code: ["lo, hi = 0, n - 1", "while lo <= hi:", "    mid = (lo + hi) // 2", "    if a[mid] == x: return mid", "    elif a[mid] < x: lo = mid + 1", "    else: hi = mid - 1", "return -1"],
    invariant: "If the target exists, it is always inside [lo, hi]. Each step discards the half that cannot contain it.",
    run: () => binarySearch([2, 5, 8, 12, 16, 23, 38, 45, 56, 72, 91], 91),
    input: { hint: "sorted numbers | target   e.g. 1,3,5,7,9 | 7", default: "2,5,8,12,16,23,38,45,56,72,91 | 91", run: (t) => { const [l, r] = t.split("|"); const a = nums(l); if (r === undefined) throw new Error("Add '| target'."); if (a.some((x, i) => i && x < a[i - 1])) throw new Error("Array must be sorted ascending."); return binarySearch(a, nums(r, 1)[0]); } } },
  { id: "quick-sort", title: "Quick Sort", blurb: "Partition around a pivot, recurse.", complexity: "O(n log n) avg",
    code: ["def qs(l, r):", "    pivot = a[r]; i = l", "    for j in range(l, r):", "        if a[j] < pivot: swap(a[i], a[j]); i += 1", "    swap(a[i], a[r])", "    # pivot now final", "    qs(l, i-1); qs(i+1, r)"],
    invariant: "After partitioning, the pivot sits at its final sorted index: everything left is smaller, everything right is not.",
    run: () => quickSort([7, 2, 9, 4, 1, 8, 3, 6, 5]),
    input: { hint: "numbers   e.g. 5,2,9,1", default: "7,2,9,4,1,8,3,6,5", run: (t) => quickSort(nums(t, 14)) } },
  { id: "bfs", title: "BFS Shortest Path", blurb: "Rings of distance on a grid.", complexity: "O(V + E)",
    code: ["q = [S]; dist[S] = 0", "while q:", "    cell = q.popleft()", "    if cell == T: break", "    for nb in neighbours(cell):", "        if unvisited(nb):", "            dist[nb] = dist[cell] + 1; q.append(nb)", "if dist[T] < 0: no path", "path = walk parents from T"],
    invariant: "Cells leave the queue in non-decreasing distance order, so the first arrival at T is a shortest path.",
    run: () => bfsGrid(["S..#....", ".#.#.##.", ".#...#..", ".####.#.", "......#T"]) },
  { id: "lcs", title: "Longest Common Subsequence", blurb: "A 2-D DP table filled cell by cell.", complexity: "O(n·m)",
    code: ["dp[i][0] = dp[0][j] = 0", "for i in 1..n:", "  for j in 1..m:", "    if a[i-1] == b[j-1]:", "        dp[i][j] = dp[i-1][j-1] + 1", "    else:", "        dp[i][j] = max(dp[i-1][j], dp[i][j-1])", "return dp[n][m]"],
    invariant: "dp[i][j] is the optimal answer for the prefixes a[0..i) and b[0..j); each cell depends only on three earlier cells.",
    run: () => lcs("AGGTAB", "GXTXAYB"),
    input: { hint: "two strings | separated   e.g. ABCBDAB | BDCABA", default: "AGGTAB | GXTXAYB", run: (t) => { const [a, b] = t.split("|").map((x) => x.trim()); if (!a || !b) throw new Error("Enter two non-empty strings separated by |."); if (a.length > 10 || b.length > 10) throw new Error("At most 10 characters each."); return lcs(a, b); } } },
  { id: "dijkstra", title: "Dijkstra", blurb: "Shortest paths with a priority queue.", complexity: "O((V+E) log V)",
    code: ["dist[src] = 0; pq = [(0, src)]", "while pq:", "    d, u = pq.pop_min()", "    if d > dist[u]: continue  # stale", "    finalise u", "    for (v, w) in adj[u]:", "        # relax edge u->v", "        if dist[u] + w < dist[v]:", "            dist[v] = dist[u] + w; parent[v] = u; pq.push((dist[v], v))", "return dist, parent"],
    invariant: "When a node is popped its distance is final (non-negative weights): any other route to it must pass through an unfinished node that is at least as far.",
    run: () => dijkstra(DEMO_GRAPH) },
  { id: "knapsack", title: "0/1 Knapsack", blurb: "Take-or-skip DP over items and capacity.", complexity: "O(n·W)",
    code: ["dp[0][c] = 0 for all c", "for i in 1..n:", "  for c in 0..W:", "    if w[i] > c: dp[i][c] = dp[i-1][c]", "    else: dp[i][c] = max(dp[i-1][c], dp[i-1][c-w[i]] + v[i])", "", "return dp[n][W]"],
    invariant: "dp[i][c] is the best value using only the first i items within capacity c, so each item is used at most once.",
    run: () => knapsack([2, 3, 4, 5], [3, 4, 5, 6], 8),
    input: { hint: "weights | values | capacity   e.g. 2,3,4 | 3,4,5 | 7", default: "2,3,4,5 | 3,4,5,6 | 8", run: (t) => { const [w, v, c] = t.split("|"); if (c === undefined) throw new Error("Format: weights | values | capacity"); const W = nums(w, 6), V = nums(v, 6), C = nums(c, 1)[0]; if (W.length !== V.length) throw new Error("Weights and values need the same count."); if (W.some((x) => x < 1) || C < 1 || C > 15) throw new Error("Weights ≥ 1, capacity 1..15."); return knapsack(W, V, C); } } },
  { id: "sliding-window", title: "Sliding Window (max sum)", blurb: "Reuse the previous window's work.", complexity: "O(n)",
    code: ["sum = sum(a[0:k]); best = sum", "for i in 1..n-k:", "    sum += a[i+k-1] - a[i-1]", "    best = max(best, sum)", "", "return best"],
    invariant: "`sum` always equals the sum of the current window, so each step needs one add and one subtract instead of k additions.",
    run: () => slidingWindowMax([2, 1, 5, 1, 3, 2, 9, 1, 4], 3),
    input: { hint: "numbers | k   e.g. 2,1,5,1,3 | 3", default: "2,1,5,1,3,2,9,1,4 | 3", run: (t) => { const [a, k] = t.split("|"); const arr = nums(a, 16); if (k === undefined) throw new Error("Add '| k'."); const K = nums(k, 1)[0]; if (K < 1 || K > arr.length) throw new Error("k must be between 1 and the array length."); return slidingWindowMax(arr, K); } } },
] as Algo[]), ...EXTRA_ALGOS];
