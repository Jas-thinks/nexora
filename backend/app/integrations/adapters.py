"""Platform adapters. Each implements only what its source really provides; the rest raises NotSupported."""
import csv
import hashlib
import io
import json
import os
from datetime import UTC, datetime
from urllib.parse import quote

from app.integrations.http import FetchError, PoliteClient
from app.services.canonical import canonicalize
from app.integrations.types import (
    NormContest, NormProblem, NormRating, NormSubmission, NotSupported, ProfileInfo, SubmissionPage, VERDICTS,
)


def ts(sec: int | float) -> datetime:
    return datetime.fromtimestamp(sec, UTC)


class PlatformAdapter:
    slug = ""

    def __init__(self, http: PoliteClient | None = None):
        self.http = http or PoliteClient()

    def validate_profile(self, handle: str) -> ProfileInfo: raise NotSupported(f"{self.slug}: profile")
    def fetch_submissions(self, handle: str, checkpoint: dict | None = None) -> SubmissionPage: raise NotSupported(f"{self.slug}: submissions")
    def fetch_rating_history(self, handle: str) -> list[NormRating]: raise NotSupported(f"{self.slug}: rating history")
    def fetch_contests(self) -> list[NormContest]: raise NotSupported(f"{self.slug}: contests")
    def fetch_problem_metadata(self) -> list[NormProblem]: raise NotSupported(f"{self.slug}: problem metadata")


# ---------------------------------------------------------------- Codeforces (official API)
CF = "https://codeforces.com/api"
CF_VERDICT = {"OK": "AC", "WRONG_ANSWER": "WA", "TIME_LIMIT_EXCEEDED": "TLE", "IDLENESS_LIMIT_EXCEEDED": "TLE",
              "MEMORY_LIMIT_EXCEEDED": "MLE", "RUNTIME_ERROR": "RE", "COMPILATION_ERROR": "CE"}


