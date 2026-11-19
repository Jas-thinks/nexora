"""Problem sources. Each uses only endpoints verified on 2026-11-19 (see docs/global-problem-source-registry.md)."""
import re
from datetime import UTC, datetime

from app.integrations.http import FetchError, PoliteClient
from app.sources.base import ProblemRecord, ProblemSource


def _dt(s: str, assume=UTC) -> datetime | None:
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=assume)
    except (ValueError, AttributeError):
        return None


class CodeforcesSource(ProblemSource):
    platform, source_name = "codeforces", "codeforces:api/problemset.problems"

    def __init__(self, http: PoliteClient | None = None):
        self.http = http or PoliteClient(min_interval=2.0)

    def pages(self, cursor):
        d = self.http.get_json("https://codeforces.com/api/problemset.problems")
        if d.get("status") != "OK":
            raise FetchError(f"Codeforces API: {d.get('comment')}")
        stats = {(s["contestId"], s["index"]): s for s in d["result"].get("problemStatistics", [])}
        out = []
        for p in d["result"]["problems"]:
            if "contestId" not in p:
                continue
            st = stats.get((p["contestId"], p["index"]), {})
            out.append(ProblemRecord("codeforces", f"{p['contestId']}{p['index']}", p["name"],
                                     f"https://codeforces.com/problemset/problem/{p['contestId']}/{p['index']}", p.get("rating"),
                                     None, sorted(p.get("tags", [])), str(p["contestId"]), p["index"], solved_count=st.get("solvedCount"),
                                     raw={"problem": p, "stat": st}))
        self.discovered_total = len(out)
        yield out, None


class AtCoderSource(ProblemSource):
    platform, source_name = "atcoder", "kenkoooo:resources/merged-problems.json"

    def __init__(self, http: PoliteClient | None = None):
        self.http = http or PoliteClient(min_interval=1.0)

    def pages(self, cursor):
        probs = self.http.get_json("https://kenkoooo.com/atcoder/resources/merged-problems.json")
        try:
            models = self.http.get_json("https://kenkoooo.com/atcoder/resources/problem-models.json")
        except FetchError:
            models = {}
        out = []
        for p in probs:
            d = (models.get(p["id"]) or {}).get("difficulty")
            out.append(ProblemRecord("atcoder", p["id"], p.get("title") or p["name"], f"https://atcoder.jp/contests/{p['contest_id']}/tasks/{p['id']}",
                                     None, f"est. difficulty {int(d)} (AtCoder Problems)" if d is not None else None, [], p["contest_id"], p.get("problem_index"),
                                     solved_count=p.get("solver_count"), raw=p))
        self.discovered_total = len(out)
        yield out, None


class DMOJSource(ProblemSource):
    platform, source_name = "dmoj", "dmoj:api/v2/problems"
    BASE, MAX_PAGES = "https://dmoj.ca/api/v2", 200

    def __init__(self, http: PoliteClient | None = None):
        self.http = http or PoliteClient(min_interval=1.0)

    def pages(self, cursor):
        page = (cursor or {}).get("page", 1)
        while page <= self.MAX_PAGES:
            d = self.http.get_json(f"{self.BASE}/problems", params={"page": page})["data"]
            recs = [ProblemRecord("dmoj", p["code"], p["name"], f"https://dmoj.ca/problem/{p['code']}", None,
                                  f"{p['points']:g} points" if p.get("points") else None, sorted(p.get("types", [])), None, None, raw=p, section=p.get("group"))
                    for p in d["objects"]]
            more = d.get("has_more")
            yield recs, ({"page": page + 1} if more else None)
            if not more:
                return
            page += 1
        raise FetchError(f"DMOJ pagination exceeded {self.MAX_PAGES} pages")

    def details(self, ref: str):
        o = self.http.get_json(f"{self.BASE}/problem/{ref}")["data"]["object"]
        return ProblemRecord("dmoj", o["code"], o["name"], f"https://dmoj.ca/problem/{o['code']}", None, f"{o['points']:g} points" if o.get("points") else None,
                             sorted(o.get("types", [])), None, None, int(o["time_limit"] * 1000) if o.get("time_limit") else None, o.get("memory_limit"),
                             raw=o, section=o.get("group"))


