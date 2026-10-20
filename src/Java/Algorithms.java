import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Graph algorithms for Assignment 3.
 *
 * Every method works only with local state created for the current request, so
 * nothing leaks between requests. All DFS traversals are iterative (explicit
 * stack plus a per-vertex "next edge" pointer), so deep graphs cannot overflow
 * the call stack and no adjacency list is rescanned.
 */
public final class Algorithms {
    /** Weights are shifted by this value so that they become non-negative. */
    private static final long WEIGHT_SHIFT = 1_000_000_000L;
    /** Edge ID occupies the low bits of a packed (weight, id) sort key. */
    private static final int ID_BITS = 24;
    private static final long ID_MASK = (1L << ID_BITS) - 1;

    // ------------------------------------------------------------------
    // DSU
    // ------------------------------------------------------------------

    /** DSU with path compression and union by size/rank; return states. */
    static Map<String, Object> dsu(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] operations = Input.operations(input);

        DisjointSet sets = new DisjointSet(n);
        int[][] states = new int[operations.length][];
        for (int i = 0; i < operations.length; i++) {
            sets.union(operations[i][0], operations[i][1]);
            states[i] = new int[] {sets.components, sets.largest};
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("states", states);
        return result;
    }

    /** Disjoint-set forest: path compression + union by size (size kept separately). */
    private static final class DisjointSet {
        final int[] parent;
        final int[] size;
        int components;
        int largest;

        DisjointSet(int n) {
            parent = new int[n];
            size = new int[n];
            for (int i = 0; i < n; i++) {
                parent[i] = i;
                size[i] = 1;
            }
            components = n;
            largest = n > 0 ? 1 : 0;
        }

        /** Iterative find: locate the root, then compress the whole path. */
        int find(int x) {
            int root = x;
            while (parent[root] != root) {
                root = parent[root];
            }
            while (parent[x] != root) {
                int next = parent[x];
                parent[x] = root;
                x = next;
            }
            return root;
        }

        /** Returns true if two different components were merged. */
        boolean union(int a, int b) {
            int rootA = find(a);
            int rootB = find(b);
            if (rootA == rootB) {
                return false;
            }
            if (size[rootA] < size[rootB]) {
                int tmp = rootA;
                rootA = rootB;
                rootB = tmp;
            }
            parent[rootB] = rootA;
            size[rootA] += size[rootB];
            components--;
            if (size[rootA] > largest) {
                largest = size[rootA];
            }
            return true;
        }
    }

    // ------------------------------------------------------------------
    // Kruskal
    // ------------------------------------------------------------------

    /** Separate Kruskal implementation; return cost, edge_ids, components. */
    static Map<String, Object> kruskal(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);
        int m = edges.length;

        // Sort primitive keys (shifted weight, original ID); the ID is kept in the low bits.
        long[] keys = new long[m];
        for (int i = 0; i < m; i++) {
            keys[i] = ((edges[i][2] + WEIGHT_SHIFT) << ID_BITS) | i;
        }
        Arrays.sort(keys);

