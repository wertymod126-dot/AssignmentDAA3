#!/usr/bin/env python3
"""Own tests for Assignment 3 (Java solution).

Run from the repository root:
    javac -d build src/Java/*.java
    python3 tests/run_tests.py

What it does
  1. Self-checks the *oracles* (independent Python algorithms) against brute force.
  2. Self-checks the *validators*: they must accept alternative valid answers and
     reject invalid witnesses.
  3. Runs hand-made cases with hand-justified expected answers.
  4. Runs seeded random small cases (loops, parallel edges, negative weights ...).
  5. Runs full-limit and deep-chain cases.
  6. Repeats mixed requests in one process to check that state is reset.

Everything the solution prints is validated semantically, so any valid optimal
forest / SCC labelling / topological order / shortest-path witness is accepted.
It writes tests/my_cases.jsonl, tests/actual_outputs.jsonl and tests/results.txt.
"""
import itertools
import json
import os
import random
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD = os.path.join(ROOT, "build")
TESTS = os.path.join(ROOT, "tests")
LOG = []


def log(line=""):
    print(line)
    LOG.append(line)


# ----------------------------------------------------------------------------
# Running the Java program (JSON Lines, one process per batch)
# ----------------------------------------------------------------------------
def run_java(requests):
    payload = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in requests)
    started = time.perf_counter()
    proc = subprocess.run(["java", "-cp", BUILD, "Main"], input=payload,
                          capture_output=True, text=True, timeout=120)
    elapsed = time.perf_counter() - started
    if proc.returncode != 0 or proc.stderr.strip():
        raise RuntimeError("java failed: rc=%s stderr=%s" % (proc.returncode, proc.stderr[:2000]))
    lines = proc.stdout.splitlines()
    if len(lines) != len(requests):
        raise RuntimeError("expected %d output lines, got %d" % (len(requests), len(lines)))
    return [json.loads(x) for x in lines], elapsed


# ----------------------------------------------------------------------------
# Independent oracles (different code and different algorithms than the solution)
# ----------------------------------------------------------------------------
def is_int(x):
    return isinstance(x, int) and not isinstance(x, bool)


def dsu_oracle(n, ops):
    parent = list(range(n))
    size = [1] * n
    comps, largest, states = n, (1 if n else 0), []

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path halving
            x = parent[x]
        return x

    for u, v in ops:
        a, b = find(u), find(v)
        if a != b:
            if size[a] < size[b]:
                a, b = b, a
            parent[b] = a
            size[a] += size[b]
            comps -= 1
            largest = max(largest, size[a])
        states.append([comps, largest])
    return states


def dsu_brute(n, ops):
    label = list(range(n))
    states = []
    for u, v in ops:
        a, b = label[u], label[v]
        if a != b:
            label = [a if x == b else x for x in label]
        counts = {}
        for x in label:
            counts[x] = counts.get(x, 0) + 1
        states.append([len(counts), max(counts.values()) if counts else 0])
    return states


def components_count(n, edges):
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    c = n
    for e in edges:
        a, b = find(e[0]), find(e[1])
        if a != b:
            parent[a] = b
            c -= 1
    return c


def mst_oracle(n, edges):
    """Python Kruskal: returns (cost, components)."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    cost, comps = 0, n
    for u, v, w in sorted(edges, key=lambda e: e[2]):
        a, b = find(u), find(v)
        if a != b:
            parent[a] = b
            cost += w
            comps -= 1
    return cost, comps


def mst_brute(n, edges):
    """Enumerate every edge subset of the right size; tiny graphs only."""
    comps = components_count(n, edges)
    need = n - comps
    best = None
    for combo in itertools.combinations(range(len(edges)), need):
        parent = list(range(n))

        def find(x):
            while parent[x] != x:
                x = parent[x]
            return x

        ok, cost = True, 0
        for i in combo:
            u, v, w = edges[i]
            a, b = find(u), find(v)
            if a == b:
                ok = False
                break
            parent[a] = b
            cost += w
        if ok and (best is None or cost < best):
            best = cost
    return (best if best is not None else 0), comps


def tarjan(n, edges):
    """Iterative Tarjan SCC (different algorithm from Kosaraju)."""
    adj = [[] for _ in range(n)]
    for u, v in edges:
        adj[u].append(v)
    index = [-1] * n
    low = [0] * n
    on_stack = [False] * n
    comp = [-1] * n
    stack, counter, labels = [], 0, 0
    for s in range(n):
        if index[s] != -1:
            continue
        work = [(s, 0)]
        index[s] = low[s] = counter
        counter += 1
        stack.append(s)
        on_stack[s] = True
        while work:
            u, i = work.pop()
            if i < len(adj[u]):
                work.append((u, i + 1))
                v = adj[u][i]
                if index[v] == -1:
                    index[v] = low[v] = counter
                    counter += 1
                    stack.append(v)
                    on_stack[v] = True
                    work.append((v, 0))
                elif on_stack[v]:
                    low[u] = min(low[u], index[v])
            else:
                if low[u] == index[u]:
                    while True:
                        w = stack.pop()
                        on_stack[w] = False
                        comp[w] = labels
                        if w == u:
                            break
                    labels += 1
                if work:
                    p = work[-1][0]
                    low[p] = min(low[p], low[u])
    return comp


def scc_brute(n, edges):
    reach = [[i == j for j in range(n)] for i in range(n)]
    for u, v in edges:
        reach[u][v] = True
    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                for j in range(n):
                    if reach[k][j]:
                        reach[i][j] = True
    comp, labels = [-1] * n, 0
    for i in range(n):
        if comp[i] == -1:
            for j in range(n):
                if reach[i][j] and reach[j][i]:
                    comp[j] = labels
            labels += 1
    return comp


def kahn(n, edges):
    """Kahn's algorithm: returns an order, or None when a directed cycle exists."""
    adj = [[] for _ in range(n)]
    indeg = [0] * n
    for e in edges:
        adj[e[0]].append(e[1])
        indeg[e[1]] += 1
    queue = [v for v in range(n) if indeg[v] == 0]
    head = 0
    while head < len(queue):
        u = queue[head]
        head += 1
        for v in adj[u]:
            indeg[v] -= 1
            if indeg[v] == 0:
                queue.append(v)
    return queue if len(queue) == n else None


