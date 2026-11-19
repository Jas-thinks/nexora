// More visualisations. Same contract as viz.ts: every algorithm returns the real sequence of states it passes through.
import type { Algo, Cell, Frame, GEdge, GNode } from "./viz";

type Tone = NonNullable<Cell["tone"]>;
const nums = (t: string, max = 12): number[] => {
  const a = t.split(/[\s,]+/).filter(Boolean).map(Number);
  if (!a.length || a.some((x) => !Number.isInteger(x) || Math.abs(x) > 999)) throw new Error("Enter integers between -999 and 999, separated by commas.");
  if (a.length > max) throw new Error(`At most ${max} values.`);
  return a;
};
const arr = (a: number[], t: Record<number, Tone> = {}): Cell[] => a.map((v, i) => ({ v, tone: t[i] ?? "idle" }));

// ------------------------------------------------------------------ binary search on the answer (monotonic predicate)
export function daysNeeded(w: number[], cap: number): number { let d = 1, cur = 0; for (const x of w) { if (cur + x > cap) { d++; cur = 0; } cur += x; } return d; }
export function shipBinaryAnswer(w: number[], days: number): Frame[] {
  const f: Frame[] = []; let lo = Math.max(...w), hi = w.reduce((a, b) => a + b, 0);
  const show = (line: number, note: string, ptr: Record<string, number>, aux: { name: string; value: string }[], tones: Record<number, Tone> = {}) => f.push({ kind: "array", cells: arr(w, tones), pointers: ptr, line, note, aux });
  show(0, `Minimise the capacity so all packages ship within ${days} days. The answer lies in [max(w)=${lo}, sum(w)=${hi}]. feasible(cap) = "can we ship in ≤ ${days} days?" is monotone: bigger capacity never hurts.`, {}, [{ name: "lo / hi", value: `${lo} / ${hi}` }]);
  while (lo < hi) {
    const mid = (lo + hi) >> 1, d = daysNeeded(w, mid);
    let cur = 0, day = 1; const tones: Record<number, Tone> = {};
    w.forEach((x, i) => { if (cur + x > mid) { day++; cur = 0; } cur += x; tones[i] = day % 2 ? "active" : "compare"; });
    show(2, `mid = ${mid}. Greedy check: pack in order, start a new day when the next package does not fit → needs ${d} day(s). feasible(${mid}) = ${d <= days}.`, {}, [{ name: "lo / mid / hi", value: `${lo} / ${mid} / ${hi}` }, { name: "days needed", value: String(d) }], tones);
    if (d <= days) { hi = mid; show(4, `feasible → the answer is ≤ ${mid}. hi = mid = ${hi}.`, {}, [{ name: "lo / hi", value: `${lo} / ${hi}` }]); }
    else { lo = mid + 1; show(5, `not feasible → the answer is > ${mid}. lo = mid + 1 = ${lo}.`, {}, [{ name: "lo / hi", value: `${lo} / ${hi}` }]); }
  }
  show(6, `lo = hi = ${lo}: the smallest feasible capacity is ${lo}. Each step halved the search space over a monotone predicate: O(n log(sum)).`, {}, [{ name: "answer", value: String(lo) }]);
  return f;
}

// ------------------------------------------------------------------ DSU
export function dsu(n: number, ops: ([string, number, number?])[]): { frames: Frame[]; components: number } {
  const p = Array.from({ length: n }, (_, i) => i), sz = Array(n).fill(1), f: Frame[] = [];
  const pos = (i: number) => ({ x: 245 + 190 * Math.cos((2 * Math.PI * i) / n - Math.PI / 2), y: 140 + 105 * Math.sin((2 * Math.PI * i) / n - Math.PI / 2) });
  const snap = (line: number, note: string, hot: number[] = [], rootsTone: Tone = "found") => f.push({ kind: "graph", directed: true, hideW: true, line, note,
    nodes: p.map((_, i) => ({ id: String(i), ...pos(i), label: p[i] === i ? `size ${sz[i]}` : "", tone: hot.includes(i) ? "compare" : p[i] === i ? rootsTone : "idle" })),
    edges: p.flatMap((q, i) => (q === i ? [] : [{ a: String(i), b: String(q), w: 0, tone: "path" as Tone }])), aux: [{ name: "parent", value: p.join(" ") }, { name: "size", value: sz.join(" ") }] });
  const find = (x: number, log: boolean): number => { const path = [x]; while (p[x] !== x) { x = p[x]; path.push(x); } for (const y of path) p[y] = x; if (log) snap(1, `find(${path[0]}) walks to root ${x}; path compression points every node on the path directly at the root.`, path); return x; };
  snap(0, `${n} singleton sets: every node is its own root. Edges point child → parent.`);
  for (const [op, a, b] of ops) {
    if (op === "find") { find(a, true); continue; }
    const ra = find(a, false), rb = find(b!, false);
    if (ra === rb) { snap(4, `union(${a},${b}): same root ${ra} → already connected, nothing to do.`, [a, b!]); continue; }
    const [big, small] = sz[ra] >= sz[rb] ? [ra, rb] : [rb, ra]; p[small] = big; sz[big] += sz[small];
    snap(5, `union(${a},${b}): roots ${ra} and ${rb}. Attach the smaller tree (root ${small}) under the larger (root ${big}) so trees stay shallow.`, [small, big]);
  }
  return { frames: f, components: p.filter((q, i) => q === i).length };
}

