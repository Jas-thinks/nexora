"""Nexora-authored practice problems for the arena. Statements are original; expected outputs are produced by reference solutions at import time
(and cross-checked against brute force in tests), so hidden tests can never contain a typo. Hidden tests include large inputs that punish naive solutions."""
import math
import random
from collections import deque

M = 10**9 + 7


def _fmt(*lines): return "\n".join(str(x) for x in lines) + "\n"


def _arr_case(a): return _fmt(len(a), " ".join(map(str, a)))


# ---- reference solutions
def ref_sum(a): return sum(a)


def ref_kadane(a):
    best = cur = a[0]
    for x in a[1:]:
        cur = max(x, cur + x); best = max(best, cur)
    return best


def ref_brackets(s):
    st, m = [], {")": "(", "]": "[", "}": "{"}
    for c in s:
        if c in "([{": st.append(c)
        elif not st or st.pop() != m[c]: return "NO"
    return "YES" if not st else "NO"


def ref_unique(s):
    last, best, l = {}, 0, 0
    for i, c in enumerate(s):
        if c in last and last[c] >= l: l = last[c] + 1
        last[c] = i; best = max(best, i - l + 1)
    return best


def ref_gcd(a):
    g = 0
    for x in a: g = math.gcd(g, x)
    return g


def ref_two_sum(a, t):
    seen = set()
    for x in a:
        if t - x in seen: return "YES"
        seen.add(x)
    return "NO"


def ref_fib(n):
    def f(k):
        if k == 0: return 0, 1
        a, b = f(k >> 1)
        c = a * ((2 * b - a) % M) % M; d = (a * a + b * b) % M
        return (d, (c + d) % M) if k & 1 else (c, d)
    return f(n)[0]


def ref_grid(g):
    h, w = len(g), len(g[0]); s = t = None
    for i in range(h):
        for j in range(w):
            if g[i][j] == "S": s = (i, j)
            if g[i][j] == "T": t = (i, j)
    d = {s: 0}; q = deque([s])
    while q:
        x, y = q.popleft()
        if (x, y) == t: return d[t]
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < h and 0 <= ny < w and g[nx][ny] != "#" and (nx, ny) not in d:
                d[(nx, ny)] = d[(x, y)] + 1; q.append((nx, ny))
    return -1


def _grid_case(g): return _fmt(f"{len(g)} {len(g[0])}", *g)


def _rand_grid(rng, h, w, p=0.25):
    g = [["#" if rng.random() < p else "." for _ in range(w)] for _ in range(h)]
    g[0][0], g[h - 1][w - 1] = "S", "T"
    return ["".join(r) for r in g]