def dag_oracle(n, source, edges):
    """Returns (acyclic, distances with None for unreachable)."""
    order = kahn(n, edges)
    if order is None:
        return False, None
    adj = [[] for _ in range(n)]
    for u, v, w in edges:
        adj[u].append((v, w))
    dist = [None] * n
    dist[source] = 0
    for u in order:
        if dist[u] is None:
            continue
        for v, w in dist_edges(adj, u):
            if dist[v] is None or dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    return True, dist


def dist_edges(adj, u):
    return adj[u]


def dag_brute(n, source, edges):
    """Bellman-Ford with explicit cycle test through transitive closure."""
    reach = [[False] * n for _ in range(n)]
    for e in edges:
        reach[e[0]][e[1]] = True
    for k in range(n):
        for i in range(n):
            if reach[i][k]:
                for j in range(n):
                    if reach[k][j]:
                        reach[i][j] = True
    if any(reach[i][i] for i in range(n)):
        return False, None
    inf = float("inf")
    dist = [inf] * n
    dist[source] = 0
    for _ in range(n):
        for u, v, w in edges:
            if dist[u] != inf and dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    return True, [None if d == inf else d for d in dist]


# ----------------------------------------------------------------------------
# Validators: return a list of error strings (empty list = valid answer)
# ----------------------------------------------------------------------------
def check_dsu(req, out):
    exp = dsu_oracle(req["n"], req["operations"])
    return [] if out.get("states") == exp else ["states differ from oracle"]


def check_forest(req, out):
    n, edges = req["n"], req["edges"]
    cost, comps = mst_oracle(n, edges)
    ids = out.get("edge_ids")
    if not isinstance(ids, list) or not all(is_int(i) for i in ids):
        return ["edge_ids is not a list of ints"]
    if out.get("components") != comps:
        return ["components %r != %r" % (out.get("components"), comps)]
    if len(ids) != len(set(ids)):
        return ["repeated edge id"]
    if any(i < 0 or i >= len(edges) for i in ids):
        return ["edge id out of range"]
    if len(ids) != n - comps:
        return ["forest must have n-c=%d edges, got %d" % (n - comps, len(ids))]
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    total = 0
    for i in ids:
        u, v, w = edges[i]
        if u == v:
            return ["self-loop selected"]
        a, b = find(u), find(v)
        if a == b:
            return ["selected edges contain a cycle"]
        parent[a] = b
        total += w
    if out.get("cost") != total:
        return ["cost %r != sum of selected weights %r" % (out.get("cost"), total)]
    if total != cost:
        return ["not optimal: %d vs optimum %d" % (total, cost)]
    return []


def check_scc(req, out, reference=None):
    n, edges = req["n"], req["edges"]
    comp, cond = out.get("component"), out.get("condensation")
    if not isinstance(comp, list) or len(comp) != n or not all(is_int(c) and c >= 0 for c in comp):
        return ["component must be n non-negative ints"]
    ref = reference if reference is not None else tarjan(n, edges)
    fwd, bwd = {}, {}
    for a, b in zip(comp, ref):
        if fwd.setdefault(a, b) != b or bwd.setdefault(b, a) != a:
            return ["partition into SCCs is wrong"]
    if not isinstance(cond, list) or not all(isinstance(p, list) and len(p) == 2 and
                                             is_int(p[0]) and is_int(p[1]) for p in cond):
        return ["condensation must be a list of [from,to] pairs"]
    got = [tuple(p) for p in cond]
    if len(got) != len(set(got)):
        return ["duplicate condensation pair"]
    expected = {(comp[u], comp[v]) for u, v in edges if comp[u] != comp[v]}
    if set(got) != expected:
        return ["condensation differs: missing=%d extra=%d" % (
            len(expected - set(got)), len(set(got) - expected))]
    return []


def check_topo(req, out):
    n, edges = req["n"], req["edges"]
    acyclic = kahn(n, edges) is not None
    if out.get("acyclic") is not acyclic:
        return ["acyclic flag should be %r" % acyclic]
    order = out.get("order")
    if not acyclic:
        return [] if order == [] else ["order must be empty for a cyclic graph"]
    if not isinstance(order, list) or sorted(order) != list(range(n)):
        return ["order is not a permutation of all vertices"]
    pos = [0] * n
    for i, v in enumerate(order):
        pos[v] = i
    for u, v in edges:
        if pos[u] >= pos[v]:
            return ["edge %d->%d goes backward" % (u, v)]
    return []


def check_dag(req, out):
    n, source, edges = req["n"], req["source"], req["edges"]
    acyclic, dist = dag_oracle(n, source, edges)
    if out.get("acyclic") is not acyclic:
        return ["acyclic flag should be %r" % acyclic]
    if not acyclic:
        if out.get("distance") != [] or out.get("parent_edge") != []:
            return ["cyclic graph must return two empty arrays"]
        return []
    d, p = out.get("distance"), out.get("parent_edge")
    if not isinstance(d, list) or not isinstance(p, list) or len(d) != n or len(p) != n:
        return ["distance/parent_edge must have length n"]
    if d != dist:
        return ["distance differs from oracle"]
    for v in range(n):
        if not is_int(p[v]):
            return ["parent_edge entries must be ints"]
        if v == source:
            if p[v] != -1 or d[v] != 0:
                return ["source must have distance 0 and parent -1"]
        elif d[v] is None:
            if p[v] != -1:
                return ["unreachable vertex %d must have parent -1" % v]
        else:
            if not 0 <= p[v] < len(edges):
                return ["parent edge id out of range at %d" % v]
            u, t, w = edges[p[v]]
            if t != v:
                return ["parent edge of %d does not end at %d" % (v, v)]
            if d[u] is None or d[u] + w != d[v]:
                return ["parent edge of %d is not on a shortest path" % v]
    return []  # DAG + strict parent chain => following parents reaches the source


