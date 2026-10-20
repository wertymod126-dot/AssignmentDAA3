# Assignment 3 – Analysis (Java)

Language: Java (`submission.json` = `{"language":"Java"}`). Files: `src/Java/Algorithms.java` (my code), `src/Java/{Main,Input,Json}.java` (supplied, unchanged).

## 1. Build, run and test commands

Run everything from the repository root.

| Purpose | Command |
|---|---|
| Build (Java 17 level) | `javac --release 17 -d build src/Java/*.java` |
| Run on a JSON Lines file | `java -cp build Main < tests/my_cases.jsonl` |
| Course checks (setup / 36 public cases / own file) | `python tools/run.py --setup`, `python tools/run.py --check`, `python tools/run.py --input tests/my_cases.jsonl` |
| My semantic tests (oracles, hand, random, full-limit, state reset) | `python3 tests/run_tests.py` → writes `tests/results.txt`, `tests/my_cases.jsonl`, `tests/actual_outputs.jsonl` |
| Route-helper tests | `javac -d build src/Java/*.java tests/RouteHelperTest.java` then `java -cp build RouteHelperTest` → `tests/route_helper_results.txt` |
| Kruskal vs Prim benchmark | `javac -d build src/Java/*.java tests/Bench.java` then `java -cp build Bench` → `tests/benchmark_results.txt` |

Environment used for every test and measurement below: Windows 11 (amd64), 16 logical processors and a 4,004 MB maximum JVM heap (both as printed by `Bench`), OpenJDK 64-Bit Server VM 21.0.12.1 (code compiled with `--release 17`), I7-13620H RAM 16 GB, Python version - Python 3.14.8 .

## 2. Common design