def _build():
    r = random.Random(20260619)
    P = {}
    arrs = [[5], [-3, -1, -2], [1, 2, 3, 4], [0, 0, 0]] + [[r.randint(-50, 50) for _ in range(r.randint(2, 30))] for _ in range(4)]
    big = [r.randint(-1000, 1000) for _ in range(200000)]
    P["array-sum"] = dict(title="Array Sum", level=1, statement="You are given n integers. Print their sum.", input="First line: n (1 ≤ n ≤ 200000). Second line: n integers with absolute value ≤ 10^9.",
                          output="One integer: the sum.", samples=[("3\n1 2 3\n", "6"), ("2\n-5 5\n", "0")], tests=[(_arr_case(a), str(ref_sum(a))) for a in arrs + [big]])
    P["max-subarray"] = dict(title="Best Stretch", level=2, statement="Given an array of n integers, find the largest possible sum of a non-empty contiguous subarray.", input="First line: n (1 ≤ n ≤ 200000). Second line: n integers, absolute value ≤ 10^4.",
                             output="One integer.", samples=[("5\n-2 1 -3 4 -1\n", "4"), ("3\n-3 -1 -2\n", "-1")], tests=[(_arr_case(a), str(ref_kadane(a))) for a in arrs + [big, [-1] * 150000]])
    br = ["()", "([)]", "((", "{[()]}", "", "(", "]["] + ["".join(r.choice("()[]{}") for _ in range(r.randint(1, 12))) for _ in range(4)] + ["(" * 100000 + ")" * 100000, "()" * 100000]
    br = [b for b in br if b]
    P["balanced-brackets"] = dict(title="Matching Pairs", level=2, statement="A string has only the characters ()[]{}. Print YES if every bracket is closed by the right kind in the right order, otherwise NO.", input="One line: the string (1 ≤ length ≤ 200000).",
                                  output="YES or NO.", samples=[("{[()]}\n", "YES"), ("([)]\n", "NO")], tests=[(_fmt(b), ref_brackets(b)) for b in br])
    us = ["a", "aaaa", "abcabcbb", "pwwkew", "abcdefghijklmnopqrstuvwxyz"] + ["".join(r.choice("abc") for _ in range(r.randint(1, 20))) for _ in range(4)] + ["".join(r.choice("abcdefghij") for _ in range(200000))]
    P["unique-window"] = dict(title="Longest Fresh Run", level=3, statement="Find the length of the longest substring (contiguous) of the given lowercase string in which all characters are different.", input="One line: a lowercase string, 1 ≤ length ≤ 200000.",
                              output="One integer.", samples=[("abcabcbb\n", "3"), ("bbbb\n", "1")], tests=[(_fmt(s), str(ref_unique(s))) for s in us])
    ga = [[7], [12, 18], [5, 10, 15], [17, 13], [2**40, 2**20 * 3]] + [[r.randint(1, 10**6) * 6 for _ in range(r.randint(2, 10))] for _ in range(3)] + [[r.randint(1, 10**9) for _ in range(200000)]]
    P["gcd-all"] = dict(title="Common Divisor", level=2, statement="Print the greatest common divisor of all n given positive integers.", input="First line: n (1 ≤ n ≤ 200000). Second line: n integers, 1 ≤ a_i ≤ 10^12.", output="One integer.",
                        samples=[("3\n12 18 24\n", "6"), ("1\n7\n", "7")], tests=[(_arr_case(a), str(ref_gcd(a))) for a in ga])
    ts = [([1, 2, 3], 5), ([1, 2, 3], 7), ([4], 8), ([3, 3], 6), ([1, 5, 9], 100)] + [([r.randint(-20, 20) for _ in range(r.randint(2, 15))], r.randint(-30, 30)) for _ in range(4)] + [([i * 2 for i in range(200000)], 399999), (list(range(0, 400000, 2)), 3)]
    P["pair-target"] = dict(title="Two That Add Up", level=2, statement="Given n integers and a target t, decide whether two DIFFERENT positions i ≠ j exist with a_i + a_j = t.", input="First line: n and t (2 ≤ n ≤ 200000, |t| ≤ 10^9). Second line: n integers.", output="YES or NO.",
                         samples=[("3 5\n1 2 3\n", "YES"), ("1 8\n4\n", "NO")], tests=[(_fmt(f"{len(a)} {t}", " ".join(map(str, a))), ref_two_sum(a, t)) for a, t in ts if len(a) >= 1])
    fs = [0, 1, 2, 10, 50, 90, 1000, 10**9, 10**12, 10**18, 123456789012345678]
    P["huge-fibonacci"] = dict(title="Huge Fibonacci", level=4, statement="Let F(0)=0, F(1)=1, F(k)=F(k-1)+F(k-2). Print F(n) modulo 1 000 000 007.", input="One integer n (0 ≤ n ≤ 10^18).", output="One integer.",
                               samples=[("10\n", "55"), ("1\n", "1")], tests=[(_fmt(n), str(ref_fib(n))) for n in fs])
    gs = [["S.T"], ["S#T"], ["S", ".", "T"], ["S..", ".#.", "..T"], ["S#.", "###", "..T"]] + [_rand_grid(r, r.randint(2, 8), r.randint(2, 8)) for _ in range(5)] + [_rand_grid(r, 700, 700, 0.1)]
    P["grid-escape"] = dict(title="Shortest Way Out", level=4, statement="A grid has open cells '.', walls '#', a start 'S' and a target 'T'. You may move up, down, left or right into open cells (S and T are open). Print the minimum number of moves from S to T, or -1 if impossible.",
                            input="First line: H and W (1 ≤ H, W ≤ 1000). Then H lines of W characters.", output="One integer.", samples=[("1 3\nS.T\n", "2"), ("1 3\nS#T\n", "-1")], tests=[(_grid_case(g), str(ref_grid(g))) for g in gs])
    return P


PROBLEMS = _build()


def public(key: str, with_samples=True) -> dict:
    p = PROBLEMS[key]
    return {"key": key, "title": p["title"], "level": p["level"], "statement": p["statement"], "input": p["input"], "output": p["output"],
            "samples": [{"input": i, "output": o} for i, o in p["samples"]] if with_samples else [], "hidden_tests": len(p["tests"])}


def tests_for(key: str) -> list[dict]:
    return [{"input": i, "expected": o} for i, o in PROBLEMS[key]["tests"]]