CHECKERS = {"dsu": check_dsu, "kruskal": check_forest, "prim": check_forest,
            "scc": check_scc, "topo": check_topo, "dag": check_dag}


# ----------------------------------------------------------------------------
# Part 1/2: meta-tests of the oracles and of the validators
# ----------------------------------------------------------------------------
def rand_edges(rng, n, m, wlo=None, whi=None, loops=True):
    out = []
    for _ in range(m):
        u, v = rng.randrange(n), rng.randrange(n)
        while not loops and n > 1 and u == v:
            v = rng.randrange(n)
        e = [u, v]
        if wlo is not None:
            e.append(rng.randint(wlo, whi))
        out.append(e)
    return out


def meta_tests():
    rng = random.Random(12345)
    log("== Meta-tests: oracles vs brute force ==")
    for _ in range(400):
        n = rng.randint(0, 6)
        m = rng.randint(0, 8) if n else 0
        ops = rand_edges(rng, n, rng.randint(0, 8)) if n else []
        assert dsu_oracle(n, ops) == dsu_brute(n, ops), (n, ops)
        wedges = rand_edges(rng, n, m, -4, 4) if n else []
        assert mst_oracle(n, wedges) == mst_brute(n, wedges), (n, wedges)
        edges = rand_edges(rng, n, m) if n else []
        a, b = tarjan(n, edges), scc_brute(n, edges)
        assert check_scc({"n": n, "edges": edges}, {"component": a, "condensation": [
            list(p) for p in {(a[u], a[v]) for u, v in edges if a[u] != a[v]}]}, reference=b) == []
        assert (kahn(n, edges) is not None) == (dag_brute(max(n, 1), 0, [e + [0] for e in edges])[0]
                                                if n else True)
        if n:
            wd = rand_edges(rng, n, m, -6, 6)
            assert dag_oracle(n, 0, wd) == dag_brute(n, 0, wd), (n, wd)
    log("  400 random tiny graphs: DSU, MST, SCC, cycle test and DAG distances agree with brute force")


def expect_reject(name, errs):
    assert errs, "validator accepted an invalid witness: " + name
    log("  rejected  %-44s -> %s" % (name, errs[0]))


def expect_accept(name, errs):
    assert not errs, "validator rejected a valid alternative: %s: %s" % (name, errs)
    log("  accepted  %s" % name)


