# API reference

_Generated 2026-11-19 15:32 UTC from the FastAPI OpenAPI schema. Interactive docs: `/docs` on a running server._

All endpoints except `/health`, `/auth/register`, `/auth/login`, `/auth/refresh` require `Authorization: Bearer <access token>`. Admin endpoints require role `admin`.

| Method | Path | Summary |
|---|---|---|
| POST | `/admin/backfill/{platform}` | Start Backfill |
| GET | `/admin/data-quality` | Data Quality |
| GET | `/admin/experiments/daily` | Daily Experiment |
| POST | `/admin/jobs/run` | Admin Run |
| POST | `/admin/labels/propose` | Propose |
| GET | `/admin/llm/usage` | Usage |
| POST | `/admin/rag/embed` | Embed Docs |
| POST | `/admin/rag/ingest` | Ingest |
| POST | `/admin/sheets/import/{source}` | Admin Import Sheet |
| POST | `/admin/sync/{kind}/{platform}` | Admin Enqueue |
| GET | `/admin/training/export` | Export Training |
| GET | `/analytics/catalog` | Analytics |
| GET | `/analytics/me` | My Analytics |
| GET | `/arena/matches` | Mine |
| POST | `/arena/matches` | Create |
| POST | `/arena/matches/join` | Join |
| GET | `/arena/matches/{mid}` | Get |
| POST | `/arena/matches/{mid}/start` | Start |
| POST | `/arena/matches/{mid}/submit` | Submit |
| GET | `/arena/problems` | Problems |
| GET | `/arena/problems/{key}` | Problem |
| POST | `/auth/forgot` | Forgot |
| POST | `/auth/login` | Login |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Me |
| DELETE | `/auth/me` | Delete Account |
| GET | `/auth/me/export` | Export Data |
| POST | `/auth/mfa/disable` | Mfa Disable |
| POST | `/auth/mfa/enable` | Mfa Enable |
| POST | `/auth/mfa/setup` | Mfa Setup |
| POST | `/auth/refresh` | Refresh |
| POST | `/auth/register` | Register |
| POST | `/auth/reset` | Reset |
| POST | `/auth/verify` | Verify Email |
| POST | `/auth/verify/request` | Request Verify |
| GET | `/bookmarks` | Bookmarks |
| POST | `/capture/submissions` | Upload |
| GET | `/capture/tokens` | List Tokens |
| POST | `/capture/tokens` | Create Token |
| DELETE | `/capture/tokens/{tid}` | Revoke |
| POST | `/catalog/sync/codeforces` | Sync Codeforces |
| GET | `/channels` | Channels |
| POST | `/channels` | Create Channel |
| GET | `/channels/{cid}/messages` | Messages |
| POST | `/channels/{cid}/messages` | Post Message |
| GET | `/contests` | Contests |
| GET | `/contests/{cid}/prep` | Prep |
| GET | `/contests/{cid}/review` | Review |
| GET | `/daily` | Get Daily |
| GET | `/daily/history` | History |
| POST | `/daily/{cid}/complete` | Complete |
| POST | `/daily/{cid}/swap` | Swap |
| GET | `/design` | List Designs |
| POST | `/design` | Create |
| POST | `/design/review` | Review Graph |
| GET | `/design/scenarios` | Scenarios |
| GET | `/design/{did}` | Get |
| PUT | `/design/{did}` | Update |
| DELETE | `/design/{did}` | Delete |
| POST | `/design/{did}/reviewed` | Mark Reviewed |
| PUT | `/drafts/{key}` | Save Draft |
| GET | `/drafts/{key}` | Get Draft |
| POST | `/execute` | Execute |
| GET | `/execute/languages` | Languages |
| GET | `/explorer` | Explorer |
| GET | `/gamification/leaderboard` | Board |
| GET | `/gamification/me` | Me |
| GET | `/health` | Health |
| GET | `/interview` | History |
| POST | `/interview` | Start |
| GET | `/interview/{sid}` | Get |
| POST | `/interview/{sid}/finish` | Finish |
| POST | `/interview/{sid}/say` | Say |
| POST | `/labels` | Add Human |
| GET | `/labels/queue` | Queue |
| GET | `/labels/stats` | Stats |
| POST | `/labels/{lid}/review` | Review |
| GET | `/mastery` | Mastery |
| GET | `/me/prefs` | Get Prefs |
| PUT | `/me/prefs` | Put Prefs |
| POST | `/mentor/chat` | Chat |
| POST | `/mentor/chat/stream` | Chat Stream |
| GET | `/mentor/history` | History |
| GET | `/mentor/status` | Status |
| POST | `/mentor/{mid}/feedback` | Feedback |
| POST | `/messages/{mid}/bookmark` | Bookmark |
| POST | `/messages/{mid}/react` | React |
| POST | `/messages/{mid}/report` | Report |
| GET | `/messages/{mid}/thread` | Thread |
| GET | `/mistakes` | Get Mistakes |
| PUT | `/mistakes/{pid}/note` | Put Note |
| GET | `/mod/reports` | Reports |
| POST | `/mod/reports/{rid}` | Moderate |
| GET | `/notes` | List Notes |
| POST | `/notes` | Add Note |
| DELETE | `/notes/{nid}` | Del Note |
| GET | `/notifications` | List Notifications |
| POST | `/notifications/read` | Mark Read |
| GET | `/patterns` | Patterns |
| GET | `/patterns/coverage` | Pattern Coverage |
| GET | `/patterns/{pid}` | Pattern Detail |
| GET | `/planner` | Get Plan |
| GET | `/planner/crash-course` | Get |
| POST | `/planner/crash-course` | Create |
| DELETE | `/planner/crash-course` | Stop |
| GET | `/planner/crash-course/options` | Options |
| POST | `/planner/crash-course/tasks/{task_id}/toggle` | Toggle |
| PUT | `/planner/goal` | Put Goal |
| DELETE | `/planner/goal` | Del Goal |
| GET | `/platforms` | Platforms |
| GET | `/problems` | List Problems |
| GET | `/problems/{pid}` | Problem Detail |
| GET | `/profile/{uid}` | Public Profile |
| GET | `/profiles` | List Profiles |
| POST | `/profiles` | Link Profile |
| DELETE | `/profiles/{pid}` | Unlink |
| POST | `/profiles/{pid}/import` | Manual Import |
| POST | `/profiles/{pid}/sync` | Sync |
| POST | `/progress` | Report Outcome |
| GET | `/ready` | Ready |
| GET | `/recommendations` | Recommendations |
| POST | `/resources/admin/seed-design` | Seed Design |
| GET | `/resources/companies` | Companies |
| GET | `/resources/companies/{slug}` | Company |
| GET | `/resources/companies/{slug}/problems` | Company Problems |
| GET | `/resources/must-do` | Must Do |
| GET | `/resources/overview` | Overview |
| GET | `/resources/system-design` | System Design |
| GET | `/revision/due` | Revision Due |
| GET | `/revision/overview` | Revision Overview |
| POST | `/revision/{pid}/review` | Do Review |
| GET | `/runs` | Runs |
| GET | `/search/messages` | Search |
| GET | `/sheet-sources` | Sheet Sources |
| GET | `/sheets` | List Sheets |
| POST | `/sheets/import` | Import User Sheet |
| POST | `/sheets/seed-starter` | Seed Starter |
| GET | `/sheets/{sheet_id}` | Get Sheet |
| GET | `/sources` | Sources |
| POST | `/stress` | Stress Test |
| GET | `/stress/generators` | Generators |
| GET | `/sync-jobs` | Jobs |
| POST | `/users/{uid}/follow` | Follow |