// ------------------------------------------------------------------ tree layout helper (in-order x, depth y)
type TNode = { v: number; l: TNode | null; r: TNode | null };
function layoutTree(root: TNode | null, hot: Record<number, Tone> = {}): { nodes: GNode[]; edges: GEdge[] } {
  const nodes: GNode[] = [], edges: GEdge[] = []; let xi = 0, maxD = 0;
  const count = (t: TNode | null): number => (t ? count(t.l) + 1 + count(t.r) : 0), total = Math.max(1, count(root));
  const go = (t: TNode | null, d: number): void => { if (!t) return; go(t.l, d + 1); const x = 35 + (xi++ * 420) / Math.max(1, total - 1 || 1); maxD = Math.max(maxD, d); nodes.push({ id: String(t.v), x: total === 1 ? 245 : x, y: 30 + d * 58, tone: hot[t.v] ?? "idle", label: "" }); go(t.r, d + 1);
    if (t.l) edges.push({ a: String(t.v), b: String(t.l.v), w: 0, tone: "idle" }); if (t.r) edges.push({ a: String(t.v), b: String(t.r.v), w: 0, tone: "idle" }); };
  go(root, 0); return { nodes, edges };
}
const ins = (t: TNode | null, v: number): TNode => { if (!t) return { v, l: null, r: null }; if (v < t.v) t.l = ins(t.l, v); else if (v > t.v) t.r = ins(t.r, v); return t; };
export const inorder = (t: TNode | null): number[] => (t ? [...inorder(t.l), t.v, ...inorder(t.r)] : []);

export function bst(values: number[], find: number): { frames: Frame[]; root: TNode | null } {
  const f: Frame[] = []; let root: TNode | null = null;
  const snap = (line: number, note: string, hot: Record<number, Tone>) => { const { nodes, edges } = layoutTree(root, hot); f.push({ kind: "graph", hideW: true, nodes: nodes.map((n) => ({ ...n, label: "" })), edges, aux: [{ name: "in-order", value: inorder(root).join(" ") }], line, note }); };
  for (const v of values) {
    if (!root) { root = ins(root, v); snap(0, `Insert ${v}: the tree is empty, so it becomes the root.`, { [v]: "found" }); continue; }
    const path: number[] = []; let c: TNode | null = root;
    while (c) { path.push(c.v); if (v === c.v) break; c = v < c.v ? c.l : c.r; }
    root = ins(root, v);
    snap(1, `Insert ${v}: compare down the path ${path.join(" → ")} (smaller goes left, larger right)${path.includes(v) ? "; already present, ignored" : `, then attach as a new leaf`}.`, Object.fromEntries([...path.map((x) => [x, "compare"]), [v, "found"]]));
  }
  let c: TNode | null = root; const path: number[] = [];
  while (c) { path.push(c.v); if (c.v === find) break; c = find < c.v ? c.l : c.r; }
  const hit = path[path.length - 1] === find;
  snap(3, `Search ${find}: follow ${path.join(" → ")}. ${hit ? "Found." : "Reached a missing child: not present."} Cost = path length ≈ height (O(log n) if balanced, O(n) if degenerate).`, Object.fromEntries(path.map((x) => [x, hit && x === find ? "found" : "compare"])));
  return { frames: f, root };
}