def validator_tests():
    log("== Meta-tests: validators accept alternatives and reject invalid witnesses ==")
    # Forest: triangle with equal weights has three different optimal forests.
    req = {"task": "kruskal", "n": 3, "edges": [[0, 1, 1], [1, 2, 1], [0, 2, 1]]}
    for ids in ([0, 1], [1, 2], [0, 2]):
        expect_accept("forest ids %s" % ids, check_forest(req, {"cost": 2, "edge_ids": ids, "components": 1}))
    expect_reject("forest with duplicate id", check_forest(req, {"cost": 2, "edge_ids": [0, 0], "components": 1}))
    expect_reject("forest too small", check_forest(req, {"cost": 1, "edge_ids": [0], "components": 1}))
    expect_reject("forest wrong cost field", check_forest(req, {"cost": 3, "edge_ids": [0, 1], "components": 1}))
    expect_reject("forest wrong component count", check_forest(req, {"cost": 2, "edge_ids": [0, 1], "components": 2}))
    req2 = {"task": "prim", "n": 3, "edges": [[0, 1, 1], [0, 1, 5], [1, 2, 2], [2, 2, -9]]}
    expect_accept("optimal forest ignoring negative loop", check_forest(req2, {"cost": 3, "edge_ids": [0, 2], "components": 1}))
    expect_reject("non-optimal forest (heavier parallel edge)", check_forest(req2, {"cost": 7, "edge_ids": [1, 2], "components": 1}))
    expect_reject("forest using the self-loop", check_forest(req2, {"cost": -7, "edge_ids": [0, 3], "components": 1}))
    req3 = {"task": "kruskal", "n": 4, "edges": [[0, 1, 1], [1, 2, 1], [0, 2, 1], [2, 3, 1]]}
    expect_reject("forest containing a cycle", check_forest(req3, {"cost": 3, "edge_ids": [0, 1, 2], "components": 1}))

    # SCC: relabelled answer is valid; wrong partitions / condensations are not.
    sreq = {"task": "scc", "n": 4, "edges": [[0, 1], [1, 0], [1, 2], [0, 2], [2, 3]]}
    expect_accept("scc labels [5,5,7,9] (README answer)", check_scc(sreq, {"component": [5, 5, 7, 9], "condensation": [[5, 7], [7, 9]]}))
    expect_accept("scc labels permuted", check_scc(sreq, {"component": [2, 2, 0, 1], "condensation": [[2, 0], [0, 1]]}))
    expect_reject("scc merged two components", check_scc(sreq, {"component": [0, 0, 0, 1], "condensation": [[0, 1]]}))
    expect_reject("scc split a component", check_scc(sreq, {"component": [0, 1, 2, 3], "condensation": [[0, 2], [1, 2], [2, 3]]}))
    expect_reject("scc duplicate condensation pair", check_scc(sreq, {"component": [5, 5, 7, 9], "condensation": [[5, 7], [5, 7], [7, 9]]}))
    expect_reject("scc missing condensation pair", check_scc(sreq, {"component": [5, 5, 7, 9], "condensation": [[5, 7]]}))
    expect_reject("scc internal pair included", check_scc(sreq, {"component": [5, 5, 7, 9], "condensation": [[5, 7], [7, 9], [5, 5]]}))
    expect_reject("scc reversed pair", check_scc(sreq, {"component": [5, 5, 7, 9], "condensation": [[7, 5], [7, 9]]}))

    # Topological order.
    treq = {"task": "topo", "n": 4, "edges": [[0, 2], [1, 2], [2, 3]]}
    expect_accept("topo [1,0,2,3]", check_topo(treq, {"acyclic": True, "order": [1, 0, 2, 3]}))
    expect_accept("topo alternative [0,1,2,3]", check_topo(treq, {"acyclic": True, "order": [0, 1, 2, 3]}))
    expect_reject("topo edge goes backward", check_topo(treq, {"acyclic": True, "order": [2, 0, 1, 3]}))
    expect_reject("topo missing a vertex", check_topo(treq, {"acyclic": True, "order": [0, 1, 2]}))
    expect_reject("topo says cyclic for a DAG", check_topo(treq, {"acyclic": False, "order": []}))
    creq = {"task": "topo", "n": 2, "edges": [[0, 1], [1, 0]]}
    expect_accept("topo cyclic -> false + []", check_topo(creq, {"acyclic": False, "order": []}))
    expect_reject("topo cyclic with a non-empty order", check_topo(creq, {"acyclic": False, "order": [0, 1]}))
    expect_reject("topo says acyclic for a cycle", check_topo(creq, {"acyclic": True, "order": [0, 1]}))

    # DAG shortest paths: vertex 2 has two tied shortest routes (ids 3 and 4).
    dreq = {"task": "dag", "n": 3, "source": 0,
            "edges": [[0, 1, 4], [0, 1, 4], [0, 1, 5], [1, 2, 0], [0, 2, 4]]}
    good = {"acyclic": True, "distance": [0, 4, 4], "parent_edge": [-1, 0, 3]}
    expect_accept("dag parent via tied edge ids 0 / 3", check_dag(dreq, good))
    expect_accept("dag other tied witness ids 1 / 4", check_dag(dreq, {"acyclic": True, "distance": [0, 4, 4], "parent_edge": [-1, 1, 4]}))
    expect_reject("dag parent is a heavier parallel edge", check_dag(dreq, {"acyclic": True, "distance": [0, 4, 4], "parent_edge": [-1, 2, 3]}))
    expect_reject("dag parent edge does not end at vertex", check_dag(dreq, {"acyclic": True, "distance": [0, 4, 4], "parent_edge": [-1, 0, 0]}))
    expect_reject("dag wrong distance", check_dag(dreq, {"acyclic": True, "distance": [0, 4, 5], "parent_edge": [-1, 0, 3]}))
    expect_reject("dag source with a parent", check_dag(dreq, {"acyclic": True, "distance": [0, 4, 4], "parent_edge": [0, 0, 3]}))
    ureq = {"task": "dag", "n": 3, "source": 0, "edges": [[0, 1, -1]]}
    expect_accept("dag unreachable null / -1, distance -1 valid", check_dag(ureq, {"acyclic": True, "distance": [0, -1, None], "parent_edge": [-1, 0, -1]}))
    expect_reject("dag unreachable reported as -1", check_dag(ureq, {"acyclic": True, "distance": [0, -1, -1], "parent_edge": [-1, 0, -1]}))
    expect_reject("dag unreachable with parent id", check_dag(ureq, {"acyclic": True, "distance": [0, -1, None], "parent_edge": [-1, 0, 0]}))
    cyc = {"task": "dag", "n": 4, "source": 0, "edges": [[0, 1, 1], [2, 3, 1], [3, 2, 1]]}
    expect_accept("dag cycle unreachable from source -> false", check_dag(cyc, {"acyclic": False, "distance": [], "parent_edge": []}))
    expect_reject("dag ignores unreachable cycle", check_dag(cyc, {"acyclic": True, "distance": [0, 1, None, None], "parent_edge": [-1, 0, -1, -1]}))


# ----------------------------------------------------------------------------
# Part 3: hand-made cases with hand-justified expectations
# ----------------------------------------------------------------------------
def H(name, req, expect, why):
    return {"name": name, "req": req, "expect": expect, "why": why}


