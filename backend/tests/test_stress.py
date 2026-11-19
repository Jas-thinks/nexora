import pytest

from app.api.stress import GENERATORS
from app.execution import runner
from app.services import stress

REAL = runner.docker_ready() and runner.image_present(runner.LANGS["python"].image)
BRUTE = "n = int(input()); a = list(map(int, input().split())); print(max(a[i] + a[j] for i in range(n) for j in range(i, n)))"
GOOD = "n = int(input()); a = list(map(int, input().split())); print(2 * max(a))"
# off-by-one style bug: only considers adjacent sums, which agrees on n=1 but not on larger inputs
BAD = "n = int(input()); a = list(map(int, input().split())); print(max(a[i] + a[i + 1] if i + 1 < n else 2 * a[i] for i in range(n)))"


def test_first_diff_pinpoints_line_and_handles_short_output():
    d = stress.first_diff("1 2\n3 4\n5", "1 2\n3 9\n5")
    assert d["line"] == 2 and d["expected_line"] == "3 4" and d["actual_line"] == "3 9"
    assert stress.first_diff("1\n2", "1")["actual_line"].startswith("(no line")
    assert stress.first_diff("1 2", "1   2\n")["line"] is None  # whitespace-insensitive


@pytest.mark.skipif(not REAL, reason="Docker + python image required")
def test_finds_small_counterexample_for_buggy_solution():
    r = stress.run(("python", BAD), ("python", BRUTE), ("python", GENERATORS["array"]), max_size=6, budget_s=60, max_iters=40)
    assert r["status"] == "found", r
    ce = r["counterexample"]
    assert ce["kind"] == "WA" and ce["size"] <= 6 and ce["diff"]["line"] == 1
    assert ce["expected"].split() != ce["actual"].split()


@pytest.mark.skipif(not REAL, reason="Docker + python image required")
def test_correct_solution_is_not_flagged_and_note_is_humble():
    r = stress.run(("python", GOOD), ("python", BRUTE), ("python", GENERATORS["array"]), max_size=5, budget_s=60, max_iters=8)
    assert r["status"] == "none_found" and "not prove" in r["note"]


@pytest.mark.skipif(not REAL, reason="Docker + python image required")
def test_broken_generator_and_broken_brute_are_reported_not_blamed_on_solution():
    r = stress.run(("python", GOOD), ("python", BRUTE), ("python", "raise SystemExit(3)"), budget_s=30, max_iters=3)
    assert r["status"] == "error" and "generator" in r["note"]
    r = stress.run(("python", GOOD), ("python", "raise SystemExit(1)"), ("python", GENERATORS["array"]), budget_s=30, max_iters=3)
    assert r["status"] == "error" and "brute force" in r["note"]
    r = stress.run(("python", "def (:"), ("python", BRUTE), ("python", GENERATORS["array"]), max_size=3, budget_s=30, max_iters=3)
    assert r["status"] == "found" and r["counterexample"]["kind"] == "solution_RE"  # interpreted language: a syntax error surfaces at run time


@pytest.mark.skipif(not REAL, reason="Docker + python image required")
def test_runtime_error_in_solution_is_a_counterexample():
    r = stress.run(("python", "import sys\nprint(1/0)"), ("python", BRUTE), ("python", GENERATORS["array"]), max_size=3, budget_s=30, max_iters=5)
    assert r["status"] == "found" and r["counterexample"]["kind"] == "solution_RE"


def test_api_requires_auth_and_validates(client):
    assert client.post("/stress", json={}).status_code in (401, 403)
    assert client.get("/stress/generators").status_code in (401, 403)
