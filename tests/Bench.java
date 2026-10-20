import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Random;

/**
 * Kruskal vs Prim benchmark on the SAME graphs at three sizes.
 *   javac -d build src/Java/*.java tests/Bench.java
 *   java -cp build Bench
 *
 * Timing boundary (identical for both methods): one call Algorithms.kruskal(request) or
 * Algorithms.prim(request), i.e. Input conversion + algorithm + building the result map.
 * Excluded: compilation, graph generation, JSON parsing and printing.
 * Timer: System.nanoTime(). Warm-up: 30 untimed calls per method and size. 9 timed calls per method.
 * The two methods are timed alternately (K, P, K, P, ...) so drift affects both equally.
 */
public final class Bench {
    private static final long SEED = 20261020L;
    private static final int WARMUP = 30;
    private static final int RUNS = 9;

    private static Map<String, Object> request(String task, int n, int[][] edges) {
        List<Object> rows = new ArrayList<>(edges.length);
        for (int[] e : edges) {
            List<Object> row = new ArrayList<>(3);
            row.add((long) e[0]);
            row.add((long) e[1]);
            row.add((long) e[2]);
            rows.add(row);
        }
        Map<String, Object> req = new LinkedHashMap<>();
        req.put("task", task);
        req.put("n", (long) n);
        req.put("edges", rows);
        return req;
    }

    private static int[][] generate(int n, int m, long seed) {
        Random rng = new Random(seed);
        int[][] edges = new int[m][];
        for (int i = 0; i < m; i++) {
            edges[i] = new int[] {rng.nextInt(n), rng.nextInt(n), (int) (rng.nextInt(2_000_000_001) - 1_000_000_000L)};
        }
        return edges;
    }

    /** Independent verification: valid forest (no loops/repeats/cycles), n-c edges, cost matches. */
    private static long verify(int n, int[][] edges, Map<String, Object> out) {
        int[] ids = (int[]) out.get("edge_ids");
        long cost = (Long) out.get("cost");
        int components = (Integer) out.get("components");
        int[] parent = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        int c = n;
        for (int[] e : edges) {
            int a = find(parent, e[0]), b = find(parent, e[1]);
            if (a != b) { parent[a] = b; c--; }
        }
        if (components != c || ids.length != n - c) throw new AssertionError("component/edge count");
        for (int i = 0; i < n; i++) parent[i] = i;
        boolean[] used = new boolean[edges.length];
        long sum = 0;
        for (int id : ids) {
            if (used[id] || edges[id][0] == edges[id][1]) throw new AssertionError("repeat or loop");
            used[id] = true;
            int a = find(parent, edges[id][0]), b = find(parent, edges[id][1]);
            if (a == b) throw new AssertionError("cycle");
            parent[a] = b;
            sum += edges[id][2];
        }
        if (sum != cost) throw new AssertionError("cost field");
        return cost;
    }

    private static int find(int[] p, int x) {
        while (p[x] != x) { p[x] = p[p[x]]; x = p[x]; }
        return x;
    }

    private static double medianMs(long[] nanos) {
        long[] s = nanos.clone();
        Arrays.sort(s);
        return s[s.length / 2] / 1e6;
    }

    private static String list(long[] nanos) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < nanos.length; i++) {
            sb.append(i > 0 ? ", " : "").append(String.format("%.2f", nanos[i] / 1e6));
        }
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println("java.version=" + System.getProperty("java.version") + " vm=" + System.getProperty("java.vm.name")
                + " os=" + System.getProperty("os.name") + " arch=" + System.getProperty("os.arch")
                + " cpus=" + Runtime.getRuntime().availableProcessors()
                + " maxHeapMB=" + Runtime.getRuntime().maxMemory() / (1024 * 1024));
        System.out.println("seed=" + SEED + " warmup=" + WARMUP + " timed runs=" + RUNS + " timer=System.nanoTime (ms below)");
        int[][] sizes = {{10_000, 25_000}, {50_000, 125_000}, {100_000, 250_000}};
        for (int[] size : sizes) {
            int n = size[0], m = size[1];
            int[][] edges = generate(n, m, SEED + n);
            Map<String, Object> kReq = request("kruskal", n, edges);
            Map<String, Object> pReq = request("prim", n, edges);

            long kCost = verify(n, edges, Algorithms.kruskal(kReq));
            long pCost = verify(n, edges, Algorithms.prim(pReq));
            if (kCost != pCost) throw new AssertionError("Kruskal and Prim disagree on cost");
            int comps = (Integer) Algorithms.kruskal(kReq).get("components");

            for (int i = 0; i < WARMUP; i++) {
                Algorithms.kruskal(kReq);
                Algorithms.prim(pReq);
            }
            long[] kt = new long[RUNS], pt = new long[RUNS];
            for (int i = 0; i < RUNS; i++) {
                long t0 = System.nanoTime();
                Algorithms.kruskal(kReq);
                kt[i] = System.nanoTime() - t0;
                t0 = System.nanoTime();
                Algorithms.prim(pReq);
                pt[i] = System.nanoTime() - t0;
            }
            System.out.println();
            System.out.println("n=" + n + " m=" + m + " components=" + comps + " optimal cost=" + kCost + " (Kruskal == Prim, forests verified)");
            System.out.println("  Kruskal ms: [" + list(kt) + "]  median " + String.format("%.2f", medianMs(kt)));
            System.out.println("  Prim    ms: [" + list(pt) + "]  median " + String.format("%.2f", medianMs(pt)));
        }
    }
}