        DisjointSet sets = new DisjointSet(n);
        int[] chosen = new int[n];
        int count = 0;
        long cost = 0;
        for (int k = 0; k < m; k++) {
            int id = (int) (keys[k] & ID_MASK);
            // A self-loop has find(u) == find(v), so it is never accepted.
            if (sets.union(edges[id][0], edges[id][1])) {
                chosen[count++] = id;
                cost += edges[id][2];
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("cost", cost);
        result.put("edge_ids", Arrays.copyOf(chosen, count));
        result.put("components", sets.components);
        return result;
    }

    // ------------------------------------------------------------------
    // Prim
    // ------------------------------------------------------------------

    /** Separate Prim implementation; restart for every unvisited component. */
    static Map<String, Object> prim(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);
        int m = edges.length;

        // Adjacency lists of edge IDs (CSR layout). Self-loops can never be in a forest.
        int[] start = new int[n + 1];
        for (int i = 0; i < m; i++) {
            if (edges[i][0] != edges[i][1]) {
                start[edges[i][0] + 1]++;
                start[edges[i][1] + 1]++;
            }
        }
        for (int v = 0; v < n; v++) {
            start[v + 1] += start[v];
        }
        int[] fill = Arrays.copyOf(start, n);
        int[] adj = new int[start[n]];
        for (int i = 0; i < m; i++) {
            if (edges[i][0] != edges[i][1]) {
                adj[fill[edges[i][0]]++] = i;
                adj[fill[edges[i][1]]++] = i;
            }
        }

        boolean[] visited = new boolean[n];
        int[] chosen = new int[n];
        int count = 0;
        long cost = 0;
        int components = 0;
        LongMinHeap heap = new LongMinHeap(Math.max(16, 2 * m));

        for (int root = 0; root < n; root++) {
            if (visited[root]) {
                continue;
            }
            components++;
            visited[root] = true;
            pushFrontier(root, edges, start, adj, visited, heap);

            while (!heap.isEmpty()) {
                int id = (int) (heap.pop() & ID_MASK);
                int u = edges[id][0];
                int v = edges[id][1];
                int target;
                if (visited[u]) {
                    if (visited[v]) {
                        continue; // stale entry: both endpoints already in the tree
                    }
                    target = v;
                } else {
                    target = u; // the edge was pushed from a visited endpoint, so v is visited
                }
                visited[target] = true;
                chosen[count++] = id;
                cost += edges[id][2];
                pushFrontier(target, edges, start, adj, visited, heap);
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("cost", cost);
        result.put("edge_ids", Arrays.copyOf(chosen, count));
        result.put("components", components);
        return result;
    }

    /** Push every edge from x that leads to a still-unvisited vertex. */
    private static void pushFrontier(int x, int[][] edges, int[] start, int[] adj,
                                     boolean[] visited, LongMinHeap heap) {
        for (int p = start[x]; p < start[x + 1]; p++) {
            int id = adj[p];
            int other = edges[id][0] == x ? edges[id][1] : edges[id][0];
            if (!visited[other]) {
                heap.push(((edges[id][2] + WEIGHT_SHIFT) << ID_BITS) | id);
            }
        }
    }

    /** Minimal binary min-heap over primitive longs (priority queues are allowed). */
    private static final class LongMinHeap {
        private long[] data;
        private int size;

        LongMinHeap(int capacity) {
            data = new long[capacity];
        }

        boolean isEmpty() {
            return size == 0;
        }

        void push(long value) {
            if (size == data.length) {
                data = Arrays.copyOf(data, size * 2);
            }
            int i = size++;
            while (i > 0) {
                int parent = (i - 1) >>> 1;
                if (data[parent] <= value) {
                    break;
                }
                data[i] = data[parent];
                i = parent;
            }
            data[i] = value;
        }

        long pop() {
            long top = data[0];
            long last = data[--size];
            if (size > 0) {
                int i = 0;
                while (true) {
                    int child = 2 * i + 1;
                    if (child >= size) {
                        break;
                    }
                    if (child + 1 < size && data[child + 1] < data[child]) {
                        child++;
                    }
                    if (data[child] >= last) {
                        break;
                    }
                    data[i] = data[child];
                    i = child;
                }
                data[i] = last;
            }
            return top;
        }
    }

    // ------------------------------------------------------------------
    // Shared adjacency builder (CSR of original edge IDs)
    // ------------------------------------------------------------------

    /**
     * Builds adjacency in compressed form. Returns {start, adj}: the edge IDs leaving
     * vertex v (or entering it when {@code reverse}) are adj[start[v] … start[v+1]-1].
     */
    private static int[][] buildAdjacency(int n, int[][] edges, boolean reverse) {
        int from = reverse ? 1 : 0;
        int m = edges.length;
        int[] start = new int[n + 1];
        for (int i = 0; i < m; i++) {
            start[edges[i][from] + 1]++;
        }
        for (int v = 0; v < n; v++) {
            start[v + 1] += start[v];
        }
        int[] fill = Arrays.copyOf(start, n);
        int[] adj = new int[m];
        for (int i = 0; i < m; i++) {
            adj[fill[edges[i][from]]++] = i;
        }
        return new int[][] {start, adj};
    }

    // ------------------------------------------------------------------
    // Kosaraju SCC
    // ------------------------------------------------------------------

    /** Kosaraju's two DFS passes; return component and exact condensation. */
    static Map<String, Object> scc(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);

        int[][] forward = buildAdjacency(n, edges, false);
        int[][] transpose = buildAdjacency(n, edges, true);
        int[] fStart = forward[0];
        int[] fAdj = forward[1];
        int[] tStart = transpose[0];
        int[] tAdj = transpose[1];

        // Pass 1: iterative DFS on the original graph, recording finish order.
        int[] finish = new int[n];
        int finished = 0;
        boolean[] seen = new boolean[n];
        int[] next = Arrays.copyOf(fStart, n); // next unexplored edge slot per vertex
        int[] stack = new int[n];
        for (int s = 0; s < n; s++) {
            if (seen[s]) {
                continue;
            }
            int sp = 0;
            stack[sp++] = s;
            seen[s] = true;
            while (sp > 0) {
                int u = stack[sp - 1];
                if (next[u] < fStart[u + 1]) {
                    int v = edges[fAdj[next[u]++]][1];
                    if (!seen[v]) {
                        seen[v] = true;
                        stack[sp++] = v;
                    }
                } else {
                    sp--;
                    finish[finished++] = u;
                }
            }
        }

        // Pass 2: DFS on the transpose in decreasing finish order; each tree is one SCC.
        int[] component = new int[n];
        Arrays.fill(component, -1);
        int[] grouped = new int[n]; // vertices listed component by component
        int groupedCount = 0;
        int labels = 0;
        for (int i = n - 1; i >= 0; i--) {
            int root = finish[i];
            if (component[root] != -1) {
                continue;
            }
            int label = labels++;
            int sp = 0;
            stack[sp++] = root;
            component[root] = label;
            while (sp > 0) {
                int u = stack[--sp];
                grouped[groupedCount++] = u;
                for (int p = tStart[u]; p < tStart[u + 1]; p++) {
                    int w = edges[tAdj[p]][0];
                    if (component[w] == -1) {
                        component[w] = label;
                        stack[sp++] = w;
                    }
                }
            }
        }

        // Condensation: scan the vertices of one component at a time (they are contiguous
        // in "grouped"); a per-target stamp removes duplicate pairs in O(n + m).
        int[] stamp = new int[labels];
        Arrays.fill(stamp, -1);
        int[][] pairs = new int[edges.length][]; // at most one distinct pair per input edge
        int pairCount = 0;
        for (int i = 0; i < n; i++) {
            int u = grouped[i];
            int from = component[u];
            for (int p = fStart[u]; p < fStart[u + 1]; p++) {
                int to = component[edges[fAdj[p]][1]];
                if (to != from && stamp[to] != from) {
                    stamp[to] = from;
                    pairs[pairCount++] = new int[] {from, to};
                }
            }
        }

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("component", component);
        result.put("condensation", Arrays.copyOf(pairs, pairCount));
        return result;
    }

    // ------------------------------------------------------------------
    // Topological order (three-state DFS)
    // ------------------------------------------------------------------

    /** Three-state DFS and reverse finish order; return acyclic and order. */
    static Map<String, Object> topo(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int[][] edges = Input.edges(input);

        int[][] forward = buildAdjacency(n, edges, false);
        int[] order = topologicalOrder(n, edges, forward[0], forward[1]);

        Map<String, Object> result = new LinkedHashMap<>();
        result.put("acyclic", order != null);
        result.put("order", order != null ? order : new int[0]);
        return result;
    }

    /**
     * Three-state iterative DFS over all components. Returns the vertices in reverse
     * finish order, or null as soon as an edge to an active (grey) vertex is found.
     * States: 0 = unvisited, 1 = active (on the DFS stack), 2 = finished.
     */
    private static int[] topologicalOrder(int n, int[][] edges, int[] start, int[] adj) {
        byte[] state = new byte[n];
        int[] next = Arrays.copyOf(start, n);
        int[] stack = new int[n];
        int[] order = new int[n];
        int filled = n; // order is filled from the back: last finished -> position 0

        for (int s = 0; s < n; s++) {
            if (state[s] != 0) {
                continue;
            }
            int sp = 0;
            stack[sp++] = s;
            state[s] = 1;
            while (sp > 0) {
                int u = stack[sp - 1];
                if (next[u] < start[u + 1]) {
                    int v = edges[adj[next[u]++]][1];
                    if (state[v] == 1) {
                        return null; // back edge (a self-loop included): directed cycle
                    }
                    if (state[v] == 0) {
                        state[v] = 1;
                        stack[sp++] = v;
                    }
                    // state 2: forward/cross edge, not a cycle
                } else {
                    state[u] = 2;
                    sp--;
                    order[--filled] = u;
                }
            }
        }
        return order;
    }

    // ------------------------------------------------------------------
    // DAG shortest paths
    // ------------------------------------------------------------------

    /** Whole-graph cycle check and DAG relaxation; return acyclic, distance, parent_edge. */
    static Map<String, Object> dag(Map<String, Object> input) {
        int n = Input.vertexCount(input);
        int source = Input.source(input);
        int[][] edges = Input.edges(input);

        int[][] forward = buildAdjacency(n, edges, false);
        int[] start = forward[0];
        int[] adj = forward[1];

        // The cycle check covers the whole graph, also parts unreachable from the source.
        int[] order = topologicalOrder(n, edges, start, adj);

        Map<String, Object> result = new LinkedHashMap<>();
        if (order == null) {
            result.put("acyclic", false);
            result.put("distance", new long[0]);
            result.put("parent_edge", new int[0]);
            return result;
        }

        long[] dist = new long[n];
        boolean[] reached = new boolean[n];
        int[] parentEdge = new int[n];
        Arrays.fill(parentEdge, -1);
        reached[source] = true;
        dist[source] = 0;

        for (int i = 0; i < n; i++) {
            int u = order[i];
            if (!reached[u]) {
                continue; // never relax from an unreachable vertex
            }
            for (int p = start[u]; p < start[u + 1]; p++) {
                int id = adj[p];
                int v = edges[id][1];
                long candidate = dist[u] + edges[id][2];
                if (!reached[v] || candidate < dist[v]) {
                    reached[v] = true;
                    dist[v] = candidate;
                    parentEdge[v] = id;
                }
            }
        }

        Long[] distance = new Long[n];
        for (int v = 0; v < n; v++) {
            distance[v] = reached[v] ? Long.valueOf(dist[v]) : null;
        }
        result.put("acyclic", true);
        result.put("distance", distance);
        result.put("parent_edge", parentEdge);
        return result;
    }

    /**
     * Route-reconstruction helper (not a JSON task). Rebuilds the vertex sequence
     * source -> ... -> target by walking parent_edge from the target back to the source.
     *
     * Contract: the route to the source itself is [source]. If the target is unreachable
     * (parent_edge is -1 for a non-source vertex), or the arrays are empty (cyclic graph),
     * or parentEdge is inconsistent, the no-route result is an EMPTY array.
     * Runs in O(L) time and output space for a route with L vertices.
     */
    static int[] route(int source, int target, int[] parentEdge, int[][] edges) {
        int n = parentEdge.length;
        if (target < 0 || target >= n || source < 0 || source >= n) {
            return new int[0];
        }
        if (target == source) {
            return new int[] {source};
        }
        int[] reversed = new int[n + 1];
        int length = 0;
        int v = target;
        while (v != source) {
            int id = parentEdge[v];
            // Guard: missing parent, an edge that does not end at v, or a corrupt cycle.
            if (id < 0 || id >= edges.length || edges[id][1] != v || length >= n) {
                return new int[0];
            }
            reversed[length++] = v;
            v = edges[id][0];
        }
        reversed[length++] = source;
        int[] path = new int[length];
        for (int i = 0; i < length; i++) {
            path[i] = reversed[length - 1 - i];
        }
        return path;
    }
}