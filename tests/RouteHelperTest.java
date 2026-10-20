    import java.util.Arrays;
import java.util.List;
import java.util.Map;

/**
 * Tests for Algorithms.route(...). Compile and run from the repository root:
 *   javac -d build src/Java/*.java tests/RouteHelperTest.java
 *   java -cp build RouteHelperTest
 * The class is in the default package, like Algorithms, so it can call the package-private methods.
 */
public final class RouteHelperTest {
    private static int failures = 0;

    private static Map<String, Object> request(int n, int source, int[][] edges) {
        java.util.List<Object> rows = new java.util.ArrayList<>();
        for (int[] e : edges) {
            java.util.List<Object> row = new java.util.ArrayList<>();
            for (int x : e) {
                row.add((long) x);
            }
            rows.add(row);
        }
        Map<String, Object> req = new java.util.LinkedHashMap<>();
        req.put("task", "dag");
        req.put("n", (long) n);
        req.put("source", (long) source);
        req.put("edges", rows);
        return req;
    }

    private static void expect(boolean condition, String message) {
        if (!condition) {
            failures++;
            System.out.println("  FAIL: " + message);
        }
    }

    /** Sum of weights along the route, using the edge IDs from parent_edge. Verifies direction. */
    private static long verifyRoute(int[] route, int[] parent, int[][] edges, int source, int target) {
        expect(route[0] == source && route[route.length - 1] == target, "route endpoints");
        long total = 0;
        for (int i = 1; i < route.length; i++) {
            int id = parent[route[i]];
            expect(edges[id][0] == route[i - 1] && edges[id][1] == route[i], "edge " + id + " must go " + route[i - 1] + "->" + route[i]);
            total += edges[id][2];
        }
        return total;
    }

    private static void show(String label, int target, int[] route, int[] parent, long cost) {
        StringBuilder ids = new StringBuilder("[");
        for (int i = 1; i < route.length; i++) {
            ids.append(i > 1 ? "," : "").append(parent[route[i]]);
        }
        ids.append("]");
        System.out.println("  " + label + ": route(target=" + target + ") = " + Arrays.toString(route)
                + ", edge IDs " + ids + ", route cost " + cost);
    }

