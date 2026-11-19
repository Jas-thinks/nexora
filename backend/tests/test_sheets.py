import json
from pathlib import Path

import pytest
from sqlalchemy import func, select

from app.core import db as dbmod
from app.importers import neetcode, takeuforward
from app.integrations.http import FetchError
from app.models.catalog import Problem, Sheet, SheetItem, SheetSection
from app.services import sheet_import
from app.services.canonical import canonicalize

FX = Path(__file__).parent / "fixtures"
NC = json.loads((FX / "neetcode_slice.json").read_text())
A2Z = (FX / "a2z_payload_slice.txt").read_text()


@pytest.fixture()
def db(client):
    with dbmod.SessionLocal() as s:
        yield s


# ------------------------------------------------------------------ canonical identity
@pytest.mark.parametrize("url,expected", [
    ("https://leetcode.com/problems/two-sum/", ("leetcode", "two-sum")),
    ("https://leetcode.com/problems/two-sum/description/?envType=study-plan", ("leetcode", "two-sum")),
    ("https://codeforces.com/contest/4/problem/A", ("codeforces", "4A")),
    ("https://codeforces.com/problemset/problem/4/a", ("codeforces", "4A")),
    ("https://atcoder.jp/contests/abc001/tasks/abc001_a", ("atcoder", "abc001_a")),
    ("https://cses.fi/problemset/task/1068", ("cses", "1068")),
])
def test_canonicalize_collapses_url_variants(url, expected):
    assert canonicalize(url)[:2] == expected


@pytest.mark.parametrize("bad", ["", "nonsense", "https://example.com/problem/1", "https://leetcode.com/", "https://acm.timus.ru/problem.aspx?num=abc"])
def test_canonicalize_rejects_unrecognised(bad):
    assert canonicalize(bad) is None


def test_similar_titles_are_never_merged(db):
    a, _ = sheet_import.get_or_create_problem(db, "https://leetcode.com/problems/two-sum/", "Two Sum", "Easy")
    b, _ = sheet_import.get_or_create_problem(db, "https://www.geeksforgeeks.org/problems/two-sum/1", "Two Sum", "Easy")
    assert a.id != b.id and (a.platform, b.platform) == ("leetcode", "geeksforgeeks")


# ------------------------------------------------------------------ importer
def spec(slug, items, sections=None):
    return {"slug": slug, "title": slug, "source_url": "https://example.org/src", "license": "test",
            "sections": sections or [{"name": "S1", "items": items}]}


def test_order_sections_and_report_preserved(db):
    items = [{"url": f"https://leetcode.com/problems/p{i}/", "title": f"P{i}", "difficulty": "Easy"} for i in (3, 1, 2)]
    r = sheet_import.import_sheet_spec(db, spec("a-sheet", items, [{"name": "B", "items": items[:2]}, {"name": "A", "items": items[2:]}]))
    rows = db.execute(select(SheetItem.source_title, SheetItem.section).order_by(SheetItem.position)).all()
    assert rows == [("P3", "B"), ("P1", "B"), ("P2", "A")]  # source order, not alphabetical
    assert [s.name for s in db.scalars(select(SheetSection).order_by(SheetSection.position))] == ["B", "A"]
    assert r["imported"] == 3 and r["new_problems"] == 3 and r["by_platform"] == {"leetcode": 3}
    sh = db.scalar(select(Sheet))
    assert sh.source_url == "https://example.org/src" and sh.imported_at and len(sh.content_hash) == 64


def test_one_problem_many_sheets_is_one_record(db):
    shared = {"url": "https://leetcode.com/problems/two-sum/", "title": "Two Sum", "difficulty": "Easy"}
    r1 = sheet_import.import_sheet_spec(db, spec("sheet-a", [shared]))
    r2 = sheet_import.import_sheet_spec(db, spec("sheet-b", [{**shared, "url": "https://leetcode.com/problems/two-sum/description/", "difficulty": "Medium"}]))
    r3 = sheet_import.import_sheet_spec(db, spec("sheet-c", [shared]))
    assert db.scalar(select(func.count()).select_from(Problem)) == 1
    assert db.scalar(select(func.count()).select_from(SheetItem)) == 3  # three memberships
    assert (r1["new_problems"], r2["reused_problems"], r3["reused_problems"]) == (1, 1, 1)
    assert db.scalar(select(Problem.source_difficulty)) == "Easy"  # first source wins; later sheets don't overwrite