def hand_cases():
    big = 1_000_000_000
    cases = []
    # DSU
    cases += [
        H("dsu README example", {"task": "dsu", "n": 4, "operations": [[0, 1], [1, 2], [0, 2], [3, 3]]},
          {"states": [[3, 2], [2, 3], [2, 3], [2, 3]]},
          "4->3 comps (size 2), 2 comps (size 3), (0,2) repeated, (3,3) self-union: nothing changes"),
        H("dsu n=0", {"task": "dsu", "n": 0, "operations": []}, {"states": []}, "no operations, no states"),
        H("dsu n=1 self-union", {"task": "dsu", "n": 1, "operations": [[0, 0]]}, {"states": [[1, 1]]},
          "one vertex: components 1, largest 1"),
        H("dsu n=3 no operations", {"task": "dsu", "n": 3, "operations": []}, {"states": []},
          "no initial state is printed"),
        H("dsu repeated and reversed unions", {"task": "dsu", "n": 5, "operations": [[0, 1], [0, 1], [1, 0], [2, 3], [1, 3], [4, 4]]},
          {"states": [[4, 2], [4, 2], [4, 2], [3, 2], [2, 4], [2, 4]]},
          "{0,1} twice more is idempotent; {2,3}; joining sizes 2+2 gives 4; self-union of 4 changes nothing"),
        H("dsu union by size", {"task": "dsu", "n": 6, "operations": [[0, 1], [2, 3], [4, 5], [0, 2], [0, 4]]},
          {"states": [[5, 2], [4, 2], [3, 2], [2, 4], [1, 6]]}, "three pairs, then 2+2=4, then 4+2=6"),
    ]
    # Kruskal / Prim
    for task in ("kruskal", "prim"):
        cases += [
            H(task + " README example", {"task": task, "n": 4, "edges": [[0, 1, 4], [1, 2, 2], [0, 2, 3]]},
              {"cost": 5, "components": 2, "count": 2}, "take 2 and 3, skip 4; vertex 3 is isolated -> 2 components"),
            H(task + " n=0", {"task": task, "n": 0, "edges": []}, {"cost": 0, "components": 0, "count": 0}, "empty graph"),
            H(task + " n=1", {"task": task, "n": 1, "edges": []}, {"cost": 0, "components": 1, "count": 0}, "single isolate"),
            H(task + " only isolates", {"task": task, "n": 3, "edges": []}, {"cost": 0, "components": 3, "count": 0}, "3 isolates"),
            H(task + " negative self-loop + parallel", {"task": task, "n": 2, "edges": [[0, 0, -5], [0, 1, 7], [0, 1, 3], [1, 0, 3]]},
              {"cost": 3, "components": 1, "count": 1}, "self-loop never chosen; cheapest 0-1 edge has weight 3 (ids 2 or 3)"),
            H(task + " negative weights", {"task": task, "n": 3, "edges": [[0, 1, -4], [1, 2, -6], [0, 2, -10]]},
              {"cost": -16, "components": 1, "count": 2}, "spanning tree needs 2 edges: -10 and -6"),
            H(task + " cost beyond 32 bits", {"task": task, "n": 4, "edges": [[0, 1, big], [1, 2, big], [2, 3, big]]},
              {"cost": 3 * big, "components": 1, "count": 3}, "3e9 does not fit int"),
            H(task + " negative cost beyond 32 bits", {"task": task, "n": 4, "edges": [[0, 1, -big], [1, 2, -big], [2, 3, -big]]},
              {"cost": -3 * big, "components": 1, "count": 3}, "-3e9 does not fit int"),
            H(task + " all ties", {"task": task, "n": 3, "edges": [[0, 1, 1], [1, 2, 1], [0, 2, 1]]},
              {"cost": 2, "components": 1, "count": 2}, "any two of the three equal edges"),
            H(task + " two trees + isolate", {"task": task, "n": 6, "edges": [[0, 1, 5], [1, 2, 1], [3, 4, 2], [0, 2, 2]]},
              {"cost": 5, "components": 3, "count": 3}, "{0,1,2}: 1+2=3, {3,4}: 2, {5} isolated -> 5"),
            H(task + " restart needed for second component", {"task": task, "n": 4, "edges": [[2, 3, -7], [0, 1, 9]]},
              {"cost": 2, "components": 2, "count": 2}, "-7 + 9, two components both must be visited"),
        ]
    # SCC
    cases += [
        H("scc README example", {"task": "scc", "n": 4, "edges": [[0, 1], [1, 0], [1, 2], [0, 2], [2, 3]]},
          {"groups": [[0, 1], [2], [3]], "cond": [[0, 1], [1, 2]]}, "{0,1} -> {2} -> {3}"),
        H("scc n=0", {"task": "scc", "n": 0, "edges": []}, {"groups": [], "cond": []}, "empty graph"),
        H("scc self-loop only", {"task": "scc", "n": 1, "edges": [[0, 0]]}, {"groups": [[0]], "cond": []}, "internal edge excluded"),
        H("scc isolates", {"task": "scc", "n": 3, "edges": []}, {"groups": [[0], [1], [2]], "cond": []}, "three singleton SCCs"),
        H("scc duplicate edges", {"task": "scc", "n": 3, "edges": [[0, 1], [0, 1], [1, 2], [1, 2], [1, 2]]},
          {"groups": [[0], [1], [2]], "cond": [[0, 1], [1, 2]]}, "duplicate cross edges give one pair each"),
        H("scc two cycles joined", {"task": "scc", "n": 5, "edges": [[0, 1], [1, 2], [2, 0], [2, 3], [3, 4], [4, 3]]},
          {"groups": [[0, 1, 2], [3, 4]], "cond": [[0, 1]]}, "3-cycle -> 2-cycle; several edges inside each"),
        H("scc diamond (no cycle)", {"task": "scc", "n": 4, "edges": [[0, 1], [0, 2], [1, 3], [2, 3]]},
          {"groups": [[0], [1], [2], [3]], "cond": [[0, 1], [0, 2], [1, 3], [2, 3]]}, "DAG: every vertex alone, 4 pairs"),
        H("scc multiple edges between two SCCs", {"task": "scc", "n": 4, "edges": [[0, 1], [1, 0], [2, 3], [3, 2], [0, 2], [1, 3], [1, 2]]},
          {"groups": [[0, 1], [2, 3]], "cond": [[0, 1]]}, "three cross edges collapse to one pair"),
    ]
    # topo
    cases += [
        H("topo README example", {"task": "topo", "n": 4, "edges": [[0, 2], [1, 2], [2, 3]]}, {"acyclic": True}, "0,1 before 2 before 3"),
        H("topo n=0", {"task": "topo", "n": 0, "edges": []}, {"acyclic": True}, "empty graph is acyclic"),
        H("topo n=1", {"task": "topo", "n": 1, "edges": []}, {"acyclic": True}, "single vertex"),
        H("topo self-loop", {"task": "topo", "n": 1, "edges": [[0, 0]]}, {"acyclic": False}, "self-loop is a cycle"),
        H("topo 2-cycle", {"task": "topo", "n": 2, "edges": [[0, 1], [1, 0]]}, {"acyclic": False}, "0->1->0"),
        H("topo cycle in a later component", {"task": "topo", "n": 5, "edges": [[0, 1], [2, 3], [3, 4], [4, 2]]},
          {"acyclic": False}, "component {2,3,4} is cyclic although {0,1} is not"),
        H("topo cross edge to finished vertex", {"task": "topo", "n": 4, "edges": [[0, 1], [0, 2], [1, 3], [2, 3]]},
          {"acyclic": True}, "second visit of 3 is an edge to a finished vertex, not a cycle"),
        H("topo forward edge to finished vertex + duplicates", {"task": "topo", "n": 3, "edges": [[0, 1], [1, 2], [0, 2], [0, 2]]},
          {"acyclic": True}, "forward and duplicate edges are fine"),
        H("topo isolates and reversed numbering", {"task": "topo", "n": 4, "edges": [[3, 2], [2, 1]]},
          {"acyclic": True}, "3,2,1 chain with isolate 0"),
    ]
    # DAG
    cases += [
        H("dag README example", {"task": "dag", "n": 5, "source": 0, "edges": [[0, 1, 3], [0, 2, 8], [1, 2, -7], [2, 3, 4]]},
          {"acyclic": True, "distance": [0, 3, -4, 0, None]}, "0->1->2->3 = 3-7+4 = 0; vertex 4 unreachable"),
        H("dag n=1", {"task": "dag", "n": 1, "source": 0, "edges": []}, {"acyclic": True, "distance": [0]}, "only the source"),
        H("dag source with unreachable predecessor", {"task": "dag", "n": 3, "source": 1, "edges": [[0, 1, 5], [1, 2, -1]]},
          {"acyclic": True, "distance": [None, 0, -1]}, "vertex 0 is not reachable from 1"),
        H("dag never relax from unreachable", {"task": "dag", "n": 4, "source": 2, "edges": [[0, 2, 1], [1, 2, 1], [2, 3, 5], [0, 3, -100]]},
          {"acyclic": True, "distance": [None, None, 0, 5]}, "0 is unreachable, so edge 0->3 (-100) must be ignored"),
        H("dag cycle unreachable from source", {"task": "dag", "n": 4, "source": 0, "edges": [[0, 1, 1], [2, 3, 1], [3, 2, 1]]},
          {"acyclic": False}, "whole-graph cycle check: 2<->3 is a cycle"),
        H("dag reachable self-loop", {"task": "dag", "n": 2, "source": 0, "edges": [[0, 0, 1]]}, {"acyclic": False}, "self-loop is a cycle"),
        H("dag self-loop on unreachable vertex", {"task": "dag", "n": 2, "source": 0, "edges": [[1, 1, -3]]}, {"acyclic": False}, "still cyclic"),
        H("dag tied and parallel edges", {"task": "dag", "n": 3, "source": 0, "edges": [[0, 1, 4], [0, 1, 4], [0, 1, 5], [1, 2, 0], [0, 2, 4]]},
          {"acyclic": True, "distance": [0, 4, 4]}, "vertex 1: 4 via ids 0/1; vertex 2: 4 via id 3 or id 4"),
        H("dag distance -1 is valid", {"task": "dag", "n": 3, "source": 0, "edges": [[0, 1, -1]]},
          {"acyclic": True, "distance": [0, -1, None]}, "-1 is a real distance; vertex 2 is null"),
        H("dag distance beyond 32 bits", {"task": "dag", "n": 5, "source": 0, "edges": [[i, i + 1, big] for i in range(4)]},
          {"acyclic": True, "distance": [0, big, 2 * big, 3 * big, 4 * big]}, "4e9 does not fit int"),
        H("dag negative distance beyond 32 bits", {"task": "dag", "n": 5, "source": 0, "edges": [[i, i + 1, -big] for i in range(4)]},
          {"acyclic": True, "distance": [0, -big, -2 * big, -3 * big, -4 * big]}, "-4e9 does not fit int"),
        H("dag source in the middle, edges both sides", {"task": "dag", "n": 5, "source": 2, "edges": [[0, 1, 1], [1, 2, 1], [2, 3, 1], [3, 4, 1]]},
          {"acyclic": True, "distance": [None, None, 0, 1, 2]}, "predecessors of the source stay unreachable"),
    ]
    return cases


