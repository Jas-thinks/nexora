"""NeetCode lists from the MIT-licensed neetcode-gh/leetcode repo (.problemSiteData.json)."""
from app.integrations.http import PoliteClient

SRC = "https://raw.githubusercontent.com/neetcode-gh/leetcode/main/.problemSiteData.json"
REPO = "https://github.com/neetcode-gh/leetcode"


def fetch(http: PoliteClient | None = None) -> list[dict]:
    return (http or PoliteClient()).get_json(SRC)


def _spec(rows: list[dict], slug: str, title: str, desc: str) -> dict:
    sections, idx = [], {}
    for r in rows:  # preserve source order; sections = the source's own "pattern" field, in first-seen order
        name = r.get("pattern") or "Unsorted"
        if name not in idx:
            idx[name] = {"name": name, "items": []}; sections.append(idx[name])
        idx[name]["items"].append({"url": f"https://leetcode.com/problems/{r['link'].strip('/')}/", "title": r["problem"],
                                   "difficulty": r.get("difficulty")})
    return {"slug": slug, "title": title, "description": desc, "source_url": REPO, "license": "MIT (neetcode-gh/leetcode)",
            "source": "NeetCode (neetcode.io), data from the open-source neetcode-gh/leetcode repository", "sections": sections}


def build_specs(rows: list[dict]) -> list[dict]:
    return [
        _spec([r for r in rows if r.get("neetcode150")], "neetcode-150", "NeetCode 150", "The NeetCode 150 list as flagged in the source data."),
        _spec([r for r in rows if r.get("blind75")], "blind-75", "Blind 75 (NeetCode data)", "Blind 75 membership as flagged in NeetCode's data."),
        _spec(rows, "neetcode-all", "NeetCode All", "Every problem in NeetCode's data set."),
    ]
