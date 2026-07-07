# Project status

The single place to see what is finished, what is in progress, and what is
still to do. Update this file whenever something changes.

Last updated: 2026-07-03 (pause switch + forever-renewing tokens)

## Latest: enterprise dashboard

The dashboard (docs/index.html) is now a single-page app with a left-side
menu showing one section at a time: **Dashboard** (stats, activity log,
recent runs), **Companies** (switch between clients, guided setup),
**Scheduled Posts** (the queue), **Auto Posts** (month campaigns),
**Admin** (Add Company creates the client's repo automatically on `main`),
**Setup Instructions** (plain-language walkthroughs of every credential),
and **Settings** (connection). Highlights:

- One-off post scheduling was removed; Auto Posts campaigns are the way to post.
- The platform lineup is Instagram and Facebook. TikTok was removed
  entirely (code, workflows, secrets and docs) at the owner's request.
- Every publish attempt (feed and stories, success or failure with the full
  API error) is written to `data/activity.json` and shown on the Dashboard.
- **Guided setup wizard** per company: modal steps with Next/Back and
  Save-and-Verify - GitHub token, Facebook Page (with automatic exchange to
  a permanent Page token), Instagram (auto-upgrade to long-lived), secret
  storage with copy buttons and existence verification, and GitHub Pages.
  Progress is saved so you can leave and return.
- Add Company (Admin) creates the repo from this template, renames the
  default branch to `main`, personalizes config.yaml, clears starter data,
  pre-loads the company card, and jumps straight into Guided setup.
- **Pause automation** button (Dashboard, per company): writes
  data/automation.json {paused}; the queue runner and content sync both
  honor it, so a company stops instantly and resumes with nothing lost.
- **Forever-renewing tokens:** Instagram (weekly refresh) and Facebook
  (weekly re-derive of a permanent Page token from the long-lived user
  token) both self-renew - set up once, never re-login.

## Done and verified live

| Area | Status | Proof |
|---|---|---|
| Instagram feed posting (photos + captions) | WORKING | live post id 18219735259325451 |
| Instagram Stories | WORKING | live story id 18064454552486450 |
| Instagram Reels (feed videos) | BUILT + tested in suite | posts via media_type REELS |
| Long-lived Instagram token, auto-renewing weekly | WORKING | refresh workflow green |
| Facebook Page feed cross-posting | WORKING | live post id ..._122112758517359188 |
| Facebook Page Stories cross-posting | WORKING | live story id 2417893102066090 |
| Randomized captions (brand + niche + viral tags) | WORKING | unique captions, live tested |
| Contact number + website in every caption | WORKING | 0813471724 + Gwalava site |
| Month-level batches: checkbox, start date, platforms per month | BUILT | engine + dashboard + tests |
| Bulk upload sorted into a chosen/new month | BUILT | dashboard |
| Platform selection per month (Instagram/Facebook) | BUILT | queue routes per item |
| Mobile view | BUILT | responsive under 700px |
| Admin portal (multi-company) | BUILT | docs/admin.html |
| Safety: 20 posts / 24h cap, past-date guard, retries | BUILT | tests cover all three |
| Approval gate: a month posts only once approved | BUILT | engine + dashboard toggle + tests |
| Failure alerting to a webhook (Slack/Discord/generic) | BUILT | queue runner + ALERT_WEBHOOK_URL + tests |
| Analytics report (likes/comments/reach) + client report page | BUILT | src/report.py + weekly job + Reports view + docs/report.html + tests |
| Test suite | GREEN | 80 tests, CI on every push |


## LIVE right now (audit 2026-07-03)

- "William Collins Ghost 1" Month 1 is ENABLED: 93 posts queued for
  Instagram + Facebook, Day 1 starting 2026-07-04, through 2026-07-23.
- GitHub Pages is serving the dashboard (branch deploy, builds green).
- All workflows green: scheduler, tests, token refresh.

## To do (user actions, not code)

- [ ] Facebook token: the old stored token was short-lived and expired 2 July,
  so Facebook mirrors fail until refreshed (Instagram is unaffected). Fix once:
  Companies -> Gwalava -> Guided setup -> Facebook step, store all FIVE secrets
  it gives you (page id, permanent page token, app id, app secret, user token).
  The new weekly job then re-derives a permanent Page token forever - this can
  never recur once the five secrets are in place.
- [ ] In the TikTok developer portal, delete the unused "Gwalava Poster" app (TikTok support was removed).

## To do (future improvements)

- [ ] LinkedIn and X (Twitter) publishers exist for text; wire them into the media queue like Facebook if ever needed.
- [ ] Analytics: pull post performance (likes/reach) back into the dashboard.
- [ ] Dedicated per-client branding on the dashboard (logo upload).

## Recently added

- **Approval gate:** every month batch has an "Approved to post" checkbox
  (Auto Posts). A month can be enabled but held for review - it only queues
  once approved. Existing campaigns (no approval flag) keep posting, so it is
  non-breaking. Card shows "awaiting approval" while an enabled month is
  unapproved.
- **Failure alerting:** when any publish fails, the queue runner POSTs a
  compact message to `ALERT_WEBHOOK_URL` (a Slack or Discord incoming webhook,
  or any endpoint - the body carries both `text` and `content`). Best effort:
  a dead webhook never blocks or crashes a posting run. Add the secret named
  `ALERT_WEBHOOK_URL` to turn it on; leave it unset to keep alerts off.
- **Analytics report:** a weekly job (Update analytics report) pulls likes,
  comments and reach/shares for every published post into data/report.json.
  The dashboard's **Reports** section shows totals and a post-by-post table;
  `docs/report.html?repo=owner/name` is a clean, controls-free, client-facing
  version safe to share as a link (reads the public report.json).

## How a new client is onboarded (repeatable)

1. Open the dashboard's **Admin** section -> "Add Company".
2. Fill in the business name, description, phone, website; it creates their
   repo (default branch main), personalizes config.yaml, and clears starter
   data.
3. On the company's card (Companies section) run the **Guided setup**
   wizard: GitHub token, Facebook Page (permanent token), Instagram
   (long-lived token), then GitHub Pages - each step verifies itself.
4. Upload their content with **Bulk upload** into Month 1, set the month's
   date + platforms, tick it, Save. Done - it runs itself.

## Key files

| File | What it is |
|---|---|
| docs/index.html | Posting dashboard (per company) |
| docs/admin.html | Admin portal (all companies) |
| src/content_sync.py | Scans content/, schedules months/days into the queue |
| src/queue_runner.py | Posts due items to the selected platforms |
| src/captions.py | Randomized captions; per-company overrides in config.yaml |
| src/content_prepare.py | Converts/resizes images for Instagram |
| src/platforms/ | Instagram and Facebook (and text-only others) |
| .github/workflows/scheduler.yml | Runs the pipeline every 15 minutes |
| .github/workflows/refresh-token.yml | Weekly: renews the Instagram + Facebook tokens forever |
| data/campaigns.json | Month batches: enabled/date/platforms per month |
| data/queue.json | The posting queue (visible in the dashboard) |
| data/automation.json | Pause switch: {paused} - honored by the engine |