// ------------------------------------------------------------------ min-heap
export function heap(values: number[], pops: number): { frames: Frame[]; popped: number[] } {
  const h: number[] = [], f: Frame[] = [], popped: number[] = [];
  const treeOf = (hot: number[]) => { const nodes: GNode[] = h.map((v, i) => { const d = Math.floor(Math.log2(i + 1)), idx = i - (2 ** d - 1), cnt = 2 ** d; return { id: String(i), x: 245 + ((idx + 0.5) / cnt - 0.5) * 440, y: 30 + d * 62, label: String(v), tone: hot.includes(i) ? "compare" : "idle" } as GNode; });
    return { nodes, edges: h.flatMap((_, i) => (i ? [{ a: String(Math.floor((i - 1) / 2)), b: String(i), w: 0, tone: "idle" as Tone }] : [])) }; };
  const snap = (line: number, note: string, hot: number[] = []) => f.push({ kind: "graph", hideW: true, ...treeOf(hot), aux: [{ name: "array", value: h.join(" ") || "∅" }, { name: "popped", value: popped.join(" ") || "—" }], line, note });
  for (const v of values) {
    h.push(v); let i = h.length - 1; snap(0, `push(${v}): append at index ${i} (keeps the tree complete), then sift up while smaller than its parent.`, [i]);
    while (i > 0 && h[(i - 1) >> 1] > h[i]) { const q = (i - 1) >> 1; [h[q], h[i]] = [h[i], h[q]]; i = q; snap(1, `Swap with parent: ${h[i]} is smaller than ${h[(i << 1) + 1] ?? h[(i << 1) + 2] ?? "its child"}; sift up to index ${i}.`, [i]); }
  }
  for (let k = 0; k < pops && h.length; k++) {
    const top = h[0]; popped.push(top); const last = h.pop()!;
    if (h.length) { h[0] = last; snap(2, `pop() returns the minimum ${top}. Move the last element (${last}) to the root and sift down.`, [0]); let i = 0;
      for (;;) { let m = i; const l = 2 * i + 1, r = l + 1; if (l < h.length && h[l] < h[m]) m = l; if (r < h.length && h[r] < h[m]) m = r; if (m === i) break; [h[i], h[m]] = [h[m], h[i]]; i = m; snap(3, `Swap with the smaller child; continue sifting down from index ${i}.`, [i]); } }
    else snap(2, `pop() returns ${top}; the heap is now empty.`);
  }
  return { frames: f, popped };
}

// ------------------------------------------------------------------ merge sort
export function mergeSort(input: number[]): Frame[] {
  const a = [...input], f: Frame[] = [];
  const snap = (line: number, note: string, t: Record<number, Tone>, ptr: Record<string, number> = {}) => f.push({ kind: "array", cells: arr(a, t), pointers: ptr, line, note });
  snap(0, "Merge sort: split in half, sort each half recursively, merge the two sorted halves. Always O(n log n).", {});
  const rec = (l: number, r: number) => {
    if (r - l <= 1) return; const m = (l + r) >> 1; rec(l, m); rec(m, r);
    const L = a.slice(l, m), R = a.slice(m, r); let i = 0, j = 0, k = l;
    const range: Record<number, Tone> = Object.fromEntries(Array.from({ length: r - l }, (_, x) => [l + x, "active" as Tone]));
    snap(3, `Merge sorted halves [${l}..${m - 1}] = ${L.join(",")} and [${m}..${r - 1}] = ${R.join(",")}.`, range);
    while (i < L.length || j < R.length) { const takeL = j >= R.length || (i < L.length && L[i] <= R[j]); a[k] = takeL ? L[i++] : R[j++]; snap(5, `Take the smaller front element ${a[k]} (from the ${takeL ? "left" : "right"} half) into position ${k}.`, { ...range, [k]: "found" }); k++; }
  };
  rec(0, a.length); snap(6, "Sorted.", Object.fromEntries(a.map((_, i) => [i, "found" as Tone]))); return f;
}

// ------------------------------------------------------------------ monotonic stack: next greater element
export function nextGreater(a: number[]): { frames: Frame[]; result: number[] } {
  const res = Array(a.length).fill(-1), st: number[] = [], f: Frame[] = [];
  const snap = (line: number, note: string, i: number, t: Record<number, Tone> = {}) => f.push({ kind: "array", cells: arr(a, { ...Object.fromEntries(st.map((s) => [s, "active" as Tone])), ...t }), pointers: { i }, line, note,
    aux: [{ name: "stack (indices)", value: st.map((s) => `${s}:${a[s]}`).join(" ") || "∅" }, { name: "next greater", value: res.map((x, k) => `${a[k]}→${x < 0 ? "–" : a[x]}`).join("  ") }] });
  for (let i = 0; i < a.length; i++) {
    snap(1, `Process a[${i}] = ${a[i]}. Pop every stacked element that is smaller: this value is their next greater.`, i, { [i]: "compare" });
    while (st.length && a[st[st.length - 1]] < a[i]) { const j = st.pop()!; res[j] = i; snap(2, `a[${i}]=${a[i]} > a[${j}]=${a[j]}: next greater of index ${j} is ${a[i]}. Pop ${j}.`, i, { [j]: "found", [i]: "compare" }); }
    st.push(i); snap(3, `Push index ${i}. The stack stays decreasing (monotone), so each element is pushed and popped once: O(n).`, i);
  }
  return { frames: f, result: res };
}

