"""Adversarial tests against REAL containers. Skipped (not faked) when Docker or the images are unavailable."""
import time

import pytest

from app.execution import runner

pytestmark = pytest.mark.skipif(not (runner.docker_ready() and all(runner.image_present(l.image) for l in runner.LANGS.values())),
                                reason="Docker + sandbox images required")


def py(code, stdin=""): return runner.run_code("python", code, stdin)
def cpp(code, stdin=""): return runner.run_code("cpp17", code, stdin)


def test_normal_programs_run_in_both_languages():
    assert py("print(sum(map(int,input().split())))", "1 2 3").stdout.strip() == "6"
    r = cpp("#include <bits/stdc++.h>\nint main(){int a,b;std::cin>>a>>b;std::cout<<a+b;}", "4 5")
    assert r.verdict == "OK" and r.stdout == "9" and r.compile_ms


def test_compile_error_is_reported_not_executed():
    r = cpp("int main(){ this is not c++ }")
    assert r.verdict == "CE" and "error" in r.stderr.lower() and r.stdout == ""


def test_runtime_error_exit_code_and_stderr():
    r = py("import sys\nprint('x'); sys.exit(3)")
    assert r.verdict == "RE" and r.exit_code == 3 and r.stdout.strip() == "x"
    assert py("1/0").verdict == "RE" and "ZeroDivisionError" in py("1/0").stderr


def test_infinite_loop_is_killed_at_the_time_limit(monkeypatch):
    monkeypatch.setitem(runner.LIMITS, "time_s", 2.0)
    t = time.time()
    r = py("while True: pass")
    assert r.verdict == "TLE" and time.time() - t < 8


def test_memory_hog_is_killed_by_the_memory_limit():
    r = py("x = bytearray(900 * 1024 * 1024)\nprint(len(x))")
    assert r.verdict in ("MLE", "RE") and r.stdout.strip() == ""


def test_fork_bomb_is_contained_by_pids_limit_and_returns_promptly():
    t = time.time()
    r = py("import os\nfor _ in range(500):\n    try:\n        os.fork()\n    except OSError as e:\n        print('blocked', e.errno); break\n")
    assert time.time() - t < 20 and (r.verdict in ("OK", "RE", "TLE", "MLE"))
    r2 = cpp("#include <unistd.h>\n#include <cstdio>\nint main(){ int n=0; for(;;){ if(fork()<0){ printf(\"blocked %d\\n\", n>=0); return 0;} n++; if(n>2000) return 0; } }")
    assert r2.verdict in ("OK", "RE", "TLE", "MLE")  # the host must stay alive; checked below by running another job
    assert py("print('host alive')").stdout.strip() == "host alive"


def test_no_network_access():
    r = py("import socket\ntry:\n    socket.create_connection(('1.1.1.1',53),2); print('OPEN')\nexcept Exception as e:\n    print('blocked')")
    assert r.stdout.strip() == "blocked"
    r = py("import socket\ntry:\n    print(socket.gethostbyname('example.com'))\nexcept Exception:\n    print('no-dns')")
    # DNS has nowhere to go: it either fails fast or hangs until the time limit (TLE). Either way no address is ever returned.
    assert r.stdout.strip() in ("no-dns", "") and r.verdict in ("OK", "TLE", "RE") and "." not in r.stdout


def test_rootfs_is_read_only_but_tmp_is_writable_and_ephemeral():
    r = py("import os\ntry:\n    open('/etc/pwn','w').write('x'); print('WROTE')\nexcept Exception as e:\n    print('ro')\nopen('/tmp/ok','w').write('1'); print('tmp-ok')")
    assert r.stdout.split() == ["ro", "tmp-ok"]
    assert py("import os\nprint(os.path.exists('/tmp/ok'))").stdout.strip() == "False"  # nothing persists between runs


def test_source_mount_is_read_only_and_host_files_are_invisible():
    r = py("try:\n    open('/w/main.py','a').write('#'); print('MODIFIED')\nexcept Exception:\n    print('ro')")
    assert r.stdout.strip() == "ro"
    r = py("import os\nprint(os.path.exists('/home/jas'), os.path.exists('/var/run/docker.sock'))")
    assert r.stdout.strip() == "False False"


def test_runs_as_unprivileged_user_without_capabilities():
    r = py("import os\nprint(os.getuid(), os.geteuid())")
    assert r.stdout.split() == ["65534", "65534"]
    r = py("import os\ntry:\n    os.setuid(0); print('ROOT')\nexcept Exception:\n    print('no-root')")
    assert r.stdout.strip() == "no-root"


def test_huge_output_is_truncated_and_killed_not_buffered():
    t = time.time()
    r = py("import sys\nwhile True:\n    sys.stdout.write('x'*100000)")
    assert r.verdict == "OLE" and len(r.stdout) <= runner.LIMITS["out_bytes"] and r.truncated and time.time() - t < 15


def test_oversize_input_and_unknown_language_are_rejected_before_docker():
    assert runner.run_code("python", "x" * 70000).verdict == "ERR"
    assert runner.run_code("brainfuck", "+").verdict == "ERR"


def test_judge_compares_whitespace_normalised_output_and_flags_wrong_answers():
    r = runner.judge("python", "a,b=map(int,input().split())\nprint(a+b)", [{"input": "1 2", "expected": "3"}, {"input": "5 5", "expected": "11"}])
    assert [t["verdict"] for t in r.tests] == ["OK", "WA"] and r.verdict == "WA"


JAVA_OK = "public class Main{public static void main(String[] a)throws Exception{java.io.BufferedReader b=new java.io.BufferedReader(new java.io.InputStreamReader(System.in));System.out.println(Integer.parseInt(b.readLine().trim())*2);}}"


@pytest.mark.skipif(not all(runner.image_present(runner.LANGS[l].image) for l in ("java", "javascript")), reason="java/node images required")
def test_java_and_javascript_run_and_obey_the_same_limits(monkeypatch):
    assert runner.run_code("java", JAVA_OK, "21").stdout.strip() == "42"
    assert runner.run_code("javascript", "console.log(Number(require('fs').readFileSync(0,'utf8'))*2)", "21").stdout.strip() == "42"
    assert runner.run_code("java", "public class Main{ oops }").verdict == "CE"
    assert runner.run_code("java", "public class Main{public static void main(String[] a){throw new RuntimeException();}}").verdict == "RE"
    monkeypatch.setitem(runner.LIMITS, "time_s", 2.0)
    assert runner.run_code("javascript", "while(true){}").verdict == "TLE"
    assert runner.run_code("java", "public class Main{public static void main(String[] a){long[] x=new long[600000000];System.out.println(x.length);}}").verdict in ("RE", "MLE")
    r = runner.run_code("javascript", "require('net').connect(53,'1.1.1.1').on('error',()=>console.log('blocked')).on('connect',()=>console.log('OPEN'));setTimeout(()=>process.exit(0),1500)")
    assert r.stdout.strip() == "blocked"
    r = runner.run_code("javascript", "const fs=require('fs');try{fs.writeFileSync('/etc/pwn','x');console.log('WROTE')}catch(e){console.log('ro')}")
    assert r.stdout.strip() == "ro"
