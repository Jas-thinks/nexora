"""First-party teaching notes (written for Nexora, project-licensed). Pattern ids link to the taxonomy.
Status: authored, NOT yet human-reviewed. Each note is deliberately short; it is retrieval material for the mentor, not a full course."""
NOTES = [
 dict(key="note:binary-search", title="Binary search on a sorted array", patterns=["binary-search", "bounds"],
  text="""Intuition: if data is sorted, one comparison discards half the candidates. Keep an interval [lo, hi) that must contain the answer; each step looks at mid and shrinks the interval.
Recognise it: sorted input, 'find first/last position', n up to 1e5-1e9 with an O(log n) hint.
Invariant: the answer, if it exists, is always inside the current interval. Off-by-one bugs come from not fixing the interval convention (closed vs half-open) before writing the loop.
Template (C++, first index with a[i] >= x): int lo=0, hi=n; while(lo<hi){ int mid=lo+(hi-lo)/2; if(a[mid]>=x) hi=mid; else lo=mid+1; } return lo;
Complexity O(log n). Common mistakes: (lo+hi) overflow, infinite loop when lo=mid in a closed interval, forgetting that lower_bound returns n when no element qualifies."""),
 dict(key="note:binary-search-answer", title="Binary search on the answer (monotonic predicate)", patterns=["binary-search-answer", "monotonic-predicate"],
  text="""Intuition: instead of searching an array, search the space of possible answers. If a yes/no check feasible(x) is monotone (all false then all true, or the reverse), binary search finds the boundary.
Recognise it: 'minimise the maximum', 'maximise the minimum', 'smallest x such that ...', and a greedy/simulation check that is easy once x is fixed.
Steps: 1) define feasible(x); 2) argue monotonicity (if x works then x+1 works, for min problems); 3) pick lo/hi that bracket the answer; 4) binary search the first true.
Template (C++): long long lo=LO, hi=HI; while(lo<hi){ long long mid=lo+(hi-lo)/2; if(feasible(mid)) hi=mid; else lo=mid+1; } return lo;
Complexity O(log(range) * cost(feasible)). Mistakes: checking monotonicity wrongly, bounds that exclude the answer, integer overflow in the check, using it on a non-monotone predicate."""),
 dict(key="note:two-pointers", title="Two pointers", patterns=["two-pointers"],
  text="""Intuition: two indices move through the data in a way that never needs to move backwards, turning an O(n^2) scan into O(n).
Recognise it: sorted array + pair/triple condition (sum equals target), merging two sorted lists, partitioning, palindrome checks.
Opposite ends: l=0,r=n-1; if a[l]+a[r]<t then l++ else r--. Same direction: a slow pointer marks the write position, a fast pointer scans.
Why it is correct: each pointer move discards candidates that cannot be part of any valid answer (justify this for the problem).
Complexity O(n) after sorting O(n log n). Mistakes: not sorting first, skipping duplicate handling, moving the wrong pointer, assuming it works on unsorted data."""),
 dict(key="note:sliding-window", title="Sliding window", patterns=["sliding-window"],
  text="""Intuition: for a contiguous subarray/substring with a constraint, maintain a window [l,r] and its aggregate; extend r, and shrink l while the constraint is violated.
Recognise it: 'longest/shortest subarray with...', 'at most K distinct', fixed-size window sums.
Template (variable window): for(r=0;r<n;r++){ add(a[r]); while(!ok()){ remove(a[l]); l++; } best=max(best,r-l+1); }
Works when removing from the left can only help restore the constraint (monotone validity). Complexity O(n) since l and r each move at most n times.
Mistakes: negative numbers break sum-based shrinking (use prefix sums + hashing instead), forgetting to update the aggregate on removal, off-by-one in window length."""),
 dict(key="note:prefix-sums", title="Prefix sums", patterns=["prefix-sums"],
  text="""Intuition: precompute cumulative sums so any range sum is a subtraction: sum(l..r)=P[r+1]-P[l].
Recognise it: many range-sum queries; 'subarray sum equals K' (store prefix sums in a hash map and look for P-K); 2D grids (2D prefix sums).
Template: P[0]=0; P[i+1]=P[i]+a[i]. Complexity O(n) build, O(1) per query.
Mistakes: off-by-one with P of size n+1, overflow (use long long), forgetting P[0]=0 in the hash-map version."""),
 dict(key="note:dp-foundations", title="Dynamic programming: state, transition, base case", patterns=["dynamic-programming", "dp-1d"],
  text="""Intuition: solve a problem by combining answers to smaller overlapping subproblems and store each once.
Method: 1) define the state precisely (what does dp[i] mean?); 2) write the transition from smaller states; 3) set base cases; 4) fix the evaluation order; 5) read the answer.
Top-down = recursion + memo; bottom-up = loops in dependency order. Space can often shrink when dp[i] depends only on a few previous values.
Example: climbing stairs dp[i]=dp[i-1]+dp[i-2], dp[0]=dp[1]=1.
Mistakes: a state that does not capture enough information (the answer depends on something not in the state), wrong iteration order, forgetting to modulo, mixing 'number of ways' with 'minimum cost' recurrences."""),
 dict(key="note:knapsack", title="0/1 knapsack", patterns=["knapsack"],
  text="""State: dp[i][c] = best value using the first i items with capacity c. Transition: dp[i][c]=max(dp[i-1][c], dp[i-1][c-w]+v) if w<=c. Base: dp[0][*]=0.
Space optimisation to one array: iterate capacity downward (c=W..w) so each item is used at most once; iterating upward gives the unbounded knapsack instead.
Complexity O(nW). Recognise it: choose a subset under a budget, subset-sum, partition problems.
Mistakes: iterating capacity upward for 0/1, using it when W is huge (pseudo-polynomial)."""),
 dict(key="note:dp-lcs-lis", title="Subsequence DP: LCS and LIS", patterns=["dp-subsequence"],
  text="""LCS: dp[i][j] = LCS length of prefixes a[0..i), b[0..j). If a[i-1]==b[j-1] then dp[i-1][j-1]+1 else max(dp[i-1][j], dp[i][j-1]). O(nm).
LIS: O(n^2) with dp[i]=1+max dp[j] for j<i, a[j]<a[i]; O(n log n) by keeping the smallest tail of an increasing subsequence of each length and binary searching (lower_bound for strict increase).
Recognise it: 'longest', 'edit distance', 'alignment', matching two sequences. Reconstruction: store parent pointers or walk the table backwards.
Mistakes: confusing subsequence with substring, strict vs non-strict LIS (lower_bound vs upper_bound)."""),
 dict(key="note:graph-traversal", title="BFS and DFS", patterns=["graph-traversal"],
  text="""BFS explores in rings of increasing distance, so on an unweighted graph the first time it reaches a node is a shortest path. Use a queue and a visited/dist array.
DFS goes deep first (recursion or stack): connected components, cycle detection, topological order, tree traversals.
Template BFS: dist[s]=0; queue<int> q; q.push(s); while(!q.empty()){ int u=q.front(); q.pop(); for(int v: g[u]) if(dist[v]<0){ dist[v]=dist[u]+1; q.push(v);} }
Complexity O(V+E). Mistakes: marking visited when popping instead of when pushing (duplicates in the queue), recursion depth overflow on long paths, forgetting disconnected components."""),
 dict(key="note:dijkstra", title="Dijkstra shortest paths", patterns=["shortest-paths"],
  text="""For non-negative edge weights: keep dist[] and a min-priority-queue of (dist,node). Pop the closest node; its distance is final because any other route to it must pass through a node at least as far. Relax its edges.
Template: priority_queue<pair<ll,int>,vector<pair<ll,int>>,greater<>> pq; dist[s]=0; pq.push({0,s}); while(!pq.empty()){ auto [d,u]=pq.top(); pq.pop(); if(d>dist[u]) continue; for(auto [v,w]: g[u]) if(dist[u]+w<dist[v]){ dist[v]=dist[u]+w; pq.push({dist[v],v}); } }
Complexity O((V+E) log V). Negative edges need Bellman-Ford; many sources on small graphs use Floyd-Warshall. Mistakes: INF overflow, forgetting the stale-entry check, using it with negative weights."""),
 dict(key="note:dsu", title="Disjoint Set Union (union-find)", patterns=["dsu"],
  text="""Maintains a partition of elements into sets with find(x) (representative) and unite(a,b). Path compression plus union by size gives near-constant amortised time (inverse Ackermann).
Template: int find(int x){ return p[x]==x? x : p[x]=find(p[x]); } bool unite(int a,int b){ a=find(a); b=find(b); if(a==b) return false; if(sz[a]<sz[b]) swap(a,b); p[b]=a; sz[a]+=sz[b]; return true; }
Recognise it: connectivity under edge additions, Kruskal's MST, grouping equivalent items, offline dynamic connectivity tricks.
Mistakes: forgetting to initialise p[i]=i, unioning non-roots, expecting it to support deletions."""),
 dict(key="note:greedy", title="Greedy algorithms and exchange arguments", patterns=["greedy", "interval-scheduling"],
  text="""A greedy algorithm repeatedly makes the locally best choice. It is only correct if you can prove it: the standard tool is an exchange argument - show any optimal solution can be transformed, step by step, to one that starts with the greedy choice without getting worse.
Classic: activity selection (sort by earliest finish time), interval merging (sort by start), fractional knapsack (by value/weight), Huffman coding.
Recognise it: a sort followed by one pass, 'minimum number of ...', scheduling. If you cannot prove it, test against brute force on small inputs.
Mistakes: sorting by the wrong key, assuming greedy works where it needs DP (0/1 knapsack, coin change with arbitrary coins)."""),
 dict(key="note:monotonic-stack", title="Monotonic stack", patterns=["monotonic-stack"],
  text="""Keep a stack whose values are monotone; when a new element breaks the order, pop elements - each pop resolves a query for that element (e.g. its next greater element).
Template (next greater): for(i=0;i<n;i++){ while(!st.empty() && a[st.back()]<a[i]){ nxt[st.back()]=i; st.pop_back(); } st.push_back(i); }
Complexity O(n): every element is pushed and popped once. Recognise it: next/previous greater or smaller, largest rectangle in a histogram, stock-span problems.
Mistakes: strictness (< vs <=) with equal values, storing values instead of indices."""),
 dict(key="note:segment-fenwick", title="Segment tree and Fenwick tree", patterns=["segment-tree", "fenwick"],
  text="""Both answer range queries with point or range updates in O(log n). Fenwick (BIT) is shorter: update(i,d){ for(++i;i<=n;i+=i&-i) t[i]+=d; } query(i){ s=0; for(++i;i>0;i-=i&-i) s+=t[i]; return s; } and range sum is query(r)-query(l-1); it needs an invertible operation.
Segment tree stores an aggregate per node covering a segment; it supports non-invertible operations (min, max, gcd) and lazy propagation for range updates.
Recognise it: many interleaved updates and range queries where prefix sums would be rebuilt too often.
Mistakes: 0/1-based index confusion in BIT, size 4n for recursive segment trees, forgetting to push lazy values down."""),
 dict(key="note:bit-modular", title="Bit manipulation and modular arithmetic", patterns=["bit-manipulation", "modular-arithmetic"],
  text="""Bits: x&(x-1) clears the lowest set bit; x&-x isolates it; (x>>k)&1 tests bit k; subsets of a set are enumerated with masks 0..(1<<n)-1.
Modular arithmetic: (a+b)%m, (a*b)%m are safe if you reduce each operand first; division needs the modular inverse - for prime m, a^(m-2) by fast exponentiation.
Fast power: long long pw(long long b,long long e,long long m){ long long r=1; b%=m; while(e){ if(e&1) r=r*b%m; b=b*b%m; e>>=1; } return r; } O(log e).
Mistakes: overflow before taking the modulus, negative remainders in C++ (add m), using Fermat's inverse with a non-prime modulus."""),
 dict(key="note:backtracking", title="Backtracking", patterns=["backtracking", "subsets-permutations"],
  text="""Build a solution one choice at a time; recurse; undo the choice (backtrack) and try the next. Prune as soon as a partial solution cannot succeed.
Template: void go(int i){ if(i==n){ record(); return; } for(choice in options(i)){ apply(choice); go(i+1); undo(choice); } }
Recognise it: generate all subsets/permutations/combinations, N-Queens, Sudoku, constraint puzzles with small n.
Complexity is exponential; the pruning rule is what makes it usable. Mistakes: forgetting to undo state, duplicates when the input has repeated values (sort + skip equal siblings), missing the pruning check."""),
]