def check_expectation(case, out):
    """Compare with the hand-justified expectation (independent of the oracles)."""
    task, exp = case["req"]["task"], case["expect"]
    if task == "dsu":
        return [] if out["states"] == exp["states"] else ["states %r != %r" % (out["states"], exp["states"])]
    if task in ("kruskal", "prim"):
        ok = out["cost"] == exp["cost"] and out["components"] == exp["components"] and len(out["edge_ids"]) == exp["count"]
        return [] if ok else ["got %r, expected %r" % (out, exp)]
    if task == "scc":
        comp = out["component"]
        label_of_group = {}
        covered = 0
        for gi, group in enumerate(exp["groups"]):
            labels = {comp[v] for v in group}
            if len(labels) != 1:
                return ["group %r was split" % group]
            label_of_group[labels.pop()] = gi
            covered += len(group)
        if len(label_of_group) != len(exp["groups"]):
            return ["distinct groups share a label"]
        pairs = {(label_of_group[a], label_of_group[b]) for a, b in out["condensation"]}
        want = {tuple(p) for p in exp["cond"]}
        return [] if pairs == want and len(out["condensation"]) == len(want) else ["condensation %r != %r" % (pairs, want)]
    if task == "topo":
        return [] if out["acyclic"] is exp["acyclic"] else ["acyclic should be %r" % exp["acyclic"]]
    if task == "dag":
        if out["acyclic"] is not exp["acyclic"]:
            return ["acyclic should be %r" % exp["acyclic"]]
        if exp["acyclic"] and out["distance"] != exp["distance"]:
            return ["distance %r != %r" % (out["distance"], exp["distance"])]
        return []
    raise AssertionError(task)


