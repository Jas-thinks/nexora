import { describe, expect, it } from "vitest";
import { ALGOS, DEMO_GRAPH, WGraph, binarySearch, bfsGrid, dijkstra, dijkstraDistances, knapsack, lcs, quickSort, slidingWindowMax } from "./viz";

const last = <T,>(a: T[]) => a[a.length - 1];

describe("visualiser engine is the real algorithm", () => {
  it("binary search finds target and ends on found cell", () => {
    const f = binarySearch([1, 3, 5, 7, 9], 7);
    const end = last(f);
    expect(end.kind === "array" && end.cells[3].tone).toBe("found");
  });
  it("binary search reports absence", () => {
    expect(last(binarySearch([1, 3, 5], 4)).note).toMatch(/not present/);
  });
  it("quick sort ends fully sorted for arbitrary input", () => {
    for (let t = 0; t < 50; t++) {
      const input = Array.from({ length: 12 }, () => Math.floor(Math.random() * 20));
      const end = last(quickSort(input));
      const vals = end.kind === "array" ? end.cells.map((c) => c.v as number) : [];
      expect(vals).toEqual([...input].sort((a, b) => a - b));
    }
  });
  it("bfs distance equals known shortest path", () => {
    const f = bfsGrid(["S.T"]);
    expect(last(f).note).toMatch(/length = 2/);
  });
  it("bfs detects unreachable target", () => {
    expect(last(bfsGrid(["S#T"])).note).toMatch(/no path/);
  });
  it("lcs matches the textbook answer", () => {
    expect(last(lcs("AGGTAB", "GXTXAYB")).note).toMatch(/= 4/);
    expect(last(lcs("abc", "xyz")).note).toMatch(/= 0/);
  });
});

function bellmanFord(g: WGraph, src = 0) {
  const d = Array(g.n).fill(Infinity); d[src] = 0;
  for (let i = 0; i < g.n; i++) for (const [a, b, w] of g.edges) { if (d[a] + w < d[b]) d[b] = d[a] + w; if (d[b] + w < d[a]) d[a] = d[b] + w; }
  return d;
}
describe("Dijkstra trace matches an independent reference", () => {
  it("demo graph equals Bellman-Ford", () => expect(dijkstraDistances(DEMO_GRAPH)).toEqual(bellmanFord(DEMO_GRAPH)));
  it("random connected graphs equal Bellman-Ford", () => {
    for (let t = 0; t < 40; t++) {
      const n = 4 + Math.floor(Math.random() * 4); const edges: [number, number, number][] = [];
      for (let v = 1; v < n; v++) edges.push([Math.floor(Math.random() * v), v, 1 + Math.floor(Math.random() * 9)]);
      for (let k = 0; k < n; k++) { const a = Math.floor(Math.random() * n), b = Math.floor(Math.random() * n); if (a !== b) edges.push([a, b, 1 + Math.floor(Math.random() * 9)]); }
      const g: WGraph = { n, pos: Array.from({ length: n }, (_, i) => [50 + i * 60, 100] as [number, number]), edges };
      expect(dijkstraDistances(g)).toEqual(bellmanFord(g));
    }
  });
  it("every frame exposes node, queue and distance state; distances never increase", () => {
    const frames = dijkstra(DEMO_GRAPH); let prev: number[] | null = null;
    for (const f of frames) {
      expect(f.kind).toBe("graph"); if (f.kind !== "graph") continue;
      expect(f.aux.map((a) => a.name)).toEqual(["dist", "parent", "priority queue (dist,node)"]);
      const d = f.aux[0].value.split(/\s+/).map((t) => (t.split("=")[1] === "∞" ? Infinity : Number(t.split("=")[1])));
      if (prev) d.forEach((x, i) => expect(x).toBeLessThanOrEqual(prev![i])); prev = d;
    }
  });
});
describe("DP / window traces", () => {
  const best = (w: number[], v: number[], c: number) => { let m = 0; for (let mask = 0; mask < 1 << w.length; mask++) { let W = 0, V = 0; for (let i = 0; i < w.length; i++) if (mask >> i & 1) { W += w[i]; V += v[i]; } if (W <= c) m = Math.max(m, V); } return m; };
  it("knapsack equals brute force", () => { for (let t = 0; t < 40; t++) { const n = 1 + Math.floor(Math.random() * 6), w = Array.from({ length: n }, () => 1 + Math.floor(Math.random() * 6)), v = Array.from({ length: n }, () => 1 + Math.floor(Math.random() * 9)), c = 1 + Math.floor(Math.random() * 12);
    expect(last(knapsack(w, v, c)).note).toContain(`value = ${best(w, v, c)}`); } });
  it("sliding window equals brute force", () => { for (let t = 0; t < 40; t++) { const a = Array.from({ length: 5 + Math.floor(Math.random() * 8) }, () => Math.floor(Math.random() * 20) - 5), k = 1 + Math.floor(Math.random() * a.length);
    let m = -Infinity; for (let i = 0; i + k <= a.length; i++) m = Math.max(m, a.slice(i, i + k).reduce((x, y) => x + y, 0));
    expect(last(slidingWindowMax(a, k)).note).toContain(`sum = ${m},`); } });
});
describe("registry & custom input validation", () => {
  it("every algorithm runs, has an invariant, and highlights only real code lines", () => {
    for (const a of ALGOS) { expect(a.invariant.length).toBeGreaterThan(10); for (const f of a.run()) expect(f.line).toBeLessThan(a.code.length); }
  });
  it("custom inputs reject bad data with a message and accept good data", () => {
    const bs = ALGOS.find((a) => a.id === "binary-search")!.input!;
    expect(() => bs.run("5,3,1 | 3")).toThrow(/sorted/); expect(() => bs.run("1,2,3")).toThrow(/target/); expect(() => bs.run("a,b | 1")).toThrow(/integers/);
    expect(bs.run("1,3,5,7 | 5").length).toBeGreaterThan(1);
    const kn = ALGOS.find((a) => a.id === "knapsack")!.input!;
    expect(() => kn.run("1,2 | 3 | 5")).toThrow(/same count/); expect(() => kn.run("1,2 | 3,4 | 99")).toThrow(/capacity/);
    for (const a of ALGOS) if (a.input) expect(a.input.run(a.input.default).length).toBeGreaterThan(1);
  });
});