* **State reset.** `Algorithms` has no static mutable fields. Every method creates its own arrays, heap and DSU from the request, so request *k* cannot influence request *k+1*. Checked in section 4 (same batch twice, in reverse order, and small requests before/after full-size ones give identical answers).
* **Deep DFS.** No recursion anywhere. DFS uses an explicit `int[] stack` plus `next[v]` (the next unexplored slot of `v`'s adjacency list). A vertex is pushed once, so the stack never exceeds `n`, and each adjacency slot is read once, so no list is rescanned. Chains of 100,000 vertices run with the default JVM stack (no `-Xss`).
* **Adjacency** is stored in compressed form (`start[]`, `adj[]` of original edge IDs), built in O(n + m) by counting. Edge IDs are therefore never lost.
* **Overflow.** Totals and distances are `long` (|total| ≤ 10⁵·10⁹ = 10¹⁴). Sort keys for Kruskal/Prim are `(w + 10⁹) << 24 | id` (non-negative, < 2⁵⁵).

## 3. Methods

### 3.1 DSU (`dsu`)
* **Steps.** `parent[i]=i`, `size[i]=1`, `components=n`, `largest=(n>0?1:0)`. For each pair: find both roots (iterative: find root, then compress the whole path), if different attach the smaller tree under the larger, add sizes, `components--`, update `largest`. Append `[components, largest]` after every operation (also when nothing changed).
* **Invariant.** Trees of `parent` are the current components; `size[r]` is the vertex count of the tree with root `r` (kept separately from any rank); `components` = number of roots; `largest` = max size over roots.
* **Correctness.** Union only happens for different roots, so repeated and self unions leave the partition and both numbers unchanged. Sizes only grow, hence a running max is the true maximum.
* **Boundaries.** `n=0` (no states), `n=1`, no operations, self-union, repeated/reversed unions.
* **Complexity.** O(n + q·α(n)) amortised time, O(n + q) memory (the `states` array is included).

### 3.2 Kruskal (`kruskal`)
* **Steps.** Pack each edge as `(w+10⁹)<<24 | id` into a `long[]`, sort it, scan in order, accept an edge iff `union(u,v)` merges two different components. Record the original ID and add the weight. `components = n − accepted`.
* **Invariant.** The accepted set is acyclic and is contained in some minimum spanning forest.
* **Correctness.** The edge being examined is a lightest edge leaving the component of its endpoint `u` (all lighter edges were already processed, and either joined components or were rejected as cycle edges), so by the cut property it can be added. Only the order of weights matters, so negative weights are fine. A self-loop always has `find(u)==find(v)` and is rejected. At the end the forest has `n−c` edges, hence `c = n − accepted` equals the number of connected components (isolates included).
* **Boundaries.** `n=0` → cost 0, ids `[]`, components 0; isolates; loops; parallel/equal edges; negative weights; totals beyond 32 bits.
* **Complexity.** O(n + m log m) time (sort dominates), O(n + m) memory.

### 3.3 Prim (`prim`)
* **Steps.** Build adjacency lists (CSR) without self-loops. For every unvisited vertex `root` (a restart; `components++`): mark it visited and push all its edges to still-unvisited neighbours into a binary min-heap of packed `(w, id)` keys. Repeatedly pop the minimum: if both endpoints are visited skip it (stale entry); otherwise the unvisited endpoint joins the tree, the edge ID and weight are recorded, and that vertex's edges to unvisited neighbours are pushed. When the heap is empty the component is complete and the outer loop moves to the next unvisited vertex.
* **Invariant.** The chosen edges form a tree on the visited set `S` of the current component and are contained in some minimum spanning tree of it; the heap contains every edge crossing the cut `(S, V∖S)` (plus stale entries).
* **Correctness.** An edge `(x,y)` with `x∈S`, `y∉S` was pushed when `x` was visited, because `y` was unvisited then; therefore the smallest non-stale entry is a lightest crossing edge (cut property). Stale entries have both endpoints in `S` and are skipped. Each restart handles one component, so `components` equals the number of restarts and isolates count (a restart with an empty frontier). The heap is empty at each restart because only stale entries could remain and they are drained.
* **Boundaries.** As Kruskal, plus: second and later components (restart), vertices with only self-loops (no adjacency), parallel edges.
* **Complexity.** Lazy heap: at most 2m pushes/pops → O(n + m log m) time, O(n + m) memory.

### 3.4 Kosaraju SCC (`scc`)
* **Steps.** (1) Iterative DFS on `G` recording finish order. (2) Iterative DFS on the transpose `Gᵀ`, starting from vertices in decreasing finish order and skipping labelled vertices; each DFS tree gets a new label `0,1,2,…`. (3) Condensation: scan the vertices in the order they were labelled (all vertices of one SCC are contiguous); for every edge `u→v` with different labels `(c, d)` emit `[c,d]` unless `stamp[d]==c` already (then set `stamp[d]=c`).
* **Invariant.** After `k` second-pass trees, the labelled vertices are exactly `k` complete SCCs, and the unlabelled root with the latest finish time lies in a source SCC of the remaining condensation.
* **Correctness.** Standard lemma: if there is an edge from SCC `C` to a different SCC `C'`, the latest finish time in `C` is later than in `C'`. So the next root belongs to an SCC `C` with no incoming edges from unlabelled SCCs; in `Gᵀ` the DFS from it cannot leave `C` into unlabelled vertices and reaches all of `C`. The stamp removes duplicates: `stamp[d]==c` means `[c,d]` was already emitted while scanning component `c`, and different `c` never share a stamp value because component `c` is scanned in one contiguous block.
* **Boundaries.** `n=0`, isolates, self-loops, duplicate edges, many parallel cross edges, a single giant cycle, long chains.
* **Complexity.** O(n + m) time (deterministic, no hashing), O(n + m) memory.

### 3.5 Topological order (`topo`)
* **Steps.** Three states per vertex: 0 unvisited, 1 active (on the DFS stack), 2 finished. Iterative DFS from every unvisited vertex. For an edge `u→v`: state 1 → cycle, stop and return `acyclic=false, order=[]`; state 0 → push; state 2 → ignore. When `u` has no more edges it becomes finished and is written to `order` from the back (so the array is the reverse finish order).
* **Invariant.** The stack holds exactly the active vertices, forming a directed path.
* **Correctness.** An edge to an active vertex closes a cycle (self-loop included, since `u` is active when its own edge is read). Conversely, if a cycle exists, when its first vertex is discovered the others are reachable through unvisited vertices, so some cycle edge points to an active vertex (white-path theorem) and is detected. An edge to a finished vertex is not a cycle. For an acyclic graph every edge `u→v` has `finish(v) < finish(u)` (v was unvisited ⇒ descendant, or already finished), so the reverse finish order places `u` before `v`.
* **Boundaries.** `n=0`, self-loop, 2-cycle, cycle in a later component, cross/forward edges to finished vertices, duplicate edges, isolates.
* **Complexity.** O(n + m) time and memory.

### 3.6 DAG shortest paths (`dag`)
* **Steps.** Build adjacency, run the same three-state DFS on the **whole** graph. If it finds a cycle (also one unreachable from the source) return `acyclic=false`, `distance=[]`, `parent_edge=[]`. Otherwise `dist[source]=0`, `reached[source]=true`, and for `u` in topological order: skip it unless `reached[u]`; for each outgoing edge `id=(u,v,w)` set `dist[v]=dist[u]+w`, `parent[v]=id` if `v` is not reached yet or the candidate is smaller. Output `distance[v]=null` and `parent_edge[v]=-1` for unreached vertices, `0`/`-1` for the source.
* **Invariant.** When `u` is processed all of its predecessors were processed, so `dist[u]` is final; `reached[v]` is true iff a processed reached vertex has an edge to `v`.
* **Correctness.** Induction along the topological order gives the exact shortest distances (negative weights are fine in a DAG). Relaxing only from reached vertices avoids using a fake infinity and cannot create distances from unreachable vertices (test: edge `0→3` of weight −100 with unreachable `0`). `parent[v]` is set together with `dist[v]`, so the final parent edge ends at `v` and satisfies `dist[v]=dist[u]+w`. It starts at an earlier vertex in topological order, so following parents terminates at a vertex without a parent, which is only the source (an edge into the source from a reached vertex would form a cycle).
* **Boundaries.** `n=1`; source not first in the topological order; unreachable vertices; `-1` as a real distance; self-loop; cycle outside the source's reach; parallel and tied edges; distances beyond 32 bits.
* **Complexity.** O(n + m) time and memory.

### 3.7 Route helper `Algorithms.route(source, target, parentEdge, edges)`
Walks from `target` to `source` through `parentEdge`, checks that every used edge really ends at the current vertex, and returns the vertex sequence reversed to run source → target. **No-route result: an empty `int[]`** (unreachable target, empty arrays from a cyclic graph, or inconsistent input). Route to the source is `[source]`. Time and space O(L) for L route vertices (plus an `n+1` scratch array).

Helper calls (my own run of `RouteHelperTest` printed the same routes and edge IDs as in this table and ended with `ALL ROUTE-HELPER CHECKS PASSED`; full output in `tests/route_helper_results.txt`):

| Case | Request | Call result | Selected edge IDs | Check |
|---|---|---|---|---|
| reachable | README example, `source=0` | `route(0,3)` = `[0,1,2,3]` | `[0,2,3]` | edges 0→1, 1→2, 2→3 in direction; cost 3−7+4 = 0 = `distance[3]` |
| reachable, negative edge | same | `route(0,2)` = `[0,1,2]` | `[0,2]` | cost 3−7 = −4 = `distance[2]`, beats direct edge 1 (8) |
| source | same | `route(0,0)` = `[0]` | – | route to the source is `[source]` |
| unreachable | same | `route(0,4)` = `[]` | – | `distance[4]` is `null` |
| parallel edges | `[[0,1,4],[0,1,4],[0,1,5],[1,2,0],[0,2,4]]` | `route(0,1)` = `[0,1]` | `[0]` | weight-4 parallel edge chosen (not id 2 with weight 5); cost 4 |
| tied routes | same | `route(0,2)` = `[0,2]` | `[4]` | tie between `0→1→2` (ids 0,3) and direct id 4, both cost 4; the solution returned id 4, either is valid |
| source in the middle | `source=2`, `[[0,2,1],[1,2,1],[2,3,5],[0,3,-100]]` | `route(2,3)` = `[2,3]`; `route(2,0)` = `[]` | `[2]` | vertex 0 is unreachable, the −100 edge is not used |
| defensive | cyclic graph, corrupt parent cycle, wrong-direction parent | all `[]` | – | no infinite loop |
| long chain | 100,000 vertices, weight 10⁹ | length 100,000 | – | total 99,999,000,000,000 = `distance` |

## 4. Tests (output in `tests/results.txt`)

Run with `python tests/run_tests.py`. The final line of my run was `TOTAL FAILURES: 0`.

1. **Oracles are checked first.** The independent Python oracles (Kruskal with path halving, iterative Tarjan, Kahn, DP over Kahn order) are compared with brute force (all edge subsets, Floyd-Warshall closure, Bellman-Ford, naive relabelling) on 400 random tiny graphs.
2. **Validators are checked.** They accept alternative valid answers (three different optimal forests of a tied triangle, permuted SCC labels, another topological order, another tied shortest-path witness) and reject invalid witnesses (duplicate/looping/cyclic/non-optimal forest, merged/split SCCs, duplicate/missing/internal/reversed condensation pair, backward edge, missing vertex, wrong flags, parent edge that does not end at the vertex or is on a heavier route, `-1` used for unreachable, ignoring a cycle unreachable from the source). There are 38 meta-checks.
3. **57 hand cases** with a written justification each (README examples, `n=0`, isolates, self/repeated unions, loops, parallel/tied edges, negative weights, totals beyond 32 bits, restart in Prim, cycle outside source reachability, source in the middle, etc.).
4. **3,000 seeded random small requests** (seed 777; loops, parallel edges, negative and +-10^9 weights, forced DAGs with occasional back edges).
5. **State reset.** The hand and random batch run twice in one process, in reverse order, and before/after five full-size requests must give identical answers.
6. **Full limits and deep graphs** (n = 100,000; m or q up to 250,000): random graphs with weights +-10^9, paths of +-10^9 (cost/distance beyond 32 bits), 100,000-vertex chains in both directions, one giant cycle, 100,000 two-cycles, 250,000 duplicate edges, random DAG, cycle unreachable from the source, isolated source. 31 requests.

Results on my machine: the 400 tiny-graph comparisons of the oracles with brute force agreed; all 38 validator meta-checks behaved as expected; 57 of 57 hand cases passed; the 3,000 random small requests had 0 failures; the state-reset checks (batch twice in one process, reversed order, before/after full-size requests) all gave identical answers; 31 of 31 full-size requests passed. Each full-size request in its own process took 0.12-0.40 s including JVM start and JSON I/O, and all 31 in one process took 3.03 s (limit 20 s). This was a single run of the test program.

Course checks: `python tools/run.py --setup` printed `PASS setup: ping`; `python tools/run.py --check` passed all 36 public cases and the `state reset: two complete batches in one process` check; `python tools/run.py --input tests/my_cases.jsonl` -> Language: Java
{"states":[[3,2],[2,3],[2,3],[2,3]]}
{"states":[]}
{"states":[[1,1]]}
{"states":[]}
{"states":[[4,2],[4,2],[4,2],[3,2],[2,4],[2,4]]}
{"states":[[5,2],[4,2],[3,2],[2,4],[1,6]]}
{"cost":5,"edge_ids":[1,2],"components":2}
{"cost":0,"edge_ids":[],"components":0}
{"cost":0,"edge_ids":[],"components":1}
{"cost":0,"edge_ids":[],"components":3}
{"cost":3,"edge_ids":[2],"components":1}
{"cost":-16,"edge_ids":[2,1],"components":1}
{"cost":3000000000,"edge_ids":[0,1,2],"components":1}
{"cost":-3000000000,"edge_ids":[0,1,2],"components":1}
{"cost":2,"edge_ids":[0,1],"components":1}
{"cost":5,"edge_ids":[1,2,3],"components":3}
{"cost":2,"edge_ids":[0,1],"components":2}
{"cost":5,"edge_ids":[2,1],"components":2}
{"cost":0,"edge_ids":[],"components":0}
{"cost":0,"edge_ids":[],"components":1}
{"cost":0,"edge_ids":[],"components":3}
{"cost":3,"edge_ids":[2],"components":1}
{"cost":-16,"edge_ids":[2,1],"components":1}
{"cost":3000000000,"edge_ids":[0,1,2],"components":1}
{"cost":-3000000000,"edge_ids":[0,1,2],"components":1}
{"cost":2,"edge_ids":[0,1],"components":1}
{"cost":5,"edge_ids":[3,1,2],"components":3}
{"cost":2,"edge_ids":[1,0],"components":2}
{"component":[0,0,1,2],"condensation":[[0,1],[1,2]]}
{"component":[],"condensation":[]}
{"component":[0],"condensation":[]}
{"component":[2,1,0],"condensation":[]}
{"component":[0,1,2],"condensation":[[0,1],[1,2]]}
{"component":[0,0,0,1,1],"condensation":[[0,1]]}
{"component":[0,2,1,3],"condensation":[[0,2],[0,1],[1,3],[2,3]]}
{"component":[0,0,1,1],"condensation":[[0,1]]}
{"acyclic":true,"order":[1,0,2,3]}
{"acyclic":true,"order":[]}
{"acyclic":true,"order":[0]}
{"acyclic":false,"order":[]}
{"acyclic":false,"order":[]}
{"acyclic":false,"order":[]}
{"acyclic":true,"order":[0,2,1,3]}
{"acyclic":true,"order":[0,1,2]}
{"acyclic":true,"order":[3,2,1,0]}
{"acyclic":true,"distance":[0,3,-4,0,null],"parent_edge":[-1,0,2,3,-1]}
{"acyclic":true,"distance":[0],"parent_edge":[-1]}
{"acyclic":true,"distance":[null,0,-1],"parent_edge":[-1,-1,1]}
{"acyclic":true,"distance":[null,null,0,5],"parent_edge":[-1,-1,-1,2]}
{"acyclic":false,"distance":[],"parent_edge":[]}
{"acyclic":false,"distance":[],"parent_edge":[]}
{"acyclic":false,"distance":[],"parent_edge":[]}
{"acyclic":true,"distance":[0,4,4],"parent_edge":[-1,0,4]}
{"acyclic":true,"distance":[0,-1,null],"parent_edge":[-1,0,-1]}
{"acyclic":true,"distance":[0,1000000000,2000000000,3000000000,4000000000],"parent_edge":[-1,0,1,2,3]}
{"acyclic":true,"distance":[0,-1000000000,-2000000000,-3000000000,-4000000000],"parent_edge":[-1,0,1,2,3]}
{"acyclic":true,"distance":[null,null,0,1,2],"parent_edge":[-1,-1,-1,2,3]}

## 5. Benchmark: Kruskal vs Prim (same graphs)

* **Graphs.** Random multigraphs (loops and parallel edges allowed), `u,v` uniform in `[0,n)`, `w` uniform in `[-10^9, 10^9]`, generated by `java.util.Random(20261020 + n)` in `tests/Bench.java`; no stored files needed. Both methods receive the identical edge array.
* **Verification first.** For every size the program checks that Kruskal and Prim return the same cost and that each result is a valid forest (no loops/repeats/cycles, `n-c` edges, cost field = sum).
* **Timing boundary (same for both).** One call `Algorithms.kruskal(request)` / `prim(request)`: input conversion + algorithm + result-map construction. Excluded: compilation, graph generation, JSON parsing and printing.
* **Method.** `System.nanoTime()`, 30 untimed warm-up calls per method and size, then 9 timed calls per method alternating K, P, K, P... The benchmark program is the unchanged `tests/Bench.java` from the repository.

| n | m | components | Kruskal timings (ms) | Kruskal median | Prim timings (ms) | Prim median |
|---:|---:|---:|---|---:|---|---:|
| 10,000 | 25,000 | 57 | 2.00, 1.94, 1.78, 1.87, 2.05, 1.73, 1.97, 2.00, 1.94 | **1.94** | 3.48, 4.00, 3.48, 3.50, 3.65, 3.40, 3.31, 3.50, 3.24 | **3.48** |
| 50,000 | 125,000 | 325 | 10.97, 11.20, 9.92, 10.44, 10.24, 10.80, 10.83, 10.86, 11.18 | **10.83** | 21.41, 21.36, 22.09, 21.55, 22.30, 21.12, 21.70, 21.29, 21.08 | **21.41** |
| 100,000 | 250,000 | 731 | 24.82, 23.91, 21.66, 23.19, 22.90, 24.78, 21.67, 23.74, 25.64 | **23.74** | 58.57, 58.59, 59.85, 55.55, 54.49, 53.59, 57.42, 51.74, 55.94 | **55.94** |

Optimal costs (identical for both): -5,296,029,722,468; -26,384,195,811,172; -52,887,400,445,009.

A second complete run of `Bench` gave these medians (ms): n = 10,000: Kruskal 1.86, Prim 3.42; n = 50,000: Kruskal 11.32, Prim 22.39; n = 100,000: Kruskal 37.25, Prim 85.55.

**Observations (measured).** Kruskal had the lower median at all three sizes in both runs. In the first run Prim's median divided by Kruskal's was 1.79, 1.98 and 2.36 for the three sizes; in the second run it was 1.84, 1.98 and 2.30. The absolute times at n = 100,000 differed a lot between the two runs (Kruskal 23.74 ms vs 37.25 ms, Prim 55.94 ms vs 85.55 ms), and the second run had single slow outliers (for example 16.38 ms for Kruskal at n = 50,000 and 104.67 ms for Prim at n = 100,000), so only the ordering and the rough factor of about 2 were stable.

**Asymptotic argument (separate from the measurements).** Both algorithms are O(n + m log m). Kruskal sorts m keys once and then does at most 2m `find` operations with almost-constant cost. Lazy Prim pushes up to 2m entries (every edge from both endpoints) into a heap and pops all of them, and also builds adjacency lists first, so a larger constant is expected.

**Limitations.** I ran the benchmark twice on a normal Windows 11 desktop session, without controlling background processes or power settings; the two runs differed noticeably at the largest size, as shown above. Only sparse random graphs with m about 2.5n were tested, so other densities or an indexed-heap Prim could rank differently. The timed call includes the shared input conversion and result building, which makes the difference between the methods look smaller than the algorithm cores alone. I did not profile the code, so I make no claim about why Prim is slower beyond the argument above, which is an expectation and not a measured fact.

## 6. Sources and AI assistance

* **Sources.** Algorithms follow the standard textbook descriptions (disjoint sets, Kruskal, Prim, Kosaraju, DFS topological sort, DAG relaxation) and the assignment README. The supplied `Main`, `Input`, `Json` are unchanged. 
* **AI assistance.** AI was used for research, debugging and brainstorming purposes