# ----------------------------------------------------------------------------
# Part 4: seeded random small cases
# ----------------------------------------------------------------------------
def random_small_requests(seed, per_task):
    rng = random.Random(seed)
    reqs = []
    wide = [-10 ** 9, 10 ** 9, 0, -1, 1]
    for _ in range(per_task):
        n = rng.randint(0, 9)
        q = rng.randint(0, 14) if n else 0
        reqs.append({"task": "dsu", "n": n, "operations": rand_edges(rng, n, q) if n else []})
        for task in ("kruskal", "prim"):
            m = rng.randint(0, 16) if n else 0
            edges = rand_edges(rng, n, m, -6, 6) if n else []
            if edges and rng.random() < 0.3:
                for e in edges:
                    if rng.random() < 0.4:
                        e[2] = rng.choice(wide)
            reqs.append({"task": task, "n": n, "edges": edges})
        m = rng.randint(0, 16) if n else 0
        reqs.append({"task": "scc", "n": n, "edges": rand_edges(rng, n, m) if n else []})
        # topo: half the cases are forced acyclic via a random permutation
        if n and rng.random() < 0.5:
            perm = list(range(n))
            rng.shuffle(perm)
            es = []
            for _ in range(rng.randint(0, 14)):
                a, b = sorted((rng.randrange(n), rng.randrange(n)))
                if a != b:
                    es.append([perm[a], perm[b]])
            if es and rng.random() < 0.3:
                es.append(rng.choice(es)[::-1])  # may or may not create a cycle
        else:
            es = rand_edges(rng, n, rng.randint(0, 14)) if n else []
        reqs.append({"task": "topo", "n": n, "edges": es})
        # dag
        n2 = rng.randint(1, 9)
        if rng.random() < 0.7:
            perm = list(range(n2))
            rng.shuffle(perm)
            de = []
            for _ in range(rng.randint(0, 16)):
                a, b = rng.randrange(n2), rng.randrange(n2)
                if a != b:
                    if a > b:
                        a, b = b, a
                    de.append([perm[a], perm[b], rng.randint(-8, 8)])
            if de and rng.random() < 0.15:
                de.append([rng.randrange(n2), rng.randrange(n2), 1])
        else:
            de = rand_edges(rng, n2, rng.randint(0, 12), -8, 8)
        reqs.append({"task": "dag", "n": n2, "source": rng.randrange(n2), "edges": de})
    return reqs


# ----------------------------------------------------------------------------
# Part 5: full-limit and deep cases (generated from fixed seeds)
# ----------------------------------------------------------------------------
N_MAX, M_MAX = 100_000, 250_000


