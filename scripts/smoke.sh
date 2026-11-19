#!/usr/bin/env bash
# End-to-end smoke test against a running stack (local compose, CI, or a freshly deployed VM).
#   scripts/smoke.sh [BASE_URL]            BASE_URL defaults to http://localhost:8080
# Env: EXPECT_REPLICAS=3   fail unless requests were served by at least this many distinct API replicas
#      WITH_SANDBOX=1      also run code through the executor (needs the language images pulled on the executor host)
set -uo pipefail
BASE="${1:-http://localhost:8080}"; EXPECT="${EXPECT_REPLICAS:-1}"
fail=0; ok() { echo "  ok   $1"; }; bad() { echo "  FAIL $1"; fail=1; }
code() { curl -s -o /dev/null -w '%{http_code}' "$@"; }
jget() { python3 -c "import sys,json;d=json.load(sys.stdin);print(eval(sys.argv[1]))" "$1"; }

echo "== smoke: $BASE"
for i in $(seq 1 60); do [ "$(code "$BASE/api/ready")" = 200 ] && break; sleep 2; done
[ "$(code "$BASE/lb-health")" = 200 ] && ok "load balancer healthy" || bad "load balancer"
[ "$(code "$BASE/api/ready")" = 200 ] && ok "api ready (database reachable)" || bad "api /ready"
[ "$(code "$BASE/")" = 200 ] && ok "web serves /" || bad "web /"
[ "$(code "$BASE/login")" = 200 ] && ok "web serves /login" || bad "web /login"

# load is spread across replicas (X-Served-By is set by every API replica)
served=$(for i in $(seq 1 40); do curl -s -D - -o /dev/null "$BASE/api/ready" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-served-by"{print $2}'; done | sort -u | wc -l)
[ "$served" -ge "$EXPECT" ] && ok "requests served by $served distinct API replica(s) (expected >= $EXPECT)" || bad "only $served API replica(s) answered (expected >= $EXPECT)"

# auth flow through the balancer, same-origin
EMAIL="smoke-$(date +%s)-$RANDOM@example.com"; PW="smoke-pass-$(date +%s)-xyz"
reg=$(curl -s -X POST "$BASE/api/auth/register" -H 'content-type: application/json' -d "{\"email\":\"$EMAIL\",\"display_name\":\"Smoke\",\"password\":\"$PW\"}")
TOK=$(echo "$reg" | jget "d.get('access_token','')" 2>/dev/null)
[ -n "$TOK" ] && ok "register + token" || { bad "register ($reg)"; TOK=""; }
H="Authorization: Bearer $TOK"
[ "$(code "$BASE/api/auth/me" -H "$H")" = 200 ] && ok "authenticated /me" || bad "/me with token"
[ "$(code "$BASE/api/auth/me")" = 401 ] && ok "/me without token is 401" || bad "/me without token should be 401"
[ "$(code "$BASE/api/metrics")" = 401 ] && ok "/metrics closed without token" || bad "/metrics must require the metrics token"
[ "$(code "$BASE/api/resources/overview" -H "$H")" = 200 ] && ok "resources overview (DB + cache path)" || bad "resources overview"
[ "$(code "$BASE/api/patterns" -H "$H")" = 200 ] && ok "patterns" || bad "patterns"

# a wrong password must not leak which half was wrong
[ "$(code -X POST "$BASE/api/auth/login" -H 'content-type: application/json' -d "{\"email\":\"$EMAIL\",\"password\":\"wrong-wrong-wrong\"}")" = 401 ] && ok "bad login is 401" || bad "bad login"

# security headers present on the edge
hdrs=$(curl -s -D - -o /dev/null "$BASE/")
echo "$hdrs" | grep -qi '^x-frame-options: DENY' && ok "X-Frame-Options" || bad "X-Frame-Options missing"
echo "$hdrs" | grep -qi '^content-security-policy:' && ok "CSP header" || bad "CSP missing"

if [ "${WITH_SANDBOX:-0}" = 1 ]; then
  out=$(curl -s -X POST "$BASE/api/execute" -H "$H" -H 'content-type: application/json' -d '{"language":"python","code":"print(6*7)","stdin":""}')
  [ "$(echo "$out" | jget "d.get('verdict')" 2>/dev/null)" = OK ] && [ "$(echo "$out" | jget "d.get('stdout','').strip()" 2>/dev/null)" = 42 ] && ok "sandbox ran code via executor (42)" || bad "sandbox run: $out"
fi
# leave nothing behind: the smoke user is deleted (matters when this runs against production on every deploy)
[ -n "$TOK" ] && { [ "$(code -X DELETE "$BASE/api/auth/me" -H "$H")" = 204 ] && ok "smoke account removed" || bad "could not delete the smoke account"; }
[ $fail = 0 ] && echo "== SMOKE PASSED" || { echo "== SMOKE FAILED"; exit 1; }