class CodeChefSource(ProblemSource):
    platform, source_name = "codechef", "codechef:api/list/problems"
    PAGE, MAX_PAGES = 100, 400

    def __init__(self, http: PoliteClient | None = None):
        self.http = http or PoliteClient(min_interval=1.0)

    @staticmethod
    def _int(x):
        try:
            return int(x)
        except (TypeError, ValueError):
            return None

    def pages(self, cursor):
        page = (cursor or {}).get("page", 1)
        while page <= self.MAX_PAGES:
            d = self.http.get_json("https://www.codechef.com/api/list/problems/all", params={"limit": self.PAGE, "page": page})
            if d.get("status") != "success":
                raise FetchError(f"CodeChef: {d.get('message')}")
            self.discovered_total = self._int(d.get("count")) or self.discovered_total
            rows = d.get("data", [])
            recs = []
            for p in rows:
                dr = self._int(p.get("difficulty_rating"))
                recs.append(ProblemRecord("codechef", p["code"].upper(), p["name"], f"https://www.codechef.com/problems/{p['code'].upper()}", None,
                                          f"CodeChef difficulty {dr}" if dr and dr > 0 else None, [], p.get("contest_code") or None, None,
                                          solved_count=self._int(p.get("distinct_successful_submissions")), submission_count=self._int(p.get("total_submissions")),
                                          accepted_count=self._int(p.get("successful_submissions")), raw=p))
            last = not rows or (self.discovered_total is not None and page * self.PAGE >= self.discovered_total)
            yield recs, (None if last else {"page": page + 1})
            if last:
                return
            page += 1
        raise FetchError(f"CodeChef pagination exceeded {self.MAX_PAGES} pages")


class YukicoderSource(ProblemSource):
    platform, source_name = "yukicoder", "yukicoder:api/v1/problems"

    def __init__(self, http: PoliteClient | None = None):
        self.http = http or PoliteClient(min_interval=1.0)

    def pages(self, cursor):
        rows = self.http.get_json("https://yukicoder.me/api/v1/problems")
        out = [ProblemRecord("yukicoder", str(p["No"]), p["Title"], f"https://yukicoder.me/problems/no/{p['No']}", None,
                             f"Level {p['Level']:g}" if p.get("Level") is not None else None,
                             sorted(t for t in (p.get("Tags") or "").split(",") if t), None, None, published_at=_dt(p.get("Date") or "", UTC), raw=p) for p in rows]
        self.discovered_total = len(out)
        yield out, None


class ProjectEulerSource(ProblemSource):
    platform, source_name = "projecteuler", "projecteuler:minimal=problems"

    def __init__(self, http: PoliteClient | None = None):
        self.http = http or PoliteClient(min_interval=1.0)

    def pages(self, cursor):
        r = self.http.client.get("https://projecteuler.net/minimal=problems")
        if r.status_code != 200:
            raise FetchError(f"Project Euler HTTP {r.status_code}", r.status_code, retryable=r.status_code >= 500)
        out = self.parse(r.text)
        self.discovered_total = len(out)
        yield out, None

    @staticmethod
    def parse(text: str) -> list[ProblemRecord]:
        out = []
        for line in text.splitlines()[1:]:  # header: ID##Title##Published##Solved By
            parts = line.split("##")
            if len(parts) < 4 or not parts[0].isdigit():
                continue
            out.append(ProblemRecord("projecteuler", parts[0], parts[1], f"https://projecteuler.net/problem={parts[0]}", None, None, [], None, None,
                                     published_at=_dt(parts[2].replace(" ", "T"), UTC), solved_count=int(parts[3]) if parts[3].isdigit() else None,
                                     raw={"line": line}))
        return out


class CSESSource(ProblemSource):
    """One request to the public problem-set page (no robots.txt; rights unclear => metadata + link only)."""
    platform, source_name = "cses", "cses:problemset page"

    def __init__(self, http: PoliteClient | None = None):
        self.http = http or PoliteClient(min_interval=2.0)

    def pages(self, cursor):
        r = self.http.client.get("https://cses.fi/problemset/")
        if r.status_code != 200:
            raise FetchError(f"CSES HTTP {r.status_code}", r.status_code, retryable=r.status_code >= 500)
        out = self.parse(r.text)
        self.discovered_total = len(out)
        yield out, None

    @staticmethod
    def parse(html: str) -> list[ProblemRecord]:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "lxml")
        out, seen = [], set()
        for h in soup.find_all("h2"):
            sec = h.get_text(strip=True)
            ul = h.find_next_sibling("ul")
            if sec == "General" or ul is None:
                continue
            for li in ul.find_all("li", class_="task"):
                a = li.find("a", href=re.compile(r"/problemset/task/(\d+)"))
                if a is None:
                    continue
                pid = re.search(r"/task/(\d+)", a["href"]).group(1)
                if pid in seen:
                    continue
                seen.add(pid)
                det = li.find("span", class_="detail")
                m = re.match(r"\s*(\d+)\s*/\s*(\d+)", det.get_text()) if det else None
                out.append(ProblemRecord("cses", pid, a.get_text(strip=True), f"https://cses.fi/problemset/task/{pid}", None, None, [sec], None, None,
                                         solved_count=int(m[1]) if m else None, submission_count=int(m[2]) if m else None, raw={"section": sec}, section=sec))
        return out


SOURCES: dict[str, type[ProblemSource]] = {c.platform: c for c in (CodeforcesSource, AtCoderSource, DMOJSource, CodeChefSource, YukicoderSource,
                                                                   ProjectEulerSource, CSESSource)}
