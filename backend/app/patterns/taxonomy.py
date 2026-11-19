"""Pattern Universe taxonomy v0.1 (AUTHORED by Nexora engineering, review_status = unreviewed).

A pattern is not a topic label. `kind` separates concepts that are related but not interchangeable:
  category     grouping node
  data_structure | algorithm | pattern (problem-solving idea) | math (mathematical technique) | optimization
Relations are explicit edges (prerequisite / related / contrasts / extends), validated by tests (acyclic prerequisites,
existing targets, unique aliases). Nothing here is derived from a model; changes go through taxonomy versioning.
"""
from dataclasses import dataclass

VERSION = "0.1.0"
REVIEW_STATUS = "unreviewed"  # flips to "human_reviewed" only after an actual review pass


@dataclass(frozen=True)
class Pattern:
    id: str
    name: str
    kind: str
    parent: str | None = None
    aliases: tuple[str, ...] = ()
    prereq: tuple[str, ...] = ()
    related: tuple[str, ...] = ()
    contrasts: tuple[str, ...] = ()  # similar-looking but different (do NOT merge)
    extends: tuple[str, ...] = ()
    cf_tags: tuple[str, ...] = ()  # Codeforces tags that evidence this pattern
    sections: tuple[str, ...] = ()  # sheet section names (lower-case, substring match) that evidence it
    complexity: str = ""
    clues: tuple[str, ...] = ()


def P(id, name, kind, parent=None, **kw):
    return Pattern(id, name, kind, parent, **{k: tuple(v) if isinstance(v, (list, tuple)) else v for k, v in kw.items()})


