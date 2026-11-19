"""Per-source capability matrix. Statuses describe what Nexora can LEGITIMATELY do today (S=Supported, P=Partial, U=Unavailable),
with the evidence. Evidence: scripts/probe_sources.py output saved at docs/evidence/source-probe-2026-11-19.json plus manual checks.
`Unavailable` includes "accessible but deliberately not ingested" (reason given). Nothing is Supported without a working, tested adapter."""
VERIFIED_ON = "2026-11-19"
S, P, U = "Supported", "Partial", "Unavailable"
AV, NA, UV = "Available", "Not available", "Unverified"
RQ, OP, NR = "Required", "Optional", "Not required"
RV, RS, UC = "Verified", "Restricted", "Unclear"
COLS = ("listing", "backfill", "detail", "topics", "difficulty", "contest", "submissions", "profile", "incremental")


def row(slug, name, url, caps, api, auth, rights, evidence, adapter=None, group="platform"):
    d = dict(zip(COLS, caps))
    return {"slug": slug, "name": name, "url": url, "group": group, **d, "official_api": api, "auth": auth, "data_rights": rights,
            "evidence": evidence, "adapter": adapter, "verified_on": VERIFIED_ON}


_U9 = (U,) * 9
_NOT_DONE = "Reachable (HTTP 200) but no verified API and no adapter built; not ingested. Link only."
MATRIX = [
    row("codeforces", "Codeforces", "https://codeforces.com/problemset", (S, S, P, S, S, S, S, S, S), AV, NR, RS,
        "Official API (apiHelp). problemset.problems returned 11,526 problems incl. rating, tags, solvedCount. HTML pages return 403 to automation (not used) so statements are link-only. robots Content-Signal ai-train=no: metadata is indexed, never used for model training.", "codeforces"),
    row("cf-gym", "Codeforces Gym", "https://codeforces.com/gyms", (P, U, U, U, U, P, U, U, P), AV, NR, RS,
        "Contest list via official API contest.list?gym=true (HTTP 200, ~1 MB). Gym problems need contest.standings per contest: not built. HTML /gyms returns 403.", "codeforces"),
    row("atcoder", "AtCoder (via AtCoder Problems)", "https://kenkoooo.com/atcoder/", (S, S, P, U, P, S, S, P, S), NA, NR, UC,
        "kenkoooo merged-problems.json (9,969 problems, solver_count) + problem-models difficulty estimates + v3 submissions API. No official AtCoder API. No tags anywhere. atcoder.jp robots disallows /users/*/history/ => rating history NOT used.", "atcoder"),
    row("codechef", "CodeChef", "https://www.codechef.com/practice", (S, S, U, U, P, P, U, U, S), NA, NR, UC,
        "Public JSON /api/list/problems/all?limit&page reports count=21,697, paginated; difficulty_rating only when set; submission stats present. No problem-detail endpoint found (/api/problems/CODE=404). Official API needs OAuth client credentials. robots does not disallow /api.", "codechef"),
    row("leetcode", "LeetCode", "https://leetcode.com/problemset/", _U9, NA, OP, RS,
        "problemset and /api/problems return 403 to automation; robots disallows /api/. GraphQL undocumented and unused. Problems enter only via sheet imports (title/difficulty/link) and user CSV import.", None),
    row("geeksforgeeks", "GeeksforGeeks", "https://www.geeksforgeeks.org/explore", _U9, UV, OP, RS, "Explore page 200 but /problems/ loops redirects for automation; robots has AI-crawler restrictions. Link only via sheets.", None),
    row("hackerrank", "HackerRank", "https://www.hackerrank.com/domains", _U9, NA, OP, RS,
        "A /rest/ JSON endpoint answers, but robots.txt disallows /rest/ => deliberately not used. HTML domains pages are JS apps.", None),
    row("hackerearth", "HackerEarth", "https://www.hackerearth.com/practice/", _U9, UV, OP, UC, _NOT_DONE, None),
    row("topcoder", "Topcoder", "https://www.topcoder.com/challenges", _U9, UV, OP, UC, "challenges redirects to a SPA; api.topcoder.com/v5/challenges returned 404 (public API not verified).", None),
    row("codesignal", "CodeSignal", "https://app.codesignal.com/arcade", _U9, NA, RQ, RS, "app.codesignal.com robots.txt: Disallow /. Not accessible.", None),
    row("cses", "CSES", "https://cses.fi/problemset/", (S, S, P, P, U, U, U, U, P), NA, NR, UC,
        "One public HTML page lists 400 tasks in sections with solved/attempted counts. No robots.txt, no explicit licence => metadata + link only, single polite request. Progress needs login (not used).", "cses"),
    row("spoj", "SPOJ", "https://www.spoj.com/problems/classical/", _U9, NA, OP, UC, "Problem pages return 403 to automation. robots disallows only status/ranks.", None),
    row("kattis", "Kattis", "https://open.kattis.com/problems", _U9, NA, OP, RS,
        "HTML list reachable (200); robots Content-Signal: ai-train=no, use=reference. No API. Conservatively not ingested.", None),
    row("dmoj", "DMOJ", "https://dmoj.ca/problems/", (S, S, S, S, P, P, U, U, S), AV, NR, RS,
        "Public API v2: /problems (5,274 incl. types, points, group) and /problem/<code> (time/memory limits, languages). Contest list exists but the problem->contest link is not in the API. Per-user submissions need a token. Content-Signal ai-train=no.", "dmoj"),
    row("timus", "Timus Online Judge", "https://acm.timus.ru/problemset.aspx", (P, U, U, U, U, U, U, U, U), NA, NR, UC,
        "HTML problem set reachable; robots permits problemset.aspx. HTML parser not built; not ingested.", None),
    row("projecteuler", "Project Euler", "https://projecteuler.net/archives", (S, S, U, U, P, U, U, U, S), NA, NR, RS,
        "minimal=problems plain-text list (ID, title, published, solved-by) returned 200. Content is CC BY-NC-SA 2.0: titles/links/counts only. No robots.txt. No profile API.", "projecteuler"),
    row("toph", "Toph", "https://toph.co/problems", _U9, NA, OP, RS, "robots Content-Signal: ai-train=no, ai-input=no. Not ingested.", None),
    row("csacademy", "CSAcademy", "https://csacademy.com/", _U9, UV, OP, UC, "Landing page only (3 KB SPA). " + _NOT_DONE, None),
    row("uva", "UVa Online Judge", "https://onlinejudge.org/index.php?option=com_onlinejudge&Itemid=8", (P, U, U, U, U, U, U, U, U), NA, OP, UC, "HTML category pages reachable; robots allows. Parser not built.", None),
    row("lightoj", "LightOJ", "https://lightoj.com/problems", _U9, UV, OP, UC, "3 MB JS-rendered page; no robots.txt. " + _NOT_DONE, None),
    row("usaco", "USACO", "https://usaco.org/index.php?page=contests", (P, U, U, U, U, P, U, U, U), NA, NR, UC, "Contest archive HTML reachable; robots allows. Parser not built.", None),
    row("aizu", "Aizu Online Judge", "https://onlinejudge.u-aizu.ac.jp/problems", _U9, UV, OP, UC, "Old judgeapi.u-aizu.ac.jp endpoint now returns 410 Gone; current API not located.", None),
    row("yukicoder", "yukicoder", "https://yukicoder.me/", (S, S, P, P, S, U, U, U, S), AV, NR, UC,
        "Official API /api/v1/problems returned 3,967 problems (No, Title, Level, Tags, Date). User APIs need a key (not used). No robots.txt.", "yukicoder"),
    row("luogu", "Luogu", "https://www.luogu.com.cn/problem/list", _U9, UV, OP, UC, "problem/list is HTML (_contentOnly returns HTML); robots allows list pages. No documented API; not ingested.", None),
    row("omegaup", "omegaUp", "https://omegaup.com/arena/", _U9, AV, OP, RS, "A JSON API exists but robots.txt disallows /api/ and the endpoint answers 429 => not used.", None),
    row("beecrowd", "beecrowd", "https://judge.beecrowd.com/en/problems/index/1", _U9, NA, OP, RS, "Returns 403 to automation; robots has AI-crawler restrictions.", None),
    row("tlx", "TLX TOKI", "https://tlx.toki.id/problems", _U9, UV, OP, UC, "SPA shell (834 B); guessed api.tlx.toki.id path returned 404.", None),
    row("quera", "Quera", "https://quera.org/problemset", _U9, UV, OP, UC, _NOT_DONE, None),
    row("eolymp", "Eolymp", "https://eolymp.com/en/problems", _U9, UV, OP, UC, "Redirects to /problems (SPA); api.eolymp.com/spec returned 404.", None),
    row("france-ioi", "France-IOI", "https://www.france-ioi.org/", _U9, UV, OP, UC, _NOT_DONE, None),
    row("kilonova", "Kilonova", "https://kilonova.ro/", _U9, AV, OP, RS, "/api/problem/search answers 400 but robots.txt disallows /api/ => not used.", None),
    row("szkopul", "Szkopuł", "https://szkopul.edu.pl/", _U9, UV, OP, UC, _NOT_DONE, None),
    row("infoarena", "infoarena", "https://infoarena.ro/", _U9, UV, OP, UC, _NOT_DONE, None),
    row("neps", "Neps Academy", "https://neps.academy/", _U9, UV, OP, UC, _NOT_DONE, None),
    row("ksp", "KSP", "https://ksp.mff.cuni.cz/", _U9, UV, OP, UC, "Czech seminar site; robots disallows its /api/tasks/. " + _NOT_DONE, None),
    row("codeup", "CodeUp", "https://codeup.kr/", _U9, NA, RQ, RS, "robots.txt: Disallow /. Not accessible.", None),
    row("mendo", "MENDO", "https://mendo.mk/", _U9, UV, OP, UC, "Redirects to http://mendo.mk/Welcome.do (plain HTTP); no robots.txt. " + _NOT_DONE, None),
    row("icpc", "ICPC (icpc.global, u.icpc.global)", "https://u.icpc.global/problems/", (P, U, U, U, U, P, U, U, U), NA, NR, UC, "Directory/resource pages (200). They point to external archives; no structured problem data. Used as discovery leads.", None, "archive"),
    row("ubc", "UBC ICPC resources", "https://icpc.cs.ubc.ca/resources", (P, U, U, U, U, U, U, U, U), NA, NR, UC, "Resource directory page (200). Discovery lead only.", None, "archive"),
    row("clist", "CLIST", "https://clist.by/", (U, U, U, U, U, P, U, U, P), AV, RQ, UC, "API returns 401 without the user's own key; site 403 to automation. Contests adapter written to docs but NOT verified live.", "clist", "archive"),
    row("google-cc", "Google Coding Competitions", "https://codingcompetitions.withgoogle.com/", _U9, NA, NR, UC, "Site returns 404 (programme archived by Google).", None, "archive"),
    row("rosalind", "Rosalind", "https://rosalind.info/problems/locations/", _U9, NA, OP, UC, "Returns 403 to automation (robots also 403).", None, "archive"),
]
BY_SLUG = {r["slug"]: r for r in MATRIX}

# Sheet / reference collections from the second directive (discovery sources); statuses live in importers/registry.py for sheets.
REFERENCES = [
    ("usaco-guide", "USACO Guide", "https://usaco.guide/", "Repository licence is CC BY-NC-SA 4.0 (non-commercial, share-alike): not ingested; link only."),
    ("a2oj", "A2OJ", "https://a2oj.netlify.app/", "1.3 KB JS shell; no data endpoint found."),
    ("kactl", "KACTL", "https://github.com/kth-competitive-programming/kactl", "Algorithm library (code), not a problem set; link only."),
    ("cp-algorithms", "CP-Algorithms", "https://cp-algorithms.com/", "Article site; useful as editorial/reference links per pattern; no structured problem data."),
    ("cses-book", "Competitive Programmer's Handbook", "https://cses.fi/book/book.pdf", "PDF (1.1 MB, HTTP 200). Reference material; link only."),
]
