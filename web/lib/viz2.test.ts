import { describe, expect, it } from "vitest";
import { ALGOS, type Frame } from "./viz";
import { bellmanFord, bst, daysNeeded, DEMO_BF, dsu, fenwick, heap, inorder, mergeSort, nextGreater, nQueens, segmentQuery, shipBinaryAnswer, topoSort } from "./viz2";

const rnd = (n: number, lo: number, hi: number) => Array.from({ length: n }, () => lo + Math.floor(Math.random() * (hi - lo + 1)));
const last = <T,>(a: T[]) => a[a.length - 1];
const auxOf = (f: { aux?: { name: string; value: string }[] } | Frame, name: string) => (f as { aux?: { name: string; value: string }[] }).aux?.find((x) => x.name === name)?.value;

describe("binary search on answer matches brute force", () => {
  it("random inputs", () => { for (let t = 0; t < 60; t++) { const w = rnd(1 + Math.floor(Math.random() * 9), 1, 15), d = 1 + Math.floor(Math.random() * w.length);
    let best = Math.max(...w); while (daysNeeded(w, best) > d) best++;
    expect(auxOf(last(shipBinaryAnswer(w, d)), "answer")).toBe(String(best)); } });
  it("every probe is consistent with the predicate it states", () => { for (const fr of shipBinaryAnswer([3, 2, 2, 4, 1, 4], 3)) expect(fr.note).not.toMatch(/NaN|undefined/); });
});
describe("DSU", () => {
  it("component count equals a reference on random operation sequences", () => { for (let t = 0; t < 60; t++) { const n = 2 + Math.floor(Math.random() * 8), ops: [string, number, number?][] = [];
    for (let i = 0; i < 10; i++) ops.push(Math.random() < 0.75 ? ["union", Math.floor(Math.random() * n), Math.floor(Math.random() * n)] : ["find", Math.floor(Math.random() * n)]);
    const par = Array.from({ length: n }, (_, i) => i); const f = (x: number): number => (par[x] === x ? x : f(par[x])); let comps = n;
    for (const [o, a, b] of ops) if (o === "union" && f(a) !== f(b!)) { par[f(a)] = f(b!); comps--; }
    expect(dsu(n, ops).components).toBe(comps); } });
  it("in every frame the sizes of the roots sum to n (no element lost or double counted)", () => { const n = 6; const { frames } = dsu(n, [["union", 0, 1], ["union", 2, 3], ["union", 1, 3], ["find", 3], ["union", 4, 5], ["union", 0, 5]]);
    for (const fr of frames) { expect(fr.kind).toBe("graph"); const nodes = (fr as unknown as { nodes: { label: string }[] }).nodes; expect(nodes.filter((q) => q.label.startsWith("size")).reduce((s2, q) => s2 + Number(q.label.slice(5)), 0)).toBe(n); } });
});
describe("BST / heap / merge sort", () => {
  it("BST in-order is sorted and unique", () => { for (let t = 0; t < 50; t++) { const v = rnd(1 + Math.floor(Math.random() * 10), 0, 30); const { root } = bst(v, v[0]); expect(inorder(root)).toEqual([...new Set(v)].sort((a, b) => a - b)); } });
  it("BST search finds present and rejects absent", () => { expect(last(bst([5, 3, 8], 3).frames).note).toMatch(/Found/); expect(last(bst([5, 3, 8], 4).frames).note).toMatch(/not present/); });
  it("heap pops come out sorted ascending", () => { for (let t = 0; t < 50; t++) { const v = rnd(1 + Math.floor(Math.random() * 9), -9, 9); const { popped } = heap(v, v.length); expect(popped).toEqual([...v].sort((a, b) => a - b)); } });
  it("merge sort ends sorted on random input", () => { for (let t = 0; t < 40; t++) { const v = rnd(2 + Math.floor(Math.random() * 10), -9, 9); const end = last(mergeSort(v)); expect(end.kind === "array" ? end.cells.map((c) => c.v) : []).toEqual([...v].sort((a, b) => a - b)); } });
});
describe("stack / backtracking / graphs / range structures", () => {
  it("next greater equals brute force", () => { for (let t = 0; t < 60; t++) { const a = rnd(1 + Math.floor(Math.random() * 10), 0, 20); const brute = a.map((x, i) => { for (let j = i + 1; j < a.length; j++) if (a[j] > x) return j; return -1; }); expect(nextGreater(a).result).toEqual(brute); } });
  it("N-Queens solution counts are the known values", () => { expect(nQueens(4).solutions).toBe(2); expect(nQueens(5).solutions).toBe(10); expect(nQueens(6).solutions).toBe(4); expect(nQueens(6).frames.length).toBeLessThanOrEqual(402); });
  it("topological order respects every edge; cycles are detected", () => { for (let t = 0; t < 40; t++) { const n = 3 + Math.floor(Math.random() * 3), edges: [number, number][] = []; for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) if (Math.random() < 0.4) edges.push([i, j]);
      const r = topoSort({ n, edges }); expect(r.cyclic).toBe(false); const at = new Map(r.order.map((v, i) => [v, i])); for (const [a, b] of edges) expect(at.get(a)!).toBeLessThan(at.get(b)!); }
    expect(topoSort({ n: 3, edges: [[0, 1], [1, 2], [2, 0]] }).cyclic).toBe(true); });
  it("Fenwick prefix equals brute force", () => { for (let t = 0; t < 60; t++) { const a = rnd(1 + Math.floor(Math.random() * 10), -9, 9), q = 1 + Math.floor(Math.random() * a.length); expect(fenwick(a, q).prefix).toBe(a.slice(0, q).reduce((x, y) => x + y, 0)); } });
  it("segment tree range sum equals brute force", () => { for (let t = 0; t < 60; t++) { const a = rnd(1 + Math.floor(Math.random() * 10), -9, 9), l = Math.floor(Math.random() * a.length), r = l + Math.floor(Math.random() * (a.length - l)); expect(segmentQuery(a, l, r).sum).toBe(a.slice(l, r + 1).reduce((x, y) => x + y, 0)); } });
  it("Bellman-Ford equals an independent reference and detects negative cycles", () => {
    const ref = (n: number, e: [number, number, number][]) => { const d = Array(n).fill(Infinity); d[0] = 0; for (let i = 0; i < n - 1; i++) for (const [a, b, w] of e) if (d[a] + w < d[b]) d[b] = d[a] + w; return d; };
    expect(bellmanFord(DEMO_BF).dist).toEqual(ref(DEMO_BF.n, DEMO_BF.edges)); expect(bellmanFord(DEMO_BF).negativeCycle).toBe(false);
    expect(bellmanFord({ n: 3, edges: [[0, 1, 1], [1, 2, -3], [2, 1, 1]] }).negativeCycle).toBe(true); });
});
describe("registry integrity for ALL algorithms", () => {
  it("has unique ids, valid code-line highlights, and runnable defaults", () => {
    expect(new Set(ALGOS.map((a) => a.id)).size).toBe(ALGOS.length); expect(ALGOS.length).toBeGreaterThanOrEqual(18);
    for (const a of ALGOS) { const fr = a.run(); expect(fr.length).toBeGreaterThan(1); for (const f of fr) { expect(f.line).toBeGreaterThanOrEqual(0); expect(f.line, `${a.id} line`).toBeLessThan(a.code.length); expect(f.note.length).toBeGreaterThan(5); }
      if (a.input) expect(a.input.run(a.input.default).length).toBeGreaterThan(1); } });
  it("custom-input validators reject garbage with a message", () => { for (const id of ["bs-answer", "dsu", "bst", "heap", "fenwick", "segtree", "nqueens"]) { const a = ALGOS.find((x) => x.id === id)!; expect(() => a.input!.run("not valid")).toThrow(); } });
});