class CodeforcesAdapter(PlatformAdapter):
    slug = "codeforces"

    def __init__(self, http: PoliteClient | None = None):
        super().__init__(http or PoliteClient(min_interval=2.0))  # official limit: 1 req / 2 s

    def _call(self, method: str, **params):
        try:
            d = self.http.get_json(f"{CF}/{method}", params=params)
        except FetchError:
            raise
        if d.get("status") != "OK":
            raise FetchError(f"Codeforces: {d.get('comment', 'API error')}")
        return d["result"]

    def validate_profile(self, handle: str) -> ProfileInfo:
        try:
            u = self._call("user.info", handles=handle)[0]
        except FetchError as e:
            if e.status == 400 or "not found" in str(e).lower():
                raise FetchError(f"Codeforces handle '{handle}' not found") from e
            raise
        return ProfileInfo(u["handle"], u.get("firstName"), u.get("rating"), u.get("maxRating"), u.get("rank"))

    @staticmethod
    def normalize_submission(s: dict) -> NormSubmission | None:
        if "verdict" not in s or s["verdict"] == "TESTING" or "contestId" not in s["problem"]:
            return None
        v = s["verdict"]
        return NormSubmission(
            external_id=str(s["id"]), problem_ref=f"{s['problem']['contestId']}{s['problem']['index']}",
            verdict=CF_VERDICT.get(v, "OTHER"), raw_verdict=v, submitted_at=ts(s["creationTimeSeconds"]),
            language=s.get("programmingLanguage"), time_ms=s.get("timeConsumedMillis"),
            memory_kb=(s["memoryConsumedBytes"] // 1024) if s.get("memoryConsumedBytes") is not None else None,
            in_contest=s.get("author", {}).get("participantType") == "CONTESTANT")

    def fetch_submissions(self, handle: str, checkpoint: dict | None = None) -> SubmissionPage:
        last = (checkpoint or {}).get("last_id", 0)
        out, skipped, start, max_id, min_unjudged = [], 0, 1, last, None
        while True:
            page = self._call("user.status", handle=handle, **{"from": start, "count": 1000})
            if not page:
                break
            done = False
            for s in page:  # newest first
                if s["id"] <= last:
                    done = True; break
                n = self.normalize_submission(s)
                if n is None:
                    skipped += 1
                    if s.get("verdict") in (None, "TESTING"):
                        min_unjudged = s["id"] if min_unjudged is None else min(min_unjudged, s["id"])
                    continue
                out.append(n); max_id = max(max_id, s["id"])
            if done or len(page) < 1000:
                break
            start += 1000
        # Never advance past a still-judging submission, or it would be missed forever.
        if min_unjudged is not None:
            max_id = min(max_id, min_unjudged - 1)
        return SubmissionPage(out, {"last_id": max(max_id, last)}, skipped)

    def fetch_rating_history(self, handle: str) -> list[NormRating]:
        return [NormRating(str(r["contestId"]), r["contestName"], ts(r["ratingUpdateTimeSeconds"]),
                           r["oldRating"], r["newRating"], r.get("rank")) for r in self._call("user.rating", handle=handle)]

    def fetch_contests(self) -> list[NormContest]:
        return [NormContest(str(c["id"]), c["name"], ts(c["startTimeSeconds"]) if "startTimeSeconds" in c else None,
                            c.get("durationSeconds"), f"https://codeforces.com/contest/{c['id']}", None, "codeforces:contest.list")
                for c in self._call("contest.list", gym="false")]

    def fetch_problem_metadata(self) -> list[NormProblem]:
        from app.services import codeforces as cf
        raw = {"result": self._call("problemset.problems")}
        return [NormProblem(i["external_id"], i["name"], i["url"], i["rating"], i["tags"]) for i in cf.normalize(raw)]


# ---------------------------------------------------------------- AtCoder (community API + public history JSON)
AC_API = "https://kenkoooo.com/atcoder"
AC_VERDICT = {"AC": "AC", "WA": "WA", "TLE": "TLE", "MLE": "MLE", "RE": "RE", "CE": "CE"}


class AtCoderAdapter(PlatformAdapter):
    slug = "atcoder"

    def validate_profile(self, handle: str) -> ProfileInfo:
        # Profile page existence only. NOT /users/*/history/ : atcoder.jp/robots.txt disallows it, so rating history is unsupported.
        r = self.http.client.get(f"https://atcoder.jp/users/{quote(handle)}")
        if r.status_code == 404:
            raise FetchError(f"AtCoder user '{handle}' not found", 404)
        if r.status_code != 200:
            raise FetchError(f"AtCoder HTTP {r.status_code}", r.status_code, retryable=r.status_code >= 500)
        return ProfileInfo(handle)

    @staticmethod
    def normalize_submission(s: dict) -> NormSubmission:
        return NormSubmission(str(s["id"]), s["problem_id"], AC_VERDICT.get(s["result"], "OTHER"), s["result"],
                              ts(s["epoch_second"]), s.get("language"), s.get("execution_time"), None, None)

    def fetch_submissions(self, handle: str, checkpoint: dict | None = None) -> SubmissionPage:
        frm = (checkpoint or {}).get("last_epoch", 0)
        out, seen = [], set()
        while True:
            page = self.http.get_json(f"{AC_API}/atcoder-api/v3/user/submissions", params={"user": handle, "from_second": frm})
            fresh = [s for s in page if s["id"] not in seen]
            for s in fresh:
                seen.add(s["id"]); out.append(self.normalize_submission(s))
            if len(page) < 500 or not fresh:
                break
            frm = max(s["epoch_second"] for s in page)
        last = max([s.submitted_at.timestamp() for s in out], default=(checkpoint or {}).get("last_epoch", 0))
        return SubmissionPage(out, {"last_epoch": int(last)})

    def fetch_rating_history(self, handle: str) -> list[NormRating]:
        raise NotSupported("atcoder: rating history is only on /users/*/history/, which robots.txt disallows; no permitted source")

    def fetch_contests(self) -> list[NormContest]:
        return [NormContest(c["id"], c["title"], ts(c["start_epoch_second"]), c["duration_second"],
                            f"https://atcoder.jp/contests/{c['id']}", None if c.get("rate_change") in (None, "") else c["rate_change"] != "-",
                            "kenkoooo:contests.json") for c in self.http.get_json(f"{AC_API}/resources/contests.json")]

    def fetch_problem_metadata(self) -> list[NormProblem]:
        probs = self.http.get_json(f"{AC_API}/resources/problems.json")
        try:
            models = self.http.get_json(f"{AC_API}/resources/problem-models.json")
        except FetchError:
            models = {}
        out = []
        for p in probs:
            d = (models.get(p["id"]) or {}).get("difficulty")
            out.append(NormProblem(p["id"], p.get("title") or p["name"], f"https://atcoder.jp/contests/{p['contest_id']}/tasks/{p['id']}",
                                   None, [], f"est. difficulty {int(d)} (AtCoder Problems)" if d is not None else None))
        return out


# ---------------------------------------------------------------- DMOJ (official API v2, public endpoints)
class DMOJAdapter(PlatformAdapter):
    slug = "dmoj"
    BASE = "https://dmoj.ca/api/v2"
    MAX_PAGES = 200

    def _paged(self, path: str):
        for page in range(1, self.MAX_PAGES + 1):  # hard cap: a misbehaving source must not loop forever
            d = self.http.get_json(f"{self.BASE}/{path}", params={"page": page})["data"]
            yield from d["objects"]
            if not d.get("has_more"):
                return
        raise FetchError(f"DMOJ pagination exceeded {self.MAX_PAGES} pages")

    def fetch_contests(self) -> list[NormContest]:
        out = []
        for c in self._paged("contests"):
            st = datetime.fromisoformat(c["start_time"]) if c.get("start_time") else None
            en = datetime.fromisoformat(c["end_time"]) if c.get("end_time") else None
            out.append(NormContest(c["key"], c["name"], st, int((en - st).total_seconds()) if st and en else None,
                                   f"https://dmoj.ca/contest/{c['key']}", c.get("is_rated"), "dmoj:/api/v2/contests"))
        return out

    def fetch_problem_metadata(self) -> list[NormProblem]:
        return [NormProblem(p["code"], p["name"], f"https://dmoj.ca/problem/{p['code']}", None, sorted(p.get("types", [])),
                            f"{p['points']:g} points" if p.get("points") else None) for p in self._paged("problems")]


# ---------------------------------------------------------------- CodeChef (public contest list only)
class CodeChefAdapter(PlatformAdapter):
    slug = "codechef"

    def fetch_contests(self) -> list[NormContest]:
        d = self.http.get_json("https://www.codechef.com/api/list/contests/all")
        out = []
        for key in ("present_contests", "future_contests", "past_contests"):
            for c in d.get(key, []):
                st = datetime.fromisoformat(c["contest_start_date_iso"]).astimezone(UTC)
                out.append(NormContest(c["contest_code"], c["contest_name"], st, int(c["contest_duration"]) * 60,
                                       f"https://www.codechef.com/{c['contest_code']}", None, "codechef:/api/list/contests/all"))
        return out


# ---------------------------------------------------------------- CLIST (needs the user's own API key)
class ClistAdapter(PlatformAdapter):
    slug = "clist"

    def fetch_contests(self) -> list[NormContest]:
        user, key = os.getenv("CODEMIND_CLIST_USERNAME"), os.getenv("CODEMIND_CLIST_KEY")
        if not (user and key):
            raise NotSupported("CLIST requires CODEMIND_CLIST_USERNAME and CODEMIND_CLIST_KEY")
        d = self.http.get_json("https://clist.by/api/v4/contest/", params={"upcoming": "true", "order_by": "start", "limit": 200},
                               headers={"Authorization": f"ApiKey {user}:{key}"})
        return [NormContest(f"clist-{c['id']}", f"{c['event']} ({c['resource']})",
                            datetime.fromisoformat(c["start"]).replace(tzinfo=UTC), int(c["duration"]), c["href"], None, "clist.by:/api/v4")
                for c in d.get("objects", [])]


# ---------------------------------------------------------------- Manual import (any platform)
def parse_manual_import(platform: str, content: str, fmt: str) -> tuple[list[NormSubmission], list[dict]]:
    """CSV/JSON rows: problem (id or URL), verdict, submitted_at (ISO-8601), optional language, id.
    Returns (valid rows, per-row errors). Imported rows are labelled USER_IMPORTED, never 'verified'."""
    rows = json.loads(content) if fmt == "json" else list(csv.DictReader(io.StringIO(content)))
    if not isinstance(rows, list):
        raise ValueError("JSON import must be a list of objects")
    ok, errors = [], []
    for i, r in enumerate(rows, 1):
        try:
            problem = str(r["problem"]).strip()
            verdict = str(r["verdict"]).strip().upper()
            if not problem or verdict not in VERDICTS:
                raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")
            canon = canonicalize(problem) if "/" in problem or "." in problem else None
            if canon:
                if canon[0] != platform:
                    raise ValueError(f"URL is a {canon[0]} problem but this profile is {platform}")
                problem = canon[1]  # canonical external id, so it links to the shared Problem record
            at = datetime.fromisoformat(str(r["submitted_at"]).replace("Z", "+00:00"))
            if at.tzinfo is None:
                at = at.replace(tzinfo=UTC)
            if at > datetime.now(UTC):
                raise ValueError("submitted_at is in the future")
            ext = str(r.get("id") or hashlib.sha1(f"{platform}|{problem}|{at.isoformat()}|{verdict}".encode()).hexdigest()[:16])
            ok.append(NormSubmission(ext, problem, verdict, verdict, at, r.get("language") or None, provenance="user_imported"))
        except (KeyError, ValueError) as e:
            errors.append({"row": i, "error": f"missing field {e}" if isinstance(e, KeyError) else str(e)})
    return ok, errors


ADAPTERS: dict[str, type[PlatformAdapter]] = {
    "codeforces": CodeforcesAdapter, "atcoder": AtCoderAdapter, "dmoj": DMOJAdapter,
    "codechef": CodeChefAdapter, "clist": ClistAdapter,
}
