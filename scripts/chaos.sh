#!/usr/bin/env bash
# Failure drills against a running compose stack. Prints what a user would have seen. Needs: docker compose, curl.
#   scripts/chaos.sh [BASE_URL]       (use the same --env-file you started the stack with: COMPOSE_ENV=path)
set -uo pipefail
BASE="${1:-http://localhost:8080}"
DC="docker compose ${COMPOSE_ENV:+--env-file $COMPOSE_ENV}"
EMAIL="chaos-$RANDOM$RANDOM@example.com"; PW="chaos-pass-$RANDOM-xyz-123"
TOK=$(curl -s -X POST "$BASE/api/auth/register" -H 'content-type: application/json' -d "{\"email\":\"$EMAIL\",\"display_name\":\"Chaos\",\"password\":\"$PW\"}" | python3 -c "import sys,json;print(json.load(sys.stdin)['access_token'])")
H="Authorization: Bearer $TOK"

# run N seconds of steady GET traffic (~15 req/s, authenticated, hitting DB+cache), return "total bad"
traffic() { local secs=$1 total=0 bad=0 end; end=$((SECONDS+secs)); while [ $SECONDS -lt $end ]; do
    c=$(curl -s -o /dev/null -w '%{http_code}' -H "$H" "$BASE/api/resources/overview"); total=$((total+1)); [ "$c" = 200 ] || bad=$((bad+1)); sleep 0.06; done; echo "$total $bad"; }

echo "== drill 1: kill one API replica under load"
( sleep 3; victim=$($DC ps -q api | head -1); docker kill "$victim" >/dev/null; echo "   killed api replica ${victim:0:12}" ) &
read -r t b < <(traffic 14); wait
echo "   requests=$t non-200=$b"; $DC up -d --no-recreate api >/dev/null 2>&1   # compose restarts the dead replica

echo "== drill 2: Redis disappears (cache + rate-limit + leader lease backend)"
$DC stop redis >/dev/null 2>&1
sleep 1; read -r t b < <(traffic 8)
echo "   requests=$t non-200=$b   (Redis down: the API must degrade, not fail)"
echo "   /ready says: $(curl -s "$BASE/api/ready")"
$DC start redis >/dev/null 2>&1; sleep 20
echo "   after Redis returns, /ready says: $(curl -s "$BASE/api/ready" | python3 -c "import sys,json;print(json.load(sys.stdin)['checks'])")"

echo "== drill 3: Postgres restarts"
( sleep 2; $DC restart db >/dev/null 2>&1 ) &
read -r t b < <(traffic 20); wait
echo "   requests=$t non-200=$b   (brief errors expected while the only database is down; recovery is the point)"
sleep 3; echo "   afterwards: /ready -> $(curl -s -o /dev/null -w '%{http_code}' "$BASE/api/ready"), authenticated request -> $(curl -s -o /dev/null -w '%{http_code}' -H "$H" "$BASE/api/resources/overview")"
