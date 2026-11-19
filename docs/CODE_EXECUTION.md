# Code execution sandbox

Code: `backend/app/execution/runner.py`, API `app/api/studio.py`. **User code never runs in the API process.**

## Isolation (per container)
`--network none` · `--read-only` rootfs · `--tmpfs /tmp` (noexec in the run stage) · `--cap-drop ALL` · `no-new-privileges` · uid 65534 · `--memory`/`--memory-swap` 256 MB (768 MB for compile) · `--cpus 1` · `--pids-limit 64` · `ulimit nofile=64, fsize=8 MB, core=0` · wall-clock timeout (4 s) enforced with `docker kill` · stdout/stderr capped (64 KB / 16 KB; the reader keeps draining and kills the container on overflow) · source mounted **read-only**; C++ compiles in a separate container and the binary is run in a different one. Images: `gcc:13` (C++17, `-O2`), `python:3.12-alpine`.

## Adversarial tests (real containers, `tests/test_sandbox_security.py`, 13 passing)
compile error reported, runtime error/exit code, infinite loop → TLE, 900 MB allocation → killed, Python and C++ fork bombs contained and host stays responsive, network and DNS unreachable, root FS read-only (but `/tmp` writable and ephemeral), source mount read-only, host paths and the Docker socket invisible, runs as uid 65534 and cannot `setuid(0)`, output flood → OLE without buffering, oversize input/unknown language rejected, sample-test judge flags WA. Tests are **skipped, not faked**, when Docker/images are missing. One real bug was found by these tests (pipe not drained after the output cap, blocking `docker kill`) and fixed.

## API limits
20 runs/min/user, 4 concurrent containers per API process (429 + `Retry-After` when busy), 64 KB code, 64 KB stdin, ≤20 sample tests. If Docker is unreachable: HTTP 503 with a clear message and the UI shows an "unavailable" banner.

## Known limits and the trust boundary
- Wall time includes container start-up (~250 ms); **peak memory is not measured** (reported `null`, never guessed).
- The API needs access to a Docker daemon. Mounting the host socket (as docker-compose does for dev) is root-equivalent on the host. **For production run the executor on a dedicated runner host/service** reachable over an authenticated internal API, and consider gVisor (`--runtime=runsc`) or Firecracker for stronger isolation than runc.
- Only C++17 and Python today. Passing sample tests is not a verified solve.

## Deployment shape (compose)
The `executor` service is its own image target (`backend/Dockerfile`, `--target executor`) with a static Docker CLI copied from the official `docker` image (Debian 13's `docker.io` package no longer ships the CLI, which broke the previous recipe). It is the only service with the Docker socket. Because sandbox containers are *siblings* on the host daemon, the executor's scratch directory (`SANDBOX_WORKDIR`) is bind-mounted at the **same path** on host and in the container. The API forwards `/execute`, judging **and the stress tester** to it when `CODEMIND_EXECUTOR_URL` is set (stress testing previously returned 501 in that mode). Verified: code run through the executor from the load balancer (`6*7` -> `42`). Production should still put the executor on its own VM (`docs/DEPLOYMENT.md`).
