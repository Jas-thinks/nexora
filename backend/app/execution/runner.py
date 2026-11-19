"""Sandboxed code execution. NEVER runs user code in the API process: every run is a short-lived, resource-limited, network-less container.

Isolation per container: --network none, --read-only rootfs, tmpfs /tmp (noexec for run stage), --cap-drop ALL, no-new-privileges,
non-root uid, --memory/--memory-swap, --cpus, --pids-limit (fork bombs), ulimits (files, file size), wall-clock timeout with `docker kill`,
bounded stdout/stderr (reader stops and kills the container past the cap). Source is mounted read-only into the run container.
Trust boundary: the API process must be able to talk to Docker. In production, run this module on a dedicated runner host/service
(see docs/CODE_EXECUTION.md); gVisor/Firecracker are the stronger upgrade path.
"""
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, field

LIMITS = {"time_s": 4.0, "memory_mb": 256, "pids": 64, "cpus": "1.0", "out_bytes": 65536, "err_bytes": 16384, "compile_s": 25.0, "compile_mb": 768}
MAX_CODE, MAX_STDIN = 64_000, 64_000


@dataclass(frozen=True)
class Lang:
    id: str
    name: str
    image: str
    file: str
    compile: list[str] | None
    run: list[str]
    monaco: str
    template: str


LANGS = {
    "cpp17": Lang("cpp17", "C++17 (GNU g++ 13)", "gcc:13", "main.cpp", ["g++", "-std=gnu++17", "-O2", "-pipe", "-o", "/w/a.out", "/w/main.cpp"], ["/w/a.out"], "cpp",
                  "#include <bits/stdc++.h>\nusing namespace std;\n\nint main() {\n    ios::sync_with_stdio(false);\n    cin.tie(nullptr);\n    \n    return 0;\n}\n"),
    "java": Lang("java", "Java 21 (Temurin)", "eclipse-temurin:21-jdk-alpine", "Main.java", ["javac", "-J-Xmx256m", "-d", "/w", "/w/Main.java"], ["java", "-Xmx180m", "-Xss64m", "-XX:+UseSerialGC", "-XX:TieredStopAtLevel=1", "-Djava.io.tmpdir=/tmp", "-cp", "/w", "Main"], "java",
                 "import java.util.*;\nimport java.io.*;\n\npublic class Main {\n    public static void main(String[] args) throws IOException {\n        BufferedReader br = new BufferedReader(new InputStreamReader(System.in));\n        \n    }\n}\n"),
    "javascript": Lang("javascript", "JavaScript (Node 22)", "node:22-alpine", "main.js", None, ["node", "--max-old-space-size=180", "/w/main.js"], "javascript",
                       "const lines = require('fs').readFileSync(0, 'utf8').split('\\n');\n\n"),
    "python": Lang("python", "Python 3.12", "python:3.12-alpine", "main.py", None, ["python", "-B", "/w/main.py"], "python",
                   "import sys\ninput = sys.stdin.readline\n\ndef main():\n    pass\n\nmain()\n"),
}


@dataclass
class RunResult:
    verdict: str  # OK CE RE TLE MLE OLE ERR
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    wall_ms: int = 0
    compile_ms: int | None = None
    truncated: bool = False
    note: str = ""
    memory_kb: None = None  # not measured (docker CLI does not expose peak RSS cheaply); never guessed
    tests: list = field(default_factory=list)


def docker_ready() -> bool:
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, timeout=8).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def image_present(image: str) -> bool:
    try:
        return subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=8).returncode == 0
    except (subprocess.SubprocessError, OSError):
        return False


def local_availability() -> dict:
    ok = docker_ready()
    return {"docker": ok, "languages": {k: {"name": v.name, "ready": ok and image_present(v.image)} for k, v in LANGS.items()}}


def _sec_flags(mem_mb: int, run_stage: bool) -> list[str]:
    f = ["--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--memory", f"{mem_mb}m", "--memory-swap", f"{mem_mb}m",
         "--cpus", LIMITS["cpus"], "--pids-limit", str(LIMITS["pids"]), "--ulimit", "nofile=64:64", "--ulimit", "fsize=8000000:8000000", "--ulimit", "core=0",
         "--user", "65534:65534", "--tmpfs", "/tmp:rw,size=32m" + (",noexec,nosuid" if run_stage else ",nosuid")]
    return f


def _bounded(cmd: list[str], stdin: bytes, timeout: float, name: str, out_cap: int, err_cap: int):
    """Run `cmd`; capture at most out_cap/err_cap bytes; kill the container on timeout or cap breach. -> (rc, out, err, timed_out, overflow, ms)."""
    t0 = time.perf_counter()
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    buf = {"o": bytearray(), "e": bytearray()}
    over = threading.Event()

    def kill():
        try:
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=20)
        except subprocess.SubprocessError:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=20)  # last resort

    def pump(stream, key, cap):
        # After the cap is hit we keep DRAINING (and discarding) so the docker CLI never blocks on a full pipe while we kill the container.
        while True:
            chunk = stream.read(4096)
            if not chunk:
                return
            room = cap - len(buf[key])
            if room > 0:
                buf[key] += chunk[:room]
            if len(chunk) > room and not over.is_set():
                over.set()
                threading.Thread(target=kill, daemon=True).start()

    def feed():
        try:
            p.stdin.write(stdin); p.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass

    ts = [threading.Thread(target=pump, args=(p.stdout, "o", out_cap), daemon=True), threading.Thread(target=pump, args=(p.stderr, "e", err_cap), daemon=True),
          threading.Thread(target=feed, daemon=True)]
    [t.start() for t in ts]
    timed_out = False
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True; kill()
        try: p.wait(timeout=10)
        except subprocess.TimeoutExpired: p.kill()
    [t.join(timeout=3) for t in ts]
    return p.returncode, bytes(buf["o"]), bytes(buf["e"]), timed_out, over.is_set(), int((time.perf_counter() - t0) * 1000)


