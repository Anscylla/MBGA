"""What working out a state costs, in province transfers, counted before writing any script.

The engine answers one question: does this province border that country. Asking is free.
Getting a province into a position to be asked about is not - it has to be handed to a probe
country and handed back afterwards, and each of those is a transfer.

That last part is what settles the matter. Grouping provinces and halving the group looks like
it should win: a group that answers no is discarded without ever being taken apart. But every
province in that group was moved in and will be moved out again, which costs exactly what
taking them apart would have. On a yes it costs more, because the halves are moved again.

Measured against the shapes a state actually has, asking one province at a time beats asking
in rounds everywhere, and by more the denser the state:

    dense planar, 30 provinces:   one by one 268 transfers,  in rounds 816
    grid, 30 provinces:           one by one 536 transfers,  in rounds 1060
    star, 30 provinces:           one by one 116 transfers,  in rounds 416

So the mod asks one at a time, and the saving worth having is not in how the question is
asked but in not asking it at all - which is what a lookup table is for.

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
        """A province entering a probe costs a transfer, and so does one leaving it: it has to
        be handed back to whoever owned it. Both are counted."""
        a, b = frozenset(a), frozenset(b)
        self.loads += len(a - self.mbg) + len(self.mbg - a)
        self.loads += len(b - self.mbh) + len(self.mbh - b)
        self.mbg, self.mbh = a, b
        self.queries += 1
        return any(frozenset((x, y)) in self.edges for x in a for y in b)


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


class HomeOracle(Oracle):
    """The engine as the mod actually meets it.

    One side of the question is the demander's own territory, which is already theirs and
    costs nothing to ask about - the mod asks whether a province borders a country, not
    whether it borders a loaded set. So only the side being asked about is ever moved.
    """

    def ask(self, a, b):
        b = frozenset(b)
        self.loads += len(b - self.mbh) + len(self.mbh - b)
        self.mbh = b
        self.queries += 1
        return any(frozenset((x, y)) in self.edges for x in a for y in b)


def reachable_from_home(n, home, oracle):
    """The same rounds, with the home side free."""
    known, unknown = set(home), set(range(n)) - set(home)
    while unknown:
        found = set()
        touching(known, unknown, oracle, found)
        if not found:
            break
        known |= found
        unknown -= found
    oracle.ask(set(), set())        # hand back whatever the probe still holds
    return known


def one_at_a_time(n, home, oracle):
    """What the mod does today: every province of the state lent out and asked about on its
    own, then the same again after every take."""
    known, unknown = set(home), set(range(n)) - set(home)
    while unknown:
        found = {p for p in sorted(unknown) if oracle.ask(known, {p})}
        if not found:
            break
        known |= found
        unknown -= found
    oracle.ask(set(), set())
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
    """What the mod pays to work out a state, in province transfers.

    The question the mod asks is whether a province borders the demander. One side of it is
    the demander's own territory, which costs nothing; the other has to be lent to a probe
    country, and lending and handing back are a transfer each.

    Asked one province at a time that is two transfers apiece, every round. Asked of a set at
    once, a round costs a load per province in the sets it has to try, and the halving finds
    the same answer in far fewer.
    """
    print('%-18s%4s%10s%14s%12s%14s%12s%8s'
          % ('topology', 'n', 'edges', 'one by one', 'transfers', 'in rounds', 'transfers', 'saved'))
    for n in (10, 20, 30, 50):
        for name, edges in (('path', path(n)), ('star', star(n)),
                            ('tree', tree(n)), ('grid', grid(n)),
                            ('dense planar', dense_planar(n))):
            a = HomeOracle(edges)
            one_at_a_time(n, {0}, a)
            b = HomeOracle(edges)
            reached = reachable_from_home(n, {0}, b)
            assert reached == one_at_a_time(n, {0}, HomeOracle(edges)), (name, n)
            print('%-18s%4d%10d%14d%12d%14d%12d%7d%%'
                  % (name, n, len(edges), a.loads, a.loads * 2, b.loads, b.loads * 2,
                     100 - b.loads * 100 // max(1, a.loads)))
        print()


if __name__ == '__main__':
    main()