// ------------------------------------------------------------------ N-Queens (backtracking)
export function nQueens(n: number): { frames: Frame[]; solutions: number } {
  const f: Frame[] = [], cols: number[] = []; let sols = 0, shown = 0;
  const board = (conf: number[] = []): Cell[][] => Array.from({ length: n }, (_, r) => Array.from({ length: n }, (_, c) => ({ v: cols[r] === c ? "♛" : "", tone: conf.includes(r * n + c) ? "compare" : cols[r] === c ? "found" : (r + c) % 2 ? "idle" : "done" } as Cell)));
  const snap = (line: number, note: string, conf: number[] = []) => { if (f.length < 400) f.push({ kind: "grid", cells: board(conf), line, note, queue: `queens: ${cols.map((c, r) => `(${r},${c})`).join(" ") || "none"} · solutions so far: ${sols}` }); };
  const ok = (r: number, c: number) => cols.every((cc, rr) => cc !== c && Math.abs(cc - c) !== r - rr);
  const go = (r: number) => {
    if (r === n) { sols++; if (shown++ < 2) snap(1, `All ${n} queens placed: solution #${sols}. Backtrack to find more.`); return; }
    for (let c = 0; c < n; c++) {
      if (!ok(r, c)) { if (f.length < 400) snap(3, `Row ${r}, column ${c}: attacked by an earlier queen. Prune (skip) this branch.`, [r * n + c]); continue; }
      cols.push(c); snap(4, `Place a queen at (${r},${c}); recurse to row ${r + 1}.`); go(r + 1); cols.pop(); if (f.length < 400) snap(6, `Undo: remove the queen from (${r},${c}) and try the next column.`);
    }
  };
  go(0); f.push({ kind: "grid", cells: board(), line: 0, note: `Done: ${sols} solution(s) for n = ${n}.${f.length >= 400 ? " (Animation truncated after 400 frames; the count is complete.)" : ""}`, queue: `total solutions: ${sols}` });
  return { frames: f, solutions: sols };
}

// ------------------------------------------------------------------ topological sort (Kahn)
export type DAG = { n: number; edges: [number, number][] };
export const DEMO_DAG: DAG = { n: 6, edges: [[5, 2], [5, 0], [4, 0], [4, 1], [2, 3], [3, 1]] };
export function topoSort(g: DAG): { frames: Frame[]; order: number[]; cyclic: boolean } {
  const pos: [number, number][] = [[70, 50], [70, 230], [200, 90], [330, 140], [70, 140], [200, 200]].slice(0, g.n).map((p, i) => (g.n > 6 ? [60 + (i % 5) * 90, 50 + Math.floor(i / 5) * 90] : p) as [number, number]);
  const indeg = Array(g.n).fill(0), adj: number[][] = Array.from({ length: g.n }, () => []); g.edges.forEach(([a, b]) => { adj[a].push(b); indeg[b]++; });
  const f: Frame[] = [], q: number[] = [], order: number[] = [], done = Array(g.n).fill(false); indeg.forEach((d, i) => d === 0 && q.push(i));
  const snap = (line: number, note: string, cur = -1) => f.push({ kind: "graph", directed: true, hideW: true, line, note, nodes: pos.map(([x, y], i) => ({ id: String(i), x, y, label: `in ${indeg[i]}`, tone: i === cur ? "compare" : done[i] ? "found" : q.includes(i) ? "active" : "idle" } as GNode)),
    edges: g.edges.map(([a, b]) => ({ a: String(a), b: String(b), w: 0, tone: (done[a] ? "path" : "idle") as Tone })), aux: [{ name: "queue", value: q.join(" ") || "∅" }, { name: "order so far", value: order.join(" → ") || "—" }] });
  snap(0, `In-degree = number of unmet prerequisites. Nodes with in-degree 0 can go first: queue = [${q.join(", ")}].`);
  while (q.length) { const u = q.shift()!; done[u] = true; order.push(u); snap(2, `Take ${u}: it has no remaining prerequisites. Append to the order and remove its outgoing edges.`, u);
    for (const v of adj[u]) { indeg[v]--; if (indeg[v] === 0) { q.push(v); snap(5, `Edge ${u}→${v} removed: in-degree of ${v} is now 0, so ${v} joins the queue.`, u); } else snap(4, `Edge ${u}→${v} removed: ${v} still waits on ${indeg[v]} other prerequisite(s).`, u); } }
  const cyclic = order.length < g.n; snap(7, cyclic ? "The queue emptied before all nodes were taken: the remaining nodes are on a cycle, so no topological order exists." : `All nodes placed: ${order.join(" → ")}. Every edge points forward in this order.`);
  return { frames: f, order, cyclic };
}