def _prepare(lang: Lang, code: str):
    """Write source to a temp dir (and compile when needed). -> (workdir, RunResult-or-None). A non-None result means compile failed."""
    work = tempfile.mkdtemp(prefix="nexora-run-")
    os.chmod(work, 0o777)  # the container user (65534) must be able to write the compiled binary
    with open(os.path.join(work, lang.file), "w", encoding="utf-8") as f:
        f.write(code)
    os.chmod(os.path.join(work, lang.file), 0o644)
    if not lang.compile:
        return work, None, None
    name = f"nexora-c-{uuid.uuid4().hex[:12]}"
    cmd = ["docker", "run", "--rm", "--name", name, *_sec_flags(LIMITS["compile_mb"], False), "-v", f"{work}:/w:rw", "-w", "/w", lang.image, *lang.compile]
    rc, out, err, to, ov, ms = _bounded(cmd, b"", LIMITS["compile_s"], name, 32768, 32768)
    if to:
        return work, RunResult("CE", stderr="Compilation timed out.", compile_ms=ms), ms
    if rc != 0:
        return work, RunResult("CE", stderr=err.decode("utf-8", "replace")[:8000], exit_code=rc, compile_ms=ms), ms
    return work, None, ms


def _run_prepared(lang: Lang, work: str, stdin: str, compile_ms: int | None = None) -> RunResult:
    name = f"nexora-r-{uuid.uuid4().hex[:12]}"
    cmd = ["docker", "run", "--rm", "-i", "--name", name, *_sec_flags(LIMITS["memory_mb"], True), "-v", f"{work}:/w:ro", "-w", "/tmp", lang.image, *lang.run]
    rc, out, err, to, ov, ms = _bounded(cmd, stdin.encode(), LIMITS["time_s"], name, LIMITS["out_bytes"], LIMITS["err_bytes"])
    s_out, s_err = out.decode("utf-8", "replace"), err.decode("utf-8", "replace")
    if to:
        v, note = "TLE", f"Time limit {LIMITS['time_s']}s exceeded (wall clock, includes container start-up)."
    elif ov:
        v, note = "OLE", "Output limit exceeded; the program was stopped."
    elif rc == 137:
        v, note = "MLE", f"Killed (exit 137): most likely the {LIMITS['memory_mb']} MB memory limit."
    elif rc != 0:
        v, note = "RE", ""
    else:
        v, note = "OK", ""
    return RunResult(v, s_out, s_err, rc, ms, compile_ms, ov, note)


def _check(language: str, code: str, stdin: str = ""):
    lang = LANGS.get(language)
    if lang is None:
        return None, RunResult("ERR", note=f"Unsupported language '{language}'")
    if len(code.encode()) > MAX_CODE or len(stdin.encode()) > MAX_STDIN:
        return None, RunResult("ERR", note="Code or input too large")
    if not docker_ready() or not image_present(lang.image):
        return None, RunResult("ERR", note="Execution backend unavailable (Docker or the language image is missing).")
    return lang, None


def local_run_code(language: str, code: str, stdin: str = "") -> RunResult:
    lang, err = _check(language, code, stdin)
    if err:
        return err
    work, cerr, cms = _prepare(lang, code)
    try:
        return cerr if cerr else _run_prepared(lang, work, stdin, cms)
    finally:
        shutil.rmtree(work, ignore_errors=True)


def local_judge(language: str, code: str, tests: list[dict], max_tests: int = 40) -> RunResult:
    """Compile ONCE, then run each test in its own container; compare whitespace-normalised output with `expected`."""
    lang, err = _check(language, code)
    if err:
        return err
    work, cerr, cms = _prepare(lang, code)
    res: list[dict] = []
    overall = "OK"
    try:
        if cerr:
            return RunResult("CE", stderr=cerr.stderr, compile_ms=cerr.compile_ms, tests=[])
        for i, t in enumerate(tests[:max_tests], 1):
            r = _run_prepared(lang, work, t.get("input", ""))
            passed = r.verdict == "OK" and r.stdout.split() == str(t.get("expected", "")).split()
            v = r.verdict if r.verdict != "OK" else ("OK" if passed else "WA")
            res.append({"n": i, "verdict": v, "wall_ms": r.wall_ms, "stdout": r.stdout[:500], "expected": str(t.get("expected", ""))[:500], "stderr": r.stderr[:500]})
            if v != "OK" and overall == "OK":
                overall = v
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return RunResult(overall, tests=res, wall_ms=sum(x["wall_ms"] for x in res), compile_ms=cms)


# ---- public entry points: local Docker by default, or a remote executor service when CODEMIND_EXECUTOR_URL is set
def _remote() -> bool:
    from app.core.config import get_settings
    return bool(get_settings().executor_url)


def availability() -> dict:
    if _remote():
        from app.execution import remote
        return remote.availability()
    return local_availability()


def run_code(language: str, code: str, stdin: str = "") -> RunResult:
    if _remote():
        from app.execution import remote
        return remote.run_code(language, code, stdin)
    return local_run_code(language, code, stdin)


def judge(language: str, code: str, tests: list[dict], max_tests: int = 40) -> RunResult:
    if _remote():
        from app.execution import remote
        return remote.judge(language, code, tests[:max_tests])
    return local_judge(language, code, tests, max_tests)