def test_reimport_is_idempotent_and_replaces_removed_entries(db):
    a = {"url": "https://leetcode.com/problems/a/", "title": "A"}; b = {"url": "https://leetcode.com/problems/b/", "title": "B"}
    sheet_import.import_sheet_spec(db, spec("s", [a, b]))
    h1 = db.scalar(select(Sheet.content_hash))
    sheet_import.import_sheet_spec(db, spec("s", [a, b]))
    assert db.scalar(select(func.count()).select_from(SheetItem)) == 2 and db.scalar(select(Sheet.content_hash)) == h1
    sheet_import.import_sheet_spec(db, spec("s", [a]))  # upstream removed B
    assert db.scalar(select(func.count()).select_from(SheetItem)) == 1 and db.scalar(select(Sheet.content_hash)) != h1


def test_invalid_and_duplicate_entries_are_reported_not_hidden(db):
    ok = {"url": "https://leetcode.com/problems/a/", "title": "A"}
    r = sheet_import.import_sheet_spec(db, spec("s", [ok, ok, {"url": "https://nowhere.example/x", "title": "Bad"}, {"url": "", "title": "Empty"}]))
    assert r["imported"] == 1 and len(r["duplicates_in_sheet"]) == 1 and [x["title"] for x in r["invalid_urls"]] == ["Bad", "Empty"]


def test_existing_codeforces_catalog_row_is_reused_not_duplicated(db):
    db.add(Problem(platform="codeforces", external_id="4A", name="Watermelon", rating=800, tags=["math"], url="https://codeforces.com/problemset/problem/4/A"))
    db.commit()
    r = sheet_import.import_sheet_spec(db, spec("cf", [{"url": "https://codeforces.com/contest/4/problem/A", "title": "Watermelon!"}]))
    p = db.scalar(select(Problem))
    assert r["reused_problems"] == 1 and db.scalar(select(func.count()).select_from(Problem)) == 1
    assert p.rating == 800 and p.name == "Watermelon" and p.canonical_url


# ------------------------------------------------------------------ NeetCode (real data slice)
def test_neetcode_specs_respect_flags_and_order():
    s150, b75, allp = neetcode.build_specs(NC)
    n150 = [r["problem"] for r in NC if r.get("neetcode150")]
    got = [i["title"] for sec in s150["sections"] for i in sec["items"]]
    assert sorted(got) == sorted(n150) and "MIT" in s150["license"]
    # order inside each section is source order
    first = s150["sections"][0]["items"][0]["title"]
    assert first == next(r["problem"] for r in NC if r.get("neetcode150"))
    assert sum(len(s["items"]) for s in allp["sections"]) == len(NC)
    assert {i["title"] for s in b75["sections"] for i in s["items"]} <= set(got) | {r["problem"] for r in NC}


def test_neetcode_import_shares_problems_across_its_three_sheets(db):
    for sp in neetcode.build_specs(NC):
        sheet_import.import_sheet_spec(db, sp)
    n_unique = len({r["link"] for r in NC})
    assert db.scalar(select(func.count()).select_from(Problem)) == n_unique
    memberships = db.scalar(select(func.count()).select_from(SheetItem))
    assert memberships > n_unique  # same canonical problem sits in several sheets


# ------------------------------------------------------------------ Striver A2Z (real payload excerpt)
def test_a2z_parser_on_real_payload():
    with_link, without = takeuforward.parse(A2Z)
    assert with_link and all(i["url"].startswith("http") and "youtu" not in i["url"] for i in with_link)
    assert with_link[0]["category"] and with_link[0]["title"]
    titles = [i["title"] for i in with_link]
    assert "Reverse a number" in titles and titles.index("Reverse a number") < titles.index("Palindrome Number")  # page order


def test_a2z_refuses_when_structure_changes():
    with pytest.raises(FetchError, match="structure changed"):
        takeuforward.build_spec("<html>totally different page</html>")


def test_a2z_import_end_to_end(db):
    sp = takeuforward.build_spec(A2Z)
    r = sheet_import.import_sheet_spec(db, sp)
    assert r["imported"] > 0 and r["by_platform"].get("leetcode", 0) == r["imported"] and r["invalid_urls"] == []
    assert "No explicit license" in db.scalar(select(Sheet.license))
