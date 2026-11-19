"""Stress tester: find the SMALLEST random input on which a solution disagrees with a trusted brute force.

The generator reads one line "<seed> <size>" from stdin and prints one test input. Sizes are tried in ascending order, and once a
counterexample is found we spend part of the remaining budget trying strictly smaller sizes, so the reported input is small
(it is the smallest *found*, not proven minimal). Absence of a counterexample is NOT a proof of correctness.
Local Docker only: each program is compiled once, then every run is its own sandbox container.
"""
import shutil
import time

from app.execution import runner

MAX_ITERS = 400


def _norm(s: str) -> list[str]:
    return s.split()


def first_diff(expected: str, actual: str) -> dict:
    """Locate the first line where whitespace-normalised outputs diverge."""
    el, al = expected.strip().splitlines(), actual.strip().splitlines()
    for i in range(max(len(el), len(al))):
        e = el[i].split() if i < len(el) else None
        a = al[i].split() if i < len(al) else None
        if e != a:
            return {"line": i + 1, "expected_line": " ".join(e) if e is not None else "(no line: output ended)", "actual_line": " ".join(a) if a is not None else "(no line: output ended)"}
    return {"line": None, "expected_line": "", "actual_line": ""}


def run(solution: tuple[str, str], brute: tuple[str, str], gen: tuple[str, str], max_size: int = 8, budget_s: float = 40.0, max_iters: int = 150, seed0: int = 1) -> dict:
    t0 = time.perf_counter()
    max_iters = min(max_iters, MAX_ITERS)
    progs, dirs = {}, []
    out: dict = {"status": "error", "iterations": 0, "elapsed_s": 0.0, "counterexample": None, "note": ""}
    try:
        for name, (lang_id, code) in (("generator", gen), ("brute force", brute), ("solution", solution)):
            lang, err = runner._check(lang_id, code)
            if err:
                out["note"] = err.note
                return out
            work, cerr, _ = runner._prepare(lang, code)
            dirs.append(work)
            if cerr:
                out["note"] = f"The {name} did not compile: {cerr.stderr[:600]}"
                return out
            progs[name] = (lang, work)

        def attempt(seed: int, size: int):
            g = runner._run_prepared(*progs["generator"], f"{seed} {size}\n")
            if g.verdict != "OK":
                return {"kind": "generator", "detail": f"The generator failed ({g.verdict}) for seed {seed}, size {size}: {g.stderr[:300]}"}
            inp = g.stdout
            b = runner._run_prepared(*progs["brute force"], inp)
            if b.verdict != "OK":
                return {"kind": "brute", "detail": f"The brute force failed ({b.verdict}) on a generated input; it cannot be used as a reference. {b.stderr[:300]}", "input": inp}
            s = runner._run_prepared(*progs["solution"], inp)
            if s.verdict != "OK":
                return {"kind": "solution_" + s.verdict, "input": inp, "expected": b.stdout, "actual": s.stdout, "stderr": s.stderr[:500], "detail": s.note or s.stderr[:300]}
            if _norm(s.stdout) != _norm(b.stdout):
                return {"kind": "WA", "input": inp, "expected": b.stdout, "actual": s.stdout, "diff": first_diff(b.stdout, s.stdout)}
            return None

        sizes = list(range(1, max_size + 1))
        best, tried, it = None, set(), 0
        for it in range(max_iters):
            if time.perf_counter() - t0 > budget_s:
                break
            size, seed = sizes[it % len(sizes)], seed0 + it
            tried.add(size)
            r = attempt(seed, size)
            out["iterations"] = it + 1
            if r is None:
                continue
            if r["kind"] in ("generator", "brute"):
                out["note"] = r["detail"]
                return out
            best = {**r, "size": size, "seed": seed}
            break
        if best:  # shrink: spend up to ~35% of the remaining budget on strictly smaller sizes
            deadline = time.perf_counter() + max(0.0, budget_s - (time.perf_counter() - t0)) * 0.35
            for size in range(1, best["size"]):
                for k in range(6):
                    if time.perf_counter() > deadline:
                        break
                    seed = seed0 + 10_000 + size * 100 + k
                    r = attempt(seed, size)
                    out["iterations"] += 1
                    if r and r["kind"] not in ("generator", "brute"):
                        best = {**r, "size": size, "seed": seed}
                        break
                else:
                    continue
                break
        out["elapsed_s"] = round(time.perf_counter() - t0, 1)
        if best:
            out["status"] = "found"
            out["counterexample"] = best
            out["note"] = "Smallest failing input found by ascending size; not proven minimal."
        else:
            out["status"] = "none_found"
            out["note"] = f"No disagreement in {out['iterations']} random inputs (sizes 1..{max_size}). That raises confidence but does not prove the solution correct."
        return out
    finally:
        for d in dirs:
            shutil.rmtree(d, ignore_errors=True)
        out["elapsed_s"] = round(time.perf_counter() - t0, 1)
