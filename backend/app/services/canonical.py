"""Canonical problem identity: (platform, external_id) derived from verified URL patterns only.

Two problems are the same iff they resolve to the same (platform, external_id). Titles are NEVER used to merge.
"""
import re
from urllib.parse import parse_qs, urlparse

_R = [
    ("codeforces", re.compile(r"codeforces\.com/(?:problemset/problem|contest|gym)/(\d+)/(?:problem/)?([A-Za-z]\d?)$"), lambda m: f"{m[1]}{m[2].upper()}", lambda m: f"https://codeforces.com/problemset/problem/{m[1]}/{m[2].upper()}"),
    ("leetcode", re.compile(r"leetcode\.(?:com|cn)/problems/([a-z0-9\-]+)"), lambda m: m[1], lambda m: f"https://leetcode.com/problems/{m[1]}/"),
    ("atcoder", re.compile(r"atcoder\.jp/contests/([a-z0-9_\-]+)/tasks/([a-z0-9_\-]+)$"), lambda m: m[2], lambda m: f"https://atcoder.jp/contests/{m[1]}/tasks/{m[2]}"),
    ("cses", re.compile(r"cses\.fi/problemset/(?:task|view)/(\d+)"), lambda m: m[1], lambda m: f"https://cses.fi/problemset/task/{m[1]}"),
    ("geeksforgeeks", re.compile(r"geeksforgeeks\.org/problems/([a-z0-9\-]+)"), lambda m: m[1], lambda m: f"https://www.geeksforgeeks.org/problems/{m[1]}/1"),
    ("spoj", re.compile(r"spoj\.com/problems/([A-Za-z0-9_]+)"), lambda m: m[1].upper(), lambda m: f"https://www.spoj.com/problems/{m[1].upper()}/"),
    ("kattis", re.compile(r"kattis\.com/problems/([a-z0-9.\-_]+)"), lambda m: m[1], lambda m: f"https://open.kattis.com/problems/{m[1]}"),
    ("dmoj", re.compile(r"dmoj\.ca/problem/([a-z0-9_]+)"), lambda m: m[1], lambda m: f"https://dmoj.ca/problem/{m[1]}"),
    ("codechef", re.compile(r"codechef\.com/(?:[a-z0-9_\-]+/)?problems/([A-Za-z0-9_]+)"), lambda m: m[1].upper(), lambda m: f"https://www.codechef.com/problems/{m[1].upper()}"),
    ("hackerrank", re.compile(r"hackerrank\.com/challenges/([a-z0-9\-]+)"), lambda m: m[1], lambda m: f"https://www.hackerrank.com/challenges/{m[1]}/problem"),
    ("projecteuler", re.compile(r"projecteuler\.net/problem=(\d+)"), lambda m: m[1], lambda m: f"https://projecteuler.net/problem={m[1]}"),
    ("yukicoder", re.compile(r"yukicoder\.me/problems/(?:no/)?(\d+)"), lambda m: m[1], lambda m: f"https://yukicoder.me/problems/no/{m[1]}"),
    ("timus", re.compile(r"acm\.timus\.ru/problem\.aspx"), None, None),  # handled via query string below
]


def canonicalize(url: str) -> tuple[str, str, str] | None:
    """-> (platform, external_id, canonical_url) or None when the URL is not a recognised problem page."""
    if not url:
        return None
    url = url.strip()
    try:
        u = urlparse(url if "://" in url else "https://" + url)
    except ValueError:
        return None
    if not u.netloc:
        return None
    host_path = f"{u.netloc.lower().removeprefix('www.')}{u.path.rstrip('/')}"
    if "acm.timus.ru" in host_path:
        num = parse_qs(u.query).get("num", [None])[0]
        return ("timus", num, f"https://acm.timus.ru/problem.aspx?num={num}") if num and num.isdigit() else None
    if "projecteuler.net" in host_path:
        m = re.search(r"problem=(\d+)", u.path + "?" + u.query)
        return ("projecteuler", m[1], f"https://projecteuler.net/problem={m[1]}") if m else None
    for platform, rx, ext, canon in _R:
        if ext is None:
            continue
        m = rx.search(host_path)
        if m:
            return platform, ext(m), canon(m)
    return None