PATTERNS: list[Pattern] = [
    # ---- top-level categories (from the product directive; expandable)
    *[P(i, n, "category") for i, n in [
        ("arrays-strings", "Arrays and strings"), ("hashing-cat", "Hashing"), ("searching-sorting", "Sorting and searching"),
        ("recursion-cat", "Recursion and backtracking"), ("dp-cat", "Dynamic programming"), ("trees-cat", "Trees"),
        ("graphs-cat", "Graphs"), ("linear-ds", "Stacks, queues and linked lists"), ("range-queries", "Range queries"),
        ("math-cat", "Mathematics and number theory"), ("strings-cat", "String algorithms"), ("geometry-cat", "Geometry"),
        ("advanced-cat", "Advanced techniques"), ("games-cat", "Game theory")]],
    # ---- arrays / basic techniques
    P("implementation", "Implementation / simulation", "pattern", "arrays-strings", cf_tags=["implementation"], sections=["pattern", "basic", "logic"]),
    P("brute-force", "Brute force / complete search", "pattern", "arrays-strings", cf_tags=["brute force"], contrasts=["meet-in-the-middle"]),
    P("prefix-sums", "Prefix and suffix sums", "pattern", "arrays-strings", aliases=["cumulative sums"], sections=["prefix"], complexity="O(n) build, O(1) query",
      clues=["many range-sum queries", "subarray sum equals K"]),
    P("two-pointers", "Two pointers", "pattern", "arrays-strings", cf_tags=["two pointers"], sections=["two pointers", "two-pointer", "2-pointer"], prereq=["sorting"],
      related=["sliding-window"], contrasts=["sliding-window"], complexity="O(n)", clues=["sorted array + pair condition", "shrink/grow from ends"]),
    P("sliding-window", "Sliding window", "pattern", "arrays-strings", sections=["sliding window", "window"], prereq=["two-pointers"], complexity="O(n)",
      clues=["contiguous subarray/substring", "longest/shortest satisfying a constraint"]),
    P("hashing", "Hash maps and sets", "data_structure", "hashing-cat", aliases=["hash table"], cf_tags=["hashing"], sections=["hashing", "hash", "arrays & hashing"], complexity="O(1) average"),
    P("string-hashing", "Rolling hash", "algorithm", "hashing-cat", prereq=["hashing", "modular-arithmetic"], related=["kmp"], contrasts=["kmp"]),
    # ---- sorting / searching
    P("sorting", "Sorting", "algorithm", "searching-sorting", cf_tags=["sortings"], sections=["sort"], complexity="O(n log n)"),
    P("custom-comparators", "Custom sorting / comparators", "pattern", "searching-sorting", prereq=["sorting"], related=["interval-scheduling"]),
    P("binary-search", "Binary search on a sorted array", "algorithm", "searching-sorting", cf_tags=["binary search"], sections=["binary search"], prereq=["sorting"], complexity="O(log n)"),
    P("bounds", "Lower and upper bound", "pattern", "searching-sorting", prereq=["binary-search"], extends=["binary-search"]),
    P("rotated-search", "Search in rotated / bitonic arrays", "pattern", "searching-sorting", prereq=["binary-search"]),
    P("monotonic-predicate", "Monotonic predicate", "pattern", "searching-sorting", prereq=["binary-search"], clues=["f(x) flips from false to true once"]),
    P("binary-search-answer", "Binary search on answer", "pattern", "searching-sorting", aliases=["answer-space binary search", "bs on answers"], sections=["on answers", "on-answers"],
      prereq=["monotonic-predicate"], contrasts=["binary-search"], complexity="O(log range * check)",
      clues=["minimise the maximum / maximise the minimum", "can we do it within X? is monotone in X"]),
    P("parallel-binary-search", "Parallel binary search", "optimization", "searching-sorting", prereq=["binary-search-answer", "dsu"]),
    P("ternary-search", "Ternary search", "algorithm", "searching-sorting", cf_tags=["ternary search"], contrasts=["binary-search"]),
    P("divide-and-conquer", "Divide and conquer", "pattern", "searching-sorting", cf_tags=["divide and conquer"], prereq=["recursion"], related=["merge-sort"]),
    P("merge-sort", "Merge sort (and inversion counting)", "algorithm", "searching-sorting", prereq=["divide-and-conquer"]),
    # ---- recursion / backtracking
    P("recursion", "Recursion", "pattern", "recursion-cat", sections=["recursion"]),
    P("backtracking", "Backtracking", "pattern", "recursion-cat", sections=["backtrack"], prereq=["recursion"], related=["brute-force"]),
    P("subsets-permutations", "Subsets, subsequences, permutations", "pattern", "recursion-cat", prereq=["backtracking"]),
    P("bitmask-enumeration", "Bitmask enumeration", "pattern", "recursion-cat", prereq=["bit-manipulation"], related=["subsets-permutations"]),
    P("meet-in-the-middle", "Meet in the middle", "optimization", "recursion-cat", cf_tags=["meet-in-the-middle"], prereq=["brute-force", "binary-search"]),
    # ---- greedy
    P("greedy", "Greedy", "pattern", "advanced-cat", cf_tags=["greedy"], sections=["greedy"], clues=["locally optimal choice is safe (exchange argument)"]),
    P("interval-scheduling", "Interval scheduling / merging", "pattern", "advanced-cat", sections=["interval", "scheduling"], prereq=["greedy", "sorting"]),
    P("constructive", "Constructive algorithms", "pattern", "advanced-cat", cf_tags=["constructive algorithms"], prereq=["implementation"]),
    # ---- dynamic programming
    P("dynamic-programming", "Dynamic programming (foundations)", "pattern", "dp-cat", cf_tags=["dp"], sections=["dp", "dynamic"], prereq=["recursion"], clues=["overlapping subproblems", "optimal substructure"]),
    P("dp-1d", "1-D DP", "pattern", "dp-cat", sections=["1-d dp", "1d dp"], prereq=["dynamic-programming"]),
    P("dp-2d", "2-D DP / grid DP", "pattern", "dp-cat", sections=["2-d dp", "2d dp"], prereq=["dp-1d"]),
    P("knapsack", "Knapsack family", "pattern", "dp-cat", prereq=["dp-1d"]),
    P("dp-subsequence", "Subsequence DP (LIS / LCS / edit distance)", "pattern", "dp-cat", prereq=["dp-2d"]),
    P("interval-dp", "Interval DP", "pattern", "dp-cat", prereq=["dp-2d"]),
    P("bitmask-dp", "Bitmask DP", "pattern", "dp-cat", cf_tags=["bitmasks"], prereq=["dp-1d", "bit-manipulation"]),
    P("digit-dp", "Digit DP", "pattern", "dp-cat", prereq=["dp-1d"]),
    P("tree-dp", "Tree DP", "pattern", "dp-cat", prereq=["dynamic-programming", "tree-traversal"]),
    P("rerooting-dp", "Rerooting DP", "pattern", "dp-cat", prereq=["tree-dp"], extends=["tree-dp"]),
    P("dp-optimization", "DP optimisations (CHT / D&C / Knuth)", "optimization", "dp-cat", prereq=["dynamic-programming", "convex-hull-trick"]),
    # ---- stacks / queues / linked lists / heaps
    P("stack", "Stack", "data_structure", "linear-ds", sections=["stack"]),
    P("queue-deque", "Queues and deques", "data_structure", "linear-ds", sections=["queue"]),
    P("monotonic-stack", "Monotonic stack / queue", "pattern", "linear-ds", sections=["monotonic"], prereq=["stack"], contrasts=["stack"]),
    P("linked-list", "Linked lists", "data_structure", "linear-ds", sections=["linked list", "linked-list", "-ll"]),
    P("heap", "Heaps / priority queues", "data_structure", "linear-ds", sections=["heap", "priority"], complexity="O(log n) push/pop"),
    # ---- trees
    P("tree-traversal", "Tree traversals", "pattern", "trees-cat", sections=["tree", "traversal"], prereq=["recursion"]),
    P("bst", "Binary search trees", "data_structure", "trees-cat", sections=["binary-search-trees", "bst"], prereq=["tree-traversal"]),
    P("trie", "Tries", "data_structure", "trees-cat", sections=["trie"]),
    P("lca", "Lowest common ancestor", "algorithm", "trees-cat", prereq=["tree-traversal"], related=["binary-lifting"]),
    P("binary-lifting", "Binary lifting", "optimization", "trees-cat", prereq=["tree-traversal"]),
    P("tree-diameter", "Tree diameter and centers", "pattern", "trees-cat", prereq=["tree-traversal"]),
    P("hld", "Heavy-light decomposition", "algorithm", "trees-cat", prereq=["lca", "segment-tree"]),
    P("centroid-decomposition", "Centroid decomposition", "algorithm", "trees-cat", prereq=["tree-traversal", "divide-and-conquer"]),
    # ---- graphs
    P("graph-traversal", "BFS and DFS", "algorithm", "graphs-cat", cf_tags=["dfs and similar", "graphs"], sections=["graph", "bfs", "dfs"], complexity="O(V+E)"),
    P("topological-sort", "Topological sorting", "algorithm", "graphs-cat", prereq=["graph-traversal"]),
    P("shortest-paths", "Shortest paths (Dijkstra / Bellman-Ford / Floyd)", "algorithm", "graphs-cat", cf_tags=["shortest paths"], sections=["shortest", "advanced graphs"], prereq=["graph-traversal", "heap"]),
    P("mst", "Minimum spanning trees", "algorithm", "graphs-cat", prereq=["dsu", "sorting"]),
    P("dsu", "Disjoint Set Union", "data_structure", "graphs-cat", cf_tags=["dsu"], sections=["union", "dsu"], complexity="O(alpha(n))"),
    P("bridges-scc", "Bridges, articulation points, SCC", "algorithm", "graphs-cat", prereq=["graph-traversal"]),
    P("bipartite", "Bipartite checking / matching", "algorithm", "graphs-cat", cf_tags=["graph matchings"], prereq=["graph-traversal"]),
    P("euler-tour", "Eulerian paths and circuits", "algorithm", "graphs-cat", prereq=["graph-traversal"]),
    P("max-flow", "Max flow / min cut", "algorithm", "graphs-cat", cf_tags=["flows"], prereq=["graph-traversal", "shortest-paths"]),
    P("two-sat", "2-SAT", "algorithm", "graphs-cat", cf_tags=["2-sat"], prereq=["bridges-scc"]),
    # ---- range queries / advanced DS
    P("sparse-table", "Sparse table", "data_structure", "range-queries", prereq=["prefix-sums"]),
    P("fenwick", "Fenwick tree (BIT)", "data_structure", "range-queries", sections=["fenwick", "bit-"], prereq=["prefix-sums", "bit-manipulation"]),
    P("segment-tree", "Segment tree", "data_structure", "range-queries", sections=["segment"], prereq=["divide-and-conquer", "prefix-sums"]),
    P("sqrt-decomposition", "Square-root decomposition / Mo's algorithm", "optimization", "range-queries", prereq=["prefix-sums"]),
    P("offline-queries", "Offline queries & coordinate compression", "optimization", "range-queries", prereq=["sorting", "fenwick"]),
    P("sweep-line", "Sweep line", "pattern", "range-queries", prereq=["sorting", "heap"]),
    P("advanced-ds", "Advanced data structures (persistent, treaps…)", "data_structure", "advanced-cat", cf_tags=["data structures"], prereq=["segment-tree"]),
    # ---- math
    P("bit-manipulation", "Bit manipulation", "math", "math-cat", cf_tags=["bitmasks"], sections=["bit manip"]),
    P("mathematics", "Mathematics (general)", "math", "math-cat", cf_tags=["math"], sections=["math"]),
    P("number-theory", "Number theory", "math", "math-cat", cf_tags=["number theory"], prereq=["mathematics"]),
    P("modular-arithmetic", "Modular arithmetic & fast exponentiation", "math", "math-cat", prereq=["number-theory"]),
    P("sieve", "Sieve and factorisation", "algorithm", "math-cat", prereq=["number-theory"]),
    P("combinatorics", "Combinatorics", "math", "math-cat", cf_tags=["combinatorics"], prereq=["modular-arithmetic"]),
    P("matrix-exponentiation", "Matrix exponentiation", "optimization", "math-cat", cf_tags=["matrices"], prereq=["modular-arithmetic", "dynamic-programming"]),
    P("probability", "Probability and expectation", "math", "math-cat", cf_tags=["probabilities"], prereq=["combinatorics"]),
    P("fft", "FFT / polynomial methods", "algorithm", "math-cat", cf_tags=["fft"], prereq=["modular-arithmetic"]),
    # ---- strings
    P("kmp", "KMP / Z-function", "algorithm", "strings-cat", cf_tags=["string suffix structures"], prereq=["implementation"], contrasts=["string-hashing"]),
    P("aho-corasick", "Aho-Corasick", "algorithm", "strings-cat", prereq=["trie", "kmp"]),
    P("suffix-structures", "Suffix arrays and automata", "data_structure", "strings-cat", prereq=["kmp", "sorting"]),
    P("string-processing", "String processing", "pattern", "strings-cat", cf_tags=["strings"], sections=["string"]),
    # ---- geometry / games
    P("geometry", "Computational geometry", "math", "geometry-cat", cf_tags=["geometry"]),
    P("convex-hull-trick", "Convex hull and line container", "optimization", "geometry-cat", prereq=["geometry"]),
    P("game-theory", "Game theory (Nim, Sprague-Grundy)", "math", "games-cat", cf_tags=["games"]),
    P("randomized", "Randomized algorithms", "pattern", "advanced-cat", prereq=["probability"]),
]
BY_ID = {p.id: p for p in PATTERNS}
EDGE_FIELDS = ("prereq", "related", "contrasts", "extends")
