#!/usr/bin/env python3
"""How many province loads a scan schedule costs, counted before writing any script.

The engine answers one question: given a set of provinces in one probe country and a set in
the other, does any province of the first touch any province of the second. Asking is free.
Changing what a probe holds is not: every province that enters a probe costs one load, and a
load is two transfers, and a transfer is what damages buildings.

So this counts loads, on graphs shaped like the ones states actually are, for the schedule
in use now and for recursive rectangle splitting.

Run: python tools/simulate_scan.py
"""
import itertools
import random


class Oracle:
    """The engine, and a count of what asking it cost."""

    def __init__(self, edges):
        self.edges = {frozenset(e) for e in edges}
        self.mbg = frozenset()
        self.mbh = frozenset()
        self.loads = 0
        self.queries = 0

    def ask(self, a, b):
        a, b = frozenset(a), frozenset(b)
        self.loads += len(a - self.mbg) + len(b - self.mbh)
        self.mbg, self.mbh = a, b
        self.queries += 1
        return any(frozenset((x, y)) in self.edges for x in a for y in b)


def brute_force(n, oracle):
    """One province against one province, every unordered pair."""
    for i, j in itertools.combinations(range(n), 2):
        oracle.ask({i}, {j})


def split(s):
    s = sorted(s)
    half = len(s) // 2
    return set(s[:half]), set(s[half:])


def scan(a, b, oracle, found):
    """Every edge between two disjoint sets."""
    if not a or not b:
        return
    if not oracle.ask(a, b):
        return
    if len(a) == 1 and len(b) == 1:
        found.add(frozenset(a | b))
        return
    # Divide the smaller set and leave the larger one where it is: reloading the larger set
    # is what costs. A set of one cannot be divided, so then the other one goes.
    divide_b = len(b) > 1 and (len(a) == 1 or len(a) >= len(b))
    if divide_b:
        b0, b1 = split(b)
        scan(a, b0, oracle, found)
        scan(a, b1, oracle, found)
    else:
        a0, a1 = split(a)
        scan(a0, b, oracle, found)
        scan(a1, b, oracle, found)


def reconstruct(s, oracle, found):
    """Every edge inside one set. Each pair meets exactly once, at the split that
    separates them."""
    if len(s) < 2:
        return
    left, right = split(s)
    scan(left, right, oracle, found)
    reconstruct(left, oracle, found)
    reconstruct(right, oracle, found)


def touching(a, b, oracle, out):
    """Which members of b touch anything in a. One probe never moves."""
    if not a or not b or not oracle.ask(a, b):
        return
    if len(b) == 1:
        out |= set(b)
        return
    b0, b1 = split(b)
    touching(a, b0, oracle, out)
    touching(a, b1, oracle, out)


def reachable_set(n, home, oracle):
    """Only what can be reached from home, never the whole graph.

    One round finds every province touching the reached set at once, so the probe holding
    that set is loaded once per round rather than once per province.
    """
    known, unknown = set(home), set(range(n)) - set(home)
    while unknown:
        found = set()
        touching(known, unknown, oracle, found)
        if not found:
            break
        known |= found
        unknown -= found
    return known


def path(n):
    return [(i, i + 1) for i in range(n - 1)]


def star(n):
    return [(0, i) for i in range(1, n)]


def tree(n, seed=1):
    rng = random.Random(seed)
    return [(rng.randrange(i), i) for i in range(1, n)]


def grid(n):
    w = int(n ** 0.5)
    h = (n + w - 1) // w
    e = []
    for y in range(h):
        for x in range(w):
            i = y * w + x
            if i >= n:
                continue
            if x + 1 < w and i + 1 < n:
                e.append((i, i + 1))
            if i + w < n:
                e.append((i, i + w))
    return e


def dense_planar(n, seed=2):
    """Points in a square, triangulated greedily without crossings: the shape a state
    actually has, at the planar limit."""
    rng = random.Random(seed)
    pts = [(rng.random(), rng.random()) for _ in range(n)]

    def crosses(p1, p2, p3, p4):
        def side(a, b, c):
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
        d1, d2 = side(p3, p4, p1), side(p3, p4, p2)
        d3, d4 = side(p1, p2, p3), side(p1, p2, p4)
        return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))

    cand = sorted(itertools.combinations(range(n), 2),
                  key=lambda e: (pts[e[0]][0] - pts[e[1]][0]) ** 2
                  + (pts[e[0]][1] - pts[e[1]][1]) ** 2)
    edges = []
    for i, j in cand:
        if any(crosses(pts[i], pts[j], pts[k], pts[l])
               for k, l in edges if len({i, j, k, l}) == 4):
            continue
        edges.append((i, j))
    return edges


def main():
    print(f'{"topologia":18}{"n":>4}{"krawedzi":>10}'
          f'{"teraz: ladowan":>16}{"transferow":>12}'
          f'{"dziel i rzadz":>15}{"transferow":>12}{"zysk":>8}'
          f'{"osiagalnosc":>14}{"zysk":>8}')
    for n in (10, 20, 30):
        for name, edges in (('sciezka', path(n)), ('gwiazda', star(n)),
                            ('drzewo', tree(n)), ('siatka', grid(n)),
                            ('planarny gesty', dense_planar(n))):
            a = Oracle(edges)
            brute_force(n, a)
            b = Oracle(edges)
            found = set()
            reconstruct(set(range(n)), b, found)
            assert found == {frozenset(e) for e in edges}, (name, n)
            c = Oracle(edges)
            reached = reachable_set(n, {0}, c)
            print(f'{name:18}{n:>4}{len(edges):>10}'
                  f'{a.loads:>16}{a.loads * 2:>12}'
                  f'{b.loads:>15}{b.loads * 2:>12}'
                  f'{100 - b.loads * 100 // a.loads:>7}%'
                  f'{c.loads:>14}{100 - c.loads * 100 // a.loads:>7}%')
        print()


if __name__ == '__main__':
    main()
