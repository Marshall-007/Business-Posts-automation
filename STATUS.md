# Project status

The single place to see what is finished, what is in progress, and what is
still to do. Update this file whenever something changes.

Last updated: 2026-07-03 (enterprise dashboard rebuild)

## Latest: enterprise dashboard

The dashboard (docs/index.html) is now a single-page app with a left-side
menu showing one section at a time: **Dashboard** (stats, activity log,
recent runs), **Companies** (switch between clients, guided setup),
**Scheduled Posts** (the queue), **Auto Posts** (month campaigns),
**Admin** (Add Company creates the client's repo automatically on `main`),
**Setup Instructions** (plain-language walkthroughs of every credential),
and **Settings** (connection). Highlights:

- One-off post scheduling was removed; Auto Posts campaigns are the way to post.
- Only Instagram and Facebook show in the UI; TikTok stays wired in the
  backend with secret placeholders for later.
- Every publish attempt (feed and stories, success or failure with the full
  API error) is written to `data/activity.json` and shown on the Dashboard.
- **Guided setup wizard** per company: modal steps with Next/Back and
  Save-and-Verify - GitHub token, Facebook Page (with automatic exchange to
  a permanent Page token), Instagram (auto-upgrade to long-lived), secret
  storage with copy buttons and existence verification, and GitHub Pages.
  Progress is saved so you can leave and return.
- Add Company (Admin) creates the repo from this template, renames the
  default branch to `main`, personalizes config.yaml, clears starter data,
  and pre-loads the company card. Gwalava ships pre-loaded.

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
| Platform selection per month (Instagram/Facebook/TikTok) | BUILT | queue routes per item |
| Mobile view | BUILT | responsive under 700px |
| Admin portal (multi-company) | BUILT | docs/admin.html |
| Safety: 20 posts / 24h cap, past-date guard, retries | BUILT | tests cover all three |
| Test suite | GREEN | 75+ tests, CI on every push |

## In progress

| Area | Where it stands | Next step |
|---|---|---|
| TikTok posting | Code complete (photos, videos, token auto-refresh every 4h). App created, URL verified, sandbox credentials issued. Blocked on the sandbox target-user step. | In the TikTok developer portal: Sandbox settings -> Target users -> add `gwalavaboardsandfurnitur`, then re-run the authorize link and the "TikTok authorize (one-time)" workflow. |
| TikTok public posting | Sandbox posts are private (SELF_ONLY) until TikTok approves the app. | Record a demo video of the flow and submit for review; then set TIKTOK_PRIVACY_LEVEL=PUBLIC_TO_EVERYONE. |

## To do (user actions, not code)

- [ ] Set a start date, platforms, and tick Month 1 of "William Collins Ghost 1", then Save - posting begins.
- [ ] TikTok: finish the sandbox target-user step above.
- [ ] Confirm GitHub Pages is serving /docs on the default branch (dashboard + admin portal + privacy/terms pages).
- [ ] Rotate the TikTok sandbox client secret after testing (it appeared in a screenshot).

## To do (future improvements)

- [ ] LinkedIn and X (Twitter) publishers exist for text; wire them into the media queue like Facebook if ever needed.
- [ ] Analytics: pull post performance (likes/reach) back into the dashboard.
- [ ] Approval mode: a "review before posting" switch per campaign.
- [ ] Dedicated per-client branding on the dashboard (logo upload).

## How a new client is onboarded (repeatable)

1. Open the **Admin portal** (docs/admin.html) -> "Set up a new company".
2. Fill in the business name, description, phone, website; it creates their
   repo from this one as a template, personalizes config.yaml, and clears
   starter data.
3. Work through the card's **setup checklist**: platform secrets
   (Instagram/Facebook/TikTok tokens), GH_PAT, then Settings -> Pages ->
   deploy branch /docs.
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
| src/platforms/ | Instagram, Facebook, TikTok (and text-only others) |
| .github/workflows/scheduler.yml | Runs the pipeline every 15 minutes |
| .github/workflows/refresh-token.yml | Keeps Instagram + TikTok tokens fresh |
| data/campaigns.json | Month batches: enabled/date/platforms per month |
| data/queue.json | The posting queue (visible in the dashboard) |
