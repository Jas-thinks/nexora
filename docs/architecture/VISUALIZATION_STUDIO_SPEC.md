# Visualization Studio spec

Code: `web/lib/viz.ts` (engine, pure TypeScript), `web/app/(app)/visualizer/page.tsx` (renderer + playback), tests `web/lib/viz.test.ts`.

## Architecture (implemented)
- **Algorithm + instrumentation are one thing**: each algorithm is a pure function returning the ordered list of `Frame`s it really passes through (so animation = execution; no separate canned animation).
- **Frame primitives** (reusable renderers): `array` (cells + named pointers), `grid`, `table` (DP), `graph` (nodes/edges/weights with per-element tone) + `aux` panels (named variables / priority queue / parent / dist).
- **Playback controller** is algorithm-agnostic: play/pause, step ±1, restart, speed, progress, line highlight (`frame.line` indexes the pseudocode).
- **Registry**: `ALGOS` entries declare title, complexity, pseudocode, **invariant**, default run, optional validated custom input. Adding an algorithm = one function + one registry entry.

## Correctness guarantees (tested)
Quick sort final state equals sorted input (50 random arrays); Dijkstra final distances equal Bellman-Ford on 40 random graphs and never increase across frames; knapsack equals brute force (40 random); sliding window equals brute force (40 random); LCS equals textbook; BFS reports shortest/unreachable correctly; every frame's highlighted line exists; custom input rejects bad data with a message.

## Coverage
Implemented (7): binary search, quick sort, BFS (grid), LCS, Dijkstra, 0/1 knapsack, sliding window.
Catalogue requested but **not built**: linked lists, stacks/queues, heaps, BST, tries, segment/Fenwick trees, DSU, sparse table, other sorts, recursion trees/backtracking (N-Queens, subsets), the remaining DP families, other graph algorithms (Bellman-Ford, Floyd, MST, SCC, flows, LCA, HLD, centroid), string algorithms, number theory, geometry, etc.

## Missing capabilities
Backward-compatible additions needed: beginner/advanced explanation toggle; edge-case explorer; memory/variable inspector beyond `aux`; recursion call-stack primitive; **AI Q&A over the trace** (needs LLM: the design is to pass the current frame + preceding frames + the pseudocode and require answers to cite frame numbers); persisted "my inputs".