// ------------------------------------------------------------------ Fenwick tree
export function fenwick(a: number[], query: number): { frames: Frame[]; prefix: number } {
  const n = a.length, t = Array(n + 1).fill(0), f: Frame[] = [];
  const view = (line: number, note: string, hot: number[], ptr: Record<string, number> = {}) => f.push({ kind: "array", cells: t.slice(1).map((v, i) => ({ v, tone: hot.includes(i + 1) ? "active" : "idle" } as Cell)), pointers: ptr, line, note, aux: [{ name: "values", value: a.join(" ") }, { name: "tree (1-indexed)", value: t.slice(1).join(" ") }] });
  view(0, "Fenwick (BIT): tree[i] stores the sum of the range (i − lowbit(i), i]. Build by adding each value with update().", []);
  a.forEach((v, idx) => { const touched: number[] = []; for (let i = idx + 1; i <= n; i += i & -i) { t[i] += v; touched.push(i); } view(1, `update(${idx + 1}, +${v}): walk i += lowbit(i) → touches ${touched.join(", ")}.`, touched); });
  let s = 0; const path: number[] = [];
  for (let i = query; i > 0; i -= i & -i) { s += t[i]; path.push(i); view(4, `query(${query}): add tree[${i}] = ${t[i]}, then i -= lowbit(i) → ${i - (i & -i)}. Running sum = ${s}.`, [...path], { i }); }
  view(5, `prefix sum of the first ${query} values = ${s}. Both update and query take O(log n).`, path);
  return { frames: f, prefix: s };
}

// ------------------------------------------------------------------ segment tree (range sum query)
export function segmentQuery(a: number[], ql: number, qr: number): { frames: Frame[]; sum: number } {
  const n = a.length, T: { l: number; r: number; s: number }[] = [], f: Frame[] = [];
  const build = (i: number, l: number, r: number): void => { T[i] = { l, r, s: 0 }; if (l === r) { T[i].s = a[l]; return; } const m = (l + r) >> 1; build(2 * i, l, m); build(2 * i + 1, m + 1, r); T[i].s = T[2 * i].s + T[2 * i + 1].s; };
  build(1, 0, n - 1);
  const ids = Object.keys(T).map(Number), depth = (i: number) => Math.floor(Math.log2(i));
  const view = (line: number, note: string, tone: Record<number, Tone>, extra: string) => f.push({ kind: "graph", hideW: true, line, note,
    nodes: ids.map((i) => { const d = depth(i), idx = i - 2 ** d, cnt = 2 ** d; return { id: String(i), x: 245 + ((idx + 0.5) / cnt - 0.5) * 460, y: 28 + d * 52, label: `[${T[i].l},${T[i].r}]=${T[i].s}`, tone: tone[i] ?? "idle" } as GNode; }),
    edges: ids.filter((i) => i > 1).map((i) => ({ a: String(i >> 1), b: String(i), w: 0, tone: "idle" as Tone })), aux: [{ name: "array", value: a.join(" ") }, { name: `query [${ql},${qr}]`, value: extra }] });
  view(0, `Each node stores the sum of its segment. Query the range [${ql}, ${qr}] by visiting only O(log n) nodes.`, {}, "running sum = 0");
  let sum = 0; const visited: Record<number, Tone> = {};
  const q = (i: number, l: number, r: number): void => {
    visited[i] = "compare";
    if (qr < l || r < ql) { view(2, `Node [${l},${r}] is completely outside [${ql},${qr}]: skip.`, { ...visited }, `running sum = ${sum}`); return; }
    if (ql <= l && r <= qr) { sum += T[i].s; visited[i] = "found"; view(3, `Node [${l},${r}] is completely inside the query: take its stored sum ${T[i].s}. Running sum = ${sum}.`, { ...visited }, `running sum = ${sum}`); return; }
    view(4, `Node [${l},${r}] partially overlaps: recurse into both children.`, { ...visited }, `running sum = ${sum}`); const m = (l + r) >> 1; q(2 * i, l, m); q(2 * i + 1, m + 1, r);
  };
  q(1, 0, n - 1); view(6, `Answer = ${sum}.`, { ...visited }, `sum = ${sum}`);
  return { frames: f, sum };
}

