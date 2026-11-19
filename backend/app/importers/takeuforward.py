"""takeUforward sheets (Striver A2Z / SDE / 79 / 75 / 180 / Blind 75), parsed from the server-rendered page payload.

Fragile by nature (framework payload, not an API): the parser is validated against a real recorded excerpt and the
importer refuses to import when the structure no longer matches. Only metadata + canonical links are stored.
robots.txt allows this path (only /api/, /profile/edit, /plus/account are disallowed).
"""
import re

from app.integrations.http import FetchError, PoliteClient

BASE = "https://takeuforward.org/prep-hub/"
SHEETS = {  # slug -> (page path, title). Paths verified 2026-11-19; the URLs originally supplied now redirect/404.
    "striver-a2z": ("strivers-a2z-dsa-sheet", "Striver's A2Z DSA Sheet"),
    "striver-sde": ("strivers-sde-sheet", "Striver's SDE Sheet"),
    "striver-79": ("strivers-79-sheet", "Striver's 79 Last-Moment Sheet"),
    "striver-75": ("strivers-75-sheet", "Striver's 75 Sheet"),
    "striver-180": ("strivers-180-master-dsa-patterns", "Striver's 180 DSA Patterns"),
    "takeuforward-blind-75": ("blind-75", "Blind 75 (takeUforward)"),
}
ROW = re.compile(r'\[(\d+),(\d+),"([^"]+)","item","(practice|learning)","([^"]+)","([^"]*)",\{([^}]*)\}')


def fetch_html(slug: str, http: PoliteClient | None = None) -> str:
    c = http or PoliteClient()
    r = c.client.get(BASE + SHEETS[slug][0])
    if r.status_code != 200:
        raise FetchError(f"takeuforward returned HTTP {r.status_code}", r.status_code, retryable=r.status_code >= 500)
    return r.text


def parse(html: str) -> tuple[list[dict], list[dict]]:
    """-> (items with a judge link, items without one). Order = page order."""
    h = html.replace('\\"', '"')
    rows = list(ROW.finditer(h))
    with_link, without = [], []
    for i, m in enumerate(rows):
        end = rows[i + 1].start() if i + 1 < len(rows) else m.end() + 600
        seg = h[m.end():min(end, m.end() + 700)]
        cat = re.search(r'"category":"([^"]+)"', m.group(7))
        category = (cat.group(1) if cat else "uncategorised").replace("--", "-")
        urls = [u for u in re.findall(r'"(https?://[^"]+)"', seg) if "youtu" not in u and "takeuforward" not in u]
        rec = {"title": m.group(5), "category": category, "kind": m.group(4)}
        (with_link if urls else without).append({**rec, "url": urls[0]} if urls else rec)
    return with_link, without


def build_spec(html: str, slug: str = "striver-a2z") -> dict:
    with_link, without = parse(html)
    if len(with_link) < 3:
        raise FetchError("A2Z page structure changed: refusing to import (parser found too few problem links)")
    sections, idx = [], {}
    for it in with_link:
        name = it["category"].replace("-", " ").title()
        if name not in idx:
            idx[name] = {"name": name, "items": []}; sections.append(idx[name])
        idx[name]["items"].append({"url": it["url"], "title": it["title"]})
    path, title = SHEETS[slug]
    return {"slug": slug, "title": title, "source_url": BASE + path,
            "license": "No explicit license. Metadata and canonical links only; no statements or editorials copied.",
            "source": f"takeUforward ({title})",
            "description": "Items with an external judge link, in page order. Section = the item's own category (the page's higher-level step/topic hierarchy is not recovered).",
            "sections": sections, "skipped": [{"title": i["title"], "category": i["category"]} for i in without]}