    public static void main(String[] args) {
        System.out.println("== README example: n=5 source=0 ==");
        int[][] edges = {{0, 1, 3}, {0, 2, 8}, {1, 2, -7}, {2, 3, 4}};
        Map<String, Object> result = Algorithms.dag(request(5, 0, edges));
        int[] parent = (int[]) result.get("parent_edge");
        Long[] distance = (Long[]) result.get("distance");
        System.out.println("  parent_edge = " + Arrays.toString(parent) + ", distance = " + Arrays.toString(distance));

        int[] toThree = Algorithms.route(0, 3, parent, edges);
        long cost = verifyRoute(toThree, parent, edges, 0, 3);
        show("reachable target 3", 3, toThree, parent, cost);
        expect(Arrays.equals(toThree, new int[] {0, 1, 2, 3}), "route to 3 must be [0,1,2,3]");
        expect(cost == 0 && cost == distance[3], "cost of route to 3 must equal distance 0");

        int[] toSource = Algorithms.route(0, 0, parent, edges);
        System.out.println("  source: route(target=0) = " + Arrays.toString(toSource));
        expect(Arrays.equals(toSource, new int[] {0}), "route to the source is [source]");

        int[] toTwo = Algorithms.route(0, 2, parent, edges);
        cost = verifyRoute(toTwo, parent, edges, 0, 2);
        show("reachable target 2 (negative edge wins over direct 8)", 2, toTwo, parent, cost);
        expect(Arrays.equals(toTwo, new int[] {0, 1, 2}) && cost == -4 && cost == distance[2], "route to 2 is [0,1,2], cost -4");

        int[] unreachable = Algorithms.route(0, 4, parent, edges);
        System.out.println("  unreachable target 4: route = " + Arrays.toString(unreachable) + "  (no-route result = empty array)");
        expect(unreachable.length == 0 && distance[4] == null, "unreachable target gives an empty array");

        System.out.println("== Tied and parallel edges: n=3 source=0 ==");
        int[][] tied = {{0, 1, 4}, {0, 1, 4}, {0, 1, 5}, {1, 2, 0}, {0, 2, 4}};
        Map<String, Object> r2 = Algorithms.dag(request(3, 0, tied));
        int[] p2 = (int[]) r2.get("parent_edge");
        Long[] d2 = (Long[]) r2.get("distance");
        System.out.println("  parent_edge = " + Arrays.toString(p2) + ", distance = " + Arrays.toString(d2));
        int[] r1 = Algorithms.route(0, 1, p2, tied);
        long c1 = verifyRoute(r1, p2, tied, 0, 1);
        show("parallel edges 0->1 (ids 0,1 weight 4; id 2 weight 5)", 1, r1, p2, c1);
        expect(Arrays.equals(r1, new int[] {0, 1}) && c1 == 4 && (p2[1] == 0 || p2[1] == 1), "parent of 1 is one of the weight-4 parallel edges");
        int[] rr2 = Algorithms.route(0, 2, p2, tied);
        long c2 = verifyRoute(rr2, p2, tied, 0, 2);
        show("tied routes to 2 (0->1->2 and direct 0->2, both cost 4)", 2, rr2, p2, c2);
        expect((Arrays.equals(rr2, new int[] {0, 1, 2}) || Arrays.equals(rr2, new int[] {0, 2})) && c2 == 4, "either tied route is valid, total cost 4");

        System.out.println("== Source in the middle: n=4 source=2 ==");
        int[][] mid = {{0, 2, 1}, {1, 2, 1}, {2, 3, 5}, {0, 3, -100}};
        Map<String, Object> r3 = Algorithms.dag(request(4, 2, mid));
        int[] p3 = (int[]) r3.get("parent_edge");
        System.out.println("  parent_edge = " + Arrays.toString(p3) + ", distance = " + Arrays.toString((Long[]) r3.get("distance")));
        int[] a = Algorithms.route(2, 3, p3, mid);
        show("reachable target 3", 3, a, p3, verifyRoute(a, p3, mid, 2, 3));
        expect(Arrays.equals(a, new int[] {2, 3}), "route 2->3");
        int[] b = Algorithms.route(2, 0, p3, mid);
        System.out.println("  unreachable target 0 (edge 0->2 points INTO the source): route = " + Arrays.toString(b));
        expect(b.length == 0, "vertex 0 is not reachable from 2");

        System.out.println("== Defensive cases ==");
        Map<String, Object> cyc = Algorithms.dag(request(3, 0, new int[][] {{0, 1, 1}, {1, 2, 1}, {2, 1, 1}}));
        int[] none = Algorithms.route(0, 2, (int[]) cyc.get("parent_edge"), new int[][] {{0, 1, 1}, {1, 2, 1}, {2, 1, 1}});
        System.out.println("  cyclic graph (parent_edge empty): route = " + Arrays.toString(none));
        expect(none.length == 0, "cyclic graph gives no route");
        int[] corrupt = Algorithms.route(0, 2, new int[] {-1, 2, 1}, new int[][] {{0, 1, 1}, {1, 2, 1}, {2, 1, 1}});
        System.out.println("  corrupt parent cycle 1<->2: route = " + Arrays.toString(corrupt));
        expect(corrupt.length == 0, "corrupt parent cycle must not loop forever");
        int[] wrongDir = Algorithms.route(0, 1, new int[] {-1, 1}, new int[][] {{0, 1, 1}, {1, 0, 1}});
        System.out.println("  parent edge that does not end at the vertex: route = " + Arrays.toString(wrongDir));
        expect(wrongDir.length == 0, "edge id 1 is 1->0, does not end at vertex 1");

        System.out.println("== Long chain (n=100000) ==");
        int n = 100_000;
        int[][] chain = new int[n - 1][];
        for (int i = 0; i < n - 1; i++) {
            chain[i] = new int[] {i, i + 1, 1_000_000_000};
        }
        Map<String, Object> big = Algorithms.dag(request(n, 0, chain));
        int[] pb = (int[]) big.get("parent_edge");
        int[] full = Algorithms.route(0, n - 1, pb, chain);
        long total = verifyRoute(full, pb, chain, 0, n - 1);
        System.out.println("  route length " + full.length + ", total weight " + total + ", distance " + ((Long[]) big.get("distance"))[n - 1]);
        expect(full.length == n && total == 99_999L * 1_000_000_000L && total == ((Long[]) big.get("distance"))[n - 1], "full chain route");

        System.out.println(failures == 0 ? "ALL ROUTE-HELPER CHECKS PASSED" : failures + " CHECK(S) FAILED");
        if (failures != 0) {
            System.exit(1);
        }
    }
}