// ------------------------------------------------------------------ Bellman-Ford (negative edges allowed)
export type BFG = { n: number; edges: [number, number, number][] };
export const DEMO_BF: BFG = { n: 5, edges: [[0, 1, 6], [0, 2, 7], [1, 2, 8], [1, 3, 5], [1, 4, -4], [2, 3, -3], [2, 4, 9], [3, 1, -2], [4, 3, 7], [4, 0, 2]] };
export function bellmanFord(g: BFG, src = 0): { frames: Frame[]; dist: number[]; negativeCycle: boolean } {
  const pos: [number, number][] = [[60, 140], [190, 50], [190, 230], [330, 50], [330, 230]], d = Array(g.n).fill(Infinity); d[src] = 0; const f: Frame[] = [];
  const snap = (line: number, note: string, hot = -1, aux = "") => f.push({ kind: "graph", directed: true, line, note, nodes: pos.slice(0, g.n).map(([x, y], i) => ({ id: String(i), x, y, label: d[i] === Infinity ? "∞" : String(d[i]), tone: d[i] < Infinity ? "active" : "idle" } as GNode)),
    edges: g.edges.map(([a, b, w], i) => ({ a: String(a), b: String(b), w, tone: (i === hot ? "path" : "idle") as Tone })), aux: [{ name: "dist", value: d.map((x, i) => `${i}=${x === Infinity ? "∞" : x}`).join("  ") }, ...(aux ? [{ name: "status", value: aux }] : [])] });
  snap(0, `Relax every edge up to ${g.n - 1} times. After round k, dist is correct for all shortest paths using ≤ k edges. Negative weights are fine; negative cycles are detected.`);
  for (let round = 1; round < g.n; round++) { let changed = false;
    g.edges.forEach(([a, b, w], i) => { if (d[a] + w < d[b]) { d[b] = d[a] + w; changed = true; snap(3, `Round ${round}: edge ${a}→${b} (w=${w}) improves dist[${b}] to ${d[b]}.`, i, `round ${round}`); } });
    if (!changed) { snap(5, `Round ${round}: nothing changed, so we can stop early.`, -1, "converged"); break; } }
  let neg = false; g.edges.forEach(([a, b, w]) => { if (d[a] + w < d[b]) neg = true; });
  snap(6, neg ? "An edge can still be relaxed after n−1 rounds: there is a negative cycle reachable from the source." : "No edge can be relaxed any more: these distances are final.", -1, neg ? "negative cycle" : "done");
  return { frames: f, dist: d, negativeCycle: neg };
}