def big_cases():
    rng = random.Random(2026)
    W = 10 ** 9
    cases = []

    def add(name, req):
        cases.append((name, req))

    # DSU
    add("dsu n=1e5 q=2.5e5 random", {"task": "dsu", "n": N_MAX, "operations": rand_edges(rng, N_MAX, M_MAX)})
    add("dsu n=1e5 chain unions (deep trees)", {"task": "dsu", "n": N_MAX, "operations": [[i, i + 1] for i in range(N_MAX - 1)] + [[0, N_MAX - 1]] * 3})
    add("dsu n=1e5 reverse chain", {"task": "dsu", "n": N_MAX, "operations": [[i + 1, i] for i in range(N_MAX - 2, -1, -1)]})
    # MST
    for task in ("kruskal", "prim"):
        add(task + " n=1e5 m=2.5e5 random weights +-1e9", {"task": task, "n": N_MAX, "edges": rand_edges(rng, N_MAX, M_MAX, -W, W)})
        add(task + " n=1e5 path of 1e9 (cost 99999e9)", {"task": task, "n": N_MAX, "edges": [[i, i + 1, W] for i in range(N_MAX - 1)]})
        add(task + " n=1e5 path of -1e9 + extra edges", {"task": task, "n": N_MAX,
            "edges": [[i, i + 1, -W] for i in range(N_MAX - 1)] + rand_edges(rng, N_MAX, M_MAX - N_MAX + 1, -W, W)})
        add(task + " n=1e5 m=2.5e5 sparse components, loops", {"task": task, "n": N_MAX, "edges": rand_edges(rng, 3000, M_MAX, -50, 50)})
        add(task + " n=1e5 m=2.5e5 all parallel equal", {"task": task, "n": N_MAX, "edges": [[0, 1, 7]] * M_MAX})
    # SCC
    add("scc n=1e5 chain (deep, 1e5 singletons)", {"task": "scc", "n": N_MAX, "edges": [[i, i + 1] for i in range(N_MAX - 1)]})
    add("scc n=1e5 big cycle (one giant SCC)", {"task": "scc", "n": N_MAX, "edges": [[i, (i + 1) % N_MAX] for i in range(N_MAX)]})
    add("scc n=1e5 reverse chain", {"task": "scc", "n": N_MAX, "edges": [[i + 1, i] for i in range(N_MAX - 1)]})
    add("scc n=1e5 m=2.5e5 random", {"task": "scc", "n": N_MAX, "edges": rand_edges(rng, N_MAX, M_MAX)})
    add("scc n=2 m=2.5e5 duplicates", {"task": "scc", "n": 2, "edges": [[0, 1]] * M_MAX})
    add("scc n=1e5 many 2-cycles chained", {"task": "scc", "n": N_MAX, "edges": [[2 * i, 2 * i + 1] for i in range(N_MAX // 2)] + [[2 * i + 1, 2 * i] for i in range(N_MAX // 2)] + [[2 * i + 1, 2 * i + 2] for i in range(N_MAX // 2 - 1)]})
    # topo
    perm = list(range(N_MAX))
    rng.shuffle(perm)
    dag_edges = []
    for _ in range(M_MAX):
        a, b = rng.randrange(N_MAX), rng.randrange(N_MAX)
        if a == b:
            b = (b + 1) % N_MAX
        if a > b:
            a, b = b, a
        dag_edges.append([perm[a], perm[b]])
    add("topo n=1e5 chain 0->1->...", {"task": "topo", "n": N_MAX, "edges": [[i, i + 1] for i in range(N_MAX - 1)]})
    add("topo n=1e5 reverse chain", {"task": "topo", "n": N_MAX, "edges": [[i + 1, i] for i in range(N_MAX - 1)]})
    add("topo n=1e5 chain closed into a cycle", {"task": "topo", "n": N_MAX, "edges": [[i, (i + 1) % N_MAX] for i in range(N_MAX)]})
    add("topo n=1e5 m=2.5e5 random DAG", {"task": "topo", "n": N_MAX, "edges": dag_edges})
    add("topo n=1e5 random DAG + one back edge", {"task": "topo", "n": N_MAX, "edges": dag_edges[:-1] + [[dag_edges[0][1], dag_edges[0][0]]]})
    add("topo n=1e5 star with 2.5e5 duplicate edges", {"task": "topo", "n": N_MAX, "edges": [[0, 1 + (i % (N_MAX - 1))] for i in range(M_MAX)]})
    # DAG
    add("dag n=1e5 chain 1e9 (distance ~1e14)", {"task": "dag", "n": N_MAX, "source": 0, "edges": [[i, i + 1, W] for i in range(N_MAX - 1)]})
    add("dag n=1e5 chain -1e9", {"task": "dag", "n": N_MAX, "source": 0, "edges": [[i, i + 1, -W] for i in range(N_MAX - 1)]})
    add("dag n=1e5 reverse chain, source = last", {"task": "dag", "n": N_MAX, "source": N_MAX - 1, "edges": [[i + 1, i, -W] for i in range(N_MAX - 1)]})
    add("dag n=1e5 m=2.5e5 random DAG weights +-1e9", {"task": "dag", "n": N_MAX, "source": perm[0], "edges": [e + [rng.randint(-W, W)] for e in dag_edges]})
    add("dag n=1e5 DAG, cycle unreachable from source", {"task": "dag", "n": N_MAX, "source": 0, "edges": [[i, i + 1, 1] for i in range(N_MAX // 2 - 1)] + [[N_MAX - 2, N_MAX - 1, 1], [N_MAX - 1, N_MAX - 2, 1]]})
    add("dag n=1e5 source isolated, big DAG elsewhere", {"task": "dag", "n": N_MAX, "source": N_MAX - 1, "edges": [[i, i + 1, 5] for i in range(N_MAX - 2)]})
    return cases


# ----------------------------------------------------------------------------
def run_batch_and_check(title, requests, names=None):
    outs, secs = run_java(requests)
    failures = 0
    for i, (req, out) in enumerate(zip(requests, outs)):
        errs = CHECKERS[req["task"]](req, out)
        if errs:
            failures += 1
            log("  FAIL %s: %s" % (names[i] if names else req["task"], errs[0]))
            if failures <= 5 and len(json.dumps(req)) < 400:
                log("       request=%s output=%s" % (json.dumps(req), json.dumps(out)))
    log("  %-46s %5d requests, %d failed, %.2fs wall (JVM start included)" % (title, len(requests), failures, secs))
    return outs, failures


def main():
    if not os.path.isdir(BUILD):
        sys.exit("compile first: javac -d build src/Java/*.java")
    failures = 0
    meta_tests()
    validator_tests()

    # --- ping + hand cases
    log("== Hand-made cases (hand-justified expectations + semantic validation) ==")
    ping, _ = run_java([{"task": "ping"}])
    assert ping == [{"status": "ready"}], ping
    log("  ping -> %s" % json.dumps(ping[0]))
    cases = hand_cases()
    reqs = [c["req"] for c in cases]
    outs, secs = run_java(reqs)
    for c, o in zip(cases, outs):
        errs = CHECKERS[c["req"]["task"]](c["req"], o) + check_expectation(c, o)
        status = "PASS" if not errs else "FAIL " + errs[0]
        failures += bool(errs)
        log("  %-4s %-52s why: %s" % (status.split()[0], c["name"], c["why"]))
        if errs:
            log("       got %s" % json.dumps(o))
    log("  %d hand cases in one process, %.2fs" % (len(cases), secs))
    with open(os.path.join(TESTS, "my_cases.jsonl"), "w") as f:
        for r in reqs:
            f.write(json.dumps(r, separators=(",", ":")) + "\n")
    with open(os.path.join(TESTS, "actual_outputs.jsonl"), "w") as f:
        for o in outs:
            f.write(json.dumps(o, separators=(",", ":")) + "\n")

    # --- random small
    log("== Seeded random small cases (seed 777, 6 task kinds x 500) ==")
    small = random_small_requests(777, 500)
    small_outs, f = run_batch_and_check("random small", small)
    failures += f

    # --- state reset: same requests repeated / reordered / interleaved with big inputs
    log("== State reset: repeated and mixed requests in ONE process ==")
    mixed = reqs + small[:600]
    first, _ = run_java(mixed)
    twice, _ = run_java(mixed + mixed)
    rev, _ = run_java(list(reversed(mixed)))
    same_twice = twice[:len(mixed)] == first and twice[len(mixed):] == first
    same_rev = list(reversed(rev)) == first
    log("  batch run twice in one process: identical answers = %s" % same_twice)
    log("  batch run in reverse order:     identical answers = %s" % same_rev)
    failures += (not same_twice) + (not same_rev)
    bigs = big_cases()
    big_reqs = [r for _, r in bigs]
    sandwich = reqs + [big_reqs[0], big_reqs[4], big_reqs[10], big_reqs[16], big_reqs[22]] + reqs
    sand, secs = run_java(sandwich)
    ok = sand[:len(reqs)] == outs and sand[-len(reqs):] == outs
    log("  small cases before/after 5 full-size requests: identical answers = %s (%.2fs)" % (ok, secs))
    failures += (not ok)

    # --- full-limit cases, one process per case so each timing is its own batch
    log("== Full-limit and deep cases (n<=1e5, m<=2.5e5), each in its own process ==")
    for name, req in bigs:
        outs1, secs = run_java([req])
        errs = CHECKERS[req["task"]](req, outs1[0])
        failures += bool(errs)
        size = len(req.get("edges", req.get("operations", [])))
        log("  %-4s %-58s n=%-6d m/q=%-6d %.2fs" % ("PASS" if not errs else "FAIL", name, req["n"], size, secs) + ("" if not errs else "  " + errs[0]))
    # whole big batch in one go (stays below the 20 s batch limit?)
    outs_all, secs = run_java(big_reqs)
    bad = sum(1 for r, o in zip(big_reqs, outs_all) if CHECKERS[r["task"]](r, o))
    log("  all %d full-size requests in one process: %d failed, %.2fs wall" % (len(big_reqs), bad, secs))
    failures += bad

    log("")
    log("TOTAL FAILURES: %d" % failures)
    with open(os.path.join(TESTS, "results.txt"), "w") as f:
        f.write("\n".join(LOG) + "\n")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
