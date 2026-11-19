# Sheet import registry

_Generated 2026-11-19 13:43 UTC. Source statuses are from manual verification on 2026-11-19; the import table is read from the database._

Rules: original order and sections preserved; canonical URL identity (never title matching); one problem = one record with many sheet memberships; metadata and links only (no statements or editorials copied); unavailable sources are reported, not substituted.

## Requested sources and their real status
| Sheet | Requested URL | Status | Where / why |
|---|---|---|---|
| CP-31 (TLE Eliminators) | https://codeforces.com/blog/entry/121310 | **not_importable** |  The Codeforces blog returns 403 to automated clients (bot protection, not bypassed). The TLE Eliminators site serves the sheet from a private API behind a JS app and publishes no licence. Community copies on GitHub carry no licence either. Alternative: Import your own copy: Sheets > Import (Codeforces IDs/URLs, optional 'ID | Section'). The importer preserves order and sections. |
| Striver A2Z DSA Sheet | https://takeuforward.org/dsa/strivers-a2z-sheet-learn-dsa-a-to-z | **importable** | https://takeuforward.org/prep-hub/strivers-a2z-dsa-sheet URL moved. Only items with an external judge link are importable; lesson/pattern-drill items without a link are counted in the report. Higher-level topic hierarchy is not recovered.  |
| Striver SDE Sheet | https://takeuforward.org/dsa/strivers-sde-sheet-top-coding-interview-problems | **importable** | https://takeuforward.org/prep-hub/strivers-sde-sheet The requested URL now redirects to a DIFFERENT sheet (Striver's 180); the real SDE sheet lives at the new URL. Single flat section.  |
| Striver CP Sheet | https://takeuforward.org/competitive-programming/strivers-cp-sheet | **unavailable** |  Returns 404 at the requested URL and at /prep-hub/. No replacement located.  |
| Striver Blind 75 | https://takeuforward.org/dsa/blind-75-leetcode-problems-detailed-video-solutions | **importable** | https://takeuforward.org/prep-hub/blind-75   |
| Striver 79 Last Moment | https://takeuforward.org/dsa/strivers-79-last-moment-dsa-sheet-ace-interviews | **importable** | https://takeuforward.org/prep-hub/strivers-79-sheet Requested URL redirected to Striver's 75, a different sheet; the 79 sheet is at the new URL.  |
| Striver 75 (additional) | — | **importable** | https://takeuforward.org/prep-hub/strivers-75-sheet   |
| Striver 180 Patterns (additional) | — | **importable** | https://takeuforward.org/prep-hub/strivers-180-master-dsa-patterns   |
| NeetCode 150 / Blind 75 / All | https://neetcode.io/practice | **importable** | https://github.com/neetcode-gh/leetcode Imported from the MIT-licensed repo data (.problemSiteData.json), not by scraping neetcode.io.  |
| Grind 75 | https://www.techinterviewhandbook.org/grind75 | **not_imported** |  Source (MIT) is yangshun/tech-interview-handbook but no standalone list file was located; the rendered page is not scraped. Pending a pass over the repo's question-set module.  |
| LeetCode Top Interview 150 | https://leetcode.com/studyplan/top-interview-150/ | **not_imported** |  No official API; study-plan data is only served via LeetCode's undocumented GraphQL, which is not used.  |
| LeetCode SQL 50 | https://leetcode.com/studyplan/top-sql-50/ | **not_imported** |  Same as Top Interview 150.  |
| Love Babbar 450 | https://450dsa.com/ | **not_imported** |  JS-rendered page; no verified open data source located yet.  |
| CSES Problem Set | https://cses.fi/problemset/ | **not_imported** |  Public HTML only, no API/robots policy stated; pending a conservative single-page metadata import.  |
| Codeforces Problemset | https://codeforces.com/problemset | **imported** |  Via the official API (problemset.problems).  |

## Imports performed (from the database)
| Sheet | Items | Sections | New problems | Reused (already canonical) | Dups in source | Invalid URLs | No problem link | Source | Licence | Imported |
|---|---|---|---|---|---|---|---|---|---|---|
| NeetCode 150 | 150 | 18 | 150 | 0 | 0 | 0 | 0 | https://github.com/neetcode-gh/leetcode | MIT (neetcode-gh/leetcode) | 2026-11-18 |
| Blind 75 (NeetCode data) | 75 | 18 | 0 | 75 | 0 | 0 | 0 | https://github.com/neetcode-gh/leetcode | MIT (neetcode-gh/leetcode) | 2026-11-18 |
| NeetCode All | 450 | 19 | 300 | 150 | 0 | 0 | 0 | https://github.com/neetcode-gh/leetcode | MIT (neetcode-gh/leetcode) | 2026-11-18 |
| Striver's A2Z DSA Sheet | 239 | 47 | 96 | 143 | 13 | 0 | 176 | https://takeuforward.org/prep-hub/strivers-a2z-dsa-sheet | No explicit license. Metadata and canonical links only; no statements or editorials copied. | 2026-11-18 |
| Striver's SDE Sheet | 102 | 1 | 1 | 101 | 1 | 0 | 22 | https://takeuforward.org/prep-hub/strivers-sde-sheet | No explicit license. Metadata and canonical links only; no statements or editorials copied. | 2026-11-18 |
| Striver's 79 Last-Moment Sheet | 56 | 1 | 0 | 56 | 0 | 0 | 11 | https://takeuforward.org/prep-hub/strivers-79-sheet | No explicit license. Metadata and canonical links only; no statements or editorials copied. | 2026-11-18 |
| Striver's 75 Sheet | 68 | 12 | 0 | 68 | 0 | 0 | 6 | https://takeuforward.org/prep-hub/strivers-75-sheet | No explicit license. Metadata and canonical links only; no statements or editorials copied. | 2026-11-18 |
| Striver's 180 DSA Patterns | 144 | 32 | 0 | 144 | 2 | 0 | 31 | https://takeuforward.org/prep-hub/strivers-180-master-dsa-patterns | No explicit license. Metadata and canonical links only; no statements or editorials copied. | 2026-11-18 |
| Blind 75 (takeUforward) | 43 | 1 | 0 | 43 | 1 | 0 | 0 | https://takeuforward.org/prep-hub/blind-75 | No explicit license. Metadata and canonical links only; no statements or editorials copied. | 2026-11-18 |

Notes: "Reused" counts problems already present from another sheet or the Codeforces catalog, which is the cross-sheet dedupe working. "No problem link" = lesson/pattern-drill entries on the source page with no external judge URL; they are counted, not invented.