const intsList = (t: string) => nums(t, 12);
export const EXTRA_ALGOS: Algo[] = [
  { id: "bs-answer", title: "Binary Search on Answer", blurb: "Search the answer space with a monotone yes/no check.", complexity: "O(n log S)", invariant: "The smallest feasible capacity is always in [lo, hi]; feasible(x) is false below it and true from it onward.",
    code: ["lo, hi = max(w), sum(w)", "while lo < hi:", "    mid = (lo + hi) // 2   # try this capacity", "    days = pack_greedily(w, mid)", "    if days <= D: hi = mid          # feasible: try smaller", "    else: lo = mid + 1              # infeasible: need more", "return lo"], run: () => shipBinaryAnswer([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 5),
    input: { hint: "weights | days   e.g. 3,2,2,4,1,4 | 3", default: "1,2,3,4,5,6,7,8,9,10 | 5", run: (t) => { const [w, d] = t.split("|"); if (d === undefined) throw new Error("Add '| days'."); const W = nums(w, 14); if (W.some((x) => x < 1)) throw new Error("Weights must be ≥ 1."); const D = nums(d, 1)[0]; if (D < 1 || D > W.length) throw new Error("days must be between 1 and the number of packages."); return shipBinaryAnswer(W, D); } } },
  { id: "dsu", title: "Union-Find (DSU)", blurb: "Merge sets, find representatives, compress paths.", complexity: "≈ O(α(n))", invariant: "Each set is a tree whose root is its representative; union-by-size and path compression keep trees almost flat.",
    code: ["parent[i] = i; size[i] = 1", "def find(x): # compress the path", "    ...", "def union(a, b):", "    ra, rb = find(a), find(b); if ra == rb: return", "    attach smaller root under larger; size[big] += size[small]"],
    run: () => dsu(8, [["union", 0, 1], ["union", 2, 3], ["union", 1, 3], ["union", 4, 5], ["find", 3], ["union", 0, 3], ["union", 6, 7], ["union", 5, 7]]).frames,
    input: { hint: "n | ops   e.g. 6 | u 0 1; u 2 3; f 3  (u = union, f = find)", default: "8 | u 0 1; u 2 3; u 1 3; u 4 5; f 3; u 0 3; u 6 7; u 5 7", run: (t) => { const [ns, os] = t.split("|"); if (os === undefined) throw new Error("Format: n | ops"); const n = nums(ns, 1)[0]; if (n < 2 || n > 10) throw new Error("n must be 2..10."); const ops = os.split(";").map((x) => x.trim()).filter(Boolean).map((x) => { const [o, a, b] = x.split(/\s+/); const A = Number(a), B = Number(b); if (!["u", "f"].includes(o) || !Number.isInteger(A) || A < 0 || A >= n || (o === "u" && (!Number.isInteger(B) || B < 0 || B >= n))) throw new Error(`Bad operation '${x}'. Use 'u a b' or 'f a' with 0 ≤ a,b < n.`); return [o === "u" ? "union" : "find", A, o === "u" ? B : undefined] as [string, number, number?]; }); if (!ops.length || ops.length > 14) throw new Error("1-14 operations."); return dsu(n, ops).frames; } } },
  { id: "bst", title: "Binary Search Tree", blurb: "Insert along comparisons, search by descending.", complexity: "O(h)", invariant: "For every node, all keys in its left subtree are smaller and all keys in its right subtree are larger.",
    code: ["insert(v): start at root", "    if v < node: go left, else if v > node: go right", "    attach as a new leaf at the first empty spot", "search(v): same descent; stop when found or empty"], run: () => bst([50, 30, 70, 20, 40, 60, 80], 60).frames,
    input: { hint: "values | search   e.g. 8,3,10,1,6 | 6", default: "50,30,70,20,40,60,80 | 60", run: (t) => { const [v, s] = t.split("|"); if (s === undefined) throw new Error("Add '| value to search'."); return bst(nums(v, 12), nums(s, 1)[0]).frames; } } },
  { id: "heap", title: "Min-Heap", blurb: "Complete tree stored in an array; sift up and down.", complexity: "O(log n) per op", invariant: "Every parent is ≤ its children, so the minimum is always at index 0.",
    code: ["push(v): append; sift up while v < parent", "pop(): take root; move last to root", "       sift down: swap with the smaller child", "parent(i) = (i-1)//2, children 2i+1, 2i+2"], run: () => heap([9, 4, 7, 1, 8, 2, 6], 3).frames,
    input: { hint: "values | pops   e.g. 5,3,8,1 | 2", default: "9,4,7,1,8,2,6 | 3", run: (t) => { const [v, p] = t.split("|"); if (p === undefined) throw new Error("Add '| number of pops'."); const P = nums(p, 1)[0]; if (P < 0 || P > 12) throw new Error("pops must be 0..12."); return heap(nums(v, 10), P).frames; } } },
  { id: "merge-sort", title: "Merge Sort", blurb: "Divide, sort halves, merge.", complexity: "O(n log n)", invariant: "After merging, the range [l, r) is sorted; merging two sorted halves is a single linear pass.",
    code: ["def sort(l, r):", "    if r - l <= 1: return", "    m = (l + r) // 2; sort(l, m); sort(m, r)", "    merge a[l:m] and a[m:r]:", "        take the smaller front element each time", "        write it into position k", "    # now a[l:r] is sorted"], run: () => mergeSort([6, 3, 8, 1, 9, 2, 7, 4]),
    input: { hint: "numbers   e.g. 5,2,9,1", default: "6,3,8,1,9,2,7,4", run: (t) => mergeSort(nums(t, 12)) } },
  { id: "mono-stack", title: "Monotonic Stack", blurb: "Next greater element in one pass.", complexity: "O(n)", invariant: "The stack holds indices of values not yet matched to a greater element, in decreasing order.",
    code: ["for i in range(n):", "    while stack and a[stack[-1]] < a[i]:", "        next_greater[stack.pop()] = i", "    stack.append(i)"], run: () => nextGreater([4, 5, 2, 25, 7, 8]).frames,
    input: { hint: "numbers   e.g. 4,5,2,25", default: "4,5,2,25,7,8", run: (t) => nextGreater(nums(t, 12)).frames } },
  { id: "nqueens", title: "N-Queens (backtracking)", blurb: "Place, prune, undo.", complexity: "exponential, pruned", invariant: "The queens placed so far never attack each other; a branch is abandoned the moment a placement would break that.",
    code: ["def go(row):", "    if row == n: count += 1; return", "    for col in range(n):", "        if attacked(row, col): continue   # prune", "        place(row, col)", "        go(row + 1)", "        undo(row, col)          # backtrack"], run: () => nQueens(4).frames,
    input: { hint: "n (4-6)", default: "4", run: (t) => { const n = nums(t, 1)[0]; if (n < 4 || n > 6) throw new Error("n must be 4..6 to keep the animation readable."); return nQueens(n).frames; } } },
  { id: "topo", title: "Topological Sort (Kahn)", blurb: "Order tasks so prerequisites come first.", complexity: "O(V + E)", invariant: "A node enters the queue only when all its prerequisites are already placed (in-degree 0).",
    code: ["indeg[v] = number of incoming edges", "queue = [v with indeg 0]", "while queue:", "    u = queue.pop(); order.append(u)", "    for v in adj[u]: indeg[v] -= 1", "        if indeg[v] == 0: queue.append(v)", "", "if len(order) < n: cycle → no order"], run: () => topoSort(DEMO_DAG).frames },
  { id: "fenwick", title: "Fenwick Tree (BIT)", blurb: "Prefix sums with point updates.", complexity: "O(log n)", invariant: "tree[i] holds the sum of the last lowbit(i) values ending at i; prefix queries combine O(log n) such blocks.",
    code: ["update(i, v):", "    while i <= n: tree[i] += v; i += i & -i", "query(i):", "    s = 0", "    while i > 0: s += tree[i]; i -= i & -i", "    return s"], run: () => fenwick([3, 2, -1, 6, 5, 4, -3, 3], 7).frames,
    input: { hint: "values | prefix length   e.g. 3,2,-1,6 | 3", default: "3,2,-1,6,5,4,-3,3 | 7", run: (t) => { const [v, q] = t.split("|"); if (q === undefined) throw new Error("Add '| prefix length'."); const a = nums(v, 12), Q = nums(q, 1)[0]; if (Q < 1 || Q > a.length) throw new Error("prefix length must be 1..n."); return fenwick(a, Q).frames; } } },
  { id: "segtree", title: "Segment Tree (range sum)", blurb: "Answer range queries by visiting O(log n) nodes.", complexity: "O(log n)", invariant: "Each node stores its segment's sum; a query takes whole nodes inside the range and splits only partially overlapping ones.",
    code: ["build(node, l, r): sum of children", "query(node, l, r):", "    if outside: return 0", "    if inside: return sum[node]", "    partial: recurse into both children", "    return left + right", "answer = query(1, 0, n-1)"], run: () => segmentQuery([2, 1, 5, 3, 4, 6, 1, 2], 2, 6).frames,
    input: { hint: "values | l r   e.g. 2,1,5,3 | 1 3", default: "2,1,5,3,4,6,1,2 | 2 6", run: (t) => { const [v, r] = t.split("|"); if (r === undefined) throw new Error("Add '| l r'."); const a = nums(v, 10), [l, rr] = r.trim().split(/\s+/).map(Number); if (!Number.isInteger(l) || !Number.isInteger(rr) || l < 0 || rr >= a.length || l > rr) throw new Error("l and r must satisfy 0 ≤ l ≤ r < n."); return segmentQuery(a, l, rr).frames; } } },
  { id: "bellman", title: "Bellman-Ford", blurb: "Shortest paths with negative edges.", complexity: "O(V·E)", invariant: "After k rounds, dist[v] is at most the length of the shortest path to v that uses ≤ k edges.",
    code: ["dist[src] = 0", "repeat n - 1 times:", "    for (u, v, w) in edges:", "        if dist[u] + w < dist[v]: dist[v] = dist[u] + w", "", "    if nothing changed: break", "if any edge still relaxes: negative cycle"], run: () => bellmanFord(DEMO_BF).frames },
];
void intsList;